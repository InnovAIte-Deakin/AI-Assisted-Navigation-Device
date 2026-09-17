"""CLI entrypoint: run the evaluation pipeline end to end.

This is a supplementary error-analysis tool, meant to be run alongside
evaluate_current_model.py against the same model, see report.py's module
docstring for why it's kept separate rather than folded into that tool's
output format.

Usage (mock mode, works today with no trained model):

    python -m evaluation.run_eval \\
        --ground-truth tests/fixtures/eval/ground_truth_small.json \\
        --predictions tests/fixtures/eval/predictions_small.json \\
        --out-dir reports/mock_run \\
        --model-name "mock (dev fixture)"

Usage (once a real candidate model exists):

    python -m evaluation.run_eval \\
        --ground-truth <path to real val-set annotations, not committed, \\
                         each record needs an "image_path" pointing at the \\
                         actual image file> \\
        --model-path ML_side/models/candidate.pt \\
        --out-dir reports/candidate_v1 \\
        --model-name "candidate_v1"

Either --predictions (mock/pre-computed) or --model-path (real Ultralytics
model) must be given, not both. In real-model mode, every ground-truth
record must carry an "image_path", the model is run against the actual
image file, never against the abstract "image_id".
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .latency import measure_latency, stats_from_timings
from .metrics import evaluate
from .predictors import MockPredictor, compute_model_lineage, load_yolo_predict_fn
from .report import build_json_report, build_markdown_report, write_json_report, write_markdown_report
from .taxonomy import TAXONOMY_CLASSES


def _load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def run(
    ground_truth_path,
    out_dir,
    predictions_path=None,
    model_path=None,
    iou_threshold: float = 0.5,
    model_name: str = "candidate model",
    measure_speed: bool = True,
    deterministic_timestamp: bool = False,
    strict: bool = True,
):
    if (predictions_path is None) == (model_path is None):
        raise ValueError("Provide exactly one of predictions_path or model_path.")

    ground_truth = _load_json(ground_truth_path)
    image_ids = [rec["image_id"] for rec in ground_truth]
    model_lineage = None
    latency = None

    if predictions_path is not None:
        predictions = _load_json(predictions_path)
        predict_fn = MockPredictor.from_fixture(predictions_path).as_predict_fn()
        # MockPredictor is a cheap dict lookup, re-running it just to time it
        # costs nothing real, so this path keeps using measure_latency() as
        # a normal, separate, warmup-then-timed measurement.
        if measure_speed:
            latency = measure_latency(predict_fn, image_ids)
    else:
        predict_fn = load_yolo_predict_fn(model_path)
        model_lineage = compute_model_lineage(model_path, getattr(predict_fn, "class_names", None))

        missing_paths = [rec["image_id"] for rec in ground_truth if not rec.get("image_path")]
        if missing_paths:
            raise ValueError(
                "Real-model evaluation requires an 'image_path' on every "
                "ground-truth record (the model must run against the actual "
                f"image file, not the image_id). Missing for: {missing_paths}"
            )
        image_paths_by_id = {rec["image_id"]: rec["image_path"] for rec in ground_truth}
        latency_inputs = [image_paths_by_id[image_id] for image_id in image_ids]

        # Real inference is expensive, so unlike the mock path, this doesn't
        # run the model separately (once to build predictions, again for a
        # warmup pass, again for a timed pass, 3x total). One optional
        # warmup pass still runs to avoid counting cold-start cost, then
        # predictions are built and timed in the same pass, reusing those
        # timings for the latency stats instead of inferring a second time.
        if measure_speed:
            for image_path in latency_inputs:
                predict_fn(image_path)  # warmup, discarded

        predictions = []
        timings_s = []
        for image_id in image_ids:
            image_path = image_paths_by_id[image_id]
            if measure_speed:
                start = time.perf_counter()
                boxes = predict_fn(image_path)
                timings_s.append(time.perf_counter() - start)
            else:
                boxes = predict_fn(image_path)
            predictions.append({"image_id": image_id, "boxes": boxes})

        if measure_speed:
            latency = stats_from_timings(timings_s)

    result = evaluate(
        ground_truth, predictions, classes=TAXONOMY_CLASSES, iou_threshold=iou_threshold, strict=strict
    )

    generated_at = None if deterministic_timestamp else datetime.now(timezone.utc).isoformat()
    report = build_json_report(
        result, latency=latency, generated_at=generated_at,
        extra_meta={"model_name": model_name}, model_lineage=model_lineage,
    )

    out_dir = Path(out_dir)
    write_json_report(report, out_dir / "error_analysis_report.json")
    write_markdown_report(build_markdown_report(report, model_name=model_name), out_dir / "error_analysis_report.md")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="WalkBuddy navigation-model supplementary error-analysis pipeline"
    )
    parser.add_argument("--ground-truth", required=True, help="Path to ground truth JSON")
    parser.add_argument("--predictions", help="Path to a mock/pre-computed predictions JSON")
    parser.add_argument(
        "--model-path",
        help="Path to a trained .pt model (real predictor). Ground-truth records must "
        "each carry an image_path when this is used.",
    )
    parser.add_argument("--out-dir", required=True, help="Directory to write the report files into")
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--model-name", default="candidate model")
    parser.add_argument("--no-latency", action="store_true", help="Skip latency measurement")
    parser.add_argument(
        "--allow-unknown-classes",
        action="store_true",
        help="Surface out-of-taxonomy classes in the report instead of failing on them.",
    )
    args = parser.parse_args()

    run(
        ground_truth_path=args.ground_truth,
        out_dir=args.out_dir,
        predictions_path=args.predictions,
        model_path=args.model_path,
        iou_threshold=args.iou_threshold,
        model_name=args.model_name,
        measure_speed=not args.no_latency,
        strict=not args.allow_unknown_classes,
    )


if __name__ == "__main__":
    main()
