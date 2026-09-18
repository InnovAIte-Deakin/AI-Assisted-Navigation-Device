# WalkBuddy Navigation Model Evaluation Pipeline

Sprint 2 task: design and implement a reproducible evaluation pipeline to
assess navigation-focused object-detection models against the approved
eight-class taxonomy (person, stairs, door, chair, table, pole, bicycle,
vehicle), so the inherited model and future candidate models can be
compared on objective evidence rather than eyeballing predictions.

Built and tested before any new model exists, using mocked predictions
and small synthetic test fixtures, per the task brief. No raw datasets or
model weight files are included here.

## What it does

Given ground truth boxes and a set of predictions for the same images, it:

- matches predicted boxes to ground truth boxes per class using IoU
- calculates overall (micro and macro averaged) and per-class precision,
  recall, and F1
- lists every missed ground-truth object (a false negative, i.e. a
  navigation hazard the model failed to flag), tagged by the proposed
  severity tier for that class where available
- lists every predicted box with no matching ground truth (a false
  detection / false positive)
- measures inference latency (mean, median, P95, FPS) for whichever
  predictor is plugged in
- writes both a machine-readable JSON report and a human-readable
  Markdown report from the same underlying result, so they can never
  disagree with each other

## Repo layout

| File | Purpose |
|---|---|
| `ML_side/evaluation/taxonomy.py` | Canonical 8-class list, proposed severity map |
| `ML_side/evaluation/matching.py` | IoU + greedy per-class box matching |
| `ML_side/evaluation/metrics.py` | Turns matches into per-class/overall metrics + hazard/false-detection lists |
| `ML_side/evaluation/latency.py` | Inference timing (mean/median/P95/FPS) |
| `ML_side/evaluation/predictors.py` | `MockPredictor` (fixture-backed) and `load_yolo_predict_fn` (real Ultralytics model) |
| `ML_side/evaluation/report.py` | Builds and writes the JSON + Markdown reports |
| `ML_side/evaluation/run_eval.py` | CLI entrypoint tying it all together |
| `ML_side/evaluation/geometry.py` | Size / aspect bucketing; `evaluate_by_geometry()` calls `evaluate()` per bucket |
| `ML_side/evaluation/geometry_report.py` | Geometry JSON (source of truth), CSV, and Markdown reports |
| `ML_side/evaluation/run_geometry_eval.py` | CLI for the geometry breakdown (`--split` required; held-out test refused) |
| `ML_side/tests/` | pytest suite, all currently run against `MockPredictor` and the fixtures below |
| `ML_side/tests/fixtures/eval/` | Small synthetic ground truth + predictions JSON (no real images) |
| `ML_side/tests/fixtures/eval/geometry/` | Synthetic size / aspect fixtures for the geometry tool |

## Determinism

Given the same ground truth, predictions, class list, and IoU threshold,
`evaluate()` and the JSON/Markdown report builders always produce the
same output, there's no reliance on set/dict iteration order, and ties in
matching are broken by a fixed rule (prediction index). This is verified
directly in `test_evaluation_pipeline.py::test_run_is_deterministic_across_repeated_calls`.

The one deliberate exception is inference latency: wall-clock timing
reflects the machine and runtime it was measured on, so it will differ
run to run and machine to machine. That's expected, not a bug, latency
numbers should always be read alongside what hardware/environment
produced them.

## Running it today (mock mode, no trained model needed)

```bash
cd ML_side
python -m evaluation.run_eval \
  --ground-truth tests/fixtures/eval/ground_truth_small.json \
  --predictions tests/fixtures/eval/predictions_small.json \
  --out-dir reports/mock_run \
  --model-name "mock (dev fixture)"
```

Writes `reports/mock_run/eval_report.json` and `eval_report.md`.

## Running it once a real candidate model exists

```bash
cd ML_side
python -m evaluation.run_eval \
  --ground-truth <path to a real held-out validation set annotations file> \
  --model-path models/candidate_v1.pt \
  --out-dir reports/candidate_v1 \
  --model-name "candidate_v1"
```

