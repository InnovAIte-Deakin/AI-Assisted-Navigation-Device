from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from PIL import Image

APPROVED_CLASSES = [
    "person",
    "stairs",
    "door",
    "chair",
    "table",
    "pole",
    "bicycle",
    "vehicle",
]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}

@dataclass(frozen=True)
class Issue:
    type: str
    file: str
    line: int | None = None
    class_id: int | None = None
    class_name: str | None = None
    bbox: list[float] | None = None
    description: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "file": self.file,
            "line": self.line,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "bbox": self.bbox,
            "description": self.description,
        }


def is_image_path(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS


def scan_files(directory: Path, pattern: str) -> dict[str, Path]:
    results: dict[str, Path] = {}
    for file_path in sorted(directory.glob(pattern)):
        if file_path.is_file():
            results[file_path.stem] = file_path
    return results


def parse_annotation_row(row: str, line_number: int, label_path: Path) -> tuple[tuple[int, tuple[float, float, float, float]] | None, Issue | None]:
    stripped = row.strip()
    if not stripped:
        return None, None

    parts = stripped.split()
    if len(parts) != 5:
        return None, Issue(
            type="malformed_row",
            file=str(label_path.name),
            line=line_number,
            description=f"Expected 5 values, found {len(parts)}",
        )

    try:
        class_id = int(float(parts[0]))
    except ValueError:
        return None, Issue(
            type="invalid_class_id",
            file=str(label_path.name),
            line=line_number,
            description=f"Class id is not an integer: {parts[0]}",
        )

    try:
        bbox = tuple(float(value) for value in parts[1:5])
    except ValueError:
        return None, Issue(
            type="malformed_row",
            file=str(label_path.name),
            line=line_number,
            class_id=class_id,
            description="BBox values must be numeric",
        )

    x_center, y_center, width, height = bbox
    if width <= 0 or height <= 0:
        return None, Issue(
            type="invalid_bbox",
            file=str(label_path.name),
            line=line_number,
            class_id=class_id,
            bbox=list(bbox),
            description="Width and height must be positive",
        )

    if not (0 <= x_center <= 1 and 0 <= y_center <= 1):
        return None, Issue(
            type="invalid_bbox",
            file=str(label_path.name),
            line=line_number,
            class_id=class_id,
            bbox=list(bbox),
            description="Center coordinates must be between 0 and 1",
        )

    if width > 1 or height > 1:
        return None, Issue(
            type="invalid_bbox",
            file=str(label_path.name),
            line=line_number,
            class_id=class_id,
            bbox=list(bbox),
            description="Width and height must not exceed 1.0",
        )

    half_w = width / 2.0
    half_h = height / 2.0
    if x_center - half_w < 0 or x_center + half_w > 1 or y_center - half_h < 0 or y_center + half_h > 1:
        return None, Issue(
            type="invalid_bbox",
            file=str(label_path.name),
            line=line_number,
            class_id=class_id,
            bbox=list(bbox),
            description="Bounding box extends outside normalized image bounds",
        )

    return (class_id, bbox), None


def inspect_annotations(label_path: Path) -> tuple[list[Issue], Counter[str]]:
    issues: list[Issue] = []
    seen_rows: Counter[str] = Counter()
    with label_path.open("r", encoding="utf-8") as fh:
        lines = fh.readlines()

    non_empty_lines = [line for line in lines if line.strip()]
    if not non_empty_lines:
        issues.append(Issue(
            type="empty_label",
            file=str(label_path.name),
            description="Label file exists but contains no annotations",
        ))
        return issues, seen_rows

    for line_number, line in enumerate(lines, start=1):
        result, issue = parse_annotation_row(line, line_number, label_path)
        if issue is not None:
            issues.append(issue)
            continue

        if result is None:
            continue

        class_id, bbox = result
        seen_rows[format_annotation_row(class_id, bbox)] += 1

        if class_id < 0 or class_id >= len(APPROVED_CLASSES):
            issues.append(Issue(
                type="invalid_class_id",
                file=str(label_path.name),
                line=line_number,
                class_id=class_id,
                description=f"Class id must be between 0 and {len(APPROVED_CLASSES) - 1}",
            ))
            continue

        class_name = APPROVED_CLASSES[class_id]
        area = bbox[2] * bbox[3]
        if area < 0.001:
            issues.append(Issue(
                type="suspicious_bbox_size",
                file=str(label_path.name),
                line=line_number,
                class_id=class_id,
                class_name=class_name,
                bbox=list(bbox),
                description=f"Suspiciously small bounding box area ({area:.6f})",
            ))
        elif area > 0.50:
            issues.append(Issue(
                type="suspicious_bbox_size",
                file=str(label_path.name),
                line=line_number,
                class_id=class_id,
                class_name=class_name,
                bbox=list(bbox),
                description=f"Suspiciously large bounding box area ({area:.6f})",
            ))

    for row, count in seen_rows.items():
        if count > 1:
            issues.append(Issue(
                type="duplicate_annotation",
                file=str(label_path.name),
                description=f"Duplicate annotation repeated {count} times: {row}",
            ))

    return issues, seen_rows


def format_annotation_row(class_id: int, bbox: tuple[float, float, float, float]) -> str:
    return f"{class_id} {' '.join(f'{coord:.6f}' for coord in bbox)}"


def collect_image_label_pairs(images_dir: Path, labels_dir: Path) -> tuple[dict[str, Path], dict[str, Path], list[str], list[str]]:
    images = scan_files(images_dir, "*")
    labels = scan_files(labels_dir, "*.txt")

    image_names = set(images)
    label_names = set(labels)

    missing_labels = sorted(name for name in image_names if name not in label_names)
    orphaned_labels = sorted(name for name in label_names if name not in image_names)
    return images, labels, missing_labels, orphaned_labels


def build_report(images: dict[str, Path], labels: dict[str, Path], missing_labels: list[str], orphaned_labels: list[str], issues: list[Issue]) -> dict[str, Any]:
    classes_used: set[str] = set()
    for issue in issues:
        if issue.class_name:
            classes_used.add(issue.class_name)

    sorted_issues = sorted(
        (issue.as_dict() for issue in issues),
        key=lambda item: (item["type"], item["file"], item["line"] or 0, item["description"]),
    )

    return {
        "approved_classes": APPROVED_CLASSES,
        "total_images": len(images),
        "total_label_files": len(labels),
        "missing_labels": missing_labels,
        "orphaned_labels": orphaned_labels,
        "issue_count": len(sorted_issues),
        "issues": sorted_issues,
        "classes_used": sorted(classes_used),
    }


def render_markdown(report: dict[str, Any]) -> str:
    missing_count = len(report["missing_labels"])
    orphaned_count = len(report["orphaned_labels"])
    issue_count = report["issue_count"]

    lines = [
        "# CVAT YOLO Export Validation Report",
        "",
        "This report was generated deterministically by `validate_cvat_yolo_export.py`.",
        "",
        "## Summary",
        "",
        f"- Approved classes: {', '.join(report['approved_classes'])}",
        f"- Total images found: {report['total_images']}",
        f"- Total label files found: {report['total_label_files']}",
        f"- Missing label files: {missing_count}",
        f"- Orphaned label files: {orphaned_count}",
        f"- Total validation issues: {issue_count}",
        "",
    ]

    if missing_count:
        lines.append("## Missing Label Files")
        lines.append("")
        for name in report["missing_labels"]:
            lines.append(f"- {name}")
        lines.append("")

    if orphaned_count:
        lines.append("## Orphaned Label Files")
        lines.append("")
        for name in report["orphaned_labels"]:
            lines.append(f"- {name}.txt")
        lines.append("")

    lines.append("## Validation Issues")
    lines.append("")
    if issue_count == 0:
        lines.append("No issues detected. The export looks valid for ingestion.")
    else:
        lines.append("| Type | File | Line | Class | Description |")
        lines.append("|---|---|---|---|---|")
        for issue in report["issues"]:
            class_name = issue.get("class_name") or "-"
            line = issue.get("line") or "-"
            lines.append(
                f"| {issue['type']} | {issue['file']} | {line} | {class_name} | {issue['description']} |"
            )
    return "\n".join(lines)


def save_reports(report: dict[str, Any], report_dir: Path) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "validation_report.json"
    markdown_path = report_dir / "validation_report.md"

    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def validate_export(root_path: Path, images_dir_name: str, labels_dir_name: str, report_dir: Path) -> dict[str, Any]:
    images_dir = root_path / images_dir_name
    labels_dir = root_path / labels_dir_name

    if not images_dir.exists() or not images_dir.is_dir():
        raise FileNotFoundError(f"Images directory not found: {images_dir}")
    if not labels_dir.exists() or not labels_dir.is_dir():
        raise FileNotFoundError(f"Labels directory not found: {labels_dir}")

    images = {name: path for name, path in scan_files(images_dir, "*").items() if is_image_path(path)}
    labels = scan_files(labels_dir, "*.txt")

    missing_labels = sorted(name for name in images if name not in labels)
    orphaned_labels = sorted(name for name in labels if name not in images)

    issues: list[Issue] = []

    for label_name in sorted(labels):
        if label_name in orphaned_labels:
            issues.append(Issue(
                type="orphaned_label",
                file=f"{label_name}.txt",
                description="Label file has no matching image",
            ))
            continue

        label_path = labels[label_name]
        file_issues, _ = inspect_annotations(label_path)
        issues.extend(file_issues)

    for image_name in missing_labels:
        issues.append(Issue(
            type="missing_label",
            file=f"{image_name}{labels[next(iter(labels))].suffix if labels else '.txt'}",
            description="Image has no corresponding label file",
        ))

    report = build_report(images, labels, missing_labels, orphaned_labels, issues)
    save_reports(report, report_dir)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate CVAT YOLO exports before WalkBuddy dataset ingestion."
    )
    parser.add_argument("export_root", type=Path, help="Path to the CVAT export root directory")
    parser.add_argument(
        "--images",
        default="images",
        help="Relative images directory inside the export root",
    )
    parser.add_argument(
        "--labels",
        default="labels",
        help="Relative labels directory inside the export root",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("./validation_reports"),
        help="Output directory for deterministic JSON and Markdown reports",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_dir = args.report_dir
    if not report_dir.is_absolute():
        report_dir = Path.cwd() / report_dir

    report = validate_export(args.export_root, args.images, args.labels, report_dir)
    print(f"Validation complete. Reports written to: {report_dir}")
    print(f"Summary: {report['issue_count']} issues, {len(report['missing_labels'])} missing labels, {len(report['orphaned_labels'])} orphaned labels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
