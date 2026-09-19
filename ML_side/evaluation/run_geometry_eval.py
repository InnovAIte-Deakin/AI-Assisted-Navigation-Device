"""CLI: size and aspect-ratio breakdown on top of evaluate().

Sibling of run_eval.py. Consumes the same ground-truth / predictions JSON
(image_id + boxes with class, bbox, and score on predictions). It does not
load a model and does not touch matching.py.

--split is required. The held-out test split is refused with no override.

Usage (synthetic fixtures, no trained model):

    python -m evaluation.run_geometry_eval \\
        --ground-truth tests/fixtures/eval/geometry/ground_truth.json \\
        --predictions tests/fixtures/eval/geometry/predictions.json \\
        --split val \\
        --out-dir reports/geometry_mock \\
        --model-name "mock (dev fixture)"

Usage (Candidate 2 on the validation split — never test):

    python -m evaluation.run_geometry_eval \\
        --ground-truth <val annotations JSON, pixel xyxy> \\
        --predictions <val predictions JSON, same schema> \\
        --split val \\
        --out-dir reports/candidate2_geometry \\
        --model-name "candidate_2"
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .geometry import (
    AspectThresholds,
    HeldOutEvidenceError,
    SizeThresholds,
    evaluate_by_geometry,
    refuse_held_out_inputs,
)
from .geometry_report import (
    build_json_report,
    build_markdown_report,
    write_csv_report,
    write_json_report,
    write_markdown_report,
)
from .taxonomy import TAXONOMY_CLASSES


def _load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def run(
    ground_truth_path,
    predictions_path,
    out_dir,
    split,
    iou_threshold: float = 0.5,
    classes=None,
    model_name: str = "candidate model",
    strict: bool = True,
    size_thresholds=None,
    aspect_thresholds=None,
    deterministic_timestamp: bool = False,
):
    canonical_split = refuse_held_out_inputs(ground_truth_path, predictions_path, split)
    ground_truth = _load_json(ground_truth_path)
    predictions = _load_json(predictions_path)
    class_list = list(classes) if classes is not None else list(TAXONOMY_CLASSES)

    result = evaluate_by_geometry(
        ground_truth,
        predictions,
        split=canonical_split,
        classes=class_list,
        iou_threshold=iou_threshold,
        size_thresholds=size_thresholds,
        aspect_thresholds=aspect_thresholds,
        strict=strict,
    )

    generated_at = None if deterministic_timestamp else datetime.now(timezone.utc).isoformat()
    report = build_json_report(
        result,
        generated_at=generated_at,
        extra_meta={"model_name": model_name},
    )

    out_dir = Path(out_dir)
    write_json_report(report, out_dir / "geometry_eval_report.json")
    write_csv_report(report, out_dir / "geometry_eval_report.csv")
    write_markdown_report(
        build_markdown_report(report, model_name=model_name),
        out_dir / "geometry_eval_report.md",
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "WalkBuddy geometry evaluation: per-class precision/recall/F1 broken "
            "down by bbox size and aspect ratio. Reuses evaluate(); does not "
            "use the held-out test split."
        )
    )
    parser.add_argument("--ground-truth", required=True, help="Path to ground truth JSON")
    parser.add_argument("--predictions", required=True, help="Path to predictions JSON")
    parser.add_argument(
        "--split",
        required=True,
        help="Dataset split this JSON came from. Required. Allowed: train, val "
        "(aliases: validation, eval). test / held-out are refused.",
    )
    parser.add_argument("--out-dir", required=True, help="Directory to write report files into")
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument(
        "--classes",
        nargs="+",
        default=None,
        help="Subset of taxonomy classes to score (default: all eight). "
        "Example: --classes pole",
    )
    parser.add_argument("--model-name", default="candidate model")
    parser.add_argument(
        "--allow-unknown-classes",
        action="store_true",
        help="Surface out-of-taxonomy classes in the report instead of failing on them.",
    )
    parser.add_argument(
        "--small-area-max",
        type=float,
        default=None,
        help="Exclusive upper bound for the small size bucket (default: 1024 = 32^2).",
    )
    parser.add_argument(
        "--medium-area-max",
        type=float,
        default=None,
        help="Exclusive upper bound for the medium size bucket (default: 9216 = 96^2).",
    )
    parser.add_argument(
        "--tall-thin-min",
        type=float,
        default=None,
        help="Inclusive height/width lower bound for tall_thin (default: 3.0).",
    )
    parser.add_argument(
        "--tall-min",
        type=float,
        default=None,
        help="Inclusive height/width lower bound for tall (default: 1.5).",
    )
    parser.add_argument(
        "--square-min",
        type=float,
        default=None,
        help="Inclusive height/width lower bound for square_ish (default: 2/3).",
    )
    args = parser.parse_args(argv)

    size_kwargs = {}
    if args.small_area_max is not None:
        size_kwargs["small_max"] = args.small_area_max
    if args.medium_area_max is not None:
        size_kwargs["medium_max"] = args.medium_area_max
    aspect_kwargs = {}
    if args.tall_thin_min is not None:
        aspect_kwargs["tall_thin_min"] = args.tall_thin_min
    if args.tall_min is not None:
        aspect_kwargs["tall_min"] = args.tall_min
    if args.square_min is not None:
        aspect_kwargs["square_min"] = args.square_min

    try:
        report = run(
            ground_truth_path=args.ground_truth,
            predictions_path=args.predictions,
            out_dir=args.out_dir,
            split=args.split,
            iou_threshold=args.iou_threshold,
            classes=args.classes,
            model_name=args.model_name,
            strict=not args.allow_unknown_classes,
            size_thresholds=SizeThresholds(**size_kwargs) if size_kwargs else None,
            aspect_thresholds=AspectThresholds(**aspect_kwargs) if aspect_kwargs else None,
        )
    except HeldOutEvidenceError as exc:
        print(f"Geometry evaluation refused: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Geometry evaluation failed: {exc}", file=sys.stderr)
        return 1

    print(f"Geometry evaluation complete: {args.out_dir}")
    print(f"Split: {report['meta']['dataset_split']}")
    print(f"Held-out test used: {report['meta']['held_out_test_used']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
