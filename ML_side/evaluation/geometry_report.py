"""JSON, CSV, and Markdown reports for evaluate_by_geometry() results.

Builders are pure functions of their inputs. generated_at is an optional
argument rather than read from the clock, so tests can assert exact output.
JSON is the source of truth; CSV and Markdown are projections of the same dict.
"""

import csv
import json
from pathlib import Path
from typing import Optional, Union

from .geometry import ASPECT_BUCKET_ORDER, SIZE_BUCKET_ORDER


ARTIFACT_TYPE = "geometry_breakdown"
SCHEMA_VERSION = "1.0.0"

CSV_FIELDNAMES = (
    "dimension",
    "bucket",
    "class",
    "support",
    "tp",
    "fp",
    "fn",
    "precision",
    "recall",
    "f1",
)

INDEPENDENT_FILTERING_NOTE = (
    "Size and aspect buckets filter ground-truth and predictions independently "
    "(COCO-style), then reuse evaluate(); a medium ground-truth box whose "
    "matching prediction is large is a false negative in the medium bucket and "
    "a false positive in the large bucket."
)


def _fmt_pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _csv_num(value: Optional[float]) -> str:
    if value is None:
        return ""
    return repr(value)


def build_json_report(
    result: dict,
    generated_at: Optional[str] = None,
    extra_meta: Optional[dict] = None,
) -> dict:
    """Assemble the machine-readable geometry report. Deterministic given inputs."""
    config = result["config"]
    meta = {
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "iou_threshold": config["iou_threshold"],
        "classes": list(config["classes"]),
        "num_images": result["num_images"],
        "dataset_split": config["dataset_split"],
        "held_out_test_used": False,
        "coordinate_space": config["coordinate_space"],
        "size_buckets": config["size_buckets"],
        "aspect_buckets": config["aspect_buckets"],
        "strict": config["strict"],
        "independent_filtering": INDEPENDENT_FILTERING_NOTE,
    }
    if generated_at is not None:
        meta["generated_at"] = generated_at
    if extra_meta:
        meta.update(extra_meta)

    return {
        "meta": meta,
        "unstratified": result["unstratified"],
        "by_size": result["by_size"],
        "by_aspect": result["by_aspect"],
        "by_size_and_aspect": result["by_size_and_aspect"],
        "bucket_support": result["bucket_support"],
        "unknown_classes": result["unknown_classes"],
        "unmatched_image_ids": result["unmatched_image_ids"],
    }


