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
