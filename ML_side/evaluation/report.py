"""Builds the machine-readable (JSON) and human-readable (Markdown)
evaluation reports from an evaluate() result.

Determinism note: build_json_report()/build_markdown_report() are pure
functions of their inputs, same result dict in, same report out, always.
generated_at is accepted as an explicit optional argument rather than
read from the system clock internally, specifically so tests can pass a
fixed value (or omit it) and assert exact output.
"""

import json
from pathlib import Path
from typing import Optional, Union


def _fmt_pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _fmt_ms(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:.1f} ms"


def build_json_report(
    result: dict,
    latency: Optional[dict] = None,
    generated_at: Optional[str] = None,
    extra_meta: Optional[dict] = None,
    model_lineage: Optional[dict] = None,
) -> dict:
    """Assembles the full report dict. Deterministic given fixed inputs.

    model_lineage identifies the exact model file this report was
    generated against (filename, size, sha256, classes, see
    predictors.compute_model_lineage()), it's None in mock-prediction mode
    where there is no real model file to fingerprint.
    """
    meta = {
        "artifact_type": "supplementary_error_analysis",
        "iou_threshold": result["config"]["iou_threshold"],
        "classes": result["config"]["classes"],
        "num_images": result["num_images"],
    }
    if generated_at is not None:
        meta["generated_at"] = generated_at
    if extra_meta:
        meta.update(extra_meta)

    report = {
        "meta": meta,
        "model": model_lineage,
        "overall": result["overall"],
        "per_class": result["per_class"],
        "missed_hazards": result["missed_hazards"],
        "false_detections": result["false_detections"],
    }
    if latency is not None:
        report["latency"] = latency
    return report


def write_json_report(report: dict, path: Union[str, Path]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(report, f, indent=2, sort_keys=False)
        f.write("\n")


def build_markdown_report(report: dict, model_name: str = "candidate model") -> str:
    """Renders the same report dict as a human-readable Markdown document."""
    meta = report["meta"]
    overall = report["overall"]
    per_class = report["per_class"]
    missed = report["missed_hazards"]
    false_dets = report["false_detections"]
    latency = report.get("latency")

    lines = []
    lines.append(f"# WalkBuddy Navigation Model Evaluation — {model_name}")
    lines.append("")
    lines.append(f"- Images evaluated: {meta['num_images']}")
    lines.append(f"- IoU threshold: {meta['iou_threshold']}")
    lines.append(f"- Classes: {', '.join(meta['classes'])}")
    if "generated_at" in meta:
        lines.append(f"- Generated: {meta['generated_at']}")
    lines.append("")

    lines.append("## Overall")
    lines.append("")
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

    lines.append("## Per-class")
    lines.append("")
    lines.append("| Class | Support | TP | FP | FN | Precision | Recall | F1 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for cls, m in per_class.items():
        lines.append(
            f"| {cls} | {m['support']} | {m['tp']} | {m['fp']} | {m['fn']} | "
            f"{_fmt_pct(m['precision'])} | {_fmt_pct(m['recall'])} | {_fmt_pct(m['f1'])} |"
        )
    lines.append("")

    lines.append(f"## Missed navigation hazards ({len(missed)})")
    lines.append("")
    lines.append("Ground-truth objects the model failed to detect, sorted by severity (CRITICAL first).")
    lines.append("")
    if missed:
        lines.append("| Severity | Class | Image | Box |")
        lines.append("|---|---|---|---|")
        for h in missed:
            lines.append(f"| {h['severity']} | {h['class']} | {h['image_id']} | {h['bbox']} |")
    else:
        lines.append("None.")
    lines.append("")

    lines.append(f"## False detections ({len(false_dets)})")
    lines.append("")
    lines.append("Predicted boxes with no matching ground-truth object.")
    lines.append("")
    if false_dets:
        lines.append("| Class | Image | Score | Box |")
        lines.append("|---|---|---|---|")
        for d in false_dets:
            lines.append(f"| {d['class']} | {d['image_id']} | {d['score']:.2f} | {d['bbox']} |")
    else:
        lines.append("None.")
    lines.append("")

    if latency is not None:
        lines.append("## Inference latency")
        lines.append("")
        lines.append(
            "Wall-clock timing from this run's environment, not deterministic "
            "across machines/runs the way the detection metrics above are."
        )
        lines.append("")
        lines.append(f"- Samples: {latency['num_samples']}")
        lines.append(f"- Mean: {_fmt_ms(latency['mean_ms'])}")
        lines.append(f"- Median: {_fmt_ms(latency['median_ms'])}")
        lines.append(f"- P95: {_fmt_ms(latency['p95_ms'])}")
        fps_str = "n/a" if latency["fps"] is None else f"{latency['fps']:.2f}"
        lines.append(f"- FPS: {fps_str}")
        lines.append("")

    return "\n".join(lines)


def write_markdown_report(markdown_text: str, path: Union[str, Path]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(markdown_text)
