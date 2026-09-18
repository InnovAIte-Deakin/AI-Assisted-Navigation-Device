# WalkBuddy Data Pipeline: Beginner Handbook

This handbook is for a student who has just joined the WalkBuddy project and needs to build a new object-detection dataset with new or changed classes.

It describes the pipeline that is implemented in `ML_side/data_pipeline` now. It does not describe the old notebooks as if they were still the production workflow, and it does not claim that planned features already exist.

## 1. The most important facts first

1. Run the pipeline through `ML_side/tools/run_data_pipeline.py`. Do not run the individual modules one by one.
2. `ML_side/config/download_sheet.yaml` is the shared registry of source facts: provider, URL, version, raw folder, licence, and approval status.
3. A versioned pipeline configuration supplies the processing decisions: final classes, source-to-final-class mappings, annotation formats, grouping rules, split ratios, review settings, and thresholds.
4. The pipeline creates missing data directories, provider directories, source directories, run workspaces, review folders, quarantine folders, and the final release directory.
5. The pipeline does **not** currently create a production pipeline configuration from only `download_sheet.yaml`. A person must create and review that configuration before a run.
6. Raw source files are preserved. Standardized images, converted labels, reviews, and checkpoints are written elsewhere.
7. A run can intentionally stop with `review_required`. That is not lost work. Resolve the review queue and run the same command again to resume.
8. A final `dataset_<release-id>` folder is created only after release gates pass.

## 2. What the user decides and what the program decides

The program automates mechanical work, but it must not invent semantic decisions.

| Decision or action | Who is responsible? | Where it happens |
| --- | --- | --- |
| Which online or manual datasets may be used | User/team | `config/download_sheet.yaml` |
| Provider, URL, provider version, folder, licence, governance status | User/team | `config/download_sheet.yaml` |
| New dataset release name | User | Versioned pipeline config: `release_id` |
| Final model classes and their numeric order | User | Versioned pipeline config: `taxonomy` |
| How each source class maps to a final class | User | Each source's `class_mapping` |
| Which source classes are deliberately excluded | User | Map them to `null` |
| Source annotation format | User | Each source's `annotation_format` |
| Raw-video/CSV pairing, frame numbering, columns, and coordinate convention | User | Each video source's `video_extraction` block |
| Video/session/source grouping method | User | Each source's `grouping`, optional metadata, and optional regex |
| Default environment tags when per-image tags are absent | User | Each source's `environment_tags` |
| Per-image environment/session metadata, when available | User/source owner | Optional metadata CSV |
| Train/validation/test proportions | User | `splits` |
| Review sample size per source | User | `qa_sample_per_source` |
| Duplicate, quality, and semantic judgments | Human reviewer | Generated review material, CSV, or CVAT |
| Create folders and download supported sources | Program | Layout and collection stages |
| Assign persistent asset UUIDs and calculate hashes | Program | Intake stage |
| Convert valid annotations to normalized YOLO boxes | Program | Annotation conversion stage |
| Preserve related groups during splitting | Program | Grouping and splitting stages |
| Detect imbalance and perform safe train-only augmentation | Program | Balance and augmentation stages |
| Package, checksum, verify, and report the release | Program | Release stage |

The final taxonomy is deliberately user-defined. Automatic class discovery would be dangerous: a misspelling or unwanted source label could silently become a model class.

## 3. The complete flow

```text
download_sheet.yaml + versioned pipeline config
                         |
                         v
create safe folder layout and run checkpoint
                         |
                         v
collect/confirm each raw source
                         |
                         v
extract configured raw video/CSV pairs into grouped frames
                         |
                         v
register UUID + hashes + provenance
                         |
                         v
exact duplicate detection --------------------> quarantine duplicate copies
                         |
                         v
source structure validation ------------------> quarantine invalid assets
                         |
                         v
EXIF correction and image standardization ----> quarantine unreadable images
                         |
                         v
annotation parsing, mapping, conversion ------> quarantine invalid/unmapped assets
                         |
                         v
logical merge of accepted UUID records
                         |
                         v
quality flags + near-duplicate clusters + semantic samples
                         |
                         v
human review; pipeline checkpoints and pauses
                         |
                         v
sequence/source grouping and group-preserving split
                         |
                         v
distribution comparison + class balance gate
                         |
                 if necessary
                         v
targeted crop/brightness/blur augmentation in train only
                         |
                         v
dataset_<release-id> + manifest + reports + checksums
```

The stage status is more useful than a simple `0/1` flag:

| Status | Meaning |
| --- | --- |
| `pass` | Stage completed successfully. |
| `warning` | Stage completed, but something needs attention in the report. |
| `review_required` | Automated work is checkpointed; a person must decide before release. |
| `fail` | A required gate failed. Other independent sources may still have been processed. |
| `skipped` | The stage was intentionally disabled or unnecessary. |

At the command-line level, exit code `0` means pass, `2` means human review is required, and `1` means failure.

## 4. Important folders and files

```text
ML_side/
|-- config/
|   |-- .env                              # local secrets if the team chooses to use it
|   |-- download_sheet.yaml               # shared source registry
|   |-- dataset_v2/                       # old/current-v2 configuration history
|   `-- dataset_v3/
|       |-- data_pipeline.example.yaml    # example only; not used automatically
|       `-- data_pipeline.sample.json     # isolated sample/test example
|-- data_pipeline/                        # the Python package explained in this guide
|-- tools/
|   `-- run_data_pipeline.py              # public command-line entry point
`-- datasets/
    |-- raw/<provider>/<source>/           # immutable downloaded or manually supplied inputs
    |-- pipeline_workspace/<run-id>/       # checkpoint DB, extracted/standardized data, and reviews
    |-- invalid/<run-id>/<reason>/         # quarantined evidence
    `-- dataset_<release-id>/              # final approved release
