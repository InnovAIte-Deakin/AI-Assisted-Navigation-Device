"""Immutable, policy-neutral ML semantics for WalkBuddy's approved MVP classes.

This contract owns class identity, base severity, display wording, and the
fact that each approved class can be a navigation hazard. It deliberately does
not decide whether any individual detection should produce a warning. Callers
must apply their own contextual direction, confidence, proximity, and temporal
stabilization rules before taking action.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from types import MappingProxyType
from typing import Mapping


class BaseSeverity(IntEnum):
    """Ordered base severities, with ``LOW`` retained for legacy fallbacks."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    def __setattr__(self, name: str, value: object) -> None:
        """Prevent mutation of enum-member identity after construction."""

        if name in {"_name_", "_value_"} and hasattr(self, name):
            raise AttributeError("BaseSeverity members are immutable.")
        super().__setattr__(name, value)


@dataclass(frozen=True)
class NavigationClass:
    """One approved navigation class and its invariant ML-facing semantics."""

    class_id: int
    name: str
    base_severity: BaseSeverity
    spoken_name: str
    potential_hazard: bool
    aliases: tuple[str, ...] = ()


NAVIGATION_CLASSES: tuple[NavigationClass, ...] = (
    NavigationClass(0, "person", BaseSeverity.HIGH, "person", True),
    NavigationClass(1, "stairs", BaseSeverity.CRITICAL, "stairs", True),
    NavigationClass(2, "door", BaseSeverity.MEDIUM, "door", True),
    NavigationClass(3, "chair", BaseSeverity.MEDIUM, "chair", True, ("office-chair",)),
    NavigationClass(4, "table", BaseSeverity.MEDIUM, "table", True),
    NavigationClass(5, "pole", BaseSeverity.HIGH, "pole", True),
    NavigationClass(6, "bicycle", BaseSeverity.HIGH, "bicycle", True),
    NavigationClass(7, "vehicle", BaseSeverity.CRITICAL, "vehicle", True),
)


def _build_class_id_lookup(
    classes: tuple[NavigationClass, ...],
) -> Mapping[int, NavigationClass]:
    expected_ids = tuple(range(len(classes)))
    class_ids = tuple(item.class_id for item in classes)
    if class_ids != expected_ids:
        raise RuntimeError("Navigation class IDs must be consecutive and ordered from 0.")
    if len({item.name for item in classes}) != len(classes):
        raise RuntimeError("Navigation class names must be unique.")
    return MappingProxyType({item.class_id: item for item in classes})


def _build_class_name_lookup(
    classes: tuple[NavigationClass, ...],
) -> Mapping[str, NavigationClass]:
    lookup: dict[str, NavigationClass] = {}
    for item in classes:
        for label in (item.name, *item.aliases):
            normalized = label.casefold()
            if normalized in lookup:
                raise RuntimeError("Navigation class names and aliases must be unique.")
            lookup[normalized] = item
    return MappingProxyType(lookup)


_BY_ID = _build_class_id_lookup(NAVIGATION_CLASSES)
_BY_NORMALIZED_NAME = _build_class_name_lookup(NAVIGATION_CLASSES)


def _normalize_label(value: object) -> str | None:
    """Apply documented case/whitespace normalization before an exact lookup."""

    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold()
    return normalized or None


def get_navigation_class(value: object) -> NavigationClass | None:
    """Return the canonical class for an exact normalized name or alias."""

    normalized = _normalize_label(value)
    return _BY_NORMALIZED_NAME.get(normalized) if normalized is not None else None


def get_navigation_class_by_id(class_id: object) -> NavigationClass | None:
    """Return the canonical class for an exact integer MVP class ID."""

    if isinstance(class_id, bool) or not isinstance(class_id, int):
        return None
    return _BY_ID.get(class_id)


def canonicalize_class_name(value: object) -> str | None:
    """Return an approved canonical name, or ``None`` for an unknown label."""

    navigation_class = get_navigation_class(value)
    return navigation_class.name if navigation_class is not None else None


def get_base_severity(value: object) -> BaseSeverity | None:
    """Return a canonical class's agreed base severity, if recognized."""

    navigation_class = get_navigation_class(value)
    return navigation_class.base_severity if navigation_class is not None else None


def get_spoken_name(value: object) -> str | None:
    """Return a canonical spoken name without heuristic suffixes."""

    navigation_class = get_navigation_class(value)
    return navigation_class.spoken_name if navigation_class is not None else None


def is_potential_hazard(value: object) -> bool:
    """Whether a recognized class may be hazardous in the right context."""

    navigation_class = get_navigation_class(value)
    return bool(navigation_class and navigation_class.potential_hazard)


def severity_rank(severity: BaseSeverity) -> int:
    """Return the deliberate numeric ordering for consumers that sort severity."""

    if not isinstance(severity, BaseSeverity):
        raise TypeError("severity must be a BaseSeverity")
    return int(severity)
