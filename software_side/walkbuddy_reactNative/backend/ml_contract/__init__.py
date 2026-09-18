"""Canonical ML-facing contracts shared by backend consumers."""

from .navigation_semantics import (
    BaseSeverity,
    NAVIGATION_CLASSES,
    NavigationClass,
    canonicalize_class_name,
    get_base_severity,
    get_navigation_class,
    get_navigation_class_by_id,
    get_spoken_name,
    is_potential_hazard,
    severity_rank,
)

__all__ = [
    "BaseSeverity",
    "NAVIGATION_CLASSES",
    "NavigationClass",
    "canonicalize_class_name",
    "get_base_severity",
    "get_navigation_class",
    "get_navigation_class_by_id",
    "get_spoken_name",
    "is_potential_hazard",
    "severity_rank",
]
