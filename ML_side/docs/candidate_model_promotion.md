# Candidate model validation and promotion gating

This offline workflow validates candidate detection-model artifacts and compares
controlled, versioned evaluations. It never replaces `ML_side/models/best.pt`,
copies weights into production, deploys a model, downloads artifacts, or starts
training.

## Lifecycle and taxonomy

The approved navigation taxonomy is fixed for this workflow:

| ID | Class |
| ---: | --- |
| 0 | `person` |
| 1 | `stairs` |
| 2 | `door` |
| 3 | `chair` |
| 4 | `table` |
| 5 | `pole` |
| 6 | `bicycle` |
| 7 | `vehicle` |

The current seven-class `best.pt` is stored as a `historical_reference` in
`ML_side/evaluation/baselines/historical_7class_baseline.json`. Its taxonomy and
unlabelled qualitative review are not comparable to a first eight-class model,
so a comparison against it always returns `REVIEW`, never an automatic pass or
failure.

The first structurally valid eight-class candidate needs human review after its
controlled evaluation. A human-approved evaluation artifact may later be
labelled `canonical_8class_baseline`; only future candidates can be evaluated
automatically against that compatible baseline.

## Validate a trusted candidate artifact

Use a model and smoke image obtained from a trusted project source. Model
loading deserializes weights. Run this from the supported backend environment
after following `docs/LOCAL_SETUP.md`; choose an output directory outside the
repository to avoid generated reports entering Git.

```powershell
& ".\software_side\walkbuddy_reactNative\backend\.venv\Scripts\python.exe" ".\ML_side\tools\validate_candidate_model.py" --model ".\path\to\candidate.pt" --smoke-image ".\path\to\trusted-smoke-image.jpg" --output ".\outside-repository\candidate-validation"
```

The validator records existence, regular-file status, size, SHA-256, load
result, detection task metadata when available, class metadata, exact class
count and ordered taxonomy, JSON-safe report metadata, and a no-save smoke
inference. The smoke inference confirms only execution, not detection quality.
An unavailable optional task field can produce `pass_with_warnings`; a missing,
malformed, non-eight-class, wrong-taxonomy, unloadable, or non-executing model
produces `fail`.

## Versioned evaluation artifacts

`ML_side/tools/evaluate_current_model.py` now writes version `1.0.0` machine
artifacts. The summary and mode-specific JSON include tool identity, UTC
timestamp, model filename/size/SHA-256/class mapping, evaluation mode, and
effective settings. Labelled-validation artifacts also identify the metric unit,
metric fields, latency unit, and Ultralytics validation source. They
intentionally omit absolute machine-specific paths.

Unlabelled audits use explicit `--operating-confidence` and `--operating-iou`
(defaults are recorded in the artifact) and pass those settings only to
`model.predict`. Labelled validation continues to use `model.val` without
forcing the operating-point values into AP calculation; its artifact records
that the Ultralytics default validation sweep is used instead.

## Compare controlled evaluations

Both inputs must be versioned `summary.json` artifacts (or directories
containing one), use the approved eight-class ID/name mapping in the same
order, use the same evaluation mode and settings, and include required labelled
validation metrics for the requested gates.

```powershell
& ".\software_side\walkbuddy_reactNative\backend\.venv\Scripts\python.exe" ".\ML_side\tools\compare_model_evaluations.py" --baseline ".\outside-repository\canonical-baseline" --candidate ".\outside-repository\candidate-evaluation" --candidate-validation ".\outside-repository\candidate-validation" --output ".\outside-repository\comparison" --gates ".\approved-promotion-gates.json"
```

The comparison reports aggregate, per-class (keyed by class name), and latency
deltas. It records the supplied gate configuration filename, SHA-256, schema,
policy status, and exact gate values, plus the candidate-validation report
filename, SHA-256, and verdict. An automatic result requires that validation
report to match the candidate evaluation's size, SHA-256, and class lineage.
Its verdict is deliberately constrained:

- `FAIL`: a candidate (or non-historical baseline) has a non-approved taxonomy,
  or a compatible candidate breaches an explicitly supplied gate.
- `REVIEW`: a historical/non-canonical baseline, incompatible mode/settings,
  unsupported metric semantics, missing or non-finite metrics, no matching
  candidate-validation report, or no explicitly supplied gate configuration.
- `PASS`: a compatible candidate satisfies every explicitly supplied gate.

`ML_side/config/promotion_gates.example.json` demonstrates the supported format
only. It is explicitly **not approved WalkBuddy policy** and is never loaded by
default; supplying it still returns `REVIEW`. Only a separately approved
configuration with `policy_status` set to `APPROVED_POLICY` is eligible for
automatic decisions. ML-team/project approval is required before any
thresholds, a canonical baseline designation, or a real promotion decision is
used.

## Exit codes

`validate_candidate_model.py` returns `0` for `pass` or `pass_with_warnings`
and `1` for `fail` or a controlled command error. `compare_model_evaluations.py`
returns `0` for `PASS`, `1` for `FAIL` or a controlled command error, and `2`
for `REVIEW`, so unattended callers can distinguish incomplete evidence from a
configured regression. `evaluate_current_model.py` returns `0` after a
completed evaluation and `1` for a controlled evaluation error.