```

The exact data roots are configurable. The tree above is what the supplied v3 example resolves to.

### Template files versus generated files

- `data_pipeline.example.yaml` and `data_pipeline.sample.json` are examples. Merely leaving them in `config` does not affect a run.
- A real configuration is used only when its path is passed with `--config`.
- `pipeline.sqlite3`, review files, standardized images, converted labels, reports, manifests, checksums, and the release `data.yaml` are generated during a run.
- `__pycache__` and `.pyc` files are Python speed caches. They can be deleted and Python may recreate them.
- `pipeline.sqlite3` is **not** a disposable cache. It is the run's checkpoint and audit record.

## 5. Starting a new dataset from scratch

### Step 1: install the required packages

From the repository root:

```powershell
python -m pip install -r .\ML_side\data_pipeline\requirements.txt
```

This installs Pillow and PyYAML. Install only the optional adapters you actually need:

```powershell
python -m pip install kagglehub
python -m pip install huggingface-hub
python -m pip install roboflow
python -m pip install cvat-sdk
python -m pip install opencv-python
```

Provider authentication is still required. For example, Roboflow collection reads `ROBOFLOW_API_KEY`. CVAT reads `CVAT_HOST`, `CVAT_USER`, and `CVAT_PASS`. `opencv-python` is required only when a source enables raw-video extraction. Do not commit real secrets to Git.

### Step 2: register every source

Edit `ML_side/config/download_sheet.yaml`. Add one stable ID under `datasets` for every source you want to use:

```yaml
datasets:
  my_new_source:
    source: kaggle
    url: "https://www.kaggle.com/datasets/owner/dataset-name"
    version:
    status: approved
    folder: my_new_source
    ethics:
      license: "CC BY 4.0"
```

User input is required for:

- the stable source ID (`my_new_source`);
- provider (`kaggle`, `roboflow`, `huggingface`, a direct URL provider, or `manual`/local placement);
- source URL and version where applicable;
- raw folder name;
- verified licence;
- governance status.

Only `approved` sources can enter a final release. `review_required` and `rejected` block release.

Do not repeat these facts in the processing config when `download_sheet` is enabled. The loader rejects duplicated provenance fields so there is one source of truth.

### Step 3: create a versioned processing configuration

Create a new version folder, for example `ML_side/config/dataset_v4`, then copy the v3 example as a starting point and name the working file `data_pipeline.yaml`.

This copy is currently a manual user action. The pipeline does not yet have an interactive first-run wizard.

Review every field. Do not assume the example's eight classes or source mappings match the new project.

```yaml
project_root: ../..
raw_root: ../../datasets/raw
download_sheet: ../download_sheet.yaml
workspace_root: ../../datasets/pipeline_workspace
invalid_root: ../../datasets/invalid
output_root: ../../datasets

release_id: navigation-v4
mode: sample
max_assets_per_source: 100
seed: 42

taxonomy_version: 2.0.0
taxonomy:
  - person
  - stairs
  - door
  - new_class

dataset_yaml:
  mode: generate

splits:
  train: 0.70
  val: 0.20
  test: 0.10

image_format: JPEG
jpeg_quality: 95
near_duplicates_enabled: true
near_duplicate_distance: 6
near_duplicate_review_distance: 10
imbalance_ratio: 4.0
distribution_drift_threshold: 0.25
qa_sample_per_source: 50
empty_after_mapping_policy: retain_negative

cvat:
  enabled: true
  project_name: WalkBuddy semantic QA

sources:
  - id: my_new_source
    annotation_format: yolo
    class_names:
      - Person
      - Staircase
      - Door
      - Bus
    class_mapping:
      0: person
      1: stairs
      2: door
      3: null
    environment_tags:
      - outdoor
    grouping: folder
```

All relative paths are resolved from the directory containing this configuration file.

### Step 4: choose the final taxonomy

The order of `taxonomy` is the final YOLO class order. In the example above:

```text
0 = person
1 = stairs
2 = door
3 = new_class
```

Changing the order changes numeric class IDs. Treat `taxonomy_version` and the class order as release-level ground truth.

The number of classes is unrestricted except that the list must be non-empty and names must be unique. When `dataset_yaml.mode` is `generate`, the release `data.yaml` is generated from this list and `nc` is calculated automatically.

### Step 5: map every source class explicitly

For each source, determine its original class ID list and add a decision for every class ID that can occur:

```yaml
class_mapping:
  0: person       # keep and map
  1: stairs       # keep and map
  2: door         # keep and map
  3: null         # deliberately exclude
```

This mapping is semantic and therefore requires a person. The program validates it and performs the conversion, but it cannot know whether a source's `vehicle` should become `vehicle`, `bus`, or be excluded.

- Mapping to a taxonomy name keeps the annotation.
- Mapping to `null` deliberately excludes that annotation.
- Omitting a source class that appears in a label is an error; that asset is quarantined.
- A mapping target not present in `taxonomy` makes configuration loading fail.

For Pascal VOC, `class_names` is also required because XML annotations contain names rather than numeric IDs. The list order converts each source name to its source numeric ID before `class_mapping` is applied.

### Step 6: describe annotation locations and formats

Supported values are:

- `auto`: paired `.txt` is treated as YOLO and paired `.xml` as Pascal VOC;
- `yolo`: normalized boxes or normalized polygons;
- `voc` or `pascal_voc`: Pascal VOC XML boxes;
- `coco`: one COCO JSON file, supplied with `annotation_file` relative to the source folder.

Examples:

```yaml
annotation_format: coco
annotation_file: annotations/instances_train.json
```

```yaml
annotation_format: voc
class_names: [Person, Door, Chair]
```

YOLO polygons are converted to their enclosing four-corner bounding box. Final labels always use normalized YOLO detection rows:

```text
class_id x_center y_center width height
```

### Step 7: supply sequence and environment information

Choose a grouping strategy for every source:

| Setting | Result |
| --- | --- |
| `dataset` | The whole source is one non-splittable group. Safest, but may make balanced splitting difficult. |
| `folder` | Images in the same relative parent folder stay together. |
| `filename-regex` | A regex extracts a video/session identifier from each relative path. |
| `metadata-column` or `metadata` | Uses `group_id`, `session_id`, or `video_id` from the optional metadata CSV. |
| `none` | Context is unknown; all assets from that source receive one unknown group. |

For a regex, include a capture group, preferably named `group`:

```yaml
grouping: filename-regex
group_pattern: "(?P<group>session_[0-9]+)"
```

If a regex or metadata strategy cannot find a group, the asset is assigned to `<source-id>:unknown`. Unknown assets are **not** assumed independent; they stay together to avoid leakage.

Optional per-image metadata CSV:

```csv
relative_path,session_id,environment_tags
images/frame_0001.jpg,walk_01,outdoor|night|crosswalk
images/frame_0002.jpg,walk_01,outdoor|night|crosswalk
```

The required column is `relative_path`. Optional grouping columns are `group_id`, then `session_id`, then `video_id`. `environment_tags` uses `|` between multiple tags. Paths must be safe relative paths with no `..`.

Point to it from the source entry:

```yaml
metadata_file: metadata.csv
grouping: metadata-column
```

When per-image tags are missing, `environment_tags` from the source entry are used. If nobody knows the environment, use `unknown`; do not invent context.

### Step 7A: configure a raw video source

Use this when a raw source contains videos paired with CSV annotations. The configured video extensions default to `.avi`, `.mp4`, `.mov`, and `.mkv`; the actual codec must also be readable by the installed OpenCV build.

Example raw layout with each CSV beside its video:

```text
raw/<provider>/<source-id>/
|-- crosswalk.avi
|-- crosswalk.csv
|-- night.avi
`-- night.csv
```

