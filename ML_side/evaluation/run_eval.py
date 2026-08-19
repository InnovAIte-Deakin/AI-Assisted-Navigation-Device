"""CLI entrypoint: run the evaluation pipeline end to end.

Usage (mock mode, works today with no trained model):

    python -m evaluation.run_eval \\
        --ground-truth tests/fixtures/eval/ground_truth_small.json \\
        --predictions tests/fixtures/eval/predictions_small.json \\
        --out-dir reports/mock_run \\
        --model-name "mock (dev fixture)"

Usage (once a real candidate model exists):

    python -m evaluation.run_eval \\
        --ground-truth <path to real val-set annotations, not committed> \\
        --model-path ML_side/models/candidate.pt \\
        --out-dir reports/candidate_v1 \\
        --model-name "candidate_v1"

Either --predictions (mock/pre-computed) or --model-path (real Ultralytics
model) must be given, not both.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .latency import measure_latency
from .metrics import evaluate
from .predictors import MockPredictor, load_yolo_predict_fn
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
):
    if (predictions_path is None) == (model_path is None):
        raise ValueError("Provide exactly one of predictions_path or model_path.")

    ground_truth = _load_json(ground_truth_path)
    image_ids = [rec["image_id"] for rec in ground_truth]

    if predictions_path is not None:
        predictions = _load_json(predictions_path)
        predict_fn = MockPredictor.from_fixture(predictions_path).as_predict_fn()
        latency_inputs = image_ids
    else:
        predict_fn = load_yolo_predict_fn(model_path)
        predictions = None  # real predictions are produced fresh, not pre-loaded
        latency_inputs = image_ids  # caller is expected to pass real image paths here in production use

    if predictions is None:
        # Real-model path: predict fresh per image to build the predictions list.
        predictions = []
        for image_id in image_ids:
            predictions.append({"image_id": image_id, "boxes": predict_fn(image_id)})

    result = evaluate(ground_truth, predictions, classes=TAXONOMY_CLASSES, iou_threshold=iou_threshold)

    latency = measure_latency(predict_fn, latency_inputs) if measure_speed else None

    generated_at = None if deterministic_timestamp else datetime.now(timezone.utc).isoformat()
    report = build_json_report(result, latency=latency, generated_at=generated_at,
                                extra_meta={"model_name": model_name})

    out_dir = Path(out_dir)
    write_json_report(report, out_dir / "eval_report.json")
    write_markdown_report(build_markdown_report(report, model_name=model_name), out_dir / "eval_report.md")

    return report


def main():
    parser = argparse.ArgumentParser(description="WalkBuddy navigation-model evaluation pipeline")
    parser.add_argument("--ground-truth", required=True, help="Path to ground truth JSON")
    parser.add_argument("--predictions", help="Path to a mock/pre-computed predictions JSON")
    parser.add_argument("--model-path", help="Path to a trained .pt model (real predictor)")
    parser.add_argument("--out-dir", required=True, help="Directory to write eval_report.json/.md into")
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--model-name", default="candidate model")
    parser.add_argument("--no-latency", action="store_true", help="Skip latency measurement")
    args = parser.parse_args()

    run(
        ground_truth_path=args.ground_truth,
        out_dir=args.out_dir,
        predictions_path=args.predictions,
        model_path=args.model_path,
        iou_threshold=args.iou_threshold,
        model_name=args.model_name,
        measure_speed=not args.no_latency,
    )


if __name__ == "__main__":
    main()
