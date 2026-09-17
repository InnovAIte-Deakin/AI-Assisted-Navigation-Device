# WalkBuddy data pipeline

This package replaces the experimental data-pipeline notebooks with a checkpointed Python workflow. The notebooks remain untouched as historical prototypes. Raw data is immutable: rejected files are hard-linked or copied into `datasets/invalid`, and every decision remains tied to a persistent asset UUID in SQLite.

## How the files work together

There is one public entry point: `ML_side/tools/run_data_pipeline.py`. It passes the command to `cli.py`; the `run` command loads the selected configuration and calls `pipeline.execute()`. `pipeline.py` is the orchestrator. The other modules do not need to be run individually.

```text
run_data_pipeline.py
  -> cli.py
     -> config.py                    load and validate user choices
     -> pipeline.py                  run/resume stages in order
        -> layout.py                 create roots/provider/source/run skeleton
        -> collection.py             obtain or confirm each configured source
        -> video_extraction.py       turn configured raw video/CSV pairs into grouped YOLO frames
        -> intake.py                 UUID, hashes, provenance, run identity
        -> deduplication.py          exact and perceptual duplicate detection
        -> validation.py             source structure and image/label pairing
        -> standardization.py        EXIF orientation and image encoding
        -> annotations.py            YOLO/VOC/COCO conversion and box validation
        -> merging.py                combine accepted source catalogues logically
        -> quality.py                image-quality flags and review requests
        -> grouping.py               source/video/session leakage groups
        -> cvat_review.py            create semantic-QA samples/tasks
        -> splitting.py              group-preserving train/val/test assignment
        -> representativeness.py     compare split source/class distributions
        -> balance.py                enforce the configured imbalance threshold
        -> augmentation.py           train-only targeted deficit augmentation
        -> release.py                package, checksum, manifest, and verify
```

Supporting modules are `models.py` (configuration/result data structures), `database.py` (SQLite schema and audit records), `quarantine.py` (recorded invalid-file handling), `reviews.py` and `cvat_sync.py` (human decisions), `reporting.py` (final QA report), and `utils.py` (hashing/copy/runtime helpers).

`ML_side/config/download_sheet.yaml` is the authoritative source registry. It owns each dataset's provider, URL, version, raw folder, licence, and governance status. A versioned configuration references it with a relative path such as `download_sheet: ../download_sheet.yaml`, selects dataset IDs, and contains only processing choices such as annotation format, class mapping, environment tags, and grouping. When a download sheet is active, repeating or overriding its provenance fields in `sources` is rejected.

The download sheet folder is interpreted beneath `<raw_root>/<provider>/`, matching the repository's existing `raw/kaggle`, `raw/roboflow`, `raw/huggingface`, and `raw/manual` layout. Both the pipeline-config checksum and download-sheet checksum are recorded and included in the run identity. Editing either creates a new run rather than resuming output created from different source information.

Before collection, `layout.py` idempotently creates the configured raw, workspace, invalid, and output roots; one raw provider directory; one empty source destination; and the standardized, labels, quality-review, semantic-review, and near-duplicate-review working directories for the run. Collection safely replaces an empty source placeholder only after a complete staged download. A manual source keeps its empty destination and reports that files are required. The final `dataset_<release-id>` directory is deliberately not created by bootstrap: it appears only after all release gates pass, so an empty directory can never be mistaken for an approved dataset.

Normally you maintain source/governance facts in the shared `download_sheet.yaml`, edit a copy of `ML_side/config/dataset_v3/data_pipeline.example.yaml` for processing behavior, then run only the entry-point command. Inline provenance remains supported only for isolated synthetic/test configurations that omit `download_sheet`.

## Generated files, checkpoints, and caches

These folders have different purposes and should not all be treated as caches:

| Location | Purpose | Safe to delete? |
| --- | --- | --- |
| `data_pipeline/__pycache__/` | Python-created bytecode (`.pyc`) used to import modules faster | Yes. Python may recreate it; Git ignores it. |
| `<workspace_root>/<run-id>/pipeline.sqlite3` | Authoritative checkpoint, provenance, stage results, transformations, reviews, and audit trail | Only when abandoning that run. Deleting it prevents resume. |
| `<workspace_root>/<run-id>/standardized/` | Geometry-final working images used by later stages | Only with the matching abandoned run. |
| `<workspace_root>/<run-id>/labels/` | Converted working YOLO labels | Only with the matching abandoned run. |
| `<workspace_root>/<run-id>/review/` | Near-duplicate/quality/CVAT review material and decision CSV | Only after the run is released or intentionally abandoned. |
| `<invalid_root>/` | Quarantine evidence with recorded reasons | Not a cache. Retain for audit unless deliberately retiring the run. |
| `<output_root>/dataset_<release-id>/` | Final verified dataset release | No; this is the deliverable. |

A run ID looks like `<release-id>-<12-character fingerprint>`. The fingerprint includes the configuration file, random seed, and all pipeline Python source. Therefore, changing pipeline code or configuration creates a new workspace instead of incorrectly resuming results produced by different logic. Re-running the exact same code and configuration resumes the existing workspace.

