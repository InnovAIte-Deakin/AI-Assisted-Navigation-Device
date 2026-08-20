# Controlled navigation-model training

`train_navigation_model.py` is the local-only foundation for a future WalkBuddy navigation-model candidate. It does not establish model quality, legal approval, privacy compliance, or production readiness.

## Inputs and eligibility

Start from [`../config/training_navigation_mvp.yaml`](../config/training_navigation_mvp.yaml), then use a reviewed local copy. The configuration must reference a repository-relative manifest and local model architecture (`.yaml`/`.yml`) or initial weights (`.pt`), never a URL or a bare Ultralytics model identifier. Exactly one model source is required.

The manifest must pass the bundled validator with `--check-files` semantics, use the approved eight-class taxonomy, have `dataset.release_decision: approved_for_training`, and record an approved licence review that permits machine-learning use. Of the manifest decisions, only `approved_for_training` is accepted; `draft`, `under_review`, `rejected`, `retired`, and `example_only` are rejected. The configuration stage must be `approved_for_internal_training` or `released`; `candidate`, `in_review`, and `rejected` are deliberately ineligible. The YOLO YAML must use the exact same ordered taxonomy and physically contain each manifest sample beneath its declared split. If an inspection report is supplied, its verdict must not be `fail`.

By default, `dataset.manifest_path` remains a repository-relative configuration field. An approved release kept in controlled external storage may instead be supplied at runtime with `--manifest-path`. The override accepts only an existing regular local `.json` file; URLs, URIs, UNC paths, missing files, and non-JSON files are rejected. The manifest is not copied, and preflight still performs full file validation against `--dataset-root`. Persisted run records keep its checksum and the sanitised `external-local/manifest.json` reference rather than the caller's absolute path.

The versioned configuration records the experiment name; manifest/YAML references; explicit stage; exactly one local model source; epochs, image size, batch, device, workers, seed, optimiser, learning rate, confidence, IoU, deterministic preference, resume behaviour, output root, and notes. Unknown fields are rejected. Epochs, image size, batch, and seed are positive non-boolean integers, while workers is a non-negative non-boolean integer so that zero selects main-process data loading; learning rate, confidence, and IoU are finite non-negative numbers. Device values are deliberately limited to `cpu`, `auto`, `mps`, `cuda`, `cuda:<index>`, or a numeric GPU index. Dataset roots are intentionally supplied at execution with `--dataset-root` rather than committed.

## Immutable release and mutable training workspace

An approved released dataset is read-only evidence. Ultralytics writes label
cache files such as `labels/train.cache` beside each label directory whenever it
loads a dataset, and the `cache` training argument does not disable that
behaviour, so pointing a trainer at the authoritative release would modify it.

Preflight therefore rejects an external `--manifest-path` whose manifest sits
inside the supplied `--dataset-root` when the configured stage is `released`.
Both `--dry-run` and confirmed training share this gate, so a run that passes
preflight cannot fail the isolation contract later.

Before real training, create a mutable local copy of the release and pass the
copy as the dataset root while keeping the authoritative manifest:

```powershell
& "C:\path\to\python.exe" ".\ML_side\training\train_navigation_model.py" --config ".\ML_side\config\training_navigation_smoke.yaml" --dataset-root "C:\path\to\mutable-training-workspace" --manifest-path "C:\path\to\WalkBuddy-Controlled-Releases\...\release_manifest.json" --dry-run
```

The wrapper does not create, copy, link, or mutate that workspace. Preparing it
is a deliberate, explicit step performed outside the tool. Full
`validate_manifest(..., check_files=True)` validation still runs against the
workspace, so an incomplete or misplaced copy fails before training starts.

Note that the manifest contract verifies sample presence and structure rather
than per-file content hashes, so workspace fidelity beyond file existence is not
established by this check alone.

## Working-directory independence

The approved dataset YAML may declare a relative `path` such as `.`. Ultralytics
resolves that against the process working directory rather than against the YAML
file, so a relative root would otherwise make training depend on where the tool
was invoked.

