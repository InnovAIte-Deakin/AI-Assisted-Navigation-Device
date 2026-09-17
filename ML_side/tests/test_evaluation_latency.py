import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # ML_side, so `evaluation` is importable

from evaluation.latency import measure_latency


def test_measure_latency_empty_images_returns_none_stats():
    stats = measure_latency(lambda img: None, images=[])
    assert stats["num_samples"] == 0
    assert stats["mean_ms"] is None
    assert stats["fps"] is None


def test_measure_latency_returns_expected_keys_and_positive_values():
    def fake_predict(img):
        time.sleep(0.001)
        return []

    stats = measure_latency(fake_predict, images=["a", "b", "c"], warmup=1, repeats=2)
    assert stats["num_samples"] == 6  # 3 images x 2 repeats
    assert stats["mean_ms"] > 0
    assert stats["median_ms"] > 0
    assert stats["p95_ms"] > 0
    assert stats["fps"] > 0


def test_measure_latency_calls_predict_fn_expected_number_of_times():
    calls = []

    def counting_predict(img):
        calls.append(img)
        return []

    measure_latency(counting_predict, images=["x", "y"], warmup=2, repeats=3)
    # warmup passes (2 * 2 images) + timed passes (3 * 2 images)
    assert len(calls) == (2 * 2) + (3 * 2)
