"""Shared taxonomy constants for the evaluation pipeline.

Canonical class order matches the approved eight-class MVP taxonomy agreed
with the team (person, stairs, door, chair, table, pole, bicycle, vehicle).
Using a fixed order (rather than alphabetical) everywhere keeps reports
deterministic and easy to compare across runs.
"""

TAXONOMY_CLASSES = [
    "person",
    "stairs",
    "door",
    "chair",
    "table",
    "pole",
    "bicycle",
    "vehicle",
]

# Proposed base severity per class, from Ben's post-processing proposal
# (Teams, ML stream group chat). Not yet formally confirmed/finalised.
# Used here only to flag missed hazards by severity in the human-readable
# report; it has no effect on the metric calculations themselves.
DEFAULT_SEVERITY = {
    "person": "HIGH",
    "stairs": "CRITICAL",
    "door": "MEDIUM",
    "chair": "MEDIUM",
    "table": "MEDIUM",
    "pole": "HIGH",
    "bicycle": "HIGH",
    "vehicle": "CRITICAL",
}