For confirmed training the tool writes an ephemeral trainer-only dataset
descriptor into a temporary directory, identical to the approved YAML except
that `path` is the absolute root already resolved by preflight. The approved YAML
is never modified, the temporary file is never written inside the dataset, and it
is removed after the trainer succeeds or fails. Persisted metadata continues to
record the sanitised original dataset reference, not the temporary descriptor.

## Failure metadata sanitisation

Third-party trainer exceptions can embed absolute local paths. Before a failure
is persisted, known locations are replaced with `<dataset-root>`,
`<external-manifest>`, `<repository-root>`, `<run-directory>`, and
`<runtime-dataset>`, in both backslash and forward-slash spellings, and any
residual absolute path is replaced with `<local-path>`. Enough of the message
survives to identify the failure. Console output is unchanged for the local
operator.

## Dry run

Use an existing controlled local dataset root. The root is not recorded in output metadata.

```powershell
python .\ML_side\training\train_navigation_model.py `
  --config .\ML_side\config\training_navigation_mvp.yaml `
  --dataset-root D:\controlled-datasets\navigation-mvp-v1 `
  --dry-run
```

A dry run validates configuration, manifest, local dataset files, YAML, model file, eligibility, output safety, and any inspection evidence. It creates no run directory, weights, or trainer output and never imports or invokes Ultralytics.

## Explicit real training

Real training is blocked unless `--confirm-training` is supplied; combining it with `--dry-run` is rejected. It uses only an existing local model path, sets `YOLO_OFFLINE=true` and disables Weights & Biases mode before the trainer is imported, and does not download datasets or weights. A remote URL, URI, traversal attempt, absolute path in the committed configuration, or missing local file fails preflight. These safeguards do not claim to prove that every future Ultralytics version suppresses all telemetry.

```powershell
python .\ML_side\training\train_navigation_model.py `
  --config .\local-training-navigation-mvp.yaml `
  --dataset-root D:\controlled-datasets\navigation-mvp-v1 `
  --confirm-training
```

The harmless `--epochs`, `--batch-size`, `--device`, `--workers`, and repository-relative `--output-root` overrides are recorded in the resolved plan. Existing run directories are protected unless `--allow-existing-run` and the configured resume policy permit reuse.

## Smoke controls

`training.fraction` is optional and defaults to `1.0`; it must be greater than zero and no greater than one, and is forwarded to Ultralytics unchanged. `training.val` is optional and defaults to `true`. The reviewable [`../config/training_navigation_smoke.yaml`](../config/training_navigation_smoke.yaml) keeps the MVP template untouched and uses one epoch, `fraction: 0.002` (about 49 of 24,480 training images), and `val: false` to prove the train path without turning a smoke run into a full validation pass. It requires a separately supplied, trusted local `ML_side/models/yolo26n.pt` checkpoint and an external `--manifest-path`; neither is downloaded by this tool.

## Artifacts and reproducibility

Real runs write ignored artifacts under `ML_side/artifacts/navigation_mvp/<run-id>/`: `run_metadata.json`, `resolved_training_config.json`, `dataset_reference.json`, `training_summary.md`, and any trainer output. Metadata files are replaced atomically where supported. Metadata records checksums, the fixed taxonomy, dataset release stage/version, Git commit/dirty state, seed, parameters, package versions, Python/OS information, status, and failure summary. It deliberately omits the absolute dataset root, credentials, and environment dumps. A trainer failure is recorded as failed and leaves partial trainer output for investigation; it is never marked successful.

The run ID is stable for unchanged configuration, manifest, dataset YAML, and local model file checksums. A completed run is therefore not silently overwritten.

## Verification

```powershell
$env:PYTHONPATH = (Resolve-Path .\ML_side).Path
python -m pytest .\ML_side\tests\test_train_navigation_model.py -q
python -m pytest .\ML_side\tests -q
python .\ML_side\training\train_navigation_model.py --help
```

Keep datasets, weight files, and generated artifacts in controlled external storage. Dataset inspection precedes this pipeline; formal evaluation of a trained candidate remains a separate later step.