`load_yolo_predict_fn()` in `predictors.py` is the integration point for
a real Ultralytics model, it reads the model's own class list at runtime
(same pattern used elsewhere in the project, e.g. the `/ml/model-info`
endpoint from PR #179) rather than hardcoding class order, so it works
whether the model was trained on 7 or 8 classes. Its logic is covered by
tests through a stubbed `ultralytics` module; only a run against a real
`.pt` file and the real Ultralytics package is left to do manually once a
trained model exists.

## Geometry breakdown (size and aspect ratio)

Reusable overlay on the same JSON and the same `evaluate()` call. It does
not reimplement IoU matching. Ground-truth and prediction boxes are filtered
independently into size and aspect buckets (COCO-style), then `evaluate()`
is run on each slice.

Size and aspect buckets filter ground-truth and predictions independently
(COCO-style), then reuse `evaluate()`; a medium ground-truth box whose
matching prediction is large is a false negative in the medium bucket and
a false positive in the large bucket.

Default size buckets (bbox area in pixel², configurable):

- small: area < 32² (1024)
- medium: 32² ≤ area < 96² (9216)
- large: area ≥ 96²

Default aspect buckets (height / width, configurable, pole-justified):

- tall_thin: h/w ≥ 3.0
- tall: 1.5 ≤ h/w < 3.0
- square_ish: 2/3 ≤ h/w < 1.5
- wide: h/w < 2/3

`--split` is required. Allowed values are `train` and `val` (aliases:
`validation`, `eval`). The held-out `test` split is refused, as is any
input path whose components name `test` or `held-out` / `heldout`. There
is no override flag. Reports always record `held_out_test_used: false`.

The tool is class-agnostic (`--classes` defaults to the full taxonomy) and
always leads the Markdown summary with a Pole focus section when `pole` is
among the requested classes.

```bash
cd ML_side
python -m evaluation.run_geometry_eval \
  --ground-truth tests/fixtures/eval/geometry/ground_truth.json \
  --predictions tests/fixtures/eval/geometry/predictions.json \
  --split val \
  --out-dir reports/geometry_mock \
  --model-name "mock (dev fixture)"
```

Writes `geometry_eval_report.json`, `geometry_eval_report.csv`, and
`geometry_eval_report.md`. Inputs must be the same pixel-xyxy JSON schema
`evaluate()` already uses (not Ultralytics `predictions.json`, and not
normalized YOLO `class x y w h` rows).

## Rerunning for Candidate 2 (and later models)

Use train / validation evidence only. Do not point this tool at the held-out
test split, at `evaluate_current_model.py --split test` artifacts, or at
`ML_side/evaluation/candidates/...-heldout-test-corrected/`.

1. Export val-split ground truth and predictions as `evaluate()` JSON
   (each record: `image_id`, `boxes` with `class`, `bbox` `[x_min,y_min,x_max,y_max]`,
   and `score` on predictions). Pixel xyxy, same unit as `run_eval`.
2. Score overall error analysis if you want it:

```bash
cd ML_side
python -m evaluation.run_eval \
  --ground-truth <path to val-split annotations JSON> \
  --predictions <path to val-split predictions JSON> \
  --out-dir reports/candidate2 \
  --model-name "candidate_2"
```

3. Score the geometry breakdown on the **same val JSON** (never `--split test`):

```bash
cd ML_side
python -m evaluation.run_geometry_eval \
  --ground-truth <path to val-split annotations JSON> \
  --predictions <path to val-split predictions JSON> \
  --split val \
  --out-dir reports/candidate2_geometry \
  --model-name "candidate_2"
```

Optional: `--classes pole` for a pole-only report; omit it to score every
class with a pole-focused Markdown section on top. Later candidates use the
same commands with a new `--model-name` and new prediction JSON.

## Tests

```bash
cd ML_side
pytest tests/ -v
```

Tests cover `MockPredictor`, a stubbed model, the small JSON fixtures in
`tests/fixtures/eval/`, and the geometry fixtures in
`tests/fixtures/eval/geometry/`. The original eval fixtures exercise clean
matches (true positives), a missed CRITICAL-severity hazard for both
`stairs` and `vehicle`, and false detections for two classes (`chair`,
`bicycle`) that have zero ground truth boxes in the fixture at all, to
check the pipeline doesn't divide by zero or crash when a class has no
support. The geometry fixtures add known small/medium/large and
tall_thin/square_ish/wide boxes, an independent-filtering cross-size pair,
empty-bucket handling, the `--classes pole` subset, determinism, and the
held-out split/path guard. Geometry PR evidence is those synthetic
fixtures plus the passing tests, not a re-score of held-out Candidate 1.

## What's intentionally not in scope for this first pass

- COCO-style mAP@[.5:.95] across multiple IoU thresholds. Single-threshold
  precision/recall/F1 (default IoU 0.5) was chosen to keep the first
  version simple, fast to review, and easy to reason about; multi-threshold
  mAP can be layered on top of the same `matching.py` primitives later if
  the team wants it.
- Real per-class severity tiers are pulled from Ben's proposed severity
  list (Teams, ML stream group chat), which is not yet formally confirmed.
  It only affects how missed hazards are labelled in the report, not the
  underlying metric calculations, so it's safe to update later without
  touching the pipeline logic.
