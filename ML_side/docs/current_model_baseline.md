# Current WalkBuddy Model Baseline

This workflow records the supplied local `best.pt` model's metadata and produces
a reproducible baseline without training, replacing, exporting, or downloading a
model or dataset.

## Before you begin

- Follow `docs/LOCAL_SETUP.md` to create the supported backend environment.
- Obtain `ML_side/models/best.pt` through the approved model-asset process.
- Inspect only model files from a trusted project source: loading `.pt` weights
  involves model deserialization.
- Do not commit model weights, private datasets, source images, or generated
  evaluation output.

The verified local artifact documented in `ML_side/models/README.md` has seven
classes: `book`, `books`, `monitor`, `office-chair`, `whiteboard`, `table`, and
`tv`. `ML_side/config/newdata.yaml` currently lists an additional `couch` class.
Do not assume another `best.pt` has the same taxonomy unless its checksum and
`model.names` metadata are inspected locally.

## Unlabelled inference audit

Use this mode for a supplied folder of `.jpg`, `.jpeg`, or `.png` images:

```powershell
& ".\software_side\walkbuddy_reactNative\backend\.venv\Scripts\python.exe" ".\ML_side\tools\evaluate_current_model.py" --model ".\ML_side\models\best.pt" --images ".\path\to\images" --output ".\ML_side\evaluation_results\unlabelled-baseline"
```

This is an **unlabelled inference audit**. It records detections, confidence,
bounding boxes, failures, throughput, and class counts. It is not precision,
recall, or mAP accuracy evaluation because no ground-truth annotations are used.

## Labelled accuracy evaluation

Use this mode only with a local YOLO dataset YAML whose image and annotation
paths are already available. The tool refuses dataset YAML files with a
`download:` directive.

```powershell
& ".\software_side\walkbuddy_reactNative\backend\.venv\Scripts\python.exe" ".\ML_side\tools\evaluate_current_model.py" --model ".\ML_side\models\best.pt" --dataset-yaml ".\path\to\labelled-dataset.yaml" --output ".\ML_side\evaluation_results\labelled-baseline"
```

This mode calls Ultralytics validation and records only metrics made available by
that validation result: precision, recall, mAP50, mAP50-95, per-class metrics,
validation image count, and timing where available. Missing values are written
as `null` with an explanation; no values are estimated or fabricated.

## Output files

Each run writes these files to the requested output directory:

- `model_metadata.json` — local path, size, SHA-256, and class mapping.
- `summary.json` — run mode and aggregate results.
- `predictions.json` — unlabelled mode only; per-image detections and failures.
- `validation_metrics.json` — labelled mode only; available validation metrics.
- `baseline_report.md` — readable summary.

The tool refuses to write into a non-empty output directory unless `--overwrite`
is supplied. It never copies source images into the output directory.

## Verified local smoke test

Windows local execution completed successfully with Ultralytics 8.4.7 and the
actual seven-class `best.pt` artifact.

- Images processed: 10
- Failures: 0
- Average inference time: 95.774 ms
- Detected class counts: `books` 4, `monitor` 2, `table` 1

This was an unlabelled smoke test, not an accuracy evaluation. The full
representative baseline dataset is still pending.

## Preliminary qualitative review

| Intended scenario | Model result | Preliminary assessment |
| --- | --- | --- |
| Bicycle | No detection | Unsupported navigation class |
| Books | No detection | Missed supported class |
| Chair | Detected as table | Incorrect class prediction |
| Door | Two books detections at low confidence | False-positive detections |
| Empty hallway | No detection | Expected negative result |
| Person | No detection | Unsupported navigation class |
| Pole | Monitor and books detections | Multiple false-positive detections |
| Table | No detection | Missed supported class |
| TV | Detected as monitor | Confusion between separately defined supported classes |
| Vehicle | No detection | Unsupported navigation class |

- This was a 10-image unlabelled qualitative smoke test.
- These observations are not precision, recall, or mAP measurements.
- The test confirms that the evaluator works against the real model.
- The active seven-class model does not cover several important navigation scenarios.
- Supported objects were missed or confused in this small sample.
- False-positive detections occurred on unrelated navigation scenes.
- The current model should remain the baseline and should not automatically be
  accepted as the future production model.
- A larger representative test set and a labelled validation set are still required.

## Completed qualitative baseline review

The completed local review processed 33 images with zero processing failures and
an average inference time of 85.43 ms.

Detected model-class totals were:

- `books`: 37
- `monitor`: 3
- `office-chair`: 3
- `table`: 1

| Assessment | Count |
|---|---:|
| Correct detection | 4 |
| Incorrect class | 2 |
| Missed supported object | 11 |
| False positive | 6 |
| Expected no detection | 3 |
| Unsupported class | 6 |
| Mixed result | 1 |
| Total | 33 |

The current seven-class model successfully produced some correct detections, but
supported classes were frequently missed in this small review. Incorrect-class
and false-positive detections also occurred. Important navigation objects were
outside the current model taxonomy. The `books` class produced many more
detections than the other classes, including false-positive patterns identified
during visual review.

The current artifact is useful as a baseline but should not automatically be
accepted as the final WalkBuddy navigation model. Any future candidate model
must be compared against this baseline using the approved target taxonomy and
dataset. A labelled validation dataset will still be required to calculate
precision, recall, and mAP.

### Limitations

- This was an unlabelled qualitative evaluation.
- Filenames were hints only; every image was directly reviewed.
- The 33 images were not a statistically balanced benchmark.
- Qualitative assessment counts are not accuracy percentages.
- No precision, recall, or mAP values were calculated.
- Inference time may vary across hardware and execution environments.
- Local source images and generated result files are not committed.

## Review template

Record qualitative errors alongside the generated JSON rather than changing the
model or configuration during baseline collection.

| Run | Image or class | False positive | Missed detection | Notes |
| --- | --- | --- | --- | --- |
| _add run identifier_ | _add image/class_ | _yes/no and detail_ | _yes/no and detail_ | _observed conditions_ |
