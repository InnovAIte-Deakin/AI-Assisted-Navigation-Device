# WalkBuddy navigation dataset manifests

This directory contains Git-safe metadata for proposed navigation-model dataset releases. A manifest records dataset lineage, licence-review evidence, target-taxonomy mapping, split membership, integrity counts, and external-storage references. It does not make a dataset legally approved, fit for training, or safe for deployment.

## Approved MVP taxonomy

Only these classes are allowed in a release manifest, in this exact ID order:

| ID | Class |
|---:|---|
| 0 | person |
| 1 | stairs |
| 2 | door |
| 3 | chair |
| 4 | table |
| 5 | pole |
| 6 | bicycle |
| 7 | vehicle |

The companion YOLO configuration is [`../config/navigation_mvp.yaml`](../config/navigation_mvp.yaml). Its dataset root is a placeholder; it does not identify an approved local dataset.

## Files and storage boundary

- [`manifest.schema.json`](manifest.schema.json) defines the version `1.0.0` manifest structure.
- [`sample_manifest.json`](sample_manifest.json) is fictional, non-sensitive, and demonstrates the required fields. It is not an approved dataset release.
- Images, annotations, model weights, consent records, and other sensitive or large material belong in controlled external storage. Commit only the manifest and related text configuration.

## Create and validate a manifest

Copy the sample, replace every fictional value with reviewed metadata, and keep image and label paths relative to the controlled dataset root. Use explicit class-mapping rationale for every source-to-target mapping; excluded and unmapped source classes must remain visible rather than being silently reclassified.

From the repository root in Windows PowerShell:

```powershell
python .\ML_side\tools\validate_dataset_manifest.py .\ML_side\datasets\sample_manifest.json
```

On macOS or Linux:

```bash
python ML_side/tools/validate_dataset_manifest.py ML_side/datasets/sample_manifest.json
```

To check that referenced relative image and label files exist, provide the local controlled dataset root explicitly:

```powershell
python .\ML_side\tools\validate_dataset_manifest.py `
  .\ML_side\datasets\sample_manifest.json `
  --dataset-root D:\controlled-datasets\navigation-mvp-v1 `
  --check-files
```

Without `--check-files`, validation is metadata-only and does not access datasets. The validator rejects absolute personal paths, file URIs, literal or percent-encoded path traversal, and mixed slash/backslash traversal in release records. File checking confirms only that listed paths exist beneath the supplied root; it does not inspect image content, annotations, consent, or licence validity.

## What validation does and does not establish

Structural validation uses the bundled Draft 2020-12 `manifest.schema.json` through a project-specific standard-library implementation. It enforces the schema keywords used here: `$defs`, `$ref`, `type`, `required`, `properties`, `additionalProperties`, `items`, `minItems`, `minLength`, `minimum`, `pattern`, `enum`, and `const`. The tool rejects a future schema that introduces an unsupported validation keyword. It is not a complete general-purpose JSON Schema implementation. Semantic validation enforces the approved taxonomy, mapping consistency, split isolation, safe relative paths, checksums, count and dimension bounds, and optional file existence.

When supplied, checksums must be SHA-256 values: exactly 64 hexadecimal characters, optionally prefixed with `sha256:`. Uppercase and lowercase hexadecimal characters are accepted deliberately; checksum comparison is outside this metadata validator.

Validation does not grant formal legal or licensing approval. A manifest must contain licence evidence and a reviewer decision, but the projectâ€™s authorised reviewers remain responsible for evaluating the evidence. Likewise, a valid manifest is not evidence that a dataset is representative, unbiased, sufficiently labelled, or suitable for a production navigation model.

## Split leakage protection and future training

Every sample records a group or sequence ID. The validator rejects a group reused across train, validation, and test splits, helping prevent near-duplicate frames from inflating future evaluation results. It also rejects duplicate sample IDs and images reused across splits.

After the dataset has independent review and an approved release decision, a future training workflow can use the manifest to build controlled YOLO split directories and update the MVP dataset configuration. Training, downloading data, and model selection are deliberately outside this manifest-validation tool.

## Known limitations

- File checks are opt-in and cannot validate external storage availability or permissions.
- Bounding-box validation applies only when boxes are recorded directly in the manifest; normal YOLO label-file parsing is future work.
- The manifest records review evidence but cannot replace legal, privacy, accessibility, or data-governance review.

## Inspect a local YOLO candidate dataset

`../tools/inspect_candidate_dataset.py` is the read-only inspection step before a candidate dataset is represented by a release manifest. It reads the supplied local dataset root and YOLO YAML, writes reports only to an explicitly selected directory outside that root, and makes no network requests. It does not download data, train a model, copy images, or change labels.

The YAML must use safe relative paths beneath the supplied root. `train` and `validation` (or `val`) are required; `test` is inspected when present. Common directory layouts such as `train/images` with paired `train/labels`, or `images/train` with paired `labels/train`, are supported through the paths declared in the YAML. Absolute paths, path traversal, and symlink escapes are rejected.

From the repository root in Windows PowerShell:

```powershell
python .\ML_side\tools\inspect_candidate_dataset.py `
  --dataset-root D:\controlled-datasets\candidate-navigation-v1 `
  --dataset-yaml D:\controlled-datasets\candidate-navigation-v1\dataset.yaml `
  --output-dir D:\controlled-reports\candidate-navigation-v1
```

