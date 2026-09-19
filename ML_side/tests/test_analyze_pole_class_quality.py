"""Tests for the pole-class training-data quality investigation tool."""

from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path

import pytest

PIL_AVAILABLE = True
try:
    from PIL import Image
except ImportError:
    PIL_AVAILABLE = False

ML_SIDE_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = ML_SIDE_DIR / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import analyze_pole_class_quality as analyzer  # noqa: E402
import inspect_candidate_dataset as inspector  # noqa: E402


# Same tiny valid GIF fixture used by test_inspect_candidate_dataset.py, so
# tests that don't care about visual content don't need Pillow at all.
IMAGE_BYTES = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==")


def write_yaml(root: Path, names: list[str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    lines = ["path: .", "train: train/images", "val: val/images", "names:"]
    lines.extend(f"  {index}: {name}" for index, name in enumerate(names))
    yaml_path = root / "candidate.yaml"
    yaml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return yaml_path


def write_label(root: Path, split: str, stem: str, lines: list[str]) -> None:
    label_dir = root / split / "labels"
    label_dir.mkdir(parents=True, exist_ok=True)
    (label_dir / f"{stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_image(root: Path, split: str, stem: str, image_bytes: bytes = IMAGE_BYTES) -> None:
    image_dir = root / split / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    (image_dir / f"{stem}.png").write_bytes(image_bytes)


def _png_bytes(pixels: list[list[int]]) -> bytes:
    """Build real PNG bytes from a 2D list of 0-255 grayscale values."""
    image = Image.new("L", (len(pixels[0]), len(pixels)))
    image.putdata([value for row in pixels for value in row])
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _gradient_image(size: int = 16, *, shift: int = 0) -> bytes:
    return _png_bytes([[max(0, min(255, (x + y) * 8 + shift)) for x in range(size)] for y in range(size)])


def _checkerboard_image(size: int = 16) -> bytes:
    return _png_bytes([[255 if (x + y) % 2 == 0 else 0 for x in range(size)] for y in range(size)])


class TestIterLabelLines:
    def test_parses_valid_rows(self, tmp_path: Path) -> None:
        label_path = tmp_path / "a.txt"
        label_path.write_text("5 0.5 0.5 0.1 0.9\n0 0.2 0.2 0.3 0.3\n", encoding="utf-8")
        rows = analyzer._iter_label_lines(label_path)
        assert rows == [(5, 0.1, 0.9), (0, 0.3, 0.3)]

    def test_skips_malformed_and_non_positive_rows(self, tmp_path: Path) -> None:
        label_path = tmp_path / "a.txt"
        label_path.write_text(
            "\n".join(
                [
                    "not five fields here",
                    "abc 0.5 0.5 0.1 0.9",
                    "5 0.5 0.5 0 0.9",
                    "5 0.5 0.5 0.1 -0.1",
                    "5 0.5 0.5 0.2 0.4",
                ]
            ),
            encoding="utf-8",
        )
        rows = analyzer._iter_label_lines(label_path)
        assert rows == [(5, 0.2, 0.4)]

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert analyzer._iter_label_lines(tmp_path / "missing.txt") == []


class TestLoadNamesFromYaml:
    def test_list_form(self, tmp_path: Path) -> None:
        yaml_path = write_yaml(tmp_path, ["person", "pole"])
        assert analyzer._load_names_from_yaml(yaml_path) == ["person", "pole"]

    def test_mapping_form(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "candidate.yaml"
        yaml_path.write_text("path: .\ntrain: train/images\nval: val/images\nnames:\n  1: pole\n  0: person\n", encoding="utf-8")
        assert analyzer._load_names_from_yaml(yaml_path) == ["person", "pole"]


class TestBuildGeometryRecords:
    def test_builds_records_only_for_files_with_annotations(self, tmp_path: Path) -> None:
        root = tmp_path / "dataset"
        write_label(root, "train", "with_box", ["5 0.5 0.5 0.1 0.9"])
        write_label(root, "train", "empty", [])
        write_label(root, "val", "with_box_val", ["0 0.5 0.5 0.2 0.2"])
        taxonomy = {0: "person", 5: "pole"}

        records, per_split_counts = analyzer._build_geometry_records(root, taxonomy)

        image_paths = sorted(str(r["image_path"]) for r in records)
        assert image_paths == ["train/images/with_box", "val/images/with_box_val"]
        assert per_split_counts["train"]["pole"] == 1
        assert per_split_counts["val"]["person"] == 1

    def test_unknown_class_id_is_skipped(self, tmp_path: Path) -> None:
        root = tmp_path / "dataset"
        write_label(root, "train", "stray", ["99 0.5 0.5 0.1 0.1"])
        write_label(root, "val", "placeholder", [])
        taxonomy = {0: "person"}

        records, per_split_counts = analyzer._build_geometry_records(root, taxonomy)

        assert records == []
        assert sum(per_split_counts["train"].values()) == 0

    def test_missing_split_label_directory_raises(self, tmp_path: Path) -> None:
        root = tmp_path / "dataset"
        (root / "train" / "labels").mkdir(parents=True)
        with pytest.raises(inspector.CandidateInspectionError):
            analyzer._build_geometry_records(root, {0: "person"})


class TestSourceDatasetName:
    def test_extracts_prefix_before_wb_sequence(self) -> None:
        assert analyzer._source_dataset_name("train/images/kaggle_light_poles_wb_001285.jpg") == "kaggle_light_poles"

    def test_falls_back_to_stem_when_pattern_does_not_match(self) -> None:
        assert analyzer._source_dataset_name("train/images/unusual_name.jpg") == "unusual_name"


class TestGenericSourceReviewCandidates:
    def test_flags_indoor_sources_case_insensitively(self) -> None:
        records = [
            {"image_path": "train/images/kaggle_light_poles_wb_000001.jpg"},
            {"image_path": "val/images/roboflow_Indoor_Detection_vineeth_wb_000002.jpg"},
            {"image_path": "train/images/kaggle_indoor_object_detection_wb_000003.jpg"},
        ]
        result = analyzer._generic_source_review_candidates(records)
        assert result == [
            "train/images/kaggle_indoor_object_detection_wb_000003.jpg",
            "val/images/roboflow_Indoor_Detection_vineeth_wb_000002.jpg",
        ]


class TestLabelSignatureAndBoxMatching:
    def test_identical_signatures_for_identical_files(self, tmp_path: Path) -> None:
        label_a = tmp_path / "a.txt"
        label_b = tmp_path / "b.txt"
        label_a.write_text("5 0.500000 0.500000 0.100000 0.900000\n", encoding="utf-8")
        label_b.write_text("5 0.500000 0.500000 0.100000 0.900000\n", encoding="utf-8")
        assert analyzer._label_signature(label_a) == analyzer._label_signature(label_b)

    def test_boxes_within_tolerance_match(self, tmp_path: Path) -> None:
        label_a = tmp_path / "a.txt"
        label_b = tmp_path / "b.txt"
        label_a.write_text("5 0.500 0.500 0.100 0.900\n", encoding="utf-8")
        label_b.write_text("5 0.510 0.490 0.105 0.895\n", encoding="utf-8")
        sig_a = analyzer._label_signature(label_a)
        sig_b = analyzer._label_signature(label_b)
        assert sig_a != sig_b  # not byte-identical
        assert analyzer._boxes_match_within_tolerance(sig_a, sig_b, tolerance=0.03)

    def test_boxes_outside_tolerance_do_not_match(self, tmp_path: Path) -> None:
        label_a = tmp_path / "a.txt"
        label_b = tmp_path / "b.txt"
        label_a.write_text("5 0.20 0.20 0.10 0.90\n", encoding="utf-8")
        label_b.write_text("5 0.80 0.80 0.10 0.90\n", encoding="utf-8")
        sig_a = analyzer._label_signature(label_a)
        sig_b = analyzer._label_signature(label_b)
        assert not analyzer._boxes_match_within_tolerance(sig_a, sig_b, tolerance=0.03)

    def test_different_box_counts_do_not_match(self, tmp_path: Path) -> None:
        label_a = tmp_path / "a.txt"
        label_b = tmp_path / "b.txt"
        label_a.write_text("5 0.5 0.5 0.1 0.9\n", encoding="utf-8")
        label_b.write_text("5 0.5 0.5 0.1 0.9\n5 0.2 0.2 0.1 0.1\n", encoding="utf-8")
        sig_a = analyzer._label_signature(label_a)
        sig_b = analyzer._label_signature(label_b)
        assert not analyzer._boxes_match_within_tolerance(sig_a, sig_b)


class TestFindPoleLabelStems:
    def test_finds_stems_with_a_pole_annotation(self, tmp_path: Path) -> None:
        root = tmp_path / "dataset"
        write_label(root, "train", "has_pole", ["5 0.5 0.5 0.1 0.9"])
        write_label(root, "train", "no_pole", ["0 0.5 0.5 0.1 0.1"])
        write_label(root, "val", "also_pole", ["5 0.2 0.2 0.1 0.1", "0 0.5 0.5 0.1 0.1"])

        stems = analyzer._find_pole_label_stems(root, {0: "person", 5: "pole"})

        assert stems == {"train": ["has_pole"], "val": ["also_pole"]}


class TestBuildPoleImageRecords:
    def test_finds_images_directly_under_dataset_root(self, tmp_path: Path) -> None:
        root = tmp_path / "dataset"
        write_image(root, "train", "pole_a")
        write_image(root, "val", "pole_b")

        records, missing = analyzer._build_pole_image_records(
            root, {"train": ["pole_a"], "val": ["pole_b"]}
        )

        assert missing == []
        image_paths = sorted(str(r["image_path"]) for r in records)
        assert image_paths == ["train/images/pole_a.png", "val/images/pole_b.png"]

    def test_reports_missing_images_instead_of_silently_skipping(self, tmp_path: Path) -> None:
        root = tmp_path / "dataset"
        write_image(root, "train", "present")
        # "absent" has a pole label but no matching image file anywhere.

        records, missing = analyzer._build_pole_image_records(
            root, {"train": ["present", "absent"], "val": []}
        )

        assert len(records) == 1
        assert missing == ["train/images/absent"]


class TestClassifyNearDuplicateGroups:
    def test_classifies_identical_similar_and_dissimilar(self, tmp_path: Path) -> None:
        root = tmp_path / "dataset"
        write_label(root, "train", "anchor", ["5 0.500000 0.500000 0.100000 0.900000"])
        write_label(root, "train", "identical_twin", ["5 0.500000 0.500000 0.100000 0.900000"])
        write_label(root, "train", "close_frame", ["5 0.510000 0.490000 0.105000 0.895000"])
        write_label(root, "val", "different_scene", ["5 0.100000 0.100000 0.050000 0.050000"])
        groups = [
            {
                "images": [
                    "train/images/anchor",
                    "train/images/identical_twin",
                    "train/images/close_frame",
                    "val/images/different_scene",
                ],
                "splits": ["train", "val"],
            }
        ]

        classified = analyzer._classify_near_duplicate_groups(groups, root)

        assert len(classified) == 1
        verdicts = {member["image"]: member["verdict"] for member in classified[0]["member_classifications"]}
        assert verdicts["train/images/identical_twin"] == "identical_labels"
        assert verdicts["train/images/close_frame"] == "similar_labels"
        assert verdicts["val/images/different_scene"] == "dissimilar_labels"


class TestCrossSplitHighConfidenceCandidates:
    def test_dissimilar_cross_split_member_does_not_count_as_cross_split(self) -> None:
        # Regression test for the exact scenario flagged in review: a
        # group's raw hash cluster spans train+val, and it does contain a
        # high-confidence (similar_labels) match -- but that match is
        # entirely within train. The val member is the one the label check
        # rejected as dissimilar_labels. This must NOT be counted as a
        # cross-split high-confidence candidate.
        group = {
            "anchor": "train/images/anchor",
            "member_classifications": [
                {"image": "train/images/same_split_match", "verdict": "similar_labels"},
                {"image": "val/images/different_scene", "verdict": "dissimilar_labels"},
            ],
        }

        candidates = analyzer._cross_split_high_confidence_candidates([group])

        assert candidates == []

    def test_genuine_cross_split_match_is_recorded_with_qualifying_members(self) -> None:
        group = {
            "anchor": "train/images/anchor",
            "member_classifications": [
                {"image": "train/images/same_split_match", "verdict": "similar_labels"},
                {"image": "val/images/real_leak", "verdict": "identical_labels"},
                {"image": "val/images/unrelated", "verdict": "dissimilar_labels"},
            ],
        }

        candidates = analyzer._cross_split_high_confidence_candidates([group])

        assert len(candidates) == 1
        qualifying_images = {member["image"] for member in candidates[0]["qualifying_members"]}
        # Only the genuinely cross-split, high-confidence member qualifies
        # -- not the same-split match, and not the dissimilar one.
        assert qualifying_images == {"val/images/real_leak"}

    def test_no_high_confidence_groups_at_all_returns_empty(self) -> None:
        assert analyzer._cross_split_high_confidence_candidates([]) == []


@pytest.mark.skipif(not PIL_AVAILABLE, reason="Pillow is required for image-based analyze() tests")
class TestAnalyzeEndToEnd:
    def _build_dataset(self, tmp_path: Path, *, include_pole_images: bool = True) -> tuple[Path, Path]:
        root = tmp_path / "dataset"
        yaml_path = write_yaml(root, ["person", "stairs", "door", "chair", "table", "pole", "bicycle", "vehicle"])
        write_label(root, "train", "pole_a", ["5 0.500000 0.500000 0.050000 0.900000"])
        write_label(root, "train", "pole_b", ["5 0.510000 0.490000 0.052000 0.895000"])
        write_label(root, "val", "pole_c", ["5 0.500000 0.500000 0.050000 0.900000"])
        write_label(root, "train", "person_only", ["0 0.500000 0.500000 0.400000 0.400000"])
        write_label(root, "val", "empty", [])

        if include_pole_images:
            # Images live directly under dataset_root's own train/images and
            # val/images -- there is no separate pre-filtered directory.
            write_image(root, "train", "pole_a", image_bytes=_gradient_image())
            write_image(root, "train", "pole_b", image_bytes=_gradient_image(shift=2))
            write_image(root, "val", "pole_c", image_bytes=_checkerboard_image())
            # person_only has no pole label, so its image is deliberately
            # never written -- it must not be required or looked up.
        return root, yaml_path

    def test_report_structure_and_pole_geometry(self, tmp_path: Path) -> None:
        root, yaml_path = self._build_dataset(tmp_path)

        report = analyzer.analyze(
            root, yaml_path, near_duplicate_hash_distance=10, execution_time_utc="2026-09-19T00:00:00Z"
        )

        assert report["class_distribution"]["overall"]["pole"] == 3
        assert report["class_distribution"]["overall"]["person"] == 1
        assert report["pole_geometry"]["annotation_count"] == 3
        # width 0.05-0.052, height ~0.9 -> aspect ratio ~17, well above the 3.0 default
        assert report["pole_geometry"]["extreme_aspect_ratio_count"] == 3
        assert report["settings"]["pole_images_scanned_for_duplicates"] == 3
        assert report["pole_images_not_found_locally"]["count"] == 0

    def test_reports_pole_images_not_found_locally(self, tmp_path: Path) -> None:
        root, yaml_path = self._build_dataset(tmp_path, include_pole_images=False)

        report = analyzer.analyze(root, yaml_path, near_duplicate_hash_distance=10)

        assert report["settings"]["pole_images_scanned_for_duplicates"] == 0
        not_found = report["pole_images_not_found_locally"]
        assert not_found["count"] == 3
        assert set(not_found["images"]) == {
            "train/images/pole_a",
            "train/images/pole_b",
            "val/images/pole_c",
        }

    def test_high_confidence_unique_image_count_counts_images_not_comparisons(self, tmp_path: Path) -> None:
        root, yaml_path = self._build_dataset(tmp_path)

        report = analyzer.analyze(root, yaml_path, near_duplicate_hash_distance=10)

        # pole_a (anchor) and pole_b (near-identical label coords) form one
        # high-confidence group -> 2 unique images, not a raw member count.
        unique = report["pole_near_duplicate_label_verification"]["high_confidence_unique_image_count"]
        assert unique["count"] == 2
        assert set(unique["images"]) >= {"train/images/pole_a.png", "train/images/pole_b.png"}

    def test_raises_when_pole_not_in_taxonomy(self, tmp_path: Path) -> None:
        root = tmp_path / "dataset"
        yaml_path = write_yaml(root, ["person", "chair"])
        write_label(root, "train", "a", ["0 0.5 0.5 0.1 0.1"])
        write_label(root, "val", "b", [])

        with pytest.raises(inspector.CandidateInspectionError, match="pole"):
            analyzer.analyze(root, yaml_path)

    def test_markdown_report_renders_without_error(self, tmp_path: Path) -> None:
        root, yaml_path = self._build_dataset(tmp_path)
        report = analyzer.analyze(root, yaml_path, near_duplicate_hash_distance=10)

        markdown = analyzer.render_markdown_report(report)

        assert "# Pole training-data quality investigation" in markdown
        assert "Total pole annotations: 3" in markdown
        assert "Manually verified examples" in markdown
        # The automated heuristic groups must be called candidates, not
        # asserted as confirmed duplicates -- "confirmed" is still fine
        # when describing the specific manually-inspected examples below.
        assert "confirmed cross-split" not in markdown.lower()
        assert "high-confidence" in markdown.lower()

    def test_cli_writes_json_and_markdown(self, tmp_path: Path) -> None:
        root, yaml_path = self._build_dataset(tmp_path)
        output_dir = tmp_path / "output"

        exit_code = analyzer.main(
            [
                "--dataset-root",
                str(root),
                "--dataset-yaml",
                str(yaml_path),
                "--output-dir",
                str(output_dir),
            ]
        )

        assert exit_code == 0
        json_path = output_dir / "pole_data_quality_report.json"
        markdown_path = output_dir / "pole_data_quality_report.md"
        assert json_path.exists()
        assert markdown_path.exists()
        report = json.loads(json_path.read_text(encoding="utf-8"))
        assert report["tool"]["name"] == "analyze_pole_class_quality"
