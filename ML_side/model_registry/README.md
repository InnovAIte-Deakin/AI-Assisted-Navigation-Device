# WalkBuddy Model Registry

## Purpose

This folder provides a version-controlled workflow for registering and managing WalkBuddy object-detection models.

The registry records each model's identity, architecture, supported taxonomy, source dataset release, training lineage, artifact reference, SHA-256 checksum, evaluation evidence, lifecycle status and known limitations.

The workflow also controls when a model may be promoted, rejected, deprecated or rolled back. Promotion is blocked when required lineage or evaluation evidence is missing.

Large model-weight files are not stored in Git. Model records reference model artifacts using filenames, approved storage locations and SHA-256 checksums.

---

## Folder Structure

```text
model_registry/
├── README.md
├── schema/
│   └── model.schema.json
├── records/
│   ├── legacy_baseline.json
│   └── navigation_candidate.json
├── tools/
│   ├── validate.py
│   └── transition.py
└── tests/
    ├── test_validation.py
    └── test_transitions.py
```

---

## Model Metadata

Each registered model contains the following information:

* model ID
* model version
* model name
* architecture
* framework
* task type
* taxonomy ID
* supported class list
* source dataset release ID
* dataset manifest reference
* training date
* training configuration reference
* model artifact filename
* approved artifact location
* SHA-256 checksum
* evaluation evidence reference
* lifecycle status
* known limitations

---

## WalkBuddy MVP Taxonomy

The approved WalkBuddy MVP object-detection taxonomy contains eight classes:

1. `person`
2. `stairs`
3. `door`
4. `chair`
5. `table`
6. `pole`
7. `bicycle`
8. `vehicle`

The class IDs must be verified against the actual dataset and model configuration before training or deployment. The class order must not be assumed without checking the dataset configuration.

---

## Lifecycle Statuses

The registry supports the following lifecycle states:

* `experimental`
* `candidate`
* `production`
* `rejected`
* `deprecated`
* `rolled_back`

The allowed transitions are:

```text
experimental -> candidate
experimental -> rejected

candidate -> production
candidate -> rejected

production -> deprecated
production -> rolled_back

deprecated -> rolled_back
```

Transitions that are not listed above are rejected by the transition tool.

For example, a model cannot move directly from `experimental` to `production`.

---

## Promotion Requirements

### Experimental to Candidate

Before an experimental model may be promoted to `candidate`, the following lineage information must be present:

* dataset release ID
* dataset manifest reference
* training date
* training configuration reference
* model artifact filename
* approved artifact location
* SHA-256 checksum

If any of these fields are missing, candidate promotion is blocked.

### Candidate to Production

Before a candidate model may be promoted to `production`, all candidate requirements must be complete.

The model must also include:

* evaluation evidence reference

If required lineage or evaluation evidence is missing, production promotion is blocked.

---

## Model Validation

The metadata validator checks a model record against the JSON schema.

From the repository root, run:

```bash
python ML_side/model_registry/tools/validate.py ML_side/model_registry/records/navigation_candidate.json
```

A valid record will return a message similar to:

```text
Valid model record: ML_side/model_registry/records/navigation_candidate.json
```

If the record does not follow the required schema, the validator reports the invalid or missing fields.

The validator checks requirements including:

* required metadata sections
* valid lifecycle status
* required object structure
* SHA-256 checksum format
* allowed values defined by the schema

---

## Lifecycle Transitions

Use the transition tool to change a model's lifecycle status.

General command:

```bash
python ML_side/model_registry/tools/transition.py <model-record.json> <target-status>
```

Example:

```bash
python ML_side/model_registry/tools/transition.py ML_side/model_registry/records/navigation_candidate.json candidate
```

If the required lineage information is incomplete, the transition is blocked.

Example:

```text
Promotion blocked: experimental -> candidate
Missing required evidence:
- dataset.release_id
- dataset.manifest_reference
- training.training_date
- training.configuration_reference
- artifact.filename
- artifact.location
- artifact.sha256
```

---

## Rejection

An experimental or candidate model may be rejected.

Example:

```bash
python ML_side/model_registry/tools/transition.py ML_side/model_registry/records/navigation_candidate.json rejected
```

A rejected model cannot be promoted further through the defined lifecycle workflow.

---

## Deprecation

A production model may be moved to `deprecated`.

Example:

```bash
python ML_side/model_registry/tools/transition.py <model-record.json> deprecated
```

This records that the model should no longer be treated as the active production model.

---

## Rollback

A production or deprecated model may be moved to `rolled_back`.

Example:

```bash
python ML_side/model_registry/tools/transition.py <model-record.json> rolled_back
```

This records that the model has been withdrawn from production use.

---

## Model Artifact Handling

Large model-weight files must not be committed to the repository.

Examples include:

```text
*.pt
*.pth
*.onnx
*.tflite
```

Instead, the model metadata record stores:

* model artifact filename
* approved artifact location
* SHA-256 checksum

For example:

```json
"artifact": {
  "filename": "navigation-v1.pt",
  "location": "approved-storage/navigation-v1.pt",
  "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
```

The SHA-256 checksum acts as a fingerprint for the model artifact. It can be used to verify that the referenced model file is the expected artifact and has not been replaced or modified.

---

## Example Model Records

### Legacy Baseline

`records/legacy_baseline.json` represents the inherited WalkBuddy `best.pt` object-detection model.

The current known model taxonomy contains seven classes:

* `book`
* `books`
* `monitor`
* `office-chair`
* `whiteboard`
* `table`
* `tv`

Its dataset release, training configuration and evaluation evidence are currently incomplete in the registry.

The model also does not match the approved WalkBuddy eight-class MVP taxonomy.

Because the record has incomplete lineage and evaluation evidence, it must not be promoted through the workflow until the required information is available.

### Navigation Candidate

`records/navigation_candidate.json` represents the planned WalkBuddy navigation object-detection model using the approved eight-class MVP taxonomy:

* `person`
* `stairs`
* `door`
* `chair`
* `table`
* `pole`
* `bicycle`
* `vehicle`

The model begins with lifecycle status:

```text
experimental
```

Its dataset release, training lineage, model artifact and evaluation evidence are completed as the model progresses through the development workflow.

---

## Automated Tests

Run all model registry tests from the repository root:

```bash
python -m pytest ML_side/model_registry/tests -v
```

The automated tests cover:

* validation of the legacy model record
* validation of the navigation candidate record
* rejection of records with missing required metadata
* rejection of invalid lifecycle statuses
* rejection of invalid SHA-256 checksum formats
* successful `experimental -> candidate` transition
* blocking candidate promotion when lineage is missing
* successful `candidate -> production` transition
* blocking production promotion when evaluation evidence is missing
* rejection workflow
* deprecation workflow
* rollback workflow
* rejection of invalid lifecycle transitions

---

## Workflow Summary

```text
Model created
      |
      v
Metadata record created
      |
      v
Schema validation
      |
      v
Dataset and training lineage completed
      |
      v
Experimental
      |
      v
Candidate
      |
      v
Evaluation evidence added
      |
      v
Production
      |
      +------> Deprecated
      |
      +------> Rolled Back

Experimental or Candidate
      |
      +------> Rejected
```

This workflow provides a traceable and controlled process for managing WalkBuddy object-detection models while keeping large model artifacts outside the Git repository.
