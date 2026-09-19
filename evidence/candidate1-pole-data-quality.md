# Pole training-data quality investigation: candidate1_controlled_train_val

## Scope and verdict

This investigates the weak `pole` YOLO class using **only** the
`candidate1_controlled_train_val` train/validation release. Held-out test
data was never included in the source package supplied for this
investigation, and the tooling used (`ML_side/tools/analyze_pole_class_quality.py`)
only ever reads `train/` and `val/` split directories — it has no code path
that can address a `test/` split at all.

**Verdict: real, fixable dataset-quality issues found.** None of them are
disqualifying on their own, but all four should be addressed before `pole`
is used to judge, or is retrained for, a Candidate 2 release.

## Dataset identity

- Package: `candidate1_controlled_train_val` (24,480 train / 6,994
  validation image-label pairs, per its own `README.txt`)
- Taxonomy: 8 classes, `pole` is target class ID 5 — an exact match to the
  approved WalkBuddy taxonomy in `ML_side/datasets/README.md` and
  `validate_dataset_manifest.APPROVED_TAXONOMY`, so no class-mapping
  ambiguity exists for this investigation
- No `metadata.json` was shipped with this package (it is a pre-review
  candidate release, not an approved manifest release), so this
  investigation is annotation/geometry analysis only — it does not attempt
  candidate-manifest generation

## Findings

### 1. Class imbalance

`pole` is the second-smallest of the 8 classes: 5,275 annotations, ahead of
only `stairs` (3,043) and well behind `person` (23,263), `door` (20,866),
and `vehicle` (15,510). See `candidate1-pole-data-quality.json` →
`class_distribution` for the full per-class, per-split table.

### 2. Geometry: extreme aspect ratio, not small size

`pole` annotations were bucketed by normalized bounding-box area (small-area
threshold 0.01) and aspect ratio (extreme threshold `max(h/w, w/h) > 3.0`),
using the exact thresholds and logic already built into
`inspect_candidate_dataset._class_geometry_buckets`, applied to every class
for comparison:

| Class | Small-area rate | Extreme-aspect-ratio rate |
|---|---:|---:|
| bicycle | 25.5% | 8.5% |
| chair | 7.5% | 5.6% |
| door | 25.9% | 26.4% |
| person | 28.2% | 52.8% |
| **pole** | **16.9%** | **64.7%** |
| stairs | 9.5% | 11.4% |
| table | 26.5% | 28.1% |
| vehicle | 22.3% | 4.6% |

`pole` has the highest extreme-aspect-ratio rate of any class by a wide
margin, but a *below-average* small-area rate. This is consistent with
poles simply being naturally thin, tall objects — it is not, by itself,
evidence of bad annotation. It is evidence that training should treat
`pole` as a shape outlier: aspect-ratio-aware augmentation and anchor-box
choices matter more for this class than for the others.

### 3. Duplicate and near-duplicate images (verified, not raw hash counts)

A raw perceptual-hash (aHash, Hamming distance ≤ 5) scan of all 4,087
pole-containing images found 449 groups covering 2,457 images (60%) —
but this number is **not trustworthy on its own**. Visual inspection
confirmed the hash is producing false positives on this class specifically,
because most pole photos share the same generic composition (a dark
vertical shape against open sky): two images of two completely different
utility poles, in different locations, were flagged as "near-duplicate"
purely because of that shared composition.

Every group was therefore re-checked against its actual YOLO label
coordinates (a much stronger duplicate signal than pixel hashing):

| Verdict | Count | Meaning |
|---|---:|---|
| `identical_labels` | 293 | Near-certain same photo (re-encoded or re-hosted) |
| `similar_labels` | 265 | Boxes close but not identical — plausible consecutive-capture frames |
| `dissimilar_labels` | 1,450 | Different scenes — hash false positive |

**293 + 265 = 558 confirmed duplicate/near-duplicate pole images (~14% of
the pole set)**, not 2,457. This is still a real, addressable issue — most
importantly:

**82 of the confirmed groups contain a match that spans both `train` and
`val`.** One verified example: `train/images/kaggle_indoor_object_detection_wb_000342.jpg`
and `val/images/roboflow_indoor_detection_vineeth_wb_019834.jpg` are the
same underlying photograph (a church doorway), re-published under two
different upstream dataset names, with near-identical label coordinates
(e.g. `0.386719` vs `0.38671875`) — and it landed in both splits. This is
train/validation leakage: any model that has effectively seen a validation
image during training will look better on that image than its true
generalization performance, which specifically inflates confidence in
exactly the class this investigation was asked to scrutinize.

Full group-by-group evidence (all 82 confirmed cross-split groups, not a
sample) is in `candidate1-pole-data-quality.json` →
`pole_near_duplicate_label_verification.confirmed_cross_split_groups`.

