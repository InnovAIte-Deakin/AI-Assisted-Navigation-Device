import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from ML_side.data.validate_cvat_yolo_export import validate_export, APPROVED_CLASSES


def create_image(path: Path, size=(640, 480)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(128, 128, 128)).save(path)


def write_label(path: Path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_validate_export_reports_missing_and_orphaned_files():
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        images_dir = root / "images"
        labels_dir = root / "labels"
        create_image(images_dir / "image_a.jpg")
        write_label(labels_dir / "image_b.txt", ["0 0.5 0.5 0.3 0.3"])

        report = validate_export(root, "images", "labels", root / "reports")

        assert report["total_images"] == 1
        assert report["total_label_files"] == 1
        assert report["missing_labels"] == ["image_a"]
        assert report["orphaned_labels"] == ["image_b"]
        assert any(issue["type"] == "missing_label" for issue in report["issues"])
        assert any(issue["type"] == "orphaned_label" for issue in report["issues"])


def test_validate_export_detects_invalid_rows_and_duplicate_annotations():
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        images_dir = root / "images"
        labels_dir = root / "labels"
        create_image(images_dir / "image_a.png")
        write_label(
            labels_dir / "image_a.txt",
            [
                "0 0.5 0.5 0.3 0.3",
                "0 0.5 0.5 0.3 0.3",
                "99 0.5 0.5 0.3 0.3",
                "1 1.1 0.5 0.2 0.2",
                "1 0.5 0.5 0.0 0.2",
                "malformed line",
            ],
        )

        report = validate_export(root, "images", "labels", root / "reports")
        issue_types = {issue["type"] for issue in report["issues"]}

        assert "duplicate_annotation" in issue_types
        assert "invalid_class_id" in issue_types
        assert "invalid_bbox" in issue_types
        assert "malformed_row" in issue_types
        assert report["issue_count"] >= 4


def test_validate_export_generates_deterministic_reports():
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        images_dir = root / "images"
        labels_dir = root / "labels"
        reports_dir = root / "reports"
        create_image(images_dir / "image_a.jpg")
        write_label(labels_dir / "image_a.txt", ["0 0.5 0.5 0.1 0.1"])

        report = validate_export(root, "images", "labels", reports_dir)
        json_path = reports_dir / "validation_report.json"
        markdown_path = reports_dir / "validation_report.md"

        assert json_path.exists()
        assert markdown_path.exists()

        loaded = json.loads(json_path.read_text(encoding="utf-8"))
        assert loaded["approved_classes"] == APPROVED_CLASSES
        assert loaded["total_images"] == 1
        assert loaded["issue_count"] == 0

        markdown_text = markdown_path.read_text(encoding="utf-8")
        assert "CVAT YOLO Export Validation Report" in markdown_text
        assert "No issues detected" in markdown_text