On macOS or Linux:

```bash
python ML_side/tools/inspect_candidate_dataset.py \
  --dataset-root /controlled-datasets/candidate-navigation-v1 \
  --dataset-yaml /controlled-datasets/candidate-navigation-v1/dataset.yaml \
  --output-dir /controlled-reports/candidate-navigation-v1
```

Image decoding and SHA-256 checksum calculation are enabled by default when the existing Python environment has Pillow. Use `--skip-image-decode` or `--skip-checksums` only when an explicitly documented limitation is acceptable; skipped checks are reported as warnings. The output directory must be outside the dataset root, so this tool cannot write reports into the inspected dataset.

### Quality checks and leakage rules

The inspector reports image and label totals by split, images without labels, orphan labels, empty label files, unsupported extensions, unreadable images, malformed YOLO rows, source- and target-class annotation distributions, and samples without valid annotations. A YOLO row must be exactly `class_id x_center y_center width height`, with a non-negative integer source ID, finite numeric values, positive dimensions, and a bounding box fully inside normalized bounds.

SHA-256 checksums identify byte-identical images. Identical checksums in different splits are a failure because they indicate direct split leakage; same-split duplicates remain a visible warning for review. The report also flags duplicate filename-stem sample identifiers and duplicate normalized paths. Filename similarity is never treated as group leakage. To check sequence or group leakage, supply an explicit group map:

```json
{
  "groups": {
    "train/images/frame_001.jpg": "walk-sequence-a",
    "validation/images/frame_101.jpg": "walk-sequence-b"
  }
}
```

Keys are safe relative image paths from the dataset root, and values are non-empty group IDs. The inspector fails if one supplied group occurs in more than one split. Without a group map it records a limitation and does not infer groups from names or paths.

The controlled verdict is `fail` when validation errors exist, `pass_with_warnings` when no errors but one or more warnings exist, and `pass` otherwise. A passing result does not establish legal, privacy, ethical, accessibility, representativeness, model-quality, production-readiness, or final dataset-fitness approval.

### Explicit mapping and candidate manifest metadata

An optional reviewed metadata JSON or YAML file supplies source-to-WalkBuddy mapping decisions. It must use the following project-specific shape; values below are fictional examples only:

```json
{
  "class_mapping": [
    {
      "source_class_id": 0,
      "target_class_id": 0,
      "target_class_name": "person",
      "mapping_rationale": "Reviewed semantic equivalence."
    }
  ],
  "excluded_source_classes": [
    { "source_class_id": 9, "reason": "Outside the approved MVP taxonomy." }
  ],
  "unmapped_source_classes": [
    { "source_class_id": 10, "reason": "Requires explicit taxonomy review." }
  ]
}
```

Every source class in the dataset YAML is displayed as mapped, excluded, or unmapped. The inspector never infers a target mapping: a mapping must use an exact approved WalkBuddy target ID/name pair and a non-empty rationale. Unknown or mismatched targets fail inspection. Excluded classes remain visible in source counts and are not added to target counts.

To request `candidate_manifest.json`, add `--generate-manifest`, `--metadata`, and a complete `--group-map`. In addition to the class decisions above, metadata must provide `dataset`, `source_provenance`, `licence`, `storage_release`, `quality_review_status`, and `known_limitations` using the fields required by [`manifest.schema.json`](manifest.schema.json). The tool withholds the manifest when any required review metadata, source-class decision, group identifier, or passing quality result is missing. It then validates a generated manifest with the existing validator before writing it. A generated file remains a candidate or review-stage record unless the supplied, reviewed metadata validly says otherwise; inspection cannot invent source, licence, reviewer, approval, or release-version values.

Example with metadata and candidate-manifest generation in PowerShell:

```powershell
python .\ML_side\tools\inspect_candidate_dataset.py `
  --dataset-root D:\controlled-datasets\candidate-navigation-v1 `
  --dataset-yaml D:\controlled-datasets\candidate-navigation-v1\dataset.yaml `
  --metadata D:\controlled-datasets\candidate-navigation-v1\reviewed_metadata.json `
  --group-map D:\controlled-datasets\candidate-navigation-v1\reviewed_groups.json `
  --output-dir D:\controlled-reports\candidate-navigation-v1 `
  --generate-manifest
```

The reports are `dataset_quality_report.json` and `dataset_quality_report.md`; apart from isolated execution-time metadata, their ordering is deterministic for unchanged input. They record both `dataset_identity` and `dataset_source_version` when reviewed metadata is supplied. Reports generated before that source-version field was added must be regenerated before they can be used by the release builder. Keep raw images, labels, review evidence, and generated reports in controlled external storage rather than Git. After appropriate independent review, the resulting candidate manifest can feed a future controlled training workflow; this tool itself does not perform training or select a model.

