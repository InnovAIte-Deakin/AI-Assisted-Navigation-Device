"""Shared taxonomy constants for the evaluation pipeline.

Pulls the eight-class taxonomy and severities directly from the backend's
ml_contract.navigation_semantics module rather than keeping a second, hand
maintained copy. That module is the single source of truth the rest of the
app already uses for class identity and base severity, this pipeline
follows it, not a parallel definition.

Per review feedback, this uses a normal package import (sys.path.append +
`from ml_contract.navigation_semantics import ...`), matching the pattern
ML_side/main.py already uses for this exact cross-boundary case, instead of
loading the file directly via importlib. ml_contract/__init__.py only
imports from navigation_semantics.py, and navigation_semantics.py itself
only imports the standard library (dataclasses, enum), so a normal import
here doesn't pull in backend dependencies like FastAPI.
"""

import os
import sys

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_PATH = os.path.normpath(
    os.path.join(
        _CURRENT_DIR, "..", "..", "software_side", "walkbuddy_reactNative", "backend"
    )
)

if os.path.exists(_BACKEND_PATH) and _BACKEND_PATH not in sys.path:
    sys.path.append(_BACKEND_PATH)

from ml_contract.navigation_semantics import (  # noqa: E402
    NAVIGATION_CLASSES,
    BaseSeverity,
    canonicalize_class_name,
    get_base_severity,
    is_potential_hazard,
    severity_rank,
)

# Canonical class order, taken directly from the contract (already ordered
# by class_id 0..7) rather than re-typed by hand here.
TAXONOMY_CLASSES = [item.name for item in NAVIGATION_CLASSES]

# Base severity per class as a plain string ("HIGH", "CRITICAL", ...), taken
# from the contract's BaseSeverity enum. Kept as a simple dict here since
# the rest of this pipeline (report sorting/labelling) only needs the name.
DEFAULT_SEVERITY = {item.name: item.base_severity.name for item in NAVIGATION_CLASSES}

__all__ = [
    "NAVIGATION_CLASSES",
    "BaseSeverity",
    "TAXONOMY_CLASSES",
    "DEFAULT_SEVERITY",
    "canonicalize_class_name",
    "get_base_severity",
    "is_potential_hazard",
    "severity_rank",
]