Example source configuration:

```yaml
- id: pedestrian_video_source
  annotation_format: yolo
  class_names: [pedestrian]
  class_mapping:
    0: person
  environment_tags: [outdoor]
  grouping: none  # extracted frames still use their source video as the automatic group
  video_extraction:
    enabled: true
    video_extensions: [.avi, .mp4, .mov, .mkv]
    annotation_pattern: "{stem}.csv"
    annotation_format: csv
    coordinate_format: xywh_pixels
    frame_column: frame
    frame_index_base: 0
    class_column: class_id
    default_class_id: null
    x_column: x
    y_column: y
    width_column: w
    height_column: h
```

If CSVs are in a labels folder, use:

```yaml
annotation_pattern: "labels/{stem}.csv"
```

An explicit frame column supports multiple objects in one frame:

```csv
frame,class_id,x,y,w,h
0,0,100,80,50,120
0,0,300,75,48,118
1,0,104,82,51,121
```

If the CSV has exactly one row per video frame and no frame column, set `frame_column: null`. Row 0 is then frame 0, row 1 is frame 1, and so on. This row-order form cannot represent multiple objects in one frame; it matches the old pedestrian-video notebook.

If every object is one source class and the CSV has no class column, set `class_column: null` and `default_class_id: 0`.

| `coordinate_format` | CSV interpretation | Default columns |
| --- | --- | --- |
| `xywh_pixels` | Top-left X/Y and pixel width/height | `x`, `y`, `w`, `h` |
| `xyxy_pixels` | Minimum X/Y and maximum X/Y | `x`, `y`, `xmax`, `ymax` |
| `yolo_normalized` | Normalized center X/Y and width/height | `x`, `y`, `w`, `h` |

Column names can be changed with `x_column`, `y_column`, `width_column`, `height_column`, `x_max_column`, and `y_max_column`. Set `frame_index_base: 1` if the CSV numbers its first frame as 1.

The extraction is deliberately safe:

- raw videos and CSVs are never edited or moved;
- output is staged beneath the run workspace before acceptance;
- only frames with at least one CSV annotation are exported;
- every exported frame receives a matching standard YOLO label;
- multiple CSV rows for a frame become multiple YOLO rows;
- a CSV reference to a nonexistent frame fails that source;
- video path, video SHA-256, frame index, frame hash, and group are recorded;
- all frames from one video automatically receive one non-splittable group, regardless of the source's normal `grouping` setting.

Raw-video extraction currently accepts CSV annotations only. Other video label formats need a separate explicit adapter and are not guessed.

### Step 8: run a cheap sample first

Use:

```yaml
mode: sample
max_assets_per_source: 100
```

The selection is deterministic for a source and seed. Sample mode runs the same stages as full mode, but on fewer registered images. It is intended to expose bad mappings, incorrect paths, and format problems cheaply.

Run from the repository root:

```powershell
python .\ML_side\tools\run_data_pipeline.py run `
  --config .\ML_side\config\dataset_v4\data_pipeline.yaml
```

Check status at any time:

```powershell
python .\ML_side\tools\run_data_pipeline.py status `
  --config .\ML_side\config\dataset_v4\data_pipeline.yaml
```

### Step 9: complete human review

The run workspace name is `<release-id>-<12-character fingerprint>`. Look inside:

```text
datasets/pipeline_workspace/<run-id>/review/
|-- near_duplicates/<cluster-id>/
|-- quality/<source-id>/<asset-id>/
|-- semantic/<source-id>/
|-- tasks.json
`-- review_decisions.csv
```

The pipeline copies or hard-links review material; it does not modify raw inputs.

Allowed decisions in `review_decisions.csv` are:

| Decision | Typical use | Effect |
| --- | --- | --- |
| `approve` | Quality or semantic sample is acceptable | Resolves that review. |
| `reject` | Image/annotation should not be used | Resolves review and quarantines the asset. |
| `keep` | Keep a candidate in a duplicate review | Resolves review and keeps it. |
| `duplicate` | Candidate is a true duplicate | Resolves review and quarantines it. |
| `not_duplicate` | Candidate is visually similar but legitimately distinct | Resolves review and keeps it. |

Fill the Boolean finding columns when relevant: `incorrect_class`, `missed_objects`, `loose_box`, `tight_box`, and `ambiguous_object`. Add useful notes. Do not change `asset_id`, `review_type`, or `external_task_id`.

Import the decisions with a real reviewer name:

```powershell
python .\ML_side\tools\run_data_pipeline.py review-import `
  --config .\ML_side\config\dataset_v4\data_pipeline.yaml `
  --csv D:\path\to\completed_review_decisions.csv `
  --reviewer "Student Name"
```

