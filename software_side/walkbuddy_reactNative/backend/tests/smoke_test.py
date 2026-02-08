"""
Hardcoded target:
  http://127.0.0.1:8000

What it does:
  - hits a representative request for each endpoint group
  - prints a simple PASS/FAIL table
  - exits non-zero if any check fails

Run:
  python smoke_test.py
  python smoke_test.py --file ./test.jpg
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx


BASE_URL = "http://127.0.0.1:8000"


@dataclass
class CheckResult:
    name: str
    method: str
    path: str
    ok: bool
    status: Optional[int]
    ms: float
    detail: str


def _fmt_ms(ms: float) -> str:
    if ms >= 1000:
        return f"{ms/1000:.2f}s"
    return f"{ms:.1f}ms"


def _safe_json(r: httpx.Response) -> Tuple[bool, Any]:
    try:
        return True, r.json()
    except Exception:
        return False, None


def _run_check(
    client: httpx.Client,
    name: str,
    method: str,
    path: str,
    *,
    expected_status: int = 200,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    files: Optional[Dict[str, Any]] = None,
    expect_json: bool = True,
    json_keys_any_of: Optional[List[str]] = None,  # at least one must exist if provided
) -> CheckResult:
    url = f"{BASE_URL}{path}"
    t0 = time.perf_counter()
    status = None

    try:
        r = client.request(method, url, params=params, json=json_body, files=files)
        status = r.status_code
        ms = (time.perf_counter() - t0) * 1000.0

        if status != expected_status:
            return CheckResult(
                name=name,
                method=method,
                path=path,
                ok=False,
                status=status,
                ms=ms,
                detail=f"expected {expected_status}, got {status}",
            )

        if expect_json:
            ok_json, data = _safe_json(r)
            if not ok_json:
                return CheckResult(
                    name=name,
                    method=method,
                    path=path,
                    ok=False,
                    status=status,
                    ms=ms,
                    detail="response not JSON",
                )
            if json_keys_any_of:
                if not isinstance(data, dict) or not any(k in data for k in json_keys_any_of):
                    return CheckResult(
                        name=name,
                        method=method,
                        path=path,
                        ok=False,
                        status=status,
                        ms=ms,
                        detail=f"missing any of keys: {json_keys_any_of}",
                    )

        return CheckResult(
            name=name,
            method=method,
            path=path,
            ok=True,
            status=status,
            ms=ms,
            detail="",
        )

    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000.0
        return CheckResult(
            name=name,
            method=method,
            path=path,
            ok=False,
            status=status,
            ms=ms,
            detail=f"exception: {type(e).__name__}: {e}",
        )


def print_table(results: List[CheckResult]) -> None:
    headers = ["status", "ms", "method", "path", "check", "detail"]
    rows: List[List[str]] = []

    for r in results:
        rows.append([
            "PASS" if r.ok else "FAIL",
            _fmt_ms(r.ms),
            r.method,
            r.path,
            r.name,
            r.detail,
        ])

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt_row(row: List[str]) -> str:
        return "  ".join(row[i].ljust(widths[i]) for i in range(len(row)))

    print(fmt_row(headers))
    print(fmt_row(["-" * w for w in widths]))
    for row in rows:
        print(fmt_row(row))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="./test.jpg", help="image file used for /ocr and /vision")
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args()

    # Read image once (fail early, loudly)
    try:
        with open(args.file, "rb") as f:
            image_bytes = f.read()
        if not image_bytes:
            print(f"ERROR: image file is empty: {args.file}")
            return 2
    except FileNotFoundError:
        print(f"ERROR: image file not found: {args.file}")
        return 2

    results: List[CheckResult] = []

    timeout = httpx.Timeout(args.timeout, connect=min(args.timeout, 5.0))
    with httpx.Client(timeout=timeout) as client:
        # ---- default ----
        results.append(_run_check(
            client,
            name="ping",
            method="GET",
            path="/ping",
            expected_status=200,
            expect_json=True,
            json_keys_any_of=["ok"],
        ))

        # ---- AI inference ----
        # /vision
        results.append(_run_check(
            client,
            name="vision",
            method="POST",
            path="/vision",
            expected_status=200,
            files={"file": ("test.jpg", image_bytes, "image/jpeg")},
            expect_json=True,
            json_keys_any_of=["detections", "guidance_message"],
        ))

        # /ocr
        results.append(_run_check(
            client,
            name="ocr",
            method="POST",
            path="/ocr",
            expected_status=200,
            files={"file": ("test.jpg", image_bytes, "image/jpeg")},
            expect_json=True,
            json_keys_any_of=["detections", "guidance_message"],
        ))

        # /chat
        results.append(_run_check(
            client,
            name="chat",
            method="POST",
            path="/chat",
            expected_status=200,
            json_body={"query": "Say one short sentence."},
            expect_json=True,
            json_keys_any_of=["response"],
        ))

        # ---- collaboration ----
        create = _run_check(
            client,
            name="collaboration create-session",
            method="POST",
            path="/collaboration/create-session",
            expected_status=200,
            expect_json=True,
            json_keys_any_of=["session_id"],
        )
        results.append(create)

        session_id = None
        if create.ok:
            r = client.post(f"{BASE_URL}/collaboration/create-session")
            ok_json, data = _safe_json(r)
            if ok_json and isinstance(data, dict):
                session_id = data.get("session_id")

        if session_id:
            results.append(_run_check(
                client,
                name="collaboration session status",
                method="GET",
                path=f"/collaboration/session/{session_id}/status",
                expected_status=200,
                expect_json=True,
                json_keys_any_of=["session_id", "user_connected", "guide_connected"],
            ))
        else:
            results.append(CheckResult(
                name="collaboration session status",
                method="GET",
                path="/collaboration/session/{id}/status",
                ok=False,
                status=None,
                ms=0.0,
                detail="skipped (create-session failed)",
            ))

        # ---- audiobooks ----
        results.append(_run_check(
            client,
            name="audiobooks filters",
            method="GET",
            path="/audiobooks/filters",
            expected_status=200,
            expect_json=True,
        ))

        results.append(_run_check(
            client,
            name="audiobooks popular",
            method="GET",
            path="/audiobooks/popular",
            expected_status=200,
            expect_json=True,
        ))

        results.append(_run_check(
            client,
            name="audiobooks search",
            method="GET",
            path="/audiobooks/search",
            expected_status=200,
            params={"q": "harry", "limit": 5},
            expect_json=True,
        ))

        results.append(_run_check(
            client,
            name="audiobooks cover",
            method="GET",
            path="/audiobooks/cover",
            expected_status=200,
            params={"title": "Harry Potter", "author": "J.K. Rowling"},
            expect_json=True,
        ))

        results.append(_run_check(
            client,
            name="audiobooks cover-proxy",
            method="GET",
            path="/audiobooks/cover-proxy",
            expected_status=200,
            params={"url": "https://librivox.org/images/librivox-logo.png"},
            expect_json=False,  # returns an image
        ))

        results.append(_run_check(
            client,
            name="audiobooks stream (GET)",
            method="GET",
            path="/audiobooks/stream",
            expected_status=200,
            params={"url": "https://example.com/audio.mp3"},
            expect_json=False,
        ))
        results.append(_run_check(
            client,
            name="audiobooks stream (HEAD)",
            method="HEAD",
            path="/audiobooks/stream",
            expected_status=200,
            params={"url": "https://example.com/audio.mp3"},
            expect_json=False,
        ))

        results.append(_run_check(
            client,
            name="audiobooks details (book_id=1)",
            method="GET",
            path="/audiobooks/1",
            expected_status=200,
            expect_json=True,
        ))

    print_table(results)

    failed = [r for r in results if not r.ok]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
