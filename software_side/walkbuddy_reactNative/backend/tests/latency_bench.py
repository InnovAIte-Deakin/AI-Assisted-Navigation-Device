"""
Purpose:
  Measure latency:
    - baseline (no load)
    - under load from /chat, /ocr, /vision (one at a time)

Usage:
  python latency_bench.py --base http://127.0.0.1:8000 --file ./test.jpg
  python latency_bench.py --base http://127.0.0.1:8000 --file ./test.jpg --duration 20 --chat-c 6 --ocr-c 2 --vision-c 2
"""

import argparse
import asyncio
import math
import statistics
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import httpx


# ---------- stats helpers ----------

def pctl(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    if p <= 0:
        return sorted_vals[0]
    if p >= 100:
        return sorted_vals[-1]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def summarize_ms(samples_ms: List[float]) -> Dict[str, float]:
    s = sorted(samples_ms)
    return {
        "n": float(len(s)),
        "p50": pctl(s, 50),
        "p90": pctl(s, 90),
        "p95": pctl(s, 95),
        "p99": pctl(s, 99),
        "max": s[-1] if s else float("nan"),
        "mean": statistics.mean(s) if s else float("nan"),
    }


def fmt_ms(x: float) -> str:
    if math.isnan(x):
        return "nan"
    if x >= 1000:
        return f"{x/1000:.2f}s"
    return f"{x:.1f}ms"


# ---------- bench primitives ----------

async def ping_loop(
    client: httpx.AsyncClient,
    ping_url: str,
    duration_s: float,
    interval_s: float,
    timeout_penalty_ms: float = 10_000.0,
) -> Tuple[List[float], int, int]:
    """
    Returns: (latencies_ms, ok_count, err_count)
    If a ping request errors/timeouts, we record a penalty latency.
    """
    end = time.perf_counter() + duration_s
    samples_ms: List[float] = []
    ok = 0
    err = 0

    while time.perf_counter() < end:
        t0 = time.perf_counter()
        try:
            r = await client.get(ping_url)
            r.raise_for_status()
        except Exception:
            err += 1
            samples_ms.append(timeout_penalty_ms)
        else:
            ok += 1
            samples_ms.append((time.perf_counter() - t0) * 1000.0)

        # keep sampling rate stable-ish
        await asyncio.sleep(interval_s)

    return samples_ms, ok, err


async def heavy_chat_worker(client: httpx.AsyncClient, url: str, duration_s: float) -> Tuple[int, int]:
    end = time.perf_counter() + duration_s
    ok = 0
    err = 0
    payload = {"query": "What's in front of me?"}

    while time.perf_counter() < end:
        try:
            r = await client.post(url, json=payload)
            r.raise_for_status()
        except Exception:
            err += 1
        else:
            ok += 1

    return ok, err


async def heavy_file_worker(
    client: httpx.AsyncClient,
    url: str,
    duration_s: float,
    file_name: str,
    file_bytes: bytes,
    content_type: str,
) -> Tuple[int, int]:
    end = time.perf_counter() + duration_s
    ok = 0
    err = 0

    while time.perf_counter() < end:
        try:
            files = {"file": (file_name, file_bytes, content_type)}
            r = await client.post(url, files=files)
            r.raise_for_status()
        except Exception:
            err += 1
        else:
            ok += 1

    return ok, err


@dataclass
class EndpointConfig:
    name: str
    path: str
    concurrency: int


@dataclass
class RunResult:
    endpoint: str
    duration_s: float
    concurrency: int
    ping_base: Dict[str, float]
    ping_load: Dict[str, float]
    ping_base_ok: int
    ping_base_err: int
    ping_load_ok: int
    ping_load_err: int
    heavy_ok: int
    heavy_err: int
    heavy_rps: float
    p95_ratio: float


def print_section(title: str) -> None:
    print("\n" + "=" * len(title))
    print(title)
    print("=" * len(title))


def print_table(results: List[RunResult]) -> None:
    # Human-readable, fixed columns
    headers = [
        "endpoint",
        "c",
        "heavy_rps",
        "ping_base_p95",
        "ping_load_p95",
        "p95_ratio",
        "ping_load_p99",
        "ping_load_max",
        "ping_load_err",
        "heavy_err",
    ]

    rows = []
    for r in results:
        rows.append([
            r.endpoint,
            str(r.concurrency),
            f"{r.heavy_rps:.2f}",
            fmt_ms(r.ping_base["p95"]),
            fmt_ms(r.ping_load["p95"]),
            f"{r.p95_ratio:.1f}x",
            fmt_ms(r.ping_load["p99"]),
            fmt_ms(r.ping_load["max"]),
            str(r.ping_load_err),
            str(r.heavy_err),
        ])

    widths = [max(len(h), *(len(row[i]) for row in rows)) for i, h in enumerate(headers)]

    def fmt_row(cols: List[str]) -> str:
        return "  ".join(cols[i].ljust(widths[i]) for i in range(len(cols)))

    print(fmt_row(headers))
    print(fmt_row(["-" * w for w in widths]))
    for row in rows:
        print(fmt_row(row))


async def run_one(
    client: httpx.AsyncClient,
    base: str,
    ping_path: str,
    cfg: EndpointConfig,
    duration_s: float,
    ping_interval_s: float,
    file_name: Optional[str],
    file_bytes: Optional[bytes],
    file_content_type: str,
) -> RunResult:
    base = base.rstrip("/")
    ping_url = f"{base}{ping_path}"
    heavy_url = f"{base}{cfg.path}"

    # Baseline pings
    base_lat, base_ok, base_err = await ping_loop(client, ping_url, duration_s, ping_interval_s)
    ping_base = summarize_ms(base_lat)

    # Start load workers
    heavy_tasks = []
    if cfg.path == "/chat":
        for _ in range(cfg.concurrency):
            heavy_tasks.append(asyncio.create_task(heavy_chat_worker(client, heavy_url, duration_s)))
    elif cfg.path in ("/ocr", "/vision"):
        if not (file_name and file_bytes):
            raise SystemExit("--file is required for /ocr and /vision")
        for _ in range(cfg.concurrency):
            heavy_tasks.append(asyncio.create_task(
                heavy_file_worker(client, heavy_url, duration_s, file_name, file_bytes, file_content_type)
            ))
    else:
        raise SystemExit(f"unsupported endpoint: {cfg.path}")

    # Ping while load runs
    ping_task = asyncio.create_task(ping_loop(client, ping_url, duration_s, ping_interval_s))

    # Collect
    heavy_ok = 0
    heavy_err = 0
    heavy_results = await asyncio.gather(*heavy_tasks, return_exceptions=True)
    for hr in heavy_results:
        if isinstance(hr, tuple) and len(hr) == 2:
            heavy_ok += int(hr[0])
            heavy_err += int(hr[1])

    load_lat, load_ok, load_err = await ping_task
    ping_load = summarize_ms(load_lat)

    heavy_total = heavy_ok + heavy_err
    heavy_rps = (heavy_total / duration_s) if duration_s > 0 else 0.0
    p95_ratio = (ping_load["p95"] / ping_base["p95"]) if ping_base["p95"] > 0 else float("inf")

    return RunResult(
        endpoint=cfg.path,
        duration_s=duration_s,
        concurrency=cfg.concurrency,
        ping_base=ping_base,
        ping_load=ping_load,
        ping_base_ok=base_ok,
        ping_base_err=base_err,
        ping_load_ok=load_ok,
        ping_load_err=load_err,
        heavy_ok=heavy_ok,
        heavy_err=heavy_err,
        heavy_rps=heavy_rps,
        p95_ratio=p95_ratio,
    )


async def main_async(args: argparse.Namespace) -> None:
    base = args.base.rstrip("/")
    endpoints: List[EndpointConfig] = []

    if "chat" in args.endpoints:
        endpoints.append(EndpointConfig("chat", "/chat", args.chat_c))
    if "ocr" in args.endpoints:
        endpoints.append(EndpointConfig("ocr", "/ocr", args.ocr_c))
    if "vision" in args.endpoints:
        endpoints.append(EndpointConfig("vision", "/vision", args.vision_c))

    file_name = None
    file_bytes = None
    if any(e.path in ("/ocr", "/vision") for e in endpoints):
        if not args.file:
            raise SystemExit("--file is required when testing ocr or vision")
        file_name = args.file.split("/")[-1]
        with open(args.file, "rb") as f:
            file_bytes = f.read()

    timeout = httpx.Timeout(args.timeout, connect=min(args.timeout, 5.0))
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Warmup ping (reduce first request noise)
        try:
            await client.get(f"{base}{args.ping}")
        except Exception:
            pass

        print_section("Latency bench")
        print(f"base={base}")
        print(f"ping={args.ping} interval={args.ping_interval}s duration={args.duration}s")
        print(f"endpoints={','.join([e.path for e in endpoints])}")
        print(f"chat_c={args.chat_c} ocr_c={args.ocr_c} vision_c={args.vision_c}")
        if file_name:
            print(f"file={file_name}")

        results: List[RunResult] = []
        for cfg in endpoints:
            print_section(f"Running load: {cfg.path} (concurrency={cfg.concurrency})")
            r = await run_one(
                client=client,
                base=base,
                ping_path=args.ping,
                cfg=cfg,
                duration_s=args.duration,
                ping_interval_s=args.ping_interval,
                file_name=file_name,
                file_bytes=file_bytes,
                file_content_type=args.file_content_type,
            )
            results.append(r)

            # brief per-endpoint readout
            print(
                f"ping baseline p95={fmt_ms(r.ping_base['p95'])}  "
                f"under load p95={fmt_ms(r.ping_load['p95'])}  "
                f"ratio={r.p95_ratio:.1f}x  "
                f"heavy_rps={r.heavy_rps:.2f}  "
                f"ping_load_err={r.ping_load_err}  heavy_err={r.heavy_err}"
            )

        print_section("Summary")
        print_table(results)


def build_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--ping", default="/ping")
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--ping-interval", type=float, default=0.05)  # 50ms sampling
    ap.add_argument("--timeout", type=float, default=30.0)

    ap.add_argument(
        "--endpoints",
        default="chat,ocr,vision",
        help="comma list: chat,ocr,vision",
    )

    ap.add_argument("--chat-c", type=int, default=6, help="concurrency for /chat")
    ap.add_argument("--ocr-c", type=int, default=2, help="concurrency for /ocr")
    ap.add_argument("--vision-c", type=int, default=2, help="concurrency for /vision")

    ap.add_argument("--file", default=None, help="image file used for /ocr and /vision")
    ap.add_argument("--file-content-type", default="image/jpeg", help="multipart content-type to send")

    ns = ap.parse_args()
    ns.endpoints = [s.strip().lower() for s in ns.endpoints.split(",") if s.strip()]
    return ns


def main() -> None:
    args = build_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