Important limitation: importing a local CSV records findings and can approve/reject an asset, but it does not rewrite bounding boxes. To import corrected boxes automatically, enable CVAT, correct the generated CVAT tasks, then run:

```powershell
python .\ML_side\tools\run_data_pipeline.py cvat-sync `
  --config .\ML_side\config\dataset_v4\data_pipeline.yaml `
  --reviewer "Student Name"
```

CVAT sync validates every exported normalized box, replaces the working annotations for reviewed assets, records the reviewer and task ID, and preserves a transformation audit entry.

After importing decisions or syncing CVAT, run the original `run` command again. The same run ID resumes completed checkpoints.

### Step 10: change to a full run

After the sample behaves correctly, change:

```yaml
mode: full
```

Remove `max_assets_per_source`; it is illegal in full mode. This configuration change intentionally creates a different run fingerprint and workspace.

### Step 11: verify the finished release

If `release_id` is `navigation-v4`, the final directory is `datasets/dataset_navigation-v4`.

```powershell
python .\ML_side\tools\run_data_pipeline.py verify `
  --release-dir .\ML_side\datasets\dataset_navigation-v4
```

Verification detects missing files, modified files, malformed checksum rows, and unexpected files. An extra image placed in a split after release therefore fails verification.

## 6. Configuration reference

### Root and identity fields

| Field | User input | Meaning |
| --- | --- | --- |
| `project_root` | Path | Repository/project root used for Git identity. |
| `raw_root` | Path | Parent of provider/source raw directories. |
| `download_sheet` | Path | Shared authoritative source registry. Recommended for real runs. |
| `workspace_root` | Path | Checkpoints, standardized files, and review material. |
| `invalid_root` | Path | Quarantine evidence. |
| `output_root` | Path | Parent of final `dataset_<release-id>`. |
| `release_id` | Text | Safe release name using letters, numbers, `.`, `_`, and `-`. |
| `seed` | Integer | Reproducible sample, split, review, and augmentation behavior. |
| `mode` | `sample` or `full` | Cheap trial or complete intake. |
| `max_assets_per_source` | Positive integer | Required only for sample mode. |

### Taxonomy and release YAML

| Field | User input | Meaning |
| --- | --- | --- |
| `taxonomy_version` | Version text | Records the semantic version of the class system. |
| `taxonomy` | Ordered list | Authoritative final class names and YOLO ID order. |
| `dataset_yaml.mode: generate` | Switch | Generate final `data.yaml` from `taxonomy`. Best default. |
| `dataset_yaml.mode: supplied` | Switch + `path` | Validate and copy a user-supplied YAML. Names/order and internal paths must match. |
| `dataset_yaml.mode: none` | Switch | Omit training YAML for an audit/package-only release. |

A supplied YAML must use `path: .`, `train: images/train`, `val: images/val`, and `test: images/test`. Its names and optional `nc` must exactly match the configured taxonomy.

### Processing and gate fields

| Field | Valid/default behavior |
| --- | --- |
| `splits` | Non-negative train/val/test values totaling exactly `1.0`; default 0.70/0.20/0.10. |
| `image_format` | `JPEG` or `PNG`. |
| `jpeg_quality` | 1–100; used only for JPEG. |
| `near_duplicates_enabled` | Enables standardized-image dHash candidate generation. |
| `near_duplicate_distance` | 0–64 and no greater than review distance; marks high-confidence statistics but still requires review. |
| `near_duplicate_review_distance` | 0–64; candidate search radius. |
| `imbalance_ratio` | Must be greater than 1; 4.0 means largest:smallest training class must be at most 4:1. |
| `distribution_drift_threshold` | 0–1 total-variation threshold against training distribution. |
| `qa_sample_per_source` | Number of unique semantic QA images per source; 0 disables semantic sampling. |
| `empty_after_mapping_policy` | `retain_negative` keeps an image whose objects were all deliberately excluded; `quarantine` rejects it. |
| `cvat.enabled` | Creates live CVAT tasks when true; creates local review packages when false. |
| `cvat.project_name` | Prefix used for generated CVAT task names. |

### Source processing fields

| Field | Required? | Meaning |
| --- | --- | --- |
| `id` | Yes | Must exactly match a `download_sheet.yaml` dataset ID. |
| `annotation_format` | Strongly recommended | `auto`, `yolo`, `coco`, `voc`, or `pascal_voc`. |
| `annotation_file` | COCO only | JSON path relative to that raw source folder. |
| `metadata_file` | Optional | CSV path relative to that raw source folder. |
| `class_names` | VOC; useful documentation elsewhere | Source class order. |
| `class_mapping` | Effectively required for labelled classes | Original numeric ID to final taxonomy name or `null`. |
| `environment_tags` | Optional | Source-level fallback tags; defaults to `unknown`. |
| `grouping` | Yes in practice | `dataset`, `folder`, `filename-regex`, `metadata-column`, `metadata`, or `none`. |
| `group_pattern` | Regex grouping only | Pattern with a named or positional capture group. |
| `video_extraction` | Raw-video sources only | Enables staged video/CSV-to-frame conversion before intake. |

## 7. What happens at every pipeline stage

### 7.1 Configuration and run identity

The loader validates all user choices before data processing. A run ID includes the release ID and a fingerprint of the processing config, download sheet, random seed, and every Python file in the pipeline package. Editing code or config creates a new run instead of incorrectly resuming old results.

The database records the Git commit, whether the working tree was dirty, code/config/download-sheet hashes, Python/platform information, and detected library versions.

### 7.2 Layout initialization

The program creates roots, provider folders, selected source folders, per-run standardized/label folders, three review areas, and a per-run quarantine root. Existing directories are accepted; a file where a directory should be is an error.

It deliberately does not create the final release folder yet.

### 7.3 Collection

- An existing non-empty raw source folder is retained.
- An empty source folder is only a destination placeholder.
- Downloads occur into a temporary sibling folder.
- ZIP members are checked for path traversal before extraction.
- The temporary folder replaces the empty placeholder only after collection succeeds.
- Manual/unsupported providers report that files must be placed manually.

One source can fail collection while other source loops continue. Release remains blocked until active failures are fixed in an appropriate new run/configuration.

### 7.4 Raw-video extraction

For an enabled video source, extraction occurs between collection and intake. It discovers configured video extensions recursively, resolves each CSV through `annotation_pattern`, validates its rows, opens the video through OpenCV, and writes only annotated frames into:

```text
pipeline_workspace/<run-id>/extracted/<source-id>/
|-- images/<video-path>/<video-stem>_<frame-index>.jpg
|-- labels/<video-path>/<video-stem>_<frame-index>.txt
|-- metadata.csv
`-- video_extraction.json
```

