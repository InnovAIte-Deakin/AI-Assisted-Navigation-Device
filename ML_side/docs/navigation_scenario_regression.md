# Navigation Scenario Regression Harness

`evaluate_navigation_scenarios.py` is an offline, class-presence regression
harness for controlled WalkBuddy navigation scenarios. It complements rather
than replaces labelled mAP evaluation and candidate-model promotion gating.
It never starts a backend service, calls an HTTP endpoint, loads a model, or
changes model artifacts.

The harness imports the approved eight-class taxonomy from
`ML_side/tools/validate_dataset_manifest.py`. This keeps ML tooling dependent
on the existing ML-side source of truth rather than creating an ML-to-backend
dependency. The required order is:

| ID | Class |
|---:|---|
| 0 | person |
| 1 | stairs |
| 2 | door |
| 3 | chair |
| 4 | table |
| 5 | pole |
| 6 | bicycle |
| 7 | vehicle |

## Inputs

A case-suite JSON file uses schema version `1.0.0`:

```json
{
  "schema_version": "1.0.0",
  "suite_id": "indoor-navigation-v1",
  "unexpected_detection_policy": "report_only",
  "cases": [
    {
      "scenario_id": "stairs-ahead",
      "description": "Stairs directly ahead in a controlled navigation scene.",
      "image": "images/stairs-ahead.jpg",
      "expected_classes": ["stairs"],
      "allowed_classes": ["person"],
      "notes": "Real scenario image supplied separately."
    }
  ]
}
```

`image` is metadata only in fixture mode. It must be a relative, traversal-free
path; no image bytes, absolute paths, credentials, or remote URIs are allowed.
Class names are exact canonical names, and duplicates are rejected. Empty
`expected_classes` is allowed for a controlled negative scenario.

The prediction fixture must name every scenario exactly once:

```json
{
  "schema_version": "1.0.0",
  "suite_id": "indoor-navigation-v1",
  "model": {
    "filename": "candidate-navigation.pt",
    "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  },
  "predictions": {
    "stairs-ahead": [
      {"class_name": "stairs", "confidence": 0.91},
      {"class_name": "person", "confidence": 0.88}
    ]
  }
}
```

Fixtures contain normalized detector outputs only. They enable repeatable
regression tests without Ultralytics, model weights, images, a GPU, or a
network connection. An optional model identity records a filename and lowercase
SHA-256 only; the harness does not read the model artifact.

## Scoring and pass/fail behaviour

Scoring is class presence per scenario, not bounding-box matching:

- TP: a required expected class was detected.
- FN: a required expected class was not detected.
- FP: a detected class was neither expected nor explicitly allowed.
- An allowed class is reported separately and does not count as TP or FP.

Duplicate detections of the same class in one scenario are represented as one
class-presence outcome. Precision is `null` when there are no predicted classes;
recall is `null` when there are no required classes; F1 is `null` only when its
own denominator is zero. This avoids fabricated values for undefined metrics.

Every scenario fails when an expected class is missed. The suite field
`unexpected_detection_policy` is explicit: `report_only` (the default) reports
FPs without failing the scenario, while `fail` also fails scenarios with FPs.
This is a detection-correctness rule, not a WalkBuddy safety policy.

`--confidence-threshold` is explicit and appears in both reports. It filters
fixture detections as a detector operating point only; it is not a risk,
proximity, distance, or safety-gate threshold.
Detections with confidence **greater than or equal to** the supplied threshold
are included.

## Run fixture replay

Use an output directory outside the repository so generated reports cannot be
committed accidentally.

```powershell
$env:PYTHONPATH = (Resolve-Path ML_side).Path
python ML_side/tools/evaluate_navigation_scenarios.py `
  --cases C:\evaluation-inputs\navigation-scenarios.json `
  --predictions C:\evaluation-inputs\candidate-predictions.json `
  --output C:\evaluation-results\scenario-regression
```

On macOS or Linux:

```bash
PYTHONPATH=ML_side python ML_side/tools/evaluate_navigation_scenarios.py \
  --cases /path/to/navigation-scenarios.json \
  --predictions /path/to/candidate-predictions.json \
  --output /path/to/scenario-regression
```

The output directory contains deterministic substantive data in:

- `scenario_evaluation.json` for machine comparison;
- `scenario_evaluation.md` for review.

Each report records the suite identity, input filenames and checksums, optional
model identity, inference setting, taxonomy, per-scenario TP/FP/FN details,
missed and unexpected class names, aggregate micro metrics, and per-class
metrics. It deliberately omits absolute paths and timestamps so fixture replay
can be compared byte-for-byte when inputs and settings are unchanged.

## Relationship to older and promotion tooling

The legacy `ML_side/testing_pipeline` is retained as historical evidence but
is deliberately bypassed: its runner imports `requests` and depends on a local
service plus obsolete `/detect` and `/two_brain` endpoints. This harness reuses
only the basic TP/FP/FN idea at a well-defined class-presence level; it does not
reuse network, endpoint, response-shape, direction, or safety assumptions.

`validate_candidate_model.py` and `compare_model_evaluations.py` remain the
authoritative candidate-validation and promotion-review tools. Scenario reports
are additional evidence only and cannot promote a model automatically.

## Current limitation

This initial implementation intentionally supports saved prediction fixtures,
not direct local YOLO inference. A future narrowly scoped adapter may load an
explicit caller-supplied local model and produce the same normalized fixture
format, after separate review. Real scenario images and labelled validation data
must be supplied and reviewed separately; no bundled case is evidence of model
quality or navigation safety.
