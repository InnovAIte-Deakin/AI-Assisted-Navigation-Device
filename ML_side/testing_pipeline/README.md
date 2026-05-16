# ML Testing Pipeline

This folder contains a repeatable, production-grade testing pipeline for the WalkBuddy navigation model endpoint. It supports image testing, video frame extraction, and automated Precision/Recall evaluation across multiple confidence thresholds.

# Run a custom thershold sweep:
python run_test_suite.py --sweep 0.2 0.45 0.6 0.8

## Main Commands

**Run the Ultimate Grid Search (Batch Images & Videos across multiple thresholds):**
By default, the suite sweeps thresholds `0.3`, `0.5`, and `0.75` to generate a Performance Matrix.
```powershell
python run_test_suite.py

## Main commands

Run all image and video test cases:

```powershell
python run_test_suite.py --cases-dir cases --results-dir results
```

Run only image cases:

```powershell
python run_test_suite.py --cases-dir cases --results-dir results --skip-video
```

Run one video case:

```powershell
python run_video_test.py --case cases/videotesting_2.json --results-dir results
```

Create a new test case interactively:

```powershell
python create_case.py
```

Compare two summary files:

```powershell
python compare_regression.py --previous results/summaries/old_summary.json --current results/summaries/summary.json
```

## What the pipeline saves

The pipeline saves raw model outputs in `results/raw_json` and `results/video_raw_json`.

It saves overall pass or fail summaries in `results/summaries/summary.json`.

It saves failed test details in `results/failure_logs` and `results/video_failure_logs`.

It saves detected video frames in `results/annotated_frames`.

## Failure categories

The improved pipeline separates failures into clearer categories:

- `missing_label`
- `missing_direction_label`
- `wrong_direction`
- `too_few_events`
- `too_few_detection_frames`
- `low_detection_rate`
- `runtime_error`
- `skipped_video`

## What was improved

The main runner can now process both image and video cases.

Video cases no longer need to be treated as a separate manual process unless you only want to run one video case.

The failure logs now include structured categories, not just plain text.

Direction wording is normalised, so `left` and `to the left` are treated consistently.

Common label aliases are supported, such as `chair` and `office-chair`, or `tv` and `monitor`.

Video testing now records detection rate, total checked frames, frames with events, label hit counts, raw JSON output, and annotated evidence frames.