### 4. Class-definition contamination from generic source datasets

70 of the 4,087 pole-containing images (1.7%) come from source datasets
whose name contains "indoor" (`roboflow_indoor_detection_vineeth`,
`kaggle_indoor_object_detection`) rather than a pole-specific outdoor
capture dataset (`kaggle_light_poles`, `roboflow_outdoor_objects`, etc.).

Four of these were visually inspected during this investigation:

- **Two are unambiguous architectural columns mislabeled as `pole`**: a
  church doorway (2 full-height boxes on decorative stone pilasters
  flanking the door) and an embassy entrance (3 full-height boxes on
  ornate Corinthian columns). Neither is a real-world hazard pole a
  navigation device should be trained to recognize.
- One was ambiguous (a horizontal railing/beam in a window scene, hard to
  judge without clearer resolution).
- One was a plausible legitimate inclusion (a floor lamp's pole-like
  stand) — not every generic-source annotation is wrong.

This is a real but narrow contamination (≤1.7% of the class), not the
dominant driver of the class's weakness — but it directly muddies what
"pole" means to the model, mixing free-standing outdoor hazard poles with
decorative building architecture. The full 70-file list is in
`candidate1-pole-data-quality.json` → `generic_source_review_candidates.images`
for manual review; this record does not claim every listed image is wrong,
only that all 70 warrant a human look.

## Dataset revision / annotation improvement plan

In priority order, for before any Candidate 2 pole-focused retraining:

1. **Fix the 82 confirmed cross-split duplicate/near-duplicate groups
   first.** For each, keep the image in exactly one split and remove it
   from the other (prefer keeping the copy in `train` and dropping the
   `val` copy, so the smaller validation set doesn't lose too much
   coverage; where a group's members disagree, prefer keeping whichever
   copy has the cleaner/original source name). This is a correctness fix,
   not a nice-to-have: leaving it in place means `pole` validation metrics
   cannot be trusted at face value.
2. **Manually review the 70 generic-source ("indoor") pole annotations**
   and either (a) remove the box entirely if it is an architectural
   element, not a hazard pole, or (b) leave it if it is a genuine pole-like
   object. Use the visually-confirmed church-doorway and embassy-entrance
   examples in this report as a reference pattern: a full-height box
   (height close to 1.0) tightly flanking an ornate doorway or entrance is
   a strong signal of a mislabeled column, not a pole.
3. **Review the remaining 265 `similar_labels` (non-cross-split) groups**
   as a lower-priority pass — these are likely genuine consecutive-capture
   frames of the same real pole. They are not wrong, but keeping many
   near-identical frames of the same physical pole adds redundancy rather
   than diversity; consider subsampling each cluster to 1-2 representative
   frames if the class needs to stay lean.
4. **Do not rely on perceptual-hash distance alone for future duplicate
   audits of this class.** It over-counted by ~3.6x here specifically
   because most pole photos share a similar sky-and-silhouette
   composition. Prefer the label-coordinate verification approach used in
   this report (already implemented and reusable in
   `analyze_pole_class_quality.py`), or tighten the hash distance and
   accept more false negatives instead of more false positives.
5. **Treat `pole`'s extreme aspect ratio as a training-strategy input, not
   an annotation defect.** Consider aspect-ratio-aware augmentation or
   anchor-box tuning specifically for this class rather than "fixing" the
   geometry — the boxes are shaped like this because poles genuinely are.
6. **When future source datasets are merged in, check for pre-existing
   photo overlap between the newly-added source and every already-included
   source before assigning a random train/val split.** The 82-group
   leakage found here happened because the same public photo was
   independently re-uploaded to two different aggregators (a supply-chain
   duplication, not an annotation mistake), so per-dataset dedup at merge
   time — not just post-hoc auditing — is the more durable fix.

## Reproducing this investigation

```bash
python3 ML_side/tools/analyze_pole_class_quality.py \
  --dataset-root <local_extraction_root>/candidate1_controlled_train_val \
  --dataset-yaml <local_extraction_root>/candidate1_controlled_train_val/data.yaml \
  --pole-images-dir <local_extraction_root>/candidate1_controlled_train_val \
  --output-dir <output_dir>
```

`--pole-images-dir` must point to a root containing `train/images/` and/or
`val/images/` subdirectories holding **only** pole-containing images (a
pre-filtered subset, not the full image set) — this keeps the tool's
near-duplicate detection at the class-scoped scale it is designed for, and
avoids needing to extract every image in a multi-gigabyte dataset locally
just to audit one class. The full label directories (`train/labels/`,
`val/labels/`) are still read in full for the class-distribution and
geometry-bucket analysis, since that needs no image files at all.

The real dataset itself is never committed to this repository (see
`ML_side/datasets/README.md`); only this generated report is.
