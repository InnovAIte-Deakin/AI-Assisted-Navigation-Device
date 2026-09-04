"""WalkBuddy navigation-model evaluation pipeline.

Provides a reproducible way to score a navigation-focused object-detection
model's predictions against ground truth for the approved eight-class
taxonomy (person, stairs, door, chair, table, pole, bicycle, vehicle).

Everything in this package is deterministic given fixed inputs: the same
ground truth + predictions + config will always produce the same metrics.
Wall-clock latency numbers are the one exception, since they reflect the
runtime environment, not the model's correctness.
"""

from .taxonomy import TAXONOMY_CLASSES, DEFAULT_SEVERITY

__all__ = ["TAXONOMY_CLASSES", "DEFAULT_SEVERITY"]