## Build a controlled canonical release

`../tools/build_navigation_dataset_release.py` is the controlled bridge from an inspected local YOLO candidate to a copied, versioned WalkBuddy release. It uses the exact approved taxonomy above, rewrites only included label class IDs, and never infers semantic equivalence from source class names. It reads the source dataset, source manifest, inspection report, and reviewed mapping configuration without changing them; the release output must be a controlled external directory, outside both the source root and this Git repository.

Start from [`../config/dataset_release.example.json`](../config/dataset_release.example.json). It is fictional metadata, not a real mapping or approval. Its `source_taxonomy` must exactly match the source YOLO YAML, including class ID, spelling, case, and order. Every source class must have exactly one explicit decision: a mapping to the matching approved ID/name pair, an excluded decision with a reason, or an unresolved decision. Unresolved classes block release creation. Unknown fields, duplicate class decisions, unknown source IDs, and targets outside the approved eight classes are rejected.

An excluded annotation is deliberately removed and counted. `empty_image_policy: retain_negative` retains images that become empty after exclusion with an empty YOLO label file; `exclude_image` omits those images and labels together. Images that were already empty negative samples are retained in their original split under either policy and are reported separately from exclusion-created negatives. Release name and version must be safe single path components containing only letters, numbers, dots, underscores, and hyphens.

The source manifest must pass file checks, record an approved licence review that permits machine-learning use, and identify the same case-sensitive dataset ID, exact source version, and exact source taxonomy recorded by the passing inspector report. The builder rejects cross-split duplicate-image or explicit group-leakage findings, unsafe paths, symlink escapes, missing files, source-YAML/mapping taxonomy mismatch, same-stem image collisions, and an output location that overlaps the source. A structurally completed release is not legal, privacy, ethical, model-quality, safety, production, or training approval. Its generated manifest defaults to `under_review`; `approved_for_training` is accepted only when explicitly supplied metadata also records an approved ML-permitted licence review and completed quality review.

Always begin with a dry run. It validates every input, plans deterministic filenames and label rows, calculates class/exclusion/split counts and checksums, and writes nothing:

```powershell
python .\ML_side\tools\build_navigation_dataset_release.py `
  --source-root D:\controlled-datasets\candidate-navigation-v1 `
  --source-yaml D:\controlled-datasets\candidate-navigation-v1\dataset.yaml `
  --source-manifest D:\controlled-reports\candidate-navigation-v1\candidate_manifest.json `
  --inspection-report D:\controlled-reports\candidate-navigation-v1\dataset_quality_report.json `
  --mapping-config D:\controlled-review\navigation-release-mapping.json `
  --output-root D:\controlled-datasets\releases `
  --release-name navigation-mvp-v1 `
  --release-version v1 `
  --dry-run
```

On macOS or Linux, use the same local-only inputs with forward slashes and `python ML_side/tools/build_navigation_dataset_release.py`. A real copy is blocked unless `--confirm-build` is supplied; `--dry-run` and `--confirm-build` cannot be combined.

```powershell
python .\ML_side\tools\build_navigation_dataset_release.py `
  --source-root D:\controlled-datasets\candidate-navigation-v1 `
  --source-yaml D:\controlled-datasets\candidate-navigation-v1\dataset.yaml `
  --source-manifest D:\controlled-reports\candidate-navigation-v1\candidate_manifest.json `
  --inspection-report D:\controlled-reports\candidate-navigation-v1\dataset_quality_report.json `
  --mapping-config D:\controlled-review\navigation-release-mapping.json `
  --output-root D:\controlled-datasets\releases `
  --release-name navigation-mvp-v1 `
  --release-version v1 `
  --confirm-build
```

The completed release has `images/train`, `images/val`, optional `images/test`, matching `labels` directories, a release-relative `dataset.yaml`, `release_manifest.json`, `release_build_report.json`, `release_build_report.md`, and `release_checksums.json`. Files are copied through a temporary sibling staging directory and promoted only after manifest, label, checksum, and inspector verification pass. A failed build removes that staging directory where possible and never treats it as a completed release. The JSON and Markdown reports derive from the same canonical counts and record source/released samples, mapped/excluded annotations, negatives, eligibility verification, and input/output SHA-256 checksums. `release_checksums.json` lists the substantive copied images, rewritten labels, YAML, and manifest; it intentionally does not checksum itself or the reports, avoiding recursive checksum churn. The deterministic release identity derives from the reviewed inputs, destination plan, and output label content; Git state is recorded separately and does not alter that identity. Keep releases, images, labels, reports, and any weights in controlled external storage rather than Git.

After an independent reviewer explicitly promotes the generated manifest to the eligible decision, the release can be used as the local `--dataset-root` for [`../training/train_navigation_model.py`](../training/train_navigation_model.py) dry-run. Training remains a separate controlled operation; this builder neither trains a model nor establishes that the dataset is fit for one.