def write_json_report(report: dict, path: Union[str, Path]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(report, f, indent=2, sort_keys=False)
        f.write("\n")


def _metric_row(dimension: str, bucket: str, cls: str, metrics: dict) -> dict:
    return {
        "dimension": dimension,
        "bucket": bucket,
        "class": cls,
        "support": metrics["support"],
        "tp": metrics["tp"],
        "fp": metrics["fp"],
        "fn": metrics["fn"],
        "precision": _csv_num(metrics["precision"]),
        "recall": _csv_num(metrics["recall"]),
        "f1": _csv_num(metrics["f1"]),
    }


def build_csv_rows(report: dict) -> list:
    """Flat rows: one per dimension × bucket × class, in a stable order."""
    classes = list(report["meta"]["classes"])
    rows = []
    for cls in classes:
        rows.append(_metric_row("unstratified", "all", cls, report["unstratified"]["per_class"][cls]))
    for bucket in SIZE_BUCKET_ORDER:
        for cls in classes:
            rows.append(_metric_row("size", bucket, cls, report["by_size"][bucket]["per_class"][cls]))
    for bucket in ASPECT_BUCKET_ORDER:
        for cls in classes:
            rows.append(
                _metric_row("aspect", bucket, cls, report["by_aspect"][bucket]["per_class"][cls])
            )
    for cls in classes:
        for size_bucket in SIZE_BUCKET_ORDER:
            for aspect_bucket in ASPECT_BUCKET_ORDER:
                key = f"{size_bucket}|{aspect_bucket}"
                rows.append(
                    _metric_row(
                        "size_and_aspect",
                        key,
                        cls,
                        report["by_size_and_aspect"][cls][key],
                    )
                )
    return rows


def write_csv_report(report: dict, path: Union[str, Path]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = build_csv_rows(report)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(CSV_FIELDNAMES))
        writer.writeheader()
        writer.writerows(rows)


def _metrics_table_row(label: str, metrics: dict) -> str:
    return (
        f"| {label} | {metrics['support']} | {metrics['tp']} | {metrics['fp']} | "
        f"{metrics['fn']} | {_fmt_pct(metrics['precision'])} | "
        f"{_fmt_pct(metrics['recall'])} | {_fmt_pct(metrics['f1'])} |"
    )


def _class_table(title: str, per_class: dict, classes: list) -> list:
    lines = [title, "", "| Class | Support | TP | FP | FN | Precision | Recall | F1 |", "|---|---|---|---|---|---|---|---|"]
    for cls in classes:
        lines.append(_metrics_table_row(cls, per_class[cls]))
    lines.append("")
    return lines


def build_markdown_report(report: dict, model_name: str = "candidate model") -> str:
    """Human-readable summary. Pole-focus section leads when pole is in classes."""
    meta = report["meta"]
    classes = list(meta["classes"])
    lines = []
    lines.append(f"# WalkBuddy Geometry Evaluation — {model_name}")
    lines.append("")
    lines.append(f"- Images evaluated: {meta['num_images']}")
    lines.append(f"- Dataset split: {meta['dataset_split']}")
    lines.append(f"- Held-out test used: {meta['held_out_test_used']}")
    lines.append(f"- IoU threshold: {meta['iou_threshold']}")
    lines.append(f"- Classes: {', '.join(classes)}")
    lines.append(f"- Coordinate space: {meta['coordinate_space']}")
    size_edges = meta["size_buckets"]
    lines.append(
        "- Size buckets (bbox area, px²; upper bound exclusive except large): "
        f"small {size_edges['small']}, medium {size_edges['medium']}, "
        f"large {size_edges['large']}"
    )
    aspect_edges = meta["aspect_buckets"]
    lines.append(
        "- Aspect buckets (height/width): "
        f"tall_thin ≥ {aspect_edges['tall_thin']['min_hw']}, "
        f"tall [{aspect_edges['tall']['min_hw']}, {aspect_edges['tall']['max_hw']}), "
        f"square_ish [{aspect_edges['square_ish']['min_hw']}, {aspect_edges['square_ish']['max_hw']}), "
        f"wide < {aspect_edges['wide']['max_hw']}"
    )
    if "generated_at" in meta:
        lines.append(f"- Generated: {meta['generated_at']}")
    lines.append("")
    lines.append(INDEPENDENT_FILTERING_NOTE)
    lines.append("")

    if "pole" in classes:
        pole_size_support = report["bucket_support"]["size"]["pole"]
        pole_aspect_support = report["bucket_support"]["aspect"]["pole"]
        lines.append("## Pole focus")
        lines.append("")
        lines.append("Ground-truth pole counts by bucket (before matching):")
        lines.append("")
        lines.append(
            "- Size: "
            + ", ".join(f"{bucket}={pole_size_support[bucket]}" for bucket in SIZE_BUCKET_ORDER)
        )
        lines.append(
            "- Aspect: "
            + ", ".join(f"{bucket}={pole_aspect_support[bucket]}" for bucket in ASPECT_BUCKET_ORDER)
        )
        lines.append("")
        lines.append("### Pole — by object size")
        lines.append("")
        lines.append("| Bucket | Support | TP | FP | FN | Precision | Recall | F1 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for bucket in SIZE_BUCKET_ORDER:
            lines.append(
                _metrics_table_row(bucket, report["by_size"][bucket]["per_class"]["pole"])
            )
        lines.append("")
        lines.append("### Pole — by aspect ratio")
        lines.append("")
        lines.append("| Bucket | Support | TP | FP | FN | Precision | Recall | F1 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for bucket in ASPECT_BUCKET_ORDER:
            lines.append(
                _metrics_table_row(bucket, report["by_aspect"][bucket]["per_class"]["pole"])
            )
        lines.append("")
        lines.append("### Pole — by size × aspect")
        lines.append("")
        lines.append("| Size | Aspect | Support | TP | FP | FN | Precision | Recall | F1 |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for size_bucket in SIZE_BUCKET_ORDER:
            for aspect_bucket in ASPECT_BUCKET_ORDER:
                metrics = report["by_size_and_aspect"]["pole"][f"{size_bucket}|{aspect_bucket}"]
                lines.append(
                    f"| {size_bucket} | {aspect_bucket} | {metrics['support']} | "
                    f"{metrics['tp']} | {metrics['fp']} | {metrics['fn']} | "
                    f"{_fmt_pct(metrics['precision'])} | {_fmt_pct(metrics['recall'])} | "
                    f"{_fmt_pct(metrics['f1'])} |"
                )
        lines.append("")

    lines.append("## By object size (all requested classes)")
    lines.append("")
    for bucket in SIZE_BUCKET_ORDER:
        lines.extend(
            _class_table(
                f"### {bucket}",
                report["by_size"][bucket]["per_class"],
                classes,
            )
        )

    lines.append("## By aspect ratio (all requested classes)")
    lines.append("")
    for bucket in ASPECT_BUCKET_ORDER:
        lines.extend(
            _class_table(
                f"### {bucket}",
                report["by_aspect"][bucket]["per_class"],
                classes,
            )
        )

    lines.append("## Unstratified (all sizes and shapes)")
    lines.append("")
    overall = report["unstratified"]["overall"]
    lines.append("| Metric | Micro | Macro |")
    lines.append("|---|---|---|")
    lines.append(
        f"| Precision | {_fmt_pct(overall['micro']['precision'])} | {_fmt_pct(overall['macro']['precision'])} |"
    )
    lines.append(
        f"| Recall | {_fmt_pct(overall['micro']['recall'])} | {_fmt_pct(overall['macro']['recall'])} |"
    )
    lines.append(
        f"| F1 | {_fmt_pct(overall['micro']['f1'])} | {_fmt_pct(overall['macro']['f1'])} |"
    )
    lines.append(
        f"| TP / FP / FN | {overall['micro']['tp']} / {overall['micro']['fp']} / {overall['micro']['fn']} | — |"
    )
    lines.append("")
    lines.extend(_class_table("### Per-class", report["unstratified"]["per_class"], classes))

    return "\n".join(lines)


def write_markdown_report(markdown_text: str, path: Union[str, Path]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(markdown_text)
