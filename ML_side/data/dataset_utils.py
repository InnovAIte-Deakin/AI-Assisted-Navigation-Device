"""Dataset preparation utilities.

Ported from:
  - ML_side/notebooks/cohort-1/01_data_processing.ipynb
  - ML_side/notebooks/cohort-1/02_object_detection_training.ipynb
  - ML_side/notebooks/cohort-2/04_training_and_depth_estimation.ipynb

The originals were single-use Colab cells wired to hardcoded
`/content/drive/MyDrive/...` paths. This module keeps the same logic but
takes paths as arguments, so it's callable from a script, a notebook, or the
rebuild pipeline instead of copy-pasted per-session.

Nothing here changes any formula or behaviour from the notebooks — this is a
straight extraction, not a redesign. See ML README, Known Gaps
("Cohort 1 not reproducible") for why this needed to happen.
"""

import glob
import os
import random
import shutil
from collections import Counter
from pathlib import Path

import yaml
from PIL import Image, ImageOps

# ---------------------------------------------------------------------------
# HEIC/HEIF conversion
# (from 01_data_processing.ipynb, cells 7-8)
# ---------------------------------------------------------------------------

HEIC_EXTS = {".heic", ".heif"}
IMG_OK_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def heic_to_jpg(src_path, dst_path):
    """Convert a single HEIC/HEIF image to JPG, applying EXIF rotation."""
    try:
        with Image.open(src_path) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.save(dst_path, quality=95)
        return True
    except Exception:
        return False


def convert_heic_directory(src_dir, dst_dir):
    """Convert every HEIC/HEIF image in src_dir to JPG in dst_dir, and copy
    over any already-supported image formats unchanged. Requires
    `pillow-heif` to be installed and its opener registered
    (`from pillow_heif import register_heif_opener; register_heif_opener()`)
    before calling this — that registration was a notebook setup step, not
    part of this function, so call it once at process start.

    Returns a dict of counts: {"converted": n, "copied": n, "failed": n}.
    """
    os.makedirs(dst_dir, exist_ok=True)
    converted = copied = failed = 0

    for p in Path(src_dir).glob("*"):
        if not p.is_file():
            continue
        suffix = p.suffix.lower()

        if suffix in HEIC_EXTS:
            out = Path(dst_dir) / f"{p.stem}.jpg"
            if heic_to_jpg(str(p), str(out)):
                converted += 1
            else:
                failed += 1
        elif suffix in IMG_OK_EXTS:
            shutil.copy2(str(p), str(Path(dst_dir) / p.name))
            copied += 1
        # anything else (videos, etc.) is silently skipped, same as notebook

    return {"converted": converted, "copied": copied, "failed": failed}


# ---------------------------------------------------------------------------
# Train/val/test split
# (from 01_data_processing.ipynb, cells 11-12)
# ---------------------------------------------------------------------------


def get_image_label_pairs(images_dir, labels_dir):
    """Match each image to its YOLO .txt label file by filename stem.
    Prints a warning for any image missing a label (same behaviour as the
    notebook — this was NOT silent there, so keeping it visible on purpose).
    """
    image_extensions = ["*.png", "*.heic", "*.jpg", "*.jpeg"]
    image_files = []
    for ext in image_extensions:
        image_files.extend(glob.glob(os.path.join(images_dir, ext)))

    pairs = []
    for image_path in image_files:
        base_name = Path(image_path).stem
        label_path = os.path.join(labels_dir, f"{base_name}.txt")
        if os.path.exists(label_path):
            pairs.append((image_path, label_path))
        else:
            print(f"Warning: No label file found for {image_path}")

    return pairs


def create_split_directories(output_dir):
    """Create train/val/test x images/labels directory structure."""
    for split in ["train", "val", "test"]:
        for subdir in ["images", "labels"]:
            os.makedirs(os.path.join(output_dir, split, subdir), exist_ok=True)


def split_dataset(pairs, train_ratio=0.7, val_ratio=0.2, test_ratio=0.1, random_seed=42):
    """Shuffle and split (image, label) pairs into train/val/test lists.
    Same ratios and seed as the notebook default (42) for reproducibility —
    change random_seed explicitly if you need a different split.
    """
    random.seed(random_seed)
    shuffled = list(pairs)
    random.shuffle(shuffled)

    total = len(shuffled)
    train_end = int(total * train_ratio)
    val_end = train_end + int(total * val_ratio)

    return shuffled[:train_end], shuffled[train_end:val_end], shuffled[val_end:]


def copy_files(pairs, split_name, output_dir):
    """Copy an (image, label) pair list into output_dir/split_name/{images,labels}."""
    images_dest = os.path.join(output_dir, split_name, "images")
    labels_dest = os.path.join(output_dir, split_name, "labels")

    for image_path, label_path in pairs:
        shutil.copy2(image_path, os.path.join(images_dest, os.path.basename(image_path)))
        shutil.copy2(label_path, os.path.join(labels_dest, os.path.basename(label_path)))


