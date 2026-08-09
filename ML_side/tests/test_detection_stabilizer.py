"""Tests for policy-neutral temporal detection stabilization."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest


ML_SIDE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML_SIDE))

from inference.detection_stabilizer import (
    DetectionStabilizer,
    DetectionStabilizerError,
    replay_frames,
)


class FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_stabilizer(clock: FakeClock, **overrides: object) -> DetectionStabilizer:
    options: dict[str, object] = {
        "class_names": ("chair", "door", "table"),
        "window_size": 5,
        "required_observations": 3,
        "cooldown_seconds": 3.0,
        "clock": clock,
    }
    options.update(overrides)
    return DetectionStabilizer(**options)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"class_names": ()}, "must not be empty"),
        ({"class_names": "chair"}, "iterable"),
        ({"class_names": {"chair"}}, "ordered"),
        ({"class_names": ("chair", "chair")}, "duplicates"),
        ({"class_names": (" chair",)}, "whitespace"),
        ({"class_names": ("chair",), "global_cooldown": 1}, "boolean"),
        ({"class_names": ("chair",), "clock": object()}, "callable"),
    ],
)
def test_constructor_validation(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(DetectionStabilizerError, match=message):
        DetectionStabilizer(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("window_size", (0, -1, True, 2.5))
def test_invalid_window_size_is_rejected(window_size: object) -> None:
    with pytest.raises(DetectionStabilizerError, match="window_size"):
        DetectionStabilizer(("chair",), window_size=window_size)  # type: ignore[arg-type]


def test_required_observations_must_fit_window() -> None:
    with pytest.raises(DetectionStabilizerError, match="must not exceed"):
        DetectionStabilizer(("chair",), window_size=2, required_observations=3)


def test_one_frame_flicker_is_suppressed() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(clock)

    for frame in (["chair"], [], [], [], []):
        assert stabilizer.observe(frame) == ()


def test_persistent_class_becomes_stable_at_startup_threshold() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(clock)

    for _ in range(2):
        assert stabilizer.observe(["chair"]) == ()
    assert stabilizer.observe(["chair"]) == ("chair",)


@pytest.mark.parametrize(
    ("window_size", "required_observations", "frames", "expected"),
    [
        (1, 1, (["chair"],), ("chair",)),
        (5, 1, (["chair"],), ("chair",)),
        (5, 3, (["chair"], ["chair"], ["chair"]), ("chair",)),
        (5, 5, (["chair"],) * 5, ("chair",)),
    ],
)
def test_n_of_m_thresholds_have_no_unnecessary_startup_delay(
    window_size: int,
    required_observations: int,
    frames: tuple[list[str], ...],
    expected: tuple[str, ...],
) -> None:
    stabilizer = make_stabilizer(
        FakeClock(),
        window_size=window_size,
        required_observations=required_observations,
    )

    for frame in frames[:-1]:
        assert stabilizer.observe(frame) == ()
    assert stabilizer.observe(frames[-1]) == expected


def test_one_below_n_of_m_threshold_remains_unstable() -> None:
    stabilizer = make_stabilizer(
        FakeClock(), window_size=5, required_observations=3
    )

    for frame in (["chair"], [], ["chair"]):
        assert stabilizer.observe(frame) == ()


def test_intermittent_class_reaches_n_of_m() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(clock)

    for frame in (["chair"], [], ["chair"], [], ["chair"]):
        stable = stabilizer.observe(frame)
    assert stable == ("chair",)


def test_class_disappears_when_its_hits_leave_window() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(clock)

    for frame in (["chair"], ["chair"], ["chair"], [], [], []):
        stable = stabilizer.observe(frame)
    assert stable == ()


def test_multiple_classes_are_tracked_independently() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(clock)

    for frame in (["chair", "door"], ["chair"], ["door"], ["chair", "door"], ["door"]):
        stable = stabilizer.observe(frame)
    assert stable == ("chair", "door")


def test_history_is_bounded_to_window_size() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(clock)

    for _ in range(100):
        stabilizer.observe(["chair"])
    assert stabilizer.history_length == 5


def test_repeated_detections_in_one_frame_count_once() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(clock, window_size=3, required_observations=2)

    assert stabilizer.observe(["chair"] * 100) == ()
    assert stabilizer.observe([]) == ()
    assert stabilizer.observe([]) == ()


def test_per_class_cooldown_suppresses_immediate_duplicate_emission() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(
        clock, window_size=1, required_observations=1, cooldown_seconds=3.0
    )
    stabilizer.observe(["chair"])

    assert stabilizer.eligible_for_emission() == ("chair",)
    assert stabilizer.mark_emitted("chair") == ("chair",)
    assert stabilizer.eligible_for_emission() == ()


def test_class_can_emit_again_after_its_cooldown() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(clock, window_size=1, required_observations=1)
    stabilizer.observe(["chair"])
    stabilizer.mark_emitted("chair")

    clock.advance(3.0)
    assert stabilizer.eligible_for_emission() == ("chair",)


def test_one_class_cooldown_does_not_block_another() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(clock, window_size=1, required_observations=1)
    stabilizer.observe(["chair", "door"])

    assert stabilizer.mark_emitted("chair") == ("chair",)
    assert stabilizer.eligible_for_emission() == ("door",)


def test_global_cooldown_rotates_stable_classes_without_starvation() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(
        clock,
        window_size=1,
        required_observations=1,
        global_cooldown=True,
    )
    stabilizer.observe(["chair", "door"])

    assert stabilizer.eligible_for_emission() == ("chair",)
    stabilizer.mark_emitted("chair")
    assert stabilizer.eligible_for_emission() == ()

    clock.advance(3.0)
    assert stabilizer.eligible_for_emission() == ("door",)
    stabilizer.mark_emitted("door")
    clock.advance(3.0)
    assert stabilizer.eligible_for_emission() == ("chair",)


def test_global_cooldown_queries_do_not_record_an_emission() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(
        clock, window_size=1, required_observations=1, global_cooldown=True
    )
    stabilizer.observe(["chair", "door"])

    assert stabilizer.eligible_for_emission() == ("chair",)
    assert stabilizer.eligible_for_emission() == ("chair",)


def test_reset_clears_history_and_cooldowns() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(clock, window_size=1, required_observations=1)
    stabilizer.observe(["chair"])
    stabilizer.mark_emitted("chair")

    stabilizer.reset()
    assert stabilizer.history_length == 0
    stabilizer.observe(["chair"])
    assert stabilizer.eligible_for_emission() == ("chair",)


def test_reset_begins_a_fresh_clock_session() -> None:
    clock = FakeClock(100.0)
    stabilizer = make_stabilizer(clock, window_size=1, required_observations=1)
    stabilizer.observe(["chair"])
    stabilizer.eligible_for_emission()

    clock.now = 1.0
    stabilizer.reset()
    stabilizer.observe(["chair"])
    assert stabilizer.eligible_for_emission() == ("chair",)


def test_instances_do_not_share_state() -> None:
    clock = FakeClock()
    first = make_stabilizer(clock, window_size=1, required_observations=1)
    second = make_stabilizer(clock, window_size=1, required_observations=1)

    first.observe(["chair"])
    first.mark_emitted("chair")
    second.observe(["chair"])
    assert second.eligible_for_emission() == ("chair",)


def test_fake_clock_makes_cooldown_deterministic() -> None:
    clock = FakeClock(10.0)
    stabilizer = make_stabilizer(clock, window_size=1, required_observations=1)
    stabilizer.observe(["chair"])
    stabilizer.mark_emitted("chair")

    clock.advance(2.99)
    assert stabilizer.eligible_for_emission() == ()
    clock.advance(0.01)
    assert stabilizer.eligible_for_emission() == ("chair",)


def test_backwards_or_invalid_clock_values_are_rejected() -> None:
    clock = FakeClock(2.0)
    stabilizer = make_stabilizer(clock, window_size=1, required_observations=1)
    stabilizer.observe(["chair"])
    stabilizer.eligible_for_emission()

    clock.now = 1.0
    with pytest.raises(DetectionStabilizerError, match="moved backwards"):
        stabilizer.eligible_for_emission()

    invalid = make_stabilizer(lambda: math.inf, window_size=1, required_observations=1)
    invalid.observe(["chair"])
    with pytest.raises(DetectionStabilizerError, match="finite"):
        invalid.eligible_for_emission()


def test_default_cooldown_uses_elapsed_monotonic_time_semantics() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(clock, window_size=1, required_observations=1)
    stabilizer.observe(["chair"])
    stabilizer.mark_emitted("chair")

    clock.advance(3.000001)
    assert stabilizer.eligible_for_emission() == ("chair",)


def test_stable_output_uses_registered_order() -> None:
    clock = FakeClock()
    stabilizer = DetectionStabilizer(
        ("door", "chair", "table"), window_size=1, required_observations=1, clock=clock
    )

    assert stabilizer.observe(["table", "chair", "door"]) == (
        "door",
        "chair",
        "table",
    )


def test_priority_order_ranks_known_classes_and_validates_unknown_ones() -> None:
    clock = FakeClock()
    stabilizer = DetectionStabilizer(
        ("chair", "door", "table"),
        window_size=1,
        required_observations=1,
        priority_order=("table", "door"),
        clock=clock,
    )
    assert stabilizer.observe(["chair", "door", "table"]) == (
        "table",
        "door",
        "chair",
    )

    with pytest.raises(DetectionStabilizerError, match="unknown"):
        DetectionStabilizer(("chair",), priority_order=("door",))
    with pytest.raises(DetectionStabilizerError, match="ordered"):
        DetectionStabilizer(("chair", "door"), priority_order={"door", "chair"})


def test_unknown_classes_are_ignored_deterministically() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(clock, window_size=1, required_observations=1)

    assert stabilizer.observe(["unknown"]) == ()
    assert stabilizer.history_length == 1


@pytest.mark.parametrize(
    "frame",
    (
        [{"confidence": 0.8}],
        [42],
        b"chair",
        [{"class_name": "chair", "confidence": "high"}],
    ),
)
def test_malformed_observations_are_rejected(frame: object) -> None:
    stabilizer = make_stabilizer(FakeClock())
    with pytest.raises(DetectionStabilizerError):
        stabilizer.observe(frame)


def test_confidence_threshold_uses_fractional_boundaries() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(
        clock,
        window_size=1,
        required_observations=1,
        min_confidence=0.8,
    )

    assert stabilizer.observe([{"class_name": "chair", "confidence": 0.8}]) == (
        "chair",
    )
    assert stabilizer.observe([{"class_name": "chair", "confidence": 0.799}]) == ()


def test_confidence_filtering_does_not_discard_other_valid_labels() -> None:
    stabilizer = make_stabilizer(
        FakeClock(),
        window_size=1,
        required_observations=1,
        min_confidence=0.8,
    )

    assert stabilizer.observe(
        [
            {"class_name": "chair", "confidence": 0.2},
            {"class_name": "door", "confidence": 0.8},
        ]
    ) == ("door",)


def test_confidence_requires_a_fractional_numeric_value_when_configured() -> None:
    stabilizer = make_stabilizer(
        FakeClock(),
        window_size=1,
        required_observations=1,
        min_confidence=0.8,
    )

    with pytest.raises(DetectionStabilizerError, match="require confidence"):
        stabilizer.observe(["chair"])
    with pytest.raises(DetectionStabilizerError, match="confidence"):
        stabilizer.observe([{"class_name": "chair", "confidence": None}])
    with pytest.raises(DetectionStabilizerError, match="confidence"):
        stabilizer.observe([{"class_name": "chair", "confidence": True}])
    assert stabilizer.observe([{"class_name": "chair", "confidence": 1}]) == (
        "chair",
    )


@pytest.mark.parametrize("confidence", (math.nan, math.inf, -math.inf, -0.1, 1.1))
def test_nan_inf_and_out_of_range_confidences_are_rejected(confidence: float) -> None:
    stabilizer = make_stabilizer(FakeClock())
    with pytest.raises(DetectionStabilizerError, match="confidence"):
        stabilizer.observe([{"class_name": "chair", "confidence": confidence}])


def test_empty_frames_advance_the_temporal_window() -> None:
    stabilizer = make_stabilizer(FakeClock())
    assert stabilizer.observe(None) == ()
    assert stabilizer.observe([]) == ()
    assert stabilizer.history_length == 2


def test_reappearance_requires_persistence_again_after_disappearance() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(clock, window_size=3, required_observations=2)

    for frame in (["chair"], ["chair"], [], [], []):
        stabilizer.observe(frame)
    assert stabilizer.stable_classes() == ()
    assert stabilizer.observe(["chair"]) == ()
    assert stabilizer.observe(["chair"]) == ("chair",)


def test_emission_is_allowed_at_exact_cooldown_boundary() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(clock, window_size=1, required_observations=1)
    stabilizer.observe(["chair"])
    stabilizer.mark_emitted("chair")

    clock.advance(3.0)
    assert stabilizer.eligible_for_emission() == ("chair",)


def test_emission_is_suppressed_just_before_cooldown_boundary() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(clock, window_size=1, required_observations=1)
    stabilizer.observe(["chair"])
    stabilizer.mark_emitted("chair")

    clock.advance(2.999999)
    assert stabilizer.eligible_for_emission() == ()


def test_emission_is_allowed_just_after_cooldown_boundary() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(clock, window_size=1, required_observations=1)
    stabilizer.observe(["chair"])
    stabilizer.mark_emitted("chair")

    clock.advance(3.000001)
    assert stabilizer.eligible_for_emission() == ("chair",)


def test_zero_cooldown_allows_another_explicit_emission_immediately() -> None:
    stabilizer = make_stabilizer(
        FakeClock(),
        window_size=1,
        required_observations=1,
        cooldown_seconds=0,
    )
    stabilizer.observe(["chair"])
    stabilizer.mark_emitted("chair")

    assert stabilizer.eligible_for_emission() == ("chair",)


def test_replay_harness_returns_deterministic_emission_sequence() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(
        clock, window_size=3, required_observations=2, cooldown_seconds=5.0
    )

    emitted = replay_frames(stabilizer, (["chair"], [], ["chair"], ["chair"]))

    assert emitted == ((), (), ("chair",), ())


def test_replay_can_be_non_mutating_and_restarts_identically_after_reset() -> None:
    clock = FakeClock()
    stabilizer = make_stabilizer(
        clock, window_size=2, required_observations=1, cooldown_seconds=5.0
    )
    frames = (["chair"], ["chair"])

    assert replay_frames(stabilizer, (), mark_emitted=True) == ()
    assert replay_frames(stabilizer, frames, mark_emitted=False) == (
        ("chair",),
        ("chair",),
    )
    stabilizer.reset()
    assert replay_frames(stabilizer, frames) == (
        ("chair",),
        (),
    )