Pixel or normalized CSV boxes become normalized YOLO center boxes. Generated metadata carries the source video, frame index, video hash, and automatic video group into intake and the final lineage manifest.

### 7.5 Intake and provenance

Supported image extensions are JPG/JPEG, PNG, BMP, WebP, TIFF, and TIF. Each image receives a deterministic UUID v5 based on source ID, relative path, and original SHA-256. The database stores original filename/path, raw image and paired label paths, source, hash, tags, optional group, and time.

Paired labels are found beside an image or by replacing an `images` path segment with `labels`, using `.txt` or `.xml`.

### 7.6 Exact duplicate detection

Original-file SHA-256 values are grouped globally. One deterministic representative is kept, preferring an asset with a label. Other copies are marked and copied/hard-linked into quarantine under `exact_duplicate`. Raw source files remain in place.

This occurs before expensive standardization and conversion.

### 7.7 Structure validation

The program checks supported annotation formats and required labels. COCO requires its configured JSON file; non-COCO images without paired annotations are quarantined. If some assets remain, a partially invalid source produces a warning. If none remain, that source fails.

### 7.8 Image standardization

Pillow fully loads the image, records the original geometry and EXIF orientation, applies EXIF transpose, converts to RGB, and writes a JPEG or PNG under the run workspace using an atomic temporary file. It does not resize images.

Unreadable images are quarantined. The output hash and transformation parameters are recorded.

### 7.9 Annotation conversion and cleaning

The converter reads annotations against the original image geometry, transforms the boxes through the EXIF orientation, then validates them against the final standardized geometry. This ordering prevents the coordinate-basis problem that occurs when annotations are normalized before geometry changes.

It supports:

- normalized YOLO center boxes;
- normalized YOLO polygons, converted to enclosing boxes;
- Pascal VOC XML boxes;
- COCO pixel `bbox` records; `iscrowd` records are skipped.

Coordinates must be finite and boxes must have positive size. A maximum one-pixel boundary error may be clamped and counted as repaired; larger out-of-bounds errors are rejected. Every encountered source class needs an explicit mapping decision.

Outputs are normalized YOLO center rows with eight decimal places. Invalid assets are quarantined with a recorded rejection transform.

### 7.10 Logical merge

Sources are merged in the SQLite catalogue by UUID. There is no risky physical flatten-and-rename step. The merge gate fails if no annotated assets exist or an accepted record lacks a standardized image or label.

### 7.11 Image-quality inspection

The current automatic flags are:

- width or height below 64 pixels;
- grayscale mean at or below 12 (`very_dark`);
- grayscale mean at or above 243 (`very_bright`);
- entropy below 1.5 (`low_information`);
- edge variance below 4.0 (`possible_blur`).

These are review flags, not automatic semantic judgments. Flagged images and a `quality.json` measurement file are prepared for a human.

### 7.12 Near-duplicate detection

The pipeline computes a 64-bit difference hash (dHash) on standardized grayscale images. A BK-tree efficiently finds images within the configured Hamming distance. Current matching is performed within each source, not across different sources.

Connected candidates become clusters. A deterministic representative is identified, every cluster member is placed in the review folder, and non-representatives receive pending reviews.

The smaller `near_duplicate_distance` currently contributes a high-confidence metric; it does **not** automatically quarantine an image. Human review is required before a suspected near duplicate is removed.

### 7.13 Sequence grouping

The selected strategy assigns every accepted original asset a `group_id`. Groups are indivisible during splitting, which prevents frames from one video/session from leaking across train, validation, and test.

`none` and missing metadata/regex matches are intentionally conservative: all unknown assets of that source share one unknown group.

### 7.14 Semantic QA and CVAT

For each source, sampling first attempts class coverage, then fills the remaining requested amount deterministically. It creates image/label folders and a YOLO annotation ZIP.

- With CVAT disabled, it creates a local task ID and files for manual inspection.
- With CVAT enabled, it creates a CVAT task, uploads images, and imports the initial YOLO labels.

Every sampled asset becomes a pending review. Release cannot continue until it is resolved.

### 7.15 Group-preserving split

The split algorithm never divides a group. It first tries to place rare-class groups so each non-zero split receives coverage, then assigns remaining groups using a combined deviation score for image totals, class counts, source counts, and environment counts. Deterministic SHA-256 tie-breaking uses the configured seed.

Exact ratios cannot always be achieved because groups are indivisible.

### 7.16 Representativeness comparison

Validation and test distributions are compared with training using total variation distance for classes, sources, and environment tags. Values above `distribution_drift_threshold` produce a warning and detailed counts. This is currently a warning, not an automatic resplit loop.

### 7.17 Class balance and augmentation

Balance is measured on training annotation counts. Every taxonomy class must occur in training. The largest non-zero count divided by the smallest must not exceed `imbalance_ratio`.

If the gate fails, augmentation targets only deficit classes in training:

- crop around an object;
- crop plus brightness adjustment;
- crop plus Gaussian blur.

The target minimum is `ceil(largest_class_count / imbalance_ratio)`. A proposed crop is rejected if it also contains a class that no longer has a deficit. This prevents augmentation from continuing to increase already-balanced high classes. Each generated asset records its parent UUID, operation, crop, seed, source, group, and tags.

If a missing/rare class has no safe source examples, augmentation fails and the message asks for additional real data. Validation and test are never augmented.

### 7.18 Release and verification

Release is blocked by unresolved reviews, unapproved/unknown governance, missing licences, or any stage whose latest result is failure.

Files are first copied into a hidden staging directory. The release contains:

```text
dataset_<release-id>/
|-- images/train, images/val, images/test
|-- labels/train, labels/val, labels/test
|-- data.yaml                 # unless mode is none
|-- manifest.json             # complete machine-readable lineage
|-- assets.csv                # convenient sample index
|-- reports/qa_report.json
|-- reports/qa_report.html
`-- checksums.sha256
```

The release is checksummed, verified, updated with the passing integrity result, checksummed again, and verified again before the staging directory is renamed into place. An existing release is never overwritten.

## 8. How the Python files work together

The public call chain is:

```text
tools/run_data_pipeline.py -> data_pipeline/cli.py -> data_pipeline/pipeline.py
                                                    -> all stage modules
```

### `ML_side/tools/run_data_pipeline.py`

Thin public launcher. It adds `ML_side` to Python's import path, imports `data_pipeline.cli.main`, and returns its exit code. Students normally run only this file.

### `data_pipeline/__init__.py`

Marks the directory as a Python package. It currently contains no pipeline logic.

### `data_pipeline/cli.py`

Owns the command-line interface.

- `_parser()` defines `run`, `review-import`, `cvat-sync`, `status`, and `verify` arguments.
- `main(argv)` routes the selected command, prints machine-readable JSON, converts stage outcomes to exit codes, and turns expected user errors into a clean failure response.

### `data_pipeline/config.py`

Loads and validates user configuration.

- `_load_mapping(path)` reads YAML or JSON and requires a top-level object.
- `_path(base, value, field)` validates and resolves a path relative to the config directory.
- `_download_sheet_sources(path)` validates and returns the shared source registry.
- `_registry_folder(...)` safely builds `<raw_root>/<provider>/<folder>` without allowing absolute/parent-escape folder entries.
- `load_config(path)` combines registry facts with processing choices and validates taxonomy, mappings, sources, ratios, modes, thresholds, formats, and dataset-YAML behavior.

### `data_pipeline/models.py`

Defines shared data structures.

- `StageStatus` is the five-value stage outcome enum.
- `StageResult` carries stage name, status, message, optional source, and metrics.
- `VideoExtractionConfig` contains validated raw-video/CSV extraction choices.
- `SourceConfig` is one validated source definition.
- `SourceConfig.target_for(source_class_id)` returns the chosen target name, `None` for deliberate exclusion, or an internal unmapped marker.
- `PipelineConfig` is the complete immutable run configuration.
- `PipelineConfig.release_dir` calculates `output_root/dataset_<release-id>`.
- `PipelineError` represents an expected, user-actionable failure.

### `data_pipeline/layout.py`

Creates safe directory structure.

- `_ensure_directory(path, label)` creates a directory or rejects a conflicting file.
- `initialise_storage_layout(config, run_id)` creates roots, providers, selected source placeholders, run work folders, review folders, and quarantine root without publishing a release.

### `data_pipeline/database.py`

Owns the SQLite checkpoint and audit schema.

- `utc_now()` returns an ISO UTC timestamp.
- `PipelineDatabase.__init__(path)` opens/creates SQLite, enables foreign keys and WAL mode, and creates/migrates schema.
- `close()`, `__enter__()`, and `__exit__()` provide safe context-manager use.
- `transaction()` supplies a database transaction context.
- `_create_schema()` creates the tables and indexes.
- `_ensure_column(...)` performs additive schema migration for older databases.
- `record_stage(...)` appends a stage outcome and metrics.
- `add_transform(...)` appends an asset transformation with hashes and parameters.
- `rows(query, parameters)` returns query results as named rows.

The main tables are `runs`, `sources`, `assets`, `annotations`, `transformations`, `stage_results`, `duplicate_candidates`, and `reviews`.

### `data_pipeline/collection.py`

Gets source files into raw storage.

- `_safe_extract(archive, destination)` rejects ZIP path traversal before extraction.
- `_download_source(source, destination)` implements direct URL, Kaggle, Hugging Face, and Roboflow adapters; unsupported/manual providers require manual file placement.
- `collect_source(...)` retains an existing non-empty source or safely stages a new download and records its outcome.

### `data_pipeline/intake.py`

Registers provenance and stable identities.

- `_paired_label(image, source_root)` searches beside the image and in a parallel `labels` tree.
- `_asset_id(source_id, relative_path, digest)` creates a deterministic UUID v5.
- `_source_metadata(source)` validates and loads the optional metadata CSV.
- `initialise_run(...)` records reproducibility information for a new run.
- `register_source(...)` stores source/provenance/governance facts.
- `ingest_source(...)` discovers images, optionally selects a deterministic sample, attaches labels/metadata, and registers assets.
- `run_id_for(config, config_path)` fingerprints release ID, seed, config, download sheet, and code.

### `data_pipeline/video_extraction.py`

Converts configured video/CSV sources into traceable image/YOLO pairs before normal intake.

- `VideoAnnotation` stores one original CSV annotation and its frame/class IDs.
- `extracted_source_root(...)` returns the deterministic per-run extracted-source folder.
- `extracted_metadata_path(...)` returns its generated metadata CSV path.
- `_annotation_path(...)` safely resolves the configured sidecar CSV inside the raw source.
- `_load_csv_annotations(...)` validates CSV columns, indices, classes, and numeric coordinates and groups rows by frame.
- `_normalise_annotation(...)` validates and converts pixel XYWH, pixel XYXY, or normalized YOLO input into normalized YOLO center form.
- `_iter_video_frames(...)` opens a video with OpenCV and yields RGB Pillow frames with zero-based indices.
- `extract_video_source(...)` stages paired files, metadata, and audit JSON; preserves failure evidence; and records metrics.

### `data_pipeline/deduplication.py`

Implements exact and perceptual duplicate stages.

- `exact_duplicates(...)` groups original SHA-256 values, keeps one deterministic representative, and quarantines other copies.
- `difference_hash(image_path, hash_size=8)` computes dHash.
- `hamming_distance(left, right)` counts different hash bits.
- `_BKNode` stores dHashes in a BK-tree; `add()` inserts and `query()` searches within a radius.
- `near_duplicates(...)` searches standardized images per source, creates connected candidate clusters, copies review evidence, and creates pending decisions.

### `data_pipeline/validation.py`

- `validate_source_structure(...)` checks annotation format requirements and image/label pairing, quarantining unsupported or unlabelled assets.

### `data_pipeline/standardization.py`

- `standardize_images(...)` loads images, applies EXIF orientation, converts to RGB JPEG/PNG without resizing, records final geometry/hashes, and quarantines unreadable data.

### `data_pipeline/annotations.py`

Parses, validates, transforms, maps, and writes boxes.

- `PixelBox` represents a source box in pixel corner coordinates.
- `_validate_box(...)` rejects non-finite, invalid, or substantially out-of-bounds boxes and clamps at most a one-pixel edge error.
- `parse_yolo(...)` parses normalized boxes or polygons.
- `parse_voc(...)` parses Pascal VOC XML using configured source class names.
- `load_coco(...)` indexes COCO boxes by image filename and skips crowds.
- `_transform_point(...)` applies an EXIF orientation transform to one point.
- `transform_orientation(...)` transforms all box corners and rebuilds the enclosing box.
- `convert_annotations(...)` performs parsing, explicit taxonomy mapping, final-geometry validation, normalized YOLO output, negative handling, quarantine, and audit logging.

### `data_pipeline/merging.py`

- `merge_source_catalogue(...)` validates and logically combines accepted UUID assets without physically flattening raw folders.

### `data_pipeline/quality.py`

- `inspect_quality(...)` measures dimensions, brightness, entropy, and edge variance, then creates human-review records for suspicious images.

### `data_pipeline/grouping.py`

- `assign_groups(...)` applies the configured dataset/folder/regex/metadata/unknown grouping rule and writes non-splittable group IDs.

### `data_pipeline/cvat_review.py`

Prepares semantic annotation review.

- `_sample_assets(rows, amount, seed)` chooses unique images with initial class coverage and deterministic random fill.
- `_annotation_zip(sample, taxonomy, destination)` builds a YOLO 1.1 import archive.
- `prepare_cvat_review(...)` creates per-source local review packages or live CVAT tasks and records pending reviews.

### `data_pipeline/reviews.py`

Imports human judgments.

- `ALLOWED_DECISIONS` defines the five accepted decision strings.
- `import_review_csv(...)` validates the CSV, records reviewer/findings/time, quarantines rejected/duplicate assets, and updates duplicate candidates.
- `unresolved_review_count(...)` counts pending items that have no later matching resolution.

### `data_pipeline/cvat_sync.py`

Imports corrected annotations from completed live CVAT tasks.

- `_safe_extract(...)` safely extracts CVAT's ZIP export.
- `_validated_rows(path, class_count)` strictly validates reviewed YOLO box rows and final class IDs.
- `sync_cvat_reviews(...)` exports each CVAT task, validates labels, replaces working annotation records/files, logs lineage, and records reviewer approval.

### `data_pipeline/splitting.py`

- `SPLITS` is the fixed train/val/test tuple.
- `_stable_tie(seed, group_id, split)` creates deterministic tie-breaking values.
- `assign_splits(...)` seeds rare-class coverage and then assigns intact groups while balancing size, class, source, and environment distributions.

### `data_pipeline/representativeness.py`

- `_distance(left, right)` calculates total variation distance between two count distributions.
- `compare_split_distributions(...)` compares validation/test with training for class, source, and environment balance and records warnings/counts.

### `data_pipeline/balance.py`

- `class_counts(...)` counts annotations globally or for one split, including augmentations.
- `check_balance(...)` requires every taxonomy class in training and enforces the configured largest-to-smallest ratio.

### `data_pipeline/augmentation.py`

- `_crop_bounds(...)` makes a randomized crop around an anchor annotation.
- `augment_training_balance(...)` creates only the deficit-class train crops/brightness/blur variants, avoids already-balanced classes, and records parent lineage.

### `data_pipeline/quarantine.py`

- `quarantine_asset(...)` changes asset status, records the reason, and normally copies/hard-links raw image/label evidence plus `quarantine.json` into the invalid tree.

### `data_pipeline/reporting.py`

- `build_report(...)` gathers image/annotation/class/split/source/environment counts, quarantine reasons, duplicate clusters, sequence groups, reviews, stage metrics, and governance status.
- `write_report(...)` writes both machine-readable JSON and a readable HTML summary.

### `data_pipeline/release.py`

Builds and verifies the immutable deliverable.

- `_write_dataset_yaml(...)` generates Ultralytics-style paths and names from the taxonomy.
- `_load_supplied_dataset_yaml(...)` validates a user-supplied YAML before copying it.
- `_lineage_manifest(...)` creates end-to-end per-sample provenance, transformation, parent, group, split, and review history.
- `_write_assets_csv(...)` writes a convenient flat index from the manifest.
- `_write_checksums(...)` hashes every approved release file except the checksum file itself.
- `verify_release(...)` detects missing, unexpected, modified, or malformed entries.
- `build_release(...)` enforces reviews/governance/gates, stages files, writes metadata/reports, verifies twice, and atomically publishes without overwriting.

### `data_pipeline/utils.py`

Small shared safety/reproducibility helpers.

- `sha256_file(...)` streams a SHA-256 file digest.
- `json_dump(...)` atomically writes sorted, indented JSON.
- `copy_or_link(...)` prefers a hard link, falls back to a metadata-preserving copy, and refuses to overwrite different content.
- `runtime_versions(...)` records Python/platform and optional module versions.
- `git_sha(...)` returns the current Git commit when available.
- `git_is_dirty(...)` reports whether tracked/untracked working changes exist.
- `directory_fingerprint(...)` hashes filenames and contents of pipeline Python files.
- `safe_relative(path, root)` proves a path stays inside its expected root.

### `data_pipeline/pipeline.py`

The orchestrator. It is the only module that decides stage order.

- `database_path(config, run_id)` locates the run's SQLite checkpoint.
- `_has_stage(...)` checks whether a source/global stage has a latest non-failure result.
- `_has_any_stage(...)` checks whether any result for a stage exists.
- `_write_review_queue(...)` creates the editable CSV from pending reviews without overwriting a populated queue.
- `execute(config_path)` loads config, creates the run/layout, runs or resumes all stages, pauses for reviews, applies split/balance/augmentation gates, and builds the release.

### `data_pipeline/requirements.txt`

Not Python code, but part of the package: required Pillow/PyYAML versions and comments listing optional provider/CVAT adapters.

### `ML_side/tests/test_data_pipeline.py`

Automated tests for the new pipeline's critical contracts. It is for developers and continuous verification, not a pipeline stage. Run it after changing pipeline code:

```powershell
python -m unittest discover -s ML_side/tests -p test_data_pipeline.py
```

Other Python tools under `ML_side/tools` serve model evaluation, candidate-dataset inspection, older release-building, or manifest validation workflows. They are not called by `data_pipeline/pipeline.py`; do not assume they are stages of this pipeline merely because they are also `.py` files.

## 9. Checkpoints, reruns, and safe deletion

The checkpoint is:

```text
datasets/pipeline_workspace/<run-id>/pipeline.sqlite3
```

Re-running the exact same code and config produces the same run ID and skips completed stages. A stage with a latest `fail` result may run again, but edits that change config or code normally produce a new run ID.

| Item | Safe to delete? |
| --- | --- |
| `data_pipeline/__pycache__` | Yes; Python recreates it. |
| An unused example YAML/JSON | Yes, if no command/script points to it; examples are not generated state. |
| `pipeline_workspace/<run-id>` | Only when intentionally abandoning that run; resume/audit data is lost. |
| `invalid/<run-id>` | Not a cache; keep for audit unless retiring the run deliberately. |
| Raw source folders | No during an active/audited release; they are original evidence. |
| `dataset_<release-id>` | No; it is the release. |
| `checksums.sha256`, `manifest.json`, reports, or `assets.csv` | No; each is part of the verified release allow-list. |

Do not edit files inside a published release. Create a new release ID and rerun instead.

## 10. Common failures and what the student should do

### “PyYAML is required”

Install `requirements.txt` using the same Python interpreter used to run the command.

### “Source is not defined in download_sheet”

The source `id` in the pipeline config must exactly match a key under `download_sheet.yaml -> datasets`.

### “Provenance fields must come from download_sheet”

Remove provider/URL/version/folder/licence/status fields from the source entry in the processing config. Keep them only in the download sheet.

### Collection fails for a manual source

Place the source files in the provider/source raw folder created by the layout stage, then rerun. A non-empty folder is retained.

### “Source class N has no explicit mapping decision”

Inspect the source's real class definition. Add class `N` to `class_mapping` with a final taxonomy name or `null`. Do not guess.

### Many assets are quarantined as `missing_annotation`

Check whether labels are beside images or in a parallel `labels` directory, and whether `annotation_format` is correct. COCO requires `annotation_file` instead of per-image label files.

### All unknown images go into one split

That is intentional leakage protection. Supply session/video metadata, a useful folder hierarchy, or a filename regex if the items are genuinely independent groups.

### The run stops at `review_required`

Inspect all generated review folders and the CSV/CVAT tasks. Import completed decisions, then rerun the same command.

### Balance still fails after augmentation

The pipeline could not create enough safe deficit-only examples. Collect or label more real data for the named classes. Do not lower the standard without documenting and approving that decision.

### Split representativeness warns

Read the class/source/environment count comparison in the stage metrics and final report. Because groups cannot be broken, the appropriate action may be better source collection or different valid grouping—not forcing individual frames across splits.

### Release directory already exists

The pipeline never overwrites releases. Verify the existing release or choose a new `release_id`. Do not delete a legitimate release merely to reuse its name.

### Verification reports an unexpected file

Remove the accidental addition only if it is truly not part of the release, or create a new governed release that includes it. Every approved release file must appear in `checksums.sha256`.

## 11. Final pre-release checklist

- [ ] Every selected source exists in `download_sheet.yaml`.
- [ ] Every licence and governance status was checked by a person.
- [ ] `release_id` and `taxonomy_version` describe a new release.
- [ ] Taxonomy names and order are correct.
- [ ] Every possible source class has an explicit keep/remap/exclude decision.
- [ ] Annotation formats and COCO paths are correct.
- [ ] Every raw video has the expected CSV, coordinate convention, frame numbering, and class-ID convention.
- [ ] Sequence grouping uses real metadata, folders, or a verified regex where possible.
- [ ] Unknown environment information is marked `unknown`, not invented.
- [ ] A deterministic sample run succeeded first.
- [ ] Near-duplicate, quality, and semantic reviews have named reviewers and notes.
- [ ] Corrected CVAT labels were synced when boxes/classes changed.
- [ ] The full run completed with no active failed gates or pending reviews.
- [ ] Training balance is at or below the chosen threshold.
- [ ] Distribution warnings were inspected.
- [ ] Final JSON/HTML reports were read.
- [ ] Final checksum verification passes with no unexpected files.
- [ ] Raw inputs, run database, quarantine evidence, and final release are retained.

## 12. Short glossary

- **Asset**: one registered image and its associated metadata/label.
- **UUID**: stable identifier used instead of collision-prone filenames.
- **Provenance**: where data came from, under what licence, and in which original file.
- **Lineage**: provenance plus every later transformation, review, split, and augmentation relationship.
- **Quarantine**: excluded data preserved with a reason for audit; not silent deletion.
- **Exact duplicate**: byte-identical image based on SHA-256.
- **Near duplicate**: visually similar image based on perceptual dHash, requiring human review.
- **Group**: assets that must remain in the same split, such as frames from one video.
- **Taxonomy**: the final ordered set of model classes.
- **Class mapping**: an explicit decision from an original source class ID to a final class or exclusion.
- **Checkpoint**: stored stage state that allows a run to resume.
- **Release gate**: condition that must pass before publishing the dataset.
- **Manifest**: machine-readable end-to-end lineage for every released sample.

When in doubt, do not guess a class, licence, sequence identity, or semantic annotation. Record the uncertainty, ask the dataset owner, and keep the evidence traceable.