def run_full_split(images_dir, labels_dir, output_dir, train_ratio=0.7, val_ratio=0.2,
                    test_ratio=0.1, random_seed=42):
    """Convenience wrapper matching the notebook's `main()` — pairs images
    with labels, creates the output structure, splits, and copies everything.
    Returns (train_pairs, val_pairs, test_pairs) for logging/verification.
    """
    pairs = get_image_label_pairs(images_dir, labels_dir)
    if not pairs:
        raise ValueError(f"No matching image-label pairs found in {images_dir} / {labels_dir}")

    create_split_directories(output_dir)
    train_pairs, val_pairs, test_pairs = split_dataset(
        pairs, train_ratio, val_ratio, test_ratio, random_seed
    )
    copy_files(train_pairs, "train", output_dir)
    copy_files(val_pairs, "val", output_dir)
    copy_files(test_pairs, "test", output_dir)
    return train_pairs, val_pairs, test_pairs


# ---------------------------------------------------------------------------
# Class counting and remapping
# (from 01/02_*.ipynb "combining book/books" cells, and 04_*.ipynb Roboflow remap)
# ---------------------------------------------------------------------------


def count_classes_in_dir(labels_dir):
    """Count YOLO class-ID occurrences across all .txt files in labels_dir."""
    counts = Counter()
    for p in Path(labels_dir).glob("*.txt"):
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    cls = int(float(line.split()[0]))
                    counts[cls] += 1
                except (ValueError, IndexError):
                    pass
    return counts


def remap_class_ids(labels_dir, id_map, make_backup=True):
    """Remap YOLO class IDs across every .txt label file in labels_dir
    according to id_map (old_id -> new_id). Generalized from two near-duplicate
    notebook cells: the book/books merge in 01/02 (a single old->new pair) and
    the Roboflow 4-class import remap in 04 (a full id_map dict) were the same
    operation done two different ways — this is the one function both should
    have called.

    If make_backup, each modified .txt gets a sibling .txt.bak before rewrite
    (only created once, never overwritten, matching notebook behaviour).

    Returns (changed_count, unknown_count) — unknown_count is how many box
    lines had a class ID not present in id_map (left unchanged, not dropped).
    """
    changed = 0
    unknown = 0

    for txt_path in Path(labels_dir).glob("*.txt"):
        with open(txt_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        out_lines = []
        file_changed = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                out_lines.append(line)
                continue
            parts = stripped.split()
            try:
                cls = int(float(parts[0]))
            except (ValueError, IndexError):
                out_lines.append(line)
                continue

            if cls in id_map:
                parts[0] = str(id_map[cls])
                out_lines.append(" ".join(parts) + "\n")
                changed += 1
                file_changed = True
            else:
                out_lines.append(line)
                unknown += 1

        if file_changed:
            if make_backup:
                backup = txt_path.with_suffix(".txt.bak")
                if not backup.exists():
                    shutil.copy2(txt_path, backup)
            with open(txt_path, "w", encoding="utf-8") as f:
                f.writelines(out_lines)

        # Drop the Ultralytics label cache so the remap is actually picked up
        cache = txt_path.parent.with_suffix(".cache")
        if cache.exists():
            try:
                cache.unlink()
            except OSError:
                pass

    return changed, unknown


# ---------------------------------------------------------------------------
# Merging multiple YOLO-format sources into one dataset
# (from 02_object_detection_training.ipynb "Combine roboflow + custom" cell)
# ---------------------------------------------------------------------------


def merge_yolo_source(src_img_dir, src_lbl_dir, dst_img_dir, dst_lbl_dir, prefix):
    """Copy one YOLO-format source (images + labels) into a combined
    destination, prefixing filenames to avoid collisions between sources.
    Missing label files get an empty .txt written (matches notebook
    behaviour — assumes a genuinely-empty/background image, not a bug).

    Returns the number of images copied.
    """
    dst_img_dir = Path(dst_img_dir)
    dst_lbl_dir = Path(dst_lbl_dir)
    dst_img_dir.mkdir(parents=True, exist_ok=True)
    dst_lbl_dir.mkdir(parents=True, exist_ok=True)

    img_exts = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
    imgs = [p for p in Path(src_img_dir).rglob("*") if p.suffix.lower() in img_exts]

    copied = 0
    for img in imgs:
        stem = img.stem
        lbl = Path(src_lbl_dir) / f"{stem}.txt"

        new_img = dst_img_dir / f"{prefix}{stem}{img.suffix.lower()}"
        new_lbl = dst_lbl_dir / f"{prefix}{stem}.txt"

        shutil.copy2(img, new_img)
        if lbl.exists():
            shutil.copy2(lbl, new_lbl)
        else:
            new_lbl.write_text("")
        copied += 1

    return copied


def write_data_yaml(output_path, train_dir, val_dir, test_dir, nc, names):
    """Write a YOLO data.yaml. output_path is the full path to the file to
    write (e.g. Path("dataset") / "data.yaml"); train/val/test dirs should
    point at the *parent* of each split's images/labels folders.
    """
    data_yaml = {
        "train": str(train_dir),
        "val": str(val_dir),
        "test": str(test_dir),
        "nc": nc,
        "names": names,
    }
    with open(output_path, "w") as f:
        yaml.safe_dump(data_yaml, f, sort_keys=False)
