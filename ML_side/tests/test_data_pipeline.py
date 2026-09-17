from __future__ import annotations

import json
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from ML_side.data_pipeline.annotations import PixelBox, transform_orientation
from ML_side.data_pipeline.config import load_config
from ML_side.data_pipeline.collection import collect_source
from ML_side.data_pipeline.pipeline import execute
from ML_side.data_pipeline.pipeline import database_path
from ML_side.data_pipeline.database import PipelineDatabase
from ML_side.data_pipeline.intake import initialise_run, run_id_for
from ML_side.data_pipeline.layout import initialise_storage_layout
from ML_side.data_pipeline.models import PipelineError
from ML_side.data_pipeline.release import verify_release
from ML_side.data_pipeline.reviews import import_review_csv


class DataPipelineTests(unittest.TestCase):
    def test_raw_video_csv_is_extracted_grouped_and_released_as_yolo_frames(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_value:
            root = Path(temporary_value)
            raw = root / "raw" / "video_source"
            raw.mkdir(parents=True)
            video_path = raw / "walk.avi"
            original_video = b"synthetic-video-evidence"
            video_path.write_bytes(original_video)
            (raw / "walk.csv").write_text(
                "frame,class_id,x,y,w,h\n"
                "0,0,8,8,24,24\n"
                "0,0,32,16,16,24\n"
                "1,0,10,10,20,20\n"
                "2,0,12,12,18,18\n",
                encoding="utf-8",
            )
            frames = []
            for index in range(3):
                image = Image.new("RGB", (64, 64))
                pixels = image.load()
                for y in range(64):
                    for x in range(64):
                        value = (x * 29 + y * 43 + x * y * (index + 1) + index * 17) % 256
                        pixels[x, y] = (value, (value * 3 + index) % 256, (value * 5 + x) % 256)
                frames.append((index, image))
            config_value = {
                "project_root": str(root), "raw_root": str(root / "raw"),
                "workspace_root": str(root / "workspace"), "invalid_root": str(root / "invalid"),
                "output_root": str(root), "release_id": "video-v1", "taxonomy": ["person"],
                "qa_sample_per_source": 0, "near_duplicates_enabled": False,
                "sources": [{
                    "id": "video_source", "folder": "video_source", "provider": "local",
                    "licence": "test-only", "governance_status": "approved",
                    "annotation_format": "yolo", "class_names": ["pedestrian"],
                    "class_mapping": {"0": "person"}, "grouping": "none",
                    "video_extraction": {
                        "enabled": True, "annotation_pattern": "{stem}.csv",
                        "coordinate_format": "xywh_pixels", "frame_column": "frame",
                        "class_column": "class_id", "default_class_id": None,
                    },
                }],
            }
            config_path = root / "pipeline.json"
            config_path.write_text(json.dumps(config_value), encoding="utf-8")
            with patch("ML_side.data_pipeline.video_extraction._iter_video_frames", return_value=iter(frames)):
                result = execute(config_path)
            self.assertEqual(result.status.value, "pass", result.message)
            self.assertEqual(video_path.read_bytes(), original_video)
            release = root / "dataset_video-v1"
            manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["samples"]), 3)
            self.assertEqual(len({sample["group_id"] for sample in manifest["samples"]}), 1)
            self.assertTrue(all(":video:walk.avi" in sample["group_id"] for sample in manifest["samples"]))
            video_transforms = [
                transform
                for sample in manifest["samples"]
                for transform in sample["transformations"]
                if transform["stage"] == "video_extraction"
            ]
            self.assertEqual(len(video_transforms), 3)
            self.assertEqual({item["parameters"]["frame_index"] for item in video_transforms}, {0, 1, 2})
            released_labels = [
                (release / sample["label"]).read_text(encoding="utf-8").splitlines()
                for sample in manifest["samples"]
            ]
            self.assertTrue(all(len(row.split()) == 5 for rows in released_labels for row in rows))
            self.assertIn(2, {len(rows) for rows in released_labels})

    def test_exif_orientation_six_rotates_box_into_final_geometry(self) -> None:
        box = PixelBox(0, 10, 20, 30, 60)
        transformed = transform_orientation(box, width=100, height=80, orientation=6)
        self.assertEqual(transformed, PixelBox(0, 20, 10, 60, 30))

    def test_end_to_end_release_is_reproducible_and_rejects_unexpected_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_value:
            root = Path(temporary_value)
            raw = root / "datasets" / "raw" / "synthetic"
            images = raw / "images"
            labels = raw / "labels"
            images.mkdir(parents=True)
            labels.mkdir(parents=True)
            taxonomy = ["person", "stairs", "door", "chair", "table", "pole", "bicycle", "vehicle"]
            for index in range(80):
                class_id = index % len(taxonomy)
                image_path = images / f"session_{index:03d}_frame.jpg"
                image = Image.new("RGB", (64, 64))
                pixels = image.load()
                for y in range(64):
                    for x in range(64):
                        value = (x * 31 + y * 17 + index * 13 + (x * y * (index + 1))) % 256
                        pixels[x, y] = (value, (value * 3 + index) % 256, (value * 7 + x) % 256)
                image.save(image_path, quality=96)
                (labels / f"session_{index:03d}_frame.txt").write_text(
                    f"{class_id} 0.5 0.5 0.5 0.5\n", encoding="utf-8"
                )
            (images / "session_999_duplicate.jpg").write_bytes((images / "session_000_frame.jpg").read_bytes())
            (labels / "session_999_duplicate.txt").write_text("0 0.5 0.5 0.5 0.5\n", encoding="utf-8")
            config_value = {
                "project_root": str(root),
                "raw_root": str(root / "datasets" / "raw"),
                "workspace_root": str(root / "datasets" / "pipeline_workspace"),
                "invalid_root": str(root / "datasets" / "invalid"),
                "output_root": str(root / "datasets"),
                "release_id": "test-v1",
                "taxonomy_version": "1.0.0",
                "taxonomy": taxonomy,
                "seed": 42,
                "near_duplicates_enabled": False,
                "qa_sample_per_source": 0,
                "sources": [
                    {
                        "id": "synthetic",
                        "folder": "synthetic",
                        "provider": "local",
                        "licence": "test-only",
                        "governance_status": "approved",
                        "annotation_format": "yolo",
                        "class_names": taxonomy,
                        "class_mapping": {str(index): name for index, name in enumerate(taxonomy)},
                        "environment_tags": ["synthetic", "indoor"],
                        "grouping": "filename-regex",
                        "group_pattern": r"session_(\d+)_",
                    }
                ],
            }
            config_path = root / "pipeline.json"
            config_path.write_text(json.dumps(config_value), encoding="utf-8")

            result = execute(config_path)
            self.assertEqual(result.status.value, "pass", result.message)
            release = root / "datasets" / "dataset_test-v1"
            valid, issues = verify_release(release)
            self.assertTrue(valid, issues)
            resumed = execute(config_path)
            self.assertEqual(resumed.status.value, "pass", resumed.message)
            manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["samples"]), 80)
            dataset_yaml = (release / "data.yaml").read_text(encoding="utf-8")
            self.assertIn("nc: 8", dataset_yaml)
            self.assertEqual(manifest["dataset_yaml"]["mode"], "generate")
            group_splits: dict[str, set[str]] = {}
            for sample in manifest["samples"]:
                group_splits.setdefault(sample["group_id"], set()).add(sample["split"])
            self.assertTrue(all(len(splits) == 1 for splits in group_splits.values()))
            report = json.loads((release / "reports" / "qa_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["integrity_verification"]["status"], "pass")
            self.assertTrue(any(item["kind"] == "exact" for item in report["duplicates"]))
            (release / "images" / "train" / "unexpected.jpg").write_bytes(b"not approved")
            valid, issues = verify_release(release)
            self.assertFalse(valid)
            self.assertTrue(any("Unexpected file" in issue for issue in issues))

    def test_augmentation_adds_only_the_deficit_class_and_only_to_train(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_value:
            root = Path(temporary_value)
            raw = root / "raw" / "imbalanced"
            images = raw / "images"
            labels = raw / "labels"
            images.mkdir(parents=True)
            labels.mkdir(parents=True)
            for index in range(30):
                class_id = 0 if index < 25 else 1
                image = Image.new("RGB", (64, 64))
                pixels = image.load()
                for y in range(64):
                    for x in range(64):
                        value = (x * 19 + y * 23 + index * 29 + x * y) % 256
                        pixels[x, y] = (value, (value + index * 7) % 256, (value * 5 + y) % 256)
                image.save(images / f"group_{index:03d}_frame.jpg", quality=95)
                (labels / f"group_{index:03d}_frame.txt").write_text(
                    f"{class_id} 0.5 0.5 0.3 0.3\n", encoding="utf-8"
                )
            config = {
                "project_root": str(root), "raw_root": str(root / "raw"),
                "workspace_root": str(root / "workspace"), "invalid_root": str(root / "invalid"),
                "output_root": str(root), "release_id": "imbalanced-v1", "taxonomy": ["common", "rare"],
                "taxonomy_version": "test", "seed": 7, "qa_sample_per_source": 0,
                "near_duplicates_enabled": False, "imbalance_ratio": 4,
                "sources": [{
                    "id": "imbalanced", "folder": "imbalanced", "licence": "test-only", "governance_status": "approved",
                    "annotation_format": "yolo", "class_names": ["common", "rare"],
                    "class_mapping": {"0": "common", "1": "rare"},
                    "grouping": "filename-regex", "group_pattern": r"group_(\d+)_",
                }],
            }
            config_path = root / "pipeline.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            result = execute(config_path)
            self.assertEqual(result.status.value, "pass", result.message)
            release = root / "dataset_imbalanced-v1"
            manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
            augmented = [sample for sample in manifest["samples"] if sample["is_augmented"]]
            self.assertTrue(augmented)
            self.assertTrue(all(sample["split"] == "train" for sample in augmented))
            for sample in augmented:
                label_rows = (release / sample["label"]).read_text(encoding="utf-8").splitlines()
                self.assertTrue(label_rows)
                self.assertTrue(all(row.split()[0] == "1" for row in label_rows))

    def test_near_duplicate_review_pauses_then_resumes_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_value:
            root = Path(temporary_value)
            image_dir = root / "raw" / "source" / "images"
            label_dir = root / "raw" / "source" / "labels"
            image_dir.mkdir(parents=True)
            label_dir.mkdir(parents=True)
            base = Image.new("RGB", (64, 64))
            pixels = base.load()
            for y in range(64):
                for x in range(64):
                    value = (x * 37 + y * 41 + x * y) % 256
                    pixels[x, y] = (value, (value * 3) % 256, (value * 5) % 256)
            base.save(image_dir / "session_a.png")
            changed = base.copy()
            changed.putpixel((10, 10), (255, 0, 255))
            changed.save(image_dir / "session_b.png")
            for name in ("session_a", "session_b"):
                (label_dir / f"{name}.txt").write_text("0 0.5 0.5 0.4 0.4\n", encoding="utf-8")
            config_value = {
                "project_root": str(root), "raw_root": str(root / "raw"),
                "workspace_root": str(root / "workspace"), "invalid_root": str(root / "invalid"),
                "output_root": str(root), "release_id": "review-v1", "taxonomy": ["object"],
                "qa_sample_per_source": 0, "near_duplicate_distance": 2, "near_duplicate_review_distance": 8,
                "sources": [{
                    "id": "source", "folder": "source", "licence": "test-only", "governance_status": "approved", "annotation_format": "yolo",
                    "class_names": ["object"], "class_mapping": {"0": "object"}, "grouping": "dataset",
                }],
            }
            config_path = root / "pipeline.json"
            config_path.write_text(json.dumps(config_value), encoding="utf-8")
            first = execute(config_path)
            self.assertEqual(first.status.value, "review_required")
            config = load_config(config_path)
            run_id = run_id_for(config, config_path)
            with PipelineDatabase(database_path(config, run_id)) as db:
                cluster = db.rows(
                    "SELECT cluster_id, asset_id FROM duplicate_candidates WHERE run_id=? AND kind='near' AND decision='pending_review'",
                    (run_id,),
                )[0]
                review_csv = root / "review.csv"
                with review_csv.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=["review_type", "asset_id", "external_task_id", "decision", "notes"])
                    writer.writeheader()
                    writer.writerow({
                        "review_type": "near_duplicate", "asset_id": cluster["asset_id"],
                        "external_task_id": cluster["cluster_id"], "decision": "duplicate", "notes": "Confirmed visually.",
                    })
                import_review_csv(db, run_id, config, review_csv, "Unit Test Reviewer")
            resumed = execute(config_path)
            self.assertEqual(resumed.status.value, "pass", resumed.message)

    def test_dataset_yaml_can_be_omitted_for_a_custom_taxonomy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_value:
            root = Path(temporary_value)
            images = root / "raw" / "source" / "images"
            labels = root / "raw" / "source" / "labels"
            images.mkdir(parents=True)
            labels.mkdir(parents=True)
            image = Image.new("RGB", (64, 64))
            pixels = image.load()
            for y in range(64):
                for x in range(64):
                    value = (x * 31 + y * 17 + x * y * 11) % 256
                    pixels[x, y] = (value, (value * 3 + x) % 256, (value * 7 + y) % 256)
            image.save(images / "sample.jpg", quality=95)
            (labels / "sample.txt").write_text("0 0.5 0.5 0.4 0.4\n", encoding="utf-8")
            config_value = {
                "project_root": str(root), "raw_root": str(root / "raw"),
                "workspace_root": str(root / "workspace"), "invalid_root": str(root / "invalid"),
                "output_root": str(root), "release_id": "no-yaml-v1",
                "taxonomy": ["custom obstacle"], "dataset_yaml": {"mode": "none"},
                "qa_sample_per_source": 0, "near_duplicates_enabled": False,
                "sources": [{
                    "id": "source", "folder": "source", "licence": "test-only",
                    "governance_status": "approved", "annotation_format": "yolo",
                    "class_names": ["source object"], "class_mapping": {"0": "custom obstacle"},
                    "grouping": "dataset",
                }],
            }
            config_path = root / "pipeline.json"
            config_path.write_text(json.dumps(config_value), encoding="utf-8")
            result = execute(config_path)
            self.assertEqual(result.status.value, "pass", result.message)
            release = root / "dataset_no-yaml-v1"
            self.assertFalse((release / "data.yaml").exists())
            manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["dataset_yaml"]["mode"], "none")
            self.assertEqual(manifest["dataset_yaml"]["class_count"], 1)

    def test_download_sheet_is_authoritative_and_changes_run_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_value:
            root = Path(temporary_value)
            config_dir = root / "config" / "dataset_v3"
            config_dir.mkdir(parents=True)
            sheet_path = root / "config" / "download_sheet.json"
            sheet = {
                "datasets": {
                    "camera_source": {
                        "source": "manual", "url": "https://example.test/dataset", "version": 3,
                        "status": "approved", "folder": "camera_source",
                        "ethics": {"license": "test-only"},
                    }
                }
            }
            sheet_path.write_text(json.dumps(sheet), encoding="utf-8")
            config_value = {
                "project_root": str(root), "raw_root": str(root / "raw"),
                "workspace_root": str(root / "workspace"), "invalid_root": str(root / "invalid"),
                "output_root": str(root), "release_id": "registry-v1", "taxonomy": ["object"],
                "download_sheet": "../download_sheet.json",
                "sources": [{
                    "id": "camera_source", "annotation_format": "yolo",
                    "class_names": ["thing"], "class_mapping": {"0": "object"},
                }],
            }
            config_path = config_dir / "pipeline.json"
            config_path.write_text(json.dumps(config_value), encoding="utf-8")
            config = load_config(config_path)
            source = config.sources[0]
            self.assertEqual(source.provider, "manual")
            self.assertEqual(source.url, "https://example.test/dataset")
            self.assertEqual(source.version, 3)
            self.assertEqual(source.licence, "test-only")
            self.assertEqual(source.governance_status, "approved")
            self.assertEqual(source.folder, (root / "raw" / "manual" / "camera_source").resolve())
            first_run_id = run_id_for(config, config_path)
            layout = initialise_storage_layout(config, first_run_id)
            self.assertEqual(layout.status.value, "pass")
            self.assertTrue(source.folder.is_dir())
            self.assertTrue((root / "raw" / "manual").is_dir())
            self.assertTrue((root / "workspace" / first_run_id / "standardized" / "camera_source").is_dir())
            self.assertTrue((root / "workspace" / first_run_id / "labels" / "camera_source").is_dir())
            self.assertTrue((root / "workspace" / first_run_id / "review" / "semantic" / "camera_source").is_dir())
            self.assertTrue((root / "invalid" / first_run_id).is_dir())

            def fake_download(_source: object, destination: Path) -> None:
                destination.mkdir(parents=True)
                (destination / "downloaded.marker").write_text("complete", encoding="utf-8")

            with PipelineDatabase(root / "layout-test.sqlite3") as db:
                initialise_run(db, first_run_id, config, config_path)
                with patch("ML_side.data_pipeline.collection._download_source", side_effect=fake_download):
                    collection = collect_source(db, first_run_id, source)
            self.assertEqual(collection.status.value, "pass")
            self.assertEqual((source.folder / "downloaded.marker").read_text(encoding="utf-8"), "complete")

            sheet["datasets"]["camera_source"]["version"] = 4
            sheet_path.write_text(json.dumps(sheet), encoding="utf-8")
            changed_config = load_config(config_path)
            self.assertNotEqual(first_run_id, run_id_for(changed_config, config_path))

            config_value["sources"][0]["url"] = "https://override.test/not-allowed"
            config_path.write_text(json.dumps(config_value), encoding="utf-8")
            with self.assertRaisesRegex(PipelineError, "must come from download_sheet"):
                load_config(config_path)


if __name__ == "__main__":
    unittest.main()