The sample configuration deliberately writes under `datasets/pipeline_sample/` so testing cannot modify production raw data, quarantine, workspace, or releases.

## Pipeline and failure branches

```text
collect -> extract configured videos -> register provenance -> exact hash dedup -> validate structure
                                             |              |
                                             +--> quarantine +--> quarantine

standardise image geometry -> convert/validate YOLO boxes -> logical UUID merge -> quality review
                                           |                     |
                                           +--> quarantine        +--> human decision

near-duplicate review -> sequence grouping -> semantic CVAT review
          |                                       |
          +--> human decision/quarantine          +--> corrected labels + audit

group-preserving split -> balance gate -> targeted train-only augmentation
                                  |                   |
                                  +--> re-check <------+-- or request more data

package dataset_<release-id> -> checksum/allow-list verification -> QA report
```

For a source with `video_extraction.enabled: true`, collection is followed by
video extraction before intake. Raw videos and CSVs remain unchanged. Only
annotated frames are written beneath the run workspace, their CSV boxes are
converted to YOLO, the source video becomes the automatic leakage group, and
intake records video/frame/hash lineage. Install `opencv-python` for this
optional stage.

Stage outcomes are `pass`, `warning`, `review_required`, `fail`, and `skipped`. The CLI returns `0` only for a completed pass, `2` when human review is required, and `1` for a failure. A failed source is isolated while other sources continue, but a final release remains blocked until every failure is fixed or represented by a future explicit waiver mechanism.

## Configuration

Copy `ML_side/config/dataset_v3/data_pipeline.example.yaml` and select IDs that exist in the shared `download_sheet.yaml`. Maintain provider, URL, version, raw folder, licence, and approval status only in the download sheet. In the versioned pipeline config, every selected source needs its processing details: annotation format, class mapping, grouping strategy, and optional environment tags. Missing environment context is recorded as `unknown`; it is never invented.

The `taxonomy` list accepts any positive number of unique classes; its order is the authoritative YOLO class-ID order. `dataset_yaml.mode` controls release metadata: `generate` creates `data.yaml`, `supplied` validates and copies an existing YAML, and `none` omits it for audit/package-only output. The generated `nc` is always derived from the taxonomy length. Classes are never silently discovered from source labels: every source class still needs an explicit mapping, so an accidental label cannot redefine the model taxonomy.

Use `mode: sample` with a positive `max_assets_per_source` for cheap deterministic test runs. Full and sample runs execute identical code. The configuration hash is part of the run identity, so a sample run cannot be confused with a full release.

Images are EXIF-oriented and re-encoded before annotations are converted. The converter transforms boxes into the final pixel geometry and then writes normalized YOLO `class x_center y_center width height` rows. A post-conversion bounds check rejects any box that no longer fits.

## Commands

From the repository root:

```powershell
python .\ML_side\tools\run_data_pipeline.py run `
  --config .\ML_side\config\dataset_v3\data_pipeline.yaml
```

When the result is `review_required`, inspect the review folders under the run workspace. Import decisions using the generated `review_decisions.csv` columns. Each decision records the reviewer, time, notes, asset/task identity, and outcome.

```powershell
python .\ML_side\tools\run_data_pipeline.py review-import `
  --config .\ML_side\config\dataset_v3\data_pipeline.yaml `
  --csv D:\reviewed\review_decisions.csv `
  --reviewer "Reviewer Name"
```

If CVAT is enabled, the first run automatically creates one stratified task per source with up to `qa_sample_per_source` unique images. After review, explicitly import the corrected labels:

```powershell
python .\ML_side\tools\run_data_pipeline.py cvat-sync `
  --config .\ML_side\config\dataset_v3\data_pipeline.yaml `
  --reviewer "Reviewer Name"
```

Run the pipeline command again to resume from its checkpoint. An unfinished CVAT task “blocks release” only in the sense that the run stays at `review_required`; it does not discard completed work or prevent unrelated sources from being processed.

Verify an existing release at any time:

```powershell
python .\ML_side\tools\run_data_pipeline.py verify `
  --release-dir .\ML_side\datasets\dataset_navigation-v3
```

Verification recalculates every approved SHA-256 digest and fails on missing, modified, or unexpected files. The release manifest includes original and parent asset IDs, source paths, groups, splits, transformations, review history, code/config identity, runtime versions, and random seeds.

## Deliberate safeguards

- Exact duplicates are quarantined immediately after registration, before image processing.
- Near duplicates are copied/hard-linked into review clusters and require human judgment.
- Unknown sequence metadata becomes one explicit unknown source group, not silent independent samples.
- Augmentation occurs only in `train`; generated samples retain `parent_asset_id` lineage.
- Targeted crops are rejected if they would duplicate an already-balanced class. If safe augmentation cannot satisfy 4:1, the release asks for additional data.
- Release creation stages into a sibling directory and never overwrites an existing release.
- Raw assets are never renamed, moved, or modified.
