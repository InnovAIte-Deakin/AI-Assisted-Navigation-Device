"""Reproducible inference-performance benchmark for a local WalkBuddy YOLO model."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import torch
import ultralytics
from ultralytics import YOLO


TOOL_NAME = "walkbuddy_inference_performance_benchmark"
TOOL_VERSION = "1.0.0"

ML_SIDE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = ML_SIDE_DIR / "models" / "best.pt"
DEFAULT_IMAGE_PATH = ML_SIDE_DIR / "testing_pipeline" / "test_assets" / "test.png"
DEFAULT_OUTPUT_PATH = ML_SIDE_DIR / "benchmark_results" / "inference_performance.json"

DEFAULT_WARMUP_RUNS = 5
DEFAULT_BENCHMARK_RUNS = 50
DEFAULT_CONFIDENCE = 0.25
DEFAULT_IOU = 0.45


class BenchmarkError(Exception):
    """Raised when the benchmark cannot be completed safely."""


def utc_now() -> str:
    """Return the current UTC time in a stable ISO-8601 format."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def calculate_sha256(path: Path) -> str:
    """Calculate the SHA-256 checksum of a local file."""
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def percentile(values: list[float], percent: float) -> float:
    """Calculate a percentile using linear interpolation."""
    if not values:
        raise BenchmarkError("Cannot calculate a percentile from no values.")

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (len(ordered) - 1) * percent
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower

    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def synchronise_device(device: str) -> None:
    """Synchronise asynchronous accelerator work before timing boundaries."""
    if device == "cuda":
        torch.cuda.synchronize()
    elif device == "mps":
        torch.mps.synchronize()


def available_devices() -> list[str]:
    """Return compute devices available to the local PyTorch runtime."""
    devices = ["cpu"]

    if torch.backends.mps.is_available():
        devices.append("mps")

    if torch.cuda.is_available():
        devices.append("cuda")

    return devices


def environment_info() -> dict[str, object]:
    """Collect the software and hardware environment for reproducibility."""
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "pytorch_version": torch.__version__,
        "ultralytics_version": ultralytics.__version__,
        "mps_available": torch.backends.mps.is_available(),
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_name": (
            torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        ),
    }


def run_single_inference(
    model: YOLO,
    image_path: Path,
    device: str,
    confidence: float,
    iou: float,
) -> float:
    """Run one inference and return wall-clock latency in milliseconds."""
    synchronise_device(device)
    started = perf_counter()

    model.predict(
        source=str(image_path),
        save=False,
        verbose=False,
        conf=confidence,
        iou=iou,
        device=device,
    )

    synchronise_device(device)
    return (perf_counter() - started) * 1000


