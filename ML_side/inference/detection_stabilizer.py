"""Deterministic, policy-neutral temporal stabilization for detections.

``DetectionStabilizer`` accepts one frame at a time.  A frame can contain
plain class-name strings or lightweight mappings with ``class_name`` and an
optional ``confidence``. A configured class is *stable* when the rolling
window contains at least the configured number of observations. During
startup, that rolling window is partial, so a class can become stable as soon
as it reaches ``required_observations``; after that, only the latest
``window_size`` frames are retained.

Stability and emission are deliberately separate:

* :meth:`observe` advances temporal state and returns stable classes.
* :meth:`eligible_for_emission` returns stable classes whose cooldowns allow
  a new emission.
* :meth:`mark_emitted` records only classes the caller actually emitted.

Recording an emission never clears temporal history; only later frames and
an explicit :meth:`reset` change that history.

The caller owns detector invocation, speech, risk policy, and any semantic
meaning of labels.  This module intentionally has no backend imports,
network activity, model access, or hard-coded hazard ordering.
"""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable, Iterable, Mapping


class DetectionStabilizerError(ValueError):
    """Raised when stabilizer configuration, observations, or clock data are invalid."""


class DetectionStabilizer:
    """Keep bounded per-frame class history and independent emission cooldowns.

    ``class_names`` defines the classes this instance tracks, in its default
    deterministic output order, and must be an ordered iterable. Observations
    for other labels are ignored; callers can track them by including them in
    ``class_names``. An optional ``priority_order`` may rank a subset of known
    labels before the remaining labels, but does not assign any WalkBuddy risk
    or hazard policy.

    ``global_cooldown=False`` (the default) means emitting one class never
    suppresses another class. With ``global_cooldown=True``, at most one
    stable class may be emitted per cooldown interval. After an actual global
    emission, selection rotates deterministically through stable classes so a
    continually stable first label cannot starve the others.
    """

    def __init__(
        self,
        class_names: Iterable[str],
        *,
        window_size: int = 5,
        required_observations: int = 3,
        cooldown_seconds: float = 3.0,
        global_cooldown: bool = False,
        priority_order: Iterable[str] | None = None,
        min_confidence: float | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._class_names = self._validate_class_names(class_names)
        self._known_classes = frozenset(self._class_names)
        self._class_order = self._build_class_order(priority_order)
        self._class_index = {
            class_name: index for index, class_name in enumerate(self._class_order)
        }
        self.window_size = self._positive_integer(window_size, "window_size")
        self.required_observations = self._positive_integer(
            required_observations, "required_observations"
        )
        if self.required_observations > self.window_size:
            raise DetectionStabilizerError(
                "required_observations must not exceed window_size"
            )
        self.cooldown_seconds = self._nonnegative_number(
            cooldown_seconds, "cooldown_seconds"
        )
        if not isinstance(global_cooldown, bool):
            raise DetectionStabilizerError("global_cooldown must be a boolean")
        self.global_cooldown = global_cooldown
        self.min_confidence = self._validate_min_confidence(min_confidence)
        if clock is not None and not callable(clock):
            raise DetectionStabilizerError("clock must be callable")
        self._clock = time.monotonic if clock is None else clock
        self.reset()

    @staticmethod
    def _validate_class_name(value: object, field_name: str) -> str:
        if not isinstance(value, str) or not value or value != value.strip():
            raise DetectionStabilizerError(
                f"{field_name} must be a non-empty string without surrounding whitespace"
            )
        return value

    @classmethod
    def _validate_class_names(cls, class_names: Iterable[str]) -> tuple[str, ...]:
        if isinstance(class_names, (str, bytes, set, frozenset)):
            raise DetectionStabilizerError(
                "class_names must be an ordered iterable of class names"
            )
        try:
            names = tuple(class_names)
        except TypeError as exc:
            raise DetectionStabilizerError(
                "class_names must be an iterable of class names"
            ) from exc
        if not names:
            raise DetectionStabilizerError("class_names must not be empty")
        validated = tuple(
            cls._validate_class_name(name, "class_names entry") for name in names
        )
        if len(set(validated)) != len(validated):
            raise DetectionStabilizerError("class_names must not contain duplicates")
        return validated

    @staticmethod
    def _positive_integer(value: object, field_name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise DetectionStabilizerError(f"{field_name} must be a positive integer")
        return value

    @staticmethod
    def _nonnegative_number(value: object, field_name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DetectionStabilizerError(f"{field_name} must be a finite number")
        number = float(value)
        if not math.isfinite(number) or number < 0:
            raise DetectionStabilizerError(
                f"{field_name} must be a finite non-negative number"
            )
        return number

    @classmethod
    def _validate_min_confidence(cls, value: float | None) -> float | None:
        if value is None:
            return None
        confidence = cls._nonnegative_number(value, "min_confidence")
        if confidence > 1.0:
            raise DetectionStabilizerError("min_confidence must be between 0 and 1")
        return confidence

    def _build_class_order(self, priority_order: Iterable[str] | None) -> tuple[str, ...]:
        if priority_order is None:
            return self._class_names
        if isinstance(priority_order, (str, bytes, set, frozenset)):
            raise DetectionStabilizerError(
                "priority_order must be an ordered iterable of known class names"
            )
        try:
            priorities = tuple(priority_order)
        except TypeError as exc:
            raise DetectionStabilizerError(
                "priority_order must be an iterable of known class names"
            ) from exc
        validated = tuple(
            self._validate_class_name(name, "priority_order entry") for name in priorities
        )
        if len(set(validated)) != len(validated):
            raise DetectionStabilizerError("priority_order must not contain duplicates")
        unknown = [name for name in validated if name not in self._known_classes]
        if unknown:
            raise DetectionStabilizerError(
                f"priority_order contains unknown class names: {', '.join(unknown)}"
            )
        priority_set = frozenset(validated)
        return validated + tuple(
            name for name in self._class_names if name not in priority_set
        )

    @property
    def history_length(self) -> int:
        """Number of frames retained in the bounded temporal window."""

        return len(self._history)

    def reset(self) -> None:
        """Clear temporal history, all cooldowns, rotation, and clock state."""

        self._history: deque[frozenset[str]] = deque(maxlen=self.window_size)
        self._last_emitted_at: dict[str, float] = {}
        self._last_global_emitted_at: float | None = None
        self._last_global_emitted_class: str | None = None
        self._last_clock_value: float | None = None

    def _iter_frame_observations(self, frame_observations: object) -> tuple[object, ...]:
        if frame_observations is None:
            return ()
        if isinstance(frame_observations, (str, Mapping)):
            return (frame_observations,)
        if isinstance(frame_observations, bytes):
            raise DetectionStabilizerError("frame observations must not be bytes")
        try:
            return tuple(frame_observations)  # type: ignore[arg-type]
        except TypeError as exc:
            raise DetectionStabilizerError(
                "frame_observations must be an iterable of observations"
            ) from exc

    def _normalise_observation(self, observation: object) -> tuple[str, float | None]:
        if isinstance(observation, str):
            return self._validate_class_name(observation, "observation class_name"), None
        if not isinstance(observation, Mapping):
            raise DetectionStabilizerError(
                "each observation must be a class-name string or mapping with class_name"
            )
        if "class_name" not in observation:
            raise DetectionStabilizerError("observation mapping is missing class_name")
        class_name = self._validate_class_name(
            observation["class_name"], "observation class_name"
        )
        if "confidence" not in observation:
            return class_name, None
        confidence = self._nonnegative_number(observation["confidence"], "confidence")
        if confidence > 1.0:
            raise DetectionStabilizerError("confidence must be between 0 and 1")
        return class_name, confidence

    def _classes_in_frame(self, frame_observations: object) -> frozenset[str]:
        classes: set[str] = set()
        for observation in self._iter_frame_observations(frame_observations):
            class_name, confidence = self._normalise_observation(observation)
            if self.min_confidence is not None:
                if confidence is None:
                    raise DetectionStabilizerError(
                        "observations require confidence when min_confidence is configured"
                    )
                if confidence < self.min_confidence:
                    continue
            if class_name in self._known_classes:
                classes.add(class_name)
        return frozenset(classes)

    def observe(self, frame_observations: object) -> tuple[str, ...]:
        """Advance one frame and return all currently stable classes.

        Unknown labels are ignored after validation.  Repeated detections of
        the same known label count once in a frame.
        """

        self._history.append(self._classes_in_frame(frame_observations))
        return self.stable_classes()

    def stable_classes(self) -> tuple[str, ...]:
        """Return stable labels in deterministic caller-controlled order.

        A startup window is valid as soon as it contains enough frames for
        ``required_observations``. This avoids delaying an M-of-N result just
        because the window has not yet reached its maximum size.
        """

        if len(self._history) < self.required_observations:
            return ()
        return tuple(
            class_name
            for class_name in self._class_order
            if sum(class_name in frame for frame in self._history)
            >= self.required_observations
        )

    def _current_time(self) -> float:
        raw_value = self._clock()
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise DetectionStabilizerError("clock must return a finite number")
        now = float(raw_value)
        if not math.isfinite(now):
            raise DetectionStabilizerError("clock must return a finite number")
        if self._last_clock_value is not None and now < self._last_clock_value:
            raise DetectionStabilizerError("clock moved backwards")
        self._last_clock_value = now
        return now

    def _eligible_at(self, now: float) -> tuple[str, ...]:
        stable = self.stable_classes()
        if not stable:
            return ()
        if self.global_cooldown:
            if (
                self._last_global_emitted_at is not None
                and now - self._last_global_emitted_at < self.cooldown_seconds
            ):
                return ()
            return (self._next_global_class(stable),)
        return tuple(
            class_name
            for class_name in stable
            if class_name not in self._last_emitted_at
            or now - self._last_emitted_at[class_name] >= self.cooldown_seconds
        )

    def _next_global_class(self, stable: tuple[str, ...]) -> str:
        """Choose the next stable label after the last global emission."""

        if self._last_global_emitted_class is None:
            return stable[0]
        stable_set = frozenset(stable)
        start_index = self._class_index[self._last_global_emitted_class]
        for offset in range(1, len(self._class_order) + 1):
            candidate = self._class_order[
                (start_index + offset) % len(self._class_order)
            ]
            if candidate in stable_set:
                return candidate
        return stable[0]

    def eligible_for_emission(self) -> tuple[str, ...]:
        """Return stable labels that may be emitted now without changing state."""

        return self._eligible_at(self._current_time())

    def _normalise_emitted_classes(self, class_names: object) -> tuple[str, ...]:
        if isinstance(class_names, str):
            raw_names = (class_names,)
        elif isinstance(class_names, (bytes, set, frozenset)):
            raise DetectionStabilizerError(
                "emitted class names must be an ordered iterable of class names"
            )
        else:
            try:
                raw_names = tuple(class_names)  # type: ignore[arg-type]
            except TypeError as exc:
                raise DetectionStabilizerError(
                    "emitted class names must be a class name or iterable of class names"
                ) from exc
        names = tuple(
            self._validate_class_name(name, "emitted class name") for name in raw_names
        )
        if not names:
            raise DetectionStabilizerError("at least one emitted class name is required")
        if len(set(names)) != len(names):
            raise DetectionStabilizerError("emitted class names must not contain duplicates")
        unknown = [name for name in names if name not in self._known_classes]
        if unknown:
            raise DetectionStabilizerError(
                f"emitted class names are not tracked: {', '.join(unknown)}"
            )
        return names

    def mark_emitted(self, class_names: object) -> tuple[str, ...]:
        """Record one or more labels that the caller actually emitted.

        Labels must currently be eligible.  The caller should invoke this only
        after it has accepted responsibility for emitting or announcing them.
        """

        names = self._normalise_emitted_classes(class_names)
        now = self._current_time()
        eligible = self._eligible_at(now)
        if any(name not in eligible for name in names):
            raise DetectionStabilizerError(
                "emitted class names must be currently eligible for emission"
            )
        if self.global_cooldown and len(names) > 1:
            raise DetectionStabilizerError(
                "global_cooldown permits only one emitted class at a time"
            )
        for name in names:
            self._last_emitted_at[name] = now
        if self.global_cooldown:
            self._last_global_emitted_at = now
            self._last_global_emitted_class = names[0]
        return names


def replay_frames(
    stabilizer: DetectionStabilizer,
    frames: Iterable[object],
    *,
    mark_emitted: bool = True,
) -> tuple[tuple[str, ...], ...]:
    """Replay local/synthetic frames and return eligible labels for each frame.

    This pure helper is intended for deterministic tests and offline debugging.
    When ``mark_emitted`` is true, each frame's eligible labels are recorded as
    emitted after being returned, so later frames observe the configured
    cooldown.  It does not perform inference, I/O, or announcement delivery.
    """

    if not isinstance(stabilizer, DetectionStabilizer):
        raise DetectionStabilizerError("stabilizer must be a DetectionStabilizer")
    if isinstance(frames, (str, bytes, Mapping, set, frozenset)):
        raise DetectionStabilizerError("frames must be an ordered iterable of frames")
    results: list[tuple[str, ...]] = []
    for frame in frames:
        stabilizer.observe(frame)
        eligible = stabilizer.eligible_for_emission()
        results.append(eligible)
        if mark_emitted and eligible:
            stabilizer.mark_emitted(eligible)
    return tuple(results)
