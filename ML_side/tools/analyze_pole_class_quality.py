"""Pole-class training-data quality investigation for a local YOLO candidate dataset.

This is a focused companion to ``inspect_candidate_dataset.py``, built for one
specific job: investigating the weak "pole" class using only train/validation
data, as required by the pole training-data quality task. It deliberately
does not run the full candidate-release inspection pipeline (which expects a
complete image set and reviewed metadata) — instead it:

1. Computes annotation-level statistics (class distribution, bounding-box
   geometry buckets) directly from every YOLO label file across train and
   validation, for all classes. This needs no image files at all, since a
   YOLO label line already carries normalized width/height.
2. Finds every pole-containing label, then hashes *only* the matching
   image files directly under ``dataset_root``'s ``train/images``/
   ``val/images`` -- reusing ``inspect_candidate_dataset``'s exact
   checksum/perceptual-hash/grouping logic, applied to a class-scoped image
   subset exactly as that module's own near-duplicate helper recommends for
   a full-corpus dataset. This needs only ``--dataset-root`` to point at a
   normal full dataset export; it never requires a separately pre-filtered
   "pole-only" image directory. If only a partial local extraction is
   available (e.g. under a disk-space constraint), any pole-labeled image
   that cannot be found is reported under
   ``pole_images_not_found_locally`` rather than silently skipped.

Held-out test data must never be passed to this tool: it only accepts
train/validation split directories, and does not know how to address a test
split at all.

Read-only: this tool never writes into the dataset root, never modifies
labels or images, and never downloads anything.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

import inspect_candidate_dataset as inspector  # noqa: E402

TOOL_NAME = "analyze_pole_class_quality"
TOOL_VERSION = "1.0.0"
SPLITS: tuple[str, ...] = ("train", "val")
APPROVED_TAXONOMY = inspector.APPROVED_TAXONOMY
POLE_CLASS_NAME = "pole"


def _taxonomy_by_id(names: Sequence[str]) -> dict[int, str]:
    return {index: name for index, name in enumerate(names)}


def _load_names_from_yaml(dataset_yaml_path: Path) -> list[str]:
    dataset_yaml = inspector._load_structured_file(dataset_yaml_path, "Dataset YAML")
    names = dataset_yaml.get("names")
    if isinstance(names, list):
        return [str(name) for name in names]
    if isinstance(names, dict):
        return [str(names[key]) for key in sorted(names, key=int)]
    raise inspector.CandidateInspectionError(f"$.names is required and must be a list or mapping: {dataset_yaml_path}")


def _iter_label_lines(label_path: Path) -> list[tuple[int, float, float]]:
    """Return (class_id, width, height) for every syntactically valid annotation row."""
    rows: list[tuple[int, float, float]] = []
    try:
        text = label_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return rows
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 5:
            continue
        raw_class_id, x_center, y_center, width, height = fields
        if re.fullmatch(r"[0-9]+", raw_class_id) is None:
            continue
        try:
            class_id = int(raw_class_id)
            width_f = float(width)
            height_f = float(height)
        except ValueError:
            continue
        if width_f <= 0 or height_f <= 0:
            continue
        rows.append((class_id, width_f, height_f))
    return rows


def _build_geometry_records(
    dataset_root: Path, taxonomy: dict[int, str]
) -> tuple[list[dict[str, object]], dict[str, Counter]]:
    """Build ``_class_geometry_buckets``-compatible records from every label file.

    Also returns per-split annotation-count Counters (by class name) as a
    cheap byproduct, since we're already walking every label file once.
    """
    records: list[dict[str, object]] = []
    per_split_counts: dict[str, Counter] = {split: Counter() for split in SPLITS}
    for split in SPLITS:
        label_dir = dataset_root / split / "labels"
        if not label_dir.is_dir():
            raise inspector.CandidateInspectionError(f"Expected label directory missing: {label_dir}")
        for label_path in sorted(label_dir.glob("*.txt")):
            annotations = []
            for class_id, width, height in _iter_label_lines(label_path):
                class_name = taxonomy.get(class_id)
                if class_name is None:
                    continue
                per_split_counts[split][class_name] += 1
                annotations.append(
                    {
                        "excluded": False,
                        "target_class_name": class_name,
                        "width": width,
                        "height": height,
                    }
                )
            if annotations:
                image_path = f"{split}/images/{label_path.stem}"
                records.append({"image_path": image_path, "annotations": annotations})
    return records, per_split_counts


def _find_pole_label_stems(dataset_root: Path, taxonomy: dict[int, str]) -> dict[str, list[str]]:
    """Return {split: [label stems]} for every label file with a pole annotation."""
    pole_class_ids = {class_id for class_id, name in taxonomy.items() if name == POLE_CLASS_NAME}
    stems_by_split: dict[str, list[str]] = {split: [] for split in SPLITS}
    for split in SPLITS:
        label_dir = dataset_root / split / "labels"
        if not label_dir.is_dir():
            raise inspector.CandidateInspectionError(f"Expected label directory missing: {label_dir}")
        for label_path in sorted(label_dir.glob("*.txt")):
            for class_id, _width, _height in _iter_label_lines(label_path):
                if class_id in pole_class_ids:
                    stems_by_split[split].append(label_path.stem)
                    break
    return stems_by_split


def _build_pole_image_records(
    dataset_root: Path, pole_stems_by_split: dict[str, list[str]], *, hash_size: int = 8
) -> tuple[list[dict[str, object]], list[str]]:
    """Hash exactly the images that have a pole label, read directly from dataset_root.

    Every pole-containing stem is looked up as ``dataset_root/{split}/images/{stem}{ext}``
    for each supported image extension -- no separate pre-filtered "pole-only"
    image directory is needed, so this works unchanged whether the caller has
    a full dataset export or only extracted the pole-relevant images locally.
    Returns (records, missing) where ``missing`` lists
    ``"{split}/images/{stem}"`` for every pole-labeled stem whose image file
    could not be found under any supported extension, so a partial local
    extraction is reported rather than silently under-counted.
    """
    records: list[dict[str, object]] = []
    missing: list[str] = []
    for split in SPLITS:
        image_dir = dataset_root / split / "images"
        for stem in pole_stems_by_split[split]:
            image_path = next(
                (
                    candidate
                    for ext in sorted(inspector.IMAGE_EXTENSIONS)
                    if (candidate := image_dir / f"{stem}{ext}").is_file()
                ),
                None,
            )
            if image_path is None:
                missing.append(f"{split}/images/{stem}")
                continue
            checksum = inspector._sha256(image_path)
            try:
                perceptual_hash: int | None = inspector._perceptual_hash(image_path, hash_size=hash_size)
            except inspector.CandidateInspectionError:
                perceptual_hash = None
            records.append(
                {
                    "split": split,
                    "image_path": f"{split}/images/{image_path.name}",
                    "source_sample_identifier": image_path.stem.casefold(),
                    "checksum": checksum,
                    "perceptual_hash": perceptual_hash,
                }
            )
    return records, sorted(missing)


def _label_signature(label_path: Path, *, precision: int = 4) -> frozenset[tuple[int, float, float, float, float]]:
    signature = set()
    for class_id, x_center, y_center, width, height in _iter_full_label_rows(label_path):
        signature.add((class_id, round(x_center, precision), round(y_center, precision), round(width, precision), round(height, precision)))
    return frozenset(signature)


def _iter_full_label_rows(label_path: Path) -> list[tuple[int, float, float, float, float]]:
    rows: list[tuple[int, float, float, float, float]] = []
    try:
        text = label_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return rows
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 5:
            continue
        raw_class_id, x, y, w, h = fields
        if re.fullmatch(r"[0-9]+", raw_class_id) is None:
            continue
        try:
            rows.append((int(raw_class_id), float(x), float(y), float(w), float(h)))
        except ValueError:
            continue
    return rows


def _boxes_match_within_tolerance(
    signature_a: frozenset[tuple[int, float, float, float, float]],
    signature_b: frozenset[tuple[int, float, float, float, float]],
    *,
    tolerance: float = 0.03,
) -> bool:
    """Greedy nearest-neighbor match: every box in A must have a same-class box in B within tolerance, and vice versa."""
    if len(signature_a) != len(signature_b):
        return False
    remaining = list(signature_b)
    for class_id, x, y, w, h in signature_a:
        best_index = None
        best_distance = None
        for index, (other_class, ox, oy, ow, oh) in enumerate(remaining):
            if other_class != class_id:
                continue
            distance = max(abs(x - ox), abs(y - oy), abs(w - ow), abs(h - oh))
            if distance <= tolerance and (best_distance is None or distance < best_distance):
                best_distance = distance
                best_index = index
        if best_index is None:
            return False
        remaining.pop(best_index)
    return True


def _classify_near_duplicate_groups(
    groups: list[dict[str, object]], dataset_root: Path
) -> list[dict[str, object]]:
    """Re-check each hash-based near-duplicate group against its labels.

    Perceptual hashing is coarse and false-positives on this class in
    particular (most pole photos share the same composition: a dark
    vertical shape against open sky). Label-coordinate agreement is a much
    stronger duplicate signal, so every group is re-classified using it:
    ``identical_labels`` (near-certain same photo, re-encoded or re-hosted),
    ``similar_labels`` (boxes close but not identical -- plausible
    consecutive-capture frames), or ``dissimilar_labels`` (best explained as
    a perceptual-hash false positive; the images are of different scenes).
    Classification compares every other group member against the group's
    first (anchor) image, mirroring how ``_near_duplicate_groups`` actually
    forms clusters around one anchor rather than requiring every pair in a
    group to be mutually close.
    """
    classified = []
    for group in groups:
        images = group["images"]  # type: ignore[index]
        anchor = images[0]
        anchor_label = dataset_root / Path(anchor).parent.parent / "labels" / (Path(anchor).stem + ".txt")
        anchor_signature = _label_signature(anchor_label)
        member_classifications = []
        for image in images[1:]:
            label_path = dataset_root / Path(image).parent.parent / "labels" / (Path(image).stem + ".txt")
            signature = _label_signature(label_path)
            if signature == anchor_signature:
                verdict = "identical_labels"
            elif _boxes_match_within_tolerance(anchor_signature, signature):
                verdict = "similar_labels"
            else:
                verdict = "dissimilar_labels"
            member_classifications.append({"image": image, "verdict": verdict})
        classified.append(
            {
                "images": images,
                "splits": group["splits"],
                "anchor": anchor,
                "member_classifications": member_classifications,
            }
        )
    return classified


def _source_dataset_name(image_path: str) -> str:
    """Extract the source-dataset name baked into a WalkBuddy-merged filename.

    Filenames follow ``<source_dataset_name>_wb_<sequence>.<ext>``. This is a
    naming convention already used across the merged dataset, not something
    invented by this tool.
    """
    stem = Path(image_path).stem
    match = re.match(r"(.+)_wb_\d+$", stem)
    return match.group(1) if match else stem


def _generic_source_review_candidates(pole_records: list[dict[str, object]]) -> list[str]:
    """Pole images sourced from a generic (non-pole-specific) dataset name.

    A source name containing "indoor" is a proxy for "not a pole-specific
    outdoor capture dataset" -- visual spot-checking during this
    investigation found some of these are architectural columns/pilasters
    mislabeled as 'pole', not real hazard poles. This flags them all for
    manual review; it does not claim every flagged image is mislabeled.
    """
    return sorted(
        str(record["image_path"])
        for record in pole_records
        if "indoor" in _source_dataset_name(str(record["image_path"])).casefold()
    )


def analyze(
    dataset_root: Path,
    dataset_yaml_path: Path,
    *,
    small_area_threshold: float = 0.01,
    extreme_aspect_ratio_threshold: float = 3.0,
    near_duplicate_hash_distance: int = 5,
    execution_time_utc: str | None = None,
) -> dict[str, object]:
    names = _load_names_from_yaml(dataset_yaml_path)
    taxonomy = _taxonomy_by_id(names)
    if POLE_CLASS_NAME not in taxonomy.values():
        raise inspector.CandidateInspectionError(
            f"'{POLE_CLASS_NAME}' is not present in the dataset YAML's names list: {names!r}"
        )

    geometry_records, per_split_counts = _build_geometry_records(dataset_root, taxonomy)
    geometry_buckets = inspector._class_geometry_buckets(
        geometry_records,
        small_area_threshold=small_area_threshold,
        extreme_aspect_ratio_threshold=extreme_aspect_ratio_threshold,
        max_examples=25,
    )
    pole_geometry = next((bucket for bucket in geometry_buckets if bucket["class_name"] == POLE_CLASS_NAME), None)

    overall_counts = Counter()
    for split_counts in per_split_counts.values():
        overall_counts.update(split_counts)

    pole_stems_by_split = _find_pole_label_stems(dataset_root, taxonomy)
    pole_records, missing_pole_images = _build_pole_image_records(dataset_root, pole_stems_by_split)
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    duplicate_findings = inspector._analysis_findings(
        pole_records,
        group_map=None,
        errors=errors,
        warnings=warnings,
        near_duplicate_hash_distance=near_duplicate_hash_distance,
    )
    classified_near_duplicates = _classify_near_duplicate_groups(
        duplicate_findings["near_duplicate_images"], dataset_root  # type: ignore[arg-type]
    )
    # verdict_counts tallies non-anchor group *members* against their
    # group's anchor -- it is a count of label-coordinate comparisons, not
    # of unique images. See high_confidence_unique_image_count below for an
    # actual image count.
    verdict_counts = Counter(
        member["verdict"] for group in classified_near_duplicates for member in group["member_classifications"]
    )
    high_confidence_groups = [
        group
        for group in classified_near_duplicates
        if any(member["verdict"] in ("identical_labels", "similar_labels") for member in group["member_classifications"])
    ]
    high_confidence_images: set[str] = set()
    for group in high_confidence_groups:
        high_confidence_images.add(str(group["anchor"]))
        high_confidence_images.update(
            member["image"]
            for member in group["member_classifications"]
            if member["verdict"] in ("identical_labels", "similar_labels")
        )
    cross_split_high_confidence = [group for group in high_confidence_groups if len(group["splits"]) > 1]

    report: dict[str, object] = {
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "execution": {
            "time_utc": execution_time_utc
            or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "network_access": False,
            "read_only_dataset_inspection": True,
            "scope": "train and validation splits only; held-out test data was never accessed by this tool.",
        },
        "settings": {
            "small_area_threshold": small_area_threshold,
            "extreme_aspect_ratio_threshold": extreme_aspect_ratio_threshold,
            "near_duplicate_hash_distance": near_duplicate_hash_distance,
            "pole_images_scanned_for_duplicates": len(pole_records),
        },
        "pole_images_not_found_locally": {
            "method": (
                "Every pole-containing label's matching image is looked up directly under "
                "dataset_root/{split}/images/ -- this lists any pole-labeled stem whose image file "
                "could not be found there (e.g. only a partial local extraction was available), so "
                "duplicate-detection coverage gaps are reported rather than silently absorbed into a "
                "smaller-than-expected scanned count."
            ),
            "count": len(missing_pole_images),
            "images": missing_pole_images,
        },
        "class_distribution": {
            "train": dict(sorted(per_split_counts["train"].items())),
            "val": dict(sorted(per_split_counts["val"].items())),
            "overall": dict(sorted(overall_counts.items())),
        },
        "class_geometry_buckets": geometry_buckets,
        "pole_geometry": pole_geometry,
        "pole_duplicate_findings": duplicate_findings,
        "pole_duplicate_analysis_warnings": warnings,
        "pole_near_duplicate_label_verification": {
            "method": (
                "Every hash-flagged near-duplicate group's non-anchor images are compared to the group's "
                "anchor image's YOLO label coordinates, since perceptual hashing alone is known to "
                "false-positive on this class (most pole photos share a generic dark-vertical-shape-on-sky "
                "composition). identical_labels = label coordinates match exactly (rounded to 4 decimal "
                "places); similar_labels = boxes close but not identical (within a 0.03 normalized-coordinate "
                "tolerance); dissimilar_labels = best explained as a perceptual-hash false positive. "
                "IMPORTANT: this is still an automated heuristic (aHash pre-filter + label-coordinate "
                "agreement), not independent human verification of every group -- only the specific examples "
                "listed under manually_verified_examples below were actually visually inspected. "
                "identical_labels/similar_labels are reported as high-confidence duplicate/near-duplicate "
                "*candidates*, not as confirmed duplicates."
            ),
            "verdict_counts_note": (
                "verdict_counts tallies non-anchor group MEMBERS compared against their group's anchor "
                "(i.e. label-coordinate comparisons), not unique images -- an image that is itself a group "
                "anchor is not included in these counts. See high_confidence_unique_image_count for a true "
                "image count."
            ),
            "verdict_counts": dict(verdict_counts),
            "high_confidence_unique_image_count": {
                "method": (
                    "Unique images that are either the anchor of a group with at least one identical_labels "
                    "or similar_labels member, or are themselves such a member -- i.e. every distinct image "
                    "involved in at least one high-confidence duplicate/near-duplicate candidate finding. "
                    "dissimilar_labels-only groups are excluded entirely."
                ),
                "count": len(high_confidence_images),
                "of_pole_images_scanned": len(pole_records),
                "images": sorted(high_confidence_images),
            },
            "groups_with_high_confidence_cross_split_candidate": len(cross_split_high_confidence),
            "high_confidence_cross_split_candidate_groups": [
                {
                    "anchor": group["anchor"],
                    "high_confidence_members": [
                        member["image"]
                        for member in group["member_classifications"]
                        if member["verdict"] in ("identical_labels", "similar_labels")
                    ],
                }
                for group in cross_split_high_confidence
            ],
        },
        "manually_verified_examples": {
            "method": (
                "The following specific images were opened and visually inspected during this "
                "investigation (not just compared by hash or label coordinates), to sanity-check the "
                "automated heuristics above before trusting them at scale."
            ),
            "examples": [
                {
                    "images": [
                        "train/images/kaggle_light_poles_wb_001285.jpg",
                        "train/images/kaggle_light_poles_wb_001336.jpg",
                    ],
                    "finding": (
                        "Visually confirmed as two different real poles in two different locations "
                        "(one with a ladder against an overcast sky, one with palm trees and sun "
                        "flare), despite being flagged as a raw perceptual-hash near-duplicate pair. "
                        "This is the false-positive case that motivated the label-coordinate "
                        "verification layer."
                    ),
                },
                {
                    "images": [
                        "train/images/kaggle_indoor_object_detection_wb_000342.jpg",
                        "val/images/roboflow_indoor_detection_vineeth_wb_019834.jpg",
                    ],
                    "finding": (
                        "Visually confirmed as the same church-doorway photograph, re-published under "
                        "two different source-dataset names, split across train and validation. Label "
                        "coordinates for both class-5 boxes match to within floating-point rounding "
                        "(e.g. 0.386719 vs 0.38671875). Also visually confirmed that both class-5 boxes "
                        "sit on the doorway's decorative stone pilasters, not a physical pole."
                    ),
                },
                {
                    "images": ["train/images/kaggle_indoor_object_detection_wb_000277.jpg"],
                    "finding": (
                        "Visually confirmed: three class-5 boxes sit on the three ornate stone columns "
                        "of an embassy entrance, not physical hazard poles."
                    ),
                },
                {
                    "images": ["train/images/roboflow_indoor_detection_vineeth_wb_018164.jpg"],
                    "finding": (
                        "Visually inspected: the class-5 box sits on a floor lamp's stand in a bedroom "
                        "photo -- a plausible legitimate pole-like object, not clearly mislabeled."
                    ),
                },
                {
                    "images": ["train/images/roboflow_indoor_detection_vineeth_wb_017389.jpg"],
                    "finding": (
                        "Visually inspected: an unusually wide, short class-5 box in a rotated window "
                        "photo -- ambiguous; could plausibly be a horizontal railing/beam rather than a "
                        "pole, but this was not conclusively determined from the image alone."
                    ),
                },
            ],
        },
        "generic_source_review_candidates": {
            "method": (
                "Pole-containing images whose source-dataset name (encoded in the filename as "
                "<source>_wb_<sequence>) contains 'indoor', as a proxy for coming from a generic "
                "object-detection dataset rather than a pole-specific outdoor capture. Visual "
                "spot-checking during this investigation found some of these are architectural "
                "columns/pilasters mislabeled as 'pole'; this list is a manual-review candidate set, "
                "not a claim that every listed image is mislabeled."
            ),
            "count": len(_generic_source_review_candidates(pole_records)),
            "total_pole_images_scanned": len(pole_records),
            "images": _generic_source_review_candidates(pole_records),
        },
    }
    return report


def render_markdown_report(report: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("# Pole training-data quality investigation")
    lines.append("")
    lines.append(f"Generated: `{report['execution']['time_utc']}`")  # type: ignore[index]
    lines.append("")
    lines.append(
        "Scope: train and validation splits only. Held-out test data was never accessed "
        "by this analysis, per the pole-class investigation's acceptance criteria."
    )
    lines.append("")

    lines.append("## Class distribution (train + validation)")
    lines.append("")
    lines.append("| Class | Train | Val | Overall |")
    lines.append("|---|---:|---:|---:|")
    overall = report["class_distribution"]["overall"]  # type: ignore[index]
    train_counts = report["class_distribution"]["train"]  # type: ignore[index]
    val_counts = report["class_distribution"]["val"]  # type: ignore[index]
    for class_name in sorted(overall):
        lines.append(
            f"| {class_name} | {train_counts.get(class_name, 0)} | {val_counts.get(class_name, 0)} | {overall[class_name]} |"
        )
    lines.append("")

    pole_geometry = report.get("pole_geometry")
    lines.append("## Pole class geometry")
    lines.append("")
    if pole_geometry is None:
        lines.append("No pole annotations were found.")
    else:
        settings = report["settings"]  # type: ignore[index]
        lines.append(f"- Total pole annotations: {pole_geometry['annotation_count']}")
        lines.append(
            f"- Small-area (normalized area < {settings['small_area_threshold']}): "
            f"{pole_geometry['small_area_count']} "
            f"({pole_geometry['small_area_count'] / pole_geometry['annotation_count']:.1%})"
        )
        lines.append(
            f"- Extreme aspect ratio (> {settings['extreme_aspect_ratio_threshold']}): "
            f"{pole_geometry['extreme_aspect_ratio_count']} "
            f"({pole_geometry['extreme_aspect_ratio_count'] / pole_geometry['annotation_count']:.1%})"
        )
    lines.append("")

    lines.append("## Pole image duplicate / near-duplicate findings")
    lines.append("")
    findings = report["pole_duplicate_findings"]  # type: ignore[index]
    not_found = report["pole_images_not_found_locally"]  # type: ignore[index]
    lines.append(f"- Pole-containing images scanned: {report['settings']['pole_images_scanned_for_duplicates']}")  # type: ignore[index]
    if not_found["count"]:
        lines.append(
            f"- **{not_found['count']} pole-labeled image(s) could not be found locally and were not "
            f"scanned** (see `pole_images_not_found_locally` in the JSON report for the exact list)."
        )
    lines.append(f"- Exact-duplicate checksum groups: {len(findings['duplicate_checksums'])}")
    lines.append(
        f"- Raw near-duplicate groups (perceptual hash distance <= "
        f"{report['settings']['near_duplicate_hash_distance']}, **before** label-coordinate "  # type: ignore[index]
        f"verification below): {len(findings['near_duplicate_images'])}"
    )
    lines.append("")

    lines.append("### Label-coordinate verification (perceptual hash alone is not trusted as-is)")
    lines.append("")
    lines.append(
        "Perceptual hashing false-positives on this class: most pole photos share the same generic "
        "composition (a dark vertical shape against open sky), so every hash-flagged group was re-checked "
        "against its YOLO label coordinates. This is still an automated heuristic, not independent human "
        "verification of every group — see \"Manually verified examples\" below for the specific images "
        "that were actually opened and inspected. `identical_labels`/`similar_labels` below are reported "
        "as high-confidence duplicate/near-duplicate **candidates**, not as confirmed duplicates."
    )
    lines.append("")
    verification = report["pole_near_duplicate_label_verification"]  # type: ignore[index]
    counts = verification["verdict_counts"]
    lines.append("| Verdict | Count (non-anchor member comparisons) |")
    lines.append("|---|---:|")
    for verdict in ("identical_labels", "similar_labels", "dissimilar_labels"):
        lines.append(f"| {verdict} | {counts.get(verdict, 0)} |")
    lines.append("")
    unique = verification["high_confidence_unique_image_count"]
    lines.append(
        f"- **{unique['count']} unique images** (of {unique['of_pole_images_scanned']} scanned) are "
        f"involved in at least one high-confidence duplicate/near-duplicate candidate finding "
        f"(this counts distinct images, including group anchors — not the "
        f"{counts.get('identical_labels', 0) + counts.get('similar_labels', 0)} member-vs-anchor "
        f"comparisons tallied above)."
    )
    lines.append(
        f"- Groups with at least one high-confidence (identical- or similar-label) candidate match "
        f"spanning both train and validation: {verification['groups_with_high_confidence_cross_split_candidate']}"
    )
    lines.append("")

    lines.append("### Manually verified examples")
    lines.append("")
    lines.append(
        "The automated findings above are a heuristic (perceptual hash + label-coordinate agreement), "
        "not a claim that every listed group was independently checked. The following specific images "
        "were actually opened and visually inspected during this investigation:"
    )
    lines.append("")
    for example in report["manually_verified_examples"]["examples"]:  # type: ignore[index]
        images = ", ".join(f"`{image}`" for image in example["images"])
        lines.append(f"- {images}: {example['finding']}")
    lines.append("")

    lines.append("## Generic-source annotation review candidates")
    lines.append("")
    review = report["generic_source_review_candidates"]  # type: ignore[index]
    lines.append(
        f"- {review['count']} of {review['total_pole_images_scanned']} pole-containing images come from a "
        "source dataset name containing \"indoor\" (a proxy for a generic object-detection source rather "
        "than a pole-specific outdoor capture)."
    )
    lines.append(
        "- Visual spot-checking during this investigation found some of these are architectural "
        "columns/pilasters mislabeled as \"pole\" (e.g. a church doorway and an embassy entrance, each "
        "with 2-3 tall full-height boxes on decorative stone columns), not real hazard poles. This is a "
        "manual-review candidate list, not a claim that every listed image is mislabeled -- one sampled "
        "image showed a plausible legitimate pole-like object (a floor lamp's stand)."
    )
    lines.append("- Full file list is in the accompanying JSON report (`generic_source_review_candidates.images`).")
    lines.append("")

    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-root",
        required=True,
        type=Path,
        help=(
            "Local root containing train/{images,labels}/ and val/{images,labels}/. All label files "
            "are read in full for the class-distribution/geometry analysis. For duplicate detection, "
            "only the specific images with a pole label are opened and hashed, looked up directly "
            "under train/images/ and val/images/ -- a full dataset export works, and so does a local "
            "extraction containing only those pole-relevant images (anything else is reported under "
            "pole_images_not_found_locally rather than silently skipped)."
        ),
    )
    parser.add_argument("--dataset-yaml", required=True, type=Path, help="Local YOLO dataset YAML file (for the class-name taxonomy).")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory to write the JSON report and Markdown summary into.")
    parser.add_argument(
        "--small-area-threshold",
        type=float,
        default=0.01,
        help="Normalized bounding-box area below which an annotation is flagged as small-area (default: 0.01).",
    )
    parser.add_argument(
        "--extreme-aspect-ratio-threshold",
        type=float,
        default=3.0,
        help="max(height/width, width/height) above which an annotation is flagged as extreme-aspect-ratio (default: 3.0).",
    )
    parser.add_argument(
        "--near-duplicate-hash-distance",
        type=int,
        default=5,
        help=(
            "Maximum perceptual-hash (aHash) Hamming distance for two pole images to be grouped as "
            "raw near-duplicate candidates (default: 5). Raw hash groups are noisy on this class -- "
            "see the label-coordinate verification layer in the output, not this raw count alone."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = analyze(
            args.dataset_root,
            args.dataset_yaml,
            small_area_threshold=args.small_area_threshold,
            extreme_aspect_ratio_threshold=args.extreme_aspect_ratio_threshold,
            near_duplicate_hash_distance=args.near_duplicate_hash_distance,
        )
    except inspector.CandidateInspectionError as exc:
        print(f"Pole class quality analysis failed: {exc}", file=sys.stderr)
        return 1
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "pole_data_quality_report.json"
    markdown_path = args.output_dir / "pole_data_quality_report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown_report(report), encoding="utf-8")
    print(f"Wrote {json_path} and {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
