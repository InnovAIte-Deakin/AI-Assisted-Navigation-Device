"""Inference latency measurement.

Note on determinism: unlike the detection metrics, wall-clock latency
numbers are *not* deterministic between runs, they depend on the machine,
load, and whether it's a mock predictor or a real model. That's expected
and fine, this module just measures it, it doesn't pretend timing is
reproducible the way the detection metrics are.
"""

import time
from typing import Callable, List, Sequence


def measure_latency(
    predict_fn: Callable,
    images: Sequence,
    warmup: int = 1,
    repeats: int = 1,
) -> dict:
    """Times predict_fn(image) across the given images.

    predict_fn: callable taking one "image" (whatever the predictor
        expects, a numpy array, a file path, a mock image id, ...) and
        returning predictions for it. Return value isn't used here, only
        the time it took to produce it.
    images: sequence of inputs to time predict_fn on.
    warmup: number of full passes over `images` run first and discarded
        (avoids counting first-call model/JIT warmup cost).
    repeats: number of timed passes over `images` to average over.

    Returns per_call timings in milliseconds plus derived stats. Returns
    zeroed-out stats (not an error) if `images` is empty, since an eval
    run against a fixture with no images is a valid, if uninteresting,
    input.
    """
    if not images:
        return {
            "num_samples": 0, "mean_ms": None, "median_ms": None,
            "p95_ms": None, "fps": None,
        }

    for _ in range(warmup):
        for image in images:
            predict_fn(image)

    timings_s: List[float] = []
    for _ in range(repeats):
        for image in images:
            start = time.perf_counter()
            predict_fn(image)
            end = time.perf_counter()
            timings_s.append(end - start)

    timings_s.sort()
    n = len(timings_s)
    mean_s = sum(timings_s) / n
    median_s = (
        timings_s[n // 2] if n % 2 == 1
        else (timings_s[n // 2 - 1] + timings_s[n // 2]) / 2
    )
    p95_index = min(n - 1, int(round(0.95 * (n - 1))))
    p95_s = timings_s[p95_index]
    fps = (1.0 / mean_s) if mean_s > 0 else None

    return {
        "num_samples": n,
        "mean_ms": mean_s * 1000,
        "median_ms": median_s * 1000,
        "p95_ms": p95_s * 1000,
        "fps": fps,
    }