def benchmark_device(
    model_path: Path,
    image_path: Path,
    device: str,
    warmup_runs: int,
    benchmark_runs: int,
    confidence: float,
    iou: float,
) -> dict[str, object]:
    """Benchmark model loading, cold inference, warm-up and repeated inference."""
    load_started = perf_counter()
    model = YOLO(str(model_path))
    model_load_ms = (perf_counter() - load_started) * 1000

    cold_latency_ms = run_single_inference(
        model,
        image_path,
        device,
        confidence,
        iou,
    )

    warmup_latencies: list[float] = []

    for _ in range(warmup_runs):
        warmup_latencies.append(
            run_single_inference(
                model,
                image_path,
                device,
                confidence,
                iou,
            )
        )

    repeated_latencies: list[float] = []

    benchmark_started = perf_counter()

    for _ in range(benchmark_runs):
        repeated_latencies.append(
            run_single_inference(
                model,
                image_path,
                device,
                confidence,
                iou,
            )
        )

    synchronise_device(device)
    benchmark_elapsed_seconds = perf_counter() - benchmark_started

    mean_latency = statistics.mean(repeated_latencies)
    median_latency = statistics.median(repeated_latencies)

    return {
        "device": device,
        "model_load_ms": round(model_load_ms, 3),
        "cold_inference_ms": round(cold_latency_ms, 3),
        "warmup_runs": warmup_runs,
        "warmup_latencies_ms": [round(value, 3) for value in warmup_latencies],
        "warmup_total_ms": round(sum(warmup_latencies), 3),
        "benchmark_runs": benchmark_runs,
        "latencies_ms": [round(value, 3) for value in repeated_latencies],
        "mean_latency_ms": round(mean_latency, 3),
        "median_latency_ms": round(median_latency, 3),
        "p95_latency_ms": round(percentile(repeated_latencies, 0.95), 3),
        "min_latency_ms": round(min(repeated_latencies), 3),
        "max_latency_ms": round(max(repeated_latencies), 3),
        "throughput_fps": round(
            benchmark_runs / benchmark_elapsed_seconds,
            3,
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark inference performance for a local WalkBuddy YOLO model."
    )

    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help=f"Local YOLO model path (default: {DEFAULT_MODEL_PATH})",
    )
    parser.add_argument(
        "--image",
        type=Path,
        default=DEFAULT_IMAGE_PATH,
        help=f"Benchmark image path (default: {DEFAULT_IMAGE_PATH})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"JSON output path (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--device",
        choices=("cpu", "mps", "cuda", "all"),
        default="all",
        help="Compute device to benchmark (default: all available devices).",
    )
    parser.add_argument(
        "--warmup-runs",
        type=int,
        default=DEFAULT_WARMUP_RUNS,
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_BENCHMARK_RUNS,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    model_path = args.model.resolve()
    image_path = args.image.resolve()
    output_path = args.output.resolve()

    if not model_path.is_file():
        raise BenchmarkError(f"Model file does not exist: {model_path}")

    if not image_path.is_file():
        raise BenchmarkError(f"Benchmark image does not exist: {image_path}")

    if args.warmup_runs < 1:
        raise BenchmarkError("--warmup-runs must be at least 1.")

    if args.runs < 1:
        raise BenchmarkError("--runs must be at least 1.")

    devices = available_devices()

    if args.device == "all":
        selected_devices = devices
    else:
        if args.device not in devices:
            raise BenchmarkError(
                f"Requested device '{args.device}' is not available. "
                f"Available devices: {', '.join(devices)}"
            )
        selected_devices = [args.device]

    report: dict[str, object] = {
        "tool": {
            "name": TOOL_NAME,
            "version": TOOL_VERSION,
        },
        "generated_at_utc": utc_now(),
        "model": {
            "path": str(model_path.relative_to(ML_SIDE_DIR.parent)),
            "filename": model_path.name,
            "size_bytes": model_path.stat().st_size,
            "sha256": calculate_sha256(model_path),
        },
        "benchmark_input": {
            "path": str(image_path.relative_to(ML_SIDE_DIR.parent)),
            "filename": image_path.name,
            "purpose": "Performance benchmarking only; not accuracy evaluation.",
        },
        "configuration": {
            "warmup_runs": args.warmup_runs,
            "benchmark_runs": args.runs,
            "confidence": DEFAULT_CONFIDENCE,
            "iou": DEFAULT_IOU,
            "selected_devices": selected_devices,
        },
        "environment": environment_info(),
        "results": [],
        "limitations": [
            "Results describe performance on this specific machine and software environment.",
            "A single repository test fixture is used for repeatability.",
            "This benchmark does not measure model accuracy or tune model parameters.",
            "The held-out test set is not used by this benchmark.",
        ],
    }

    results = report["results"]

    assert isinstance(results, list)

    for device in selected_devices:
        print(f"Benchmarking {device}...")

        results.append(
            benchmark_device(
                model_path=model_path,
                image_path=image_path,
                device=device,
                warmup_runs=args.warmup_runs,
                benchmark_runs=args.runs,
                confidence=DEFAULT_CONFIDENCE,
                iou=DEFAULT_IOU,
            )
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")

    print(f"Benchmark complete: {output_path}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BenchmarkError as exc:
        print(f"Benchmark error: {exc}", file=sys.stderr)
        sys.exit(2)