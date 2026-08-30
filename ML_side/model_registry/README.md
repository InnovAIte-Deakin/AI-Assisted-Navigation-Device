# WalkBuddy Model Registry

## Overview

The WalkBuddy Model Registry provides a version-controlled workflow for registering and managing WalkBuddy object-detection models.

The registry records the metadata and lineage required to identify a model, understand how it was produced, locate its model artifact, link it to evaluation evidence, and track its lifecycle status.

The registry also provides controlled lifecycle transitions for:

- experimental models
- candidate models
- production models
- rejected models
- deprecated models
- rolled-back models

A model cannot be promoted when required metadata or lineage is missing.

A `candidate -> production` transition additionally requires a matching `PASS` result from the existing WalkBuddy candidate-validation, evaluation, and model-comparison workflow.

The registry manages **metadata and lifecycle records only**. It does not train models, modify datasets, copy model weights, replace deployed weights, or deploy models.

---

## Purpose

The registry is intended to prevent situations where a model exists but important information about it is unclear.

For every registered model, the team should be able to determine:

- which model it is
- which version it is
- which architecture and framework it uses
- which object-detection taxonomy it supports
- which dataset release was used
- which training configuration produced it
- where the model artifact is stored
- which SHA-256 checksum identifies the artifact
- which evaluation evidence belongs to the model
- whether the model is experimental, candidate, production, rejected, deprecated, or rolled back
- which known limitations apply to the model

This provides traceability between:

```text
Dataset release
      |
      v
Training configuration
      |
      v
Model artifact
      |
      v
Candidate validation
      |
      v
Model evaluation
      |
      v
Model comparison
      |
      v
Lifecycle decision
```

---

## Folder Structure

```text
ML_side/model_registry/
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

### `schema/`

Contains the machine-readable JSON Schema used to define a valid WalkBuddy model registry record.

### `records/`

Contains version-controlled metadata records for registered models.

Each model should have its own record.

### `tools/`

Contains command-line tools for:

- validating model records
- applying controlled lifecycle transitions

### `tests/`

Contains automated tests for registry validation and lifecycle-transition behaviour.

---

# Model Registry Record

Each model record is stored as JSON.

The schema requires the following main sections:

```text
schema_version
model_id
model_version
identity
taxonomy
dataset
training
artifact
evaluation
lifecycle
limitations
```

---

## 1. Model Identity

The model record contains a unique model ID and version.

Example:

```json
{
  "model_id": "WB-OD-NAV-001",
  "model_version": "1.0.0"
}
```

The identity section also records information such as:

```json
{
  "identity": {
    "name": "WalkBuddy Navigation Object Detection Model",
    "architecture": "YOLO",
    "framework": "Ultralytics",
    "task": "object_detection"
  }
}
```

This identifies what type of model the record describes.

---

## 2. Taxonomy

The taxonomy section records the classes supported by the model.

Example:

```json
{
  "taxonomy": {
    "taxonomy_id": "walkbuddy-mvp-8-v1",
    "classes": [
      "person",
      "stairs",
      "door",
      "chair",
      "table",
      "pole",
      "bicycle",
      "vehicle"
    ]
  }
}
```

The model registry does **not** maintain an independent source of truth for the approved WalkBuddy class list.

For promotion validation, the registry uses the existing canonical taxonomy defined by:

```text
ML_side/tools/validate_dataset_manifest.py
```

through:

```python
APPROVED_TAXONOMY
```

The currently approved ordered taxonomy is:

| Class ID | Class |
| ---: | --- |
| 0 | `person` |
| 1 | `stairs` |
| 2 | `door` |
| 3 | `chair` |
| 4 | `table` |
| 5 | `pole` |
| 6 | `bicycle` |
| 7 | `vehicle` |

Candidate and production promotion are blocked if the registered taxonomy does not match the canonical taxonomy.

The canonical source must be updated through the appropriate dataset/taxonomy workflow rather than independently changing the model registry.

---

## 3. Dataset Lineage

The dataset section identifies the controlled dataset release used to train the model.

Example:

```json
{
  "dataset": {
    "release_id": "walkbuddy-dataset-v2",
    "manifest_reference": "ML_side/datasets/releases/v2/manifest.json"
  }
}
```

The registry does not create or validate dataset releases itself.

It records references to the controlled dataset release and manifest produced by the dataset workflow.

This makes it possible to trace a trained model back to its source data.

---

## 4. Training Lineage

The training section records when the model was trained and where its training configuration can be found.

Example:

```json
{
  "training": {
    "training_date": "2026-08-30",
    "configuration_reference": "ML_side/training/configs/navigation-v1.yaml"
  }
}
```

The training date uses the JSON Schema `date` format.

Date-format validation is enabled by the registry validator.

Invalid values such as:

```text
banana
```

or other malformed dates do not pass registry validation.

---

## 5. Model Artifact

The artifact section identifies the trained model file without storing the model weights in the registry.

Example:

```json
{
  "artifact": {
    "filename": "navigation-v1.pt",
    "location": "approved-model-storage/navigation-v1.pt",
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }
}
```

The registry records:

- filename
- approved storage location
- SHA-256 checksum

The artifact location should identify an approved storage location used by the project.

---

## 6. SHA-256 Checksum

The SHA-256 value acts as a fingerprint for the exact model artifact.

The registry schema requires a SHA-256 value to contain exactly 64 hexadecimal characters when a checksum is present.

Example:

```text
198df54da4f6aa071b342bee77b100e78f243df785b325ec364036e106572238
```

The checksum is important because two files may have the same filename while containing different model weights.

For production lifecycle validation, the registered SHA-256 must match the candidate represented by the model-comparison evidence.

---

## 7. Evaluation Evidence

The evaluation section points to the versioned evaluation evidence associated with the model.

Example:

```json
{
  "evaluation": {
    "evidence_reference": "evaluation/navigation-v1/summary.json"
  }
}
```

The model registry does not calculate evaluation metrics itself.

Evaluation is performed by the existing tooling in:

```text
ML_side/tools/evaluate_current_model.py
```

The registry consumes the resulting evaluation lineage when a model is considered for production.

For a production transition, the referenced evaluation artifact must match the model represented by the successful comparison report.

Matching includes:

- model filename
- SHA-256 checksum
- class count
- ordered taxonomy
- evaluation mode

---

# Lifecycle

The registry supports these lifecycle states:

```text
experimental
candidate
production
rejected
deprecated
rolled_back
```

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

Transitions that are not explicitly allowed are rejected.

For example:

```text
experimental -> production
```

is not allowed.

Likewise:

```text
rejected -> production
```

is not allowed.

---

# Full Record Validation Before Transitions

Every lifecycle transition first validates the complete registry record against:

```text
ML_side/model_registry/schema/model.schema.json
```

The transition does not proceed if the record is malformed.

This includes validation of:

- required fields
- object structure
- lifecycle status
- task value
- SHA-256 format
- training-date format
- other schema constraints

For example, this checksum is invalid:

```json
{
  "sha256": "12345"
}
```

A lifecycle transition will be blocked before any promotion logic is applied.

---

# Experimental to Candidate

An experimental model can only become a candidate after required lineage information is available.

The following fields are required:

```text
dataset.release_id
dataset.manifest_reference
training.training_date
training.configuration_reference
artifact.filename
artifact.location
artifact.sha256
```

The registered taxonomy must also match the canonical WalkBuddy taxonomy.

If any required information is missing, the transition is blocked.

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

# Candidate Validation and Evaluation Workflow

The registry integrates with the existing WalkBuddy model-validation and evaluation workflow.

That workflow is implemented separately from this registry.

The relevant tools are:

```text
ML_side/tools/validate_candidate_model.py
ML_side/tools/evaluate_current_model.py
ML_side/tools/compare_model_evaluations.py
```

The workflow is:

```text
Candidate artifact
      |
      v
validate_candidate_model.py
      |
      v
Candidate-validation report
      |
      v
evaluate_current_model.py
      |
      v
Versioned evaluation artifact
      |
      v
compare_model_evaluations.py
      |
      v
PASS / FAIL / REVIEW
```

The registry consumes this evidence when determining whether a candidate may receive the `production` lifecycle status.

It does not duplicate the evaluation or comparison logic.

---

# PASS / FAIL / REVIEW

The existing model-comparison workflow produces one of three verdicts.

## `PASS`

A `PASS` indicates that the candidate is technically compatible and satisfies every explicitly approved promotion gate.

A production transition may proceed only if the PASS evidence also matches the model registered in the model registry.

## `FAIL`

A `FAIL` indicates that candidate validation, taxonomy compatibility, or an approved promotion gate failed.

A `FAIL` cannot produce a production lifecycle transition.

## `REVIEW`

A `REVIEW` indicates that automatic promotion is not currently justified.

Examples include:

- missing approved promotion gates
- historical baseline
- non-canonical baseline
- incompatible evaluation settings
- missing metrics
- unsupported metric semantics
- missing candidate-validation evidence

A `REVIEW` cannot produce a production lifecycle transition.

---

# Candidate to Production

A candidate model cannot become `production` merely because an evaluation reference is present.

The transition requires a `model_comparison.json` artifact produced by:

```text
ML_side/tools/compare_model_evaluations.py
```

The registry requires:

1. supported model-comparison schema version
2. correct comparison-tool identity
3. overall verdict `PASS`
4. technical compatibility status `compatible`
5. an explicitly supplied promotion-gate configuration
6. policy status `APPROVED_POLICY`
7. policy result `PASS`
8. successful candidate-validation evidence
9. matching model SHA-256
10. matching model filename
11. matching class count
12. matching ordered taxonomy
13. registry taxonomy matching the canonical WalkBuddy taxonomy
14. matching evaluation lineage

If any of these checks fails, the transition is blocked.

---

## Production Transition Command

Use:

```bash
python ML_side/model_registry/tools/transition.py <model-record.json> production --promotion-report <model_comparison.json>
```

Example:

```bash
python ML_side/model_registry/tools/transition.py ML_side/model_registry/records/navigation_candidate.json production --promotion-report path/to/model_comparison.json
```

The `model_comparison.json` file should be the output generated by the existing model-comparison workflow.

---

# Promotion Policy

The existing example promotion policy is located at:

```text
ML_side/config/promotion_gates.example.json
```

It is explicitly marked:

```text
EXAMPLE_NOT_APPROVED_POLICY
```

This file demonstrates the supported gate structure only.

It is **not** an approved WalkBuddy promotion policy.

Therefore, using the example configuration cannot authorize a production transition.

Automatic PASS eligibility requires a separately approved gate configuration with:

```text
policy_status = APPROVED_POLICY
```

The model registry does not define promotion thresholds itself.

---

# Matching Promotion Evidence

Production evidence must belong to the exact model represented by the registry record.

The registry verifies that the candidate represented by the PASS comparison has the same:

```text
filename
SHA-256
class count
ordered taxonomy
```

as the registry record.

The registered evaluation artifact is also loaded and checked against the candidate represented in the PASS comparison.

This prevents a PASS produced for one model from being reused to authorize a different model.

For example:

```text
Registry SHA:
aaaaaaaa...

PASS report SHA:
bbbbbbbb...

Result:
PRODUCTION BLOCKED
```

---

# Historical Baseline

The current inherited WalkBuddy `best.pt` model is represented by:

```text
ML_side/model_registry/records/legacy_baseline.json
```

The existing evaluation workflow also represents the inherited model as a historical reference in:

```text
ML_side/evaluation/baselines/historical_7class_baseline.json
```

Its known taxonomy is:

```text
0 -> book
1 -> books
2 -> monitor
3 -> office-chair
4 -> whiteboard
5 -> table
6 -> tv
```

This differs from the approved eight-class navigation taxonomy.

The historical seven-class model therefore cannot automatically approve or reject the first eight-class navigation model.

Its incomplete historical lineage is preserved rather than replaced with invented metadata.

---

# Navigation Candidate Record

The example navigation candidate is stored at:

```text
ML_side/model_registry/records/navigation_candidate.json
```

It represents the planned eight-class navigation model.

The record begins as:

```text
experimental
```

Unknown information is represented as `null` rather than being guessed.

For example, until a real trained artifact exists:

```json
{
  "artifact": {
    "filename": null,
    "location": null,
    "sha256": null
  }
}
```

The record can later be completed using verified dataset, training, artifact, and evaluation information.

Future real models should normally receive their own model records.

---

# Registering a New Model

When a new model is trained, the team should:

1. create a new JSON record under:

```text
ML_side/model_registry/records/
```

2. assign a unique model ID and version

3. record the model architecture and framework

4. record the exact supported taxonomy

5. record the controlled dataset release and manifest

6. record the training date and training configuration reference

7. store the model weights in the approved model-artifact location

8. record the artifact filename and location

9. calculate and record the model SHA-256 checksum

10. validate the registry record

11. complete candidate validation and evaluation using the existing ML tooling

12. link the evaluation evidence in the registry

13. use the controlled transition tool when changing lifecycle status

---

# Validate a Model Record

From the repository root, run:

```bash
python ML_side/model_registry/tools/validate.py <model-record.json>
```

Example:

```bash
python ML_side/model_registry/tools/validate.py ML_side/model_registry/records/navigation_candidate.json
```

A valid record produces output similar to:

```text
Valid model record: ML_side/model_registry/records/navigation_candidate.json
```

Invalid records report the relevant field.

Example:

```text
Validation failed:
- artifact.sha256: value does not match the required SHA-256 pattern
```

---

# Candidate Transition

Example:

```bash
python ML_side/model_registry/tools/transition.py ML_side/model_registry/records/navigation_candidate.json candidate
```

The transition will be blocked if the required lineage is incomplete.

---

# Rejection

Experimental and candidate models may be rejected.

Example:

```bash
python ML_side/model_registry/tools/transition.py <model-record.json> rejected
```

Supported rejection transitions are:

```text
experimental -> rejected
candidate -> rejected
```

Rejected models cannot subsequently be promoted through the defined lifecycle workflow.

---

# Deprecation

A production model may be deprecated:

```bash
python ML_side/model_registry/tools/transition.py <model-record.json> deprecated
```

This changes the registry lifecycle status.

It does not delete or modify the model artifact.

---

# Rollback

A production or deprecated model may be moved to:

```text
rolled_back
```

Example:

```bash
python ML_side/model_registry/tools/transition.py <model-record.json> rolled_back
```

Supported rollback transitions are:

```text
production -> rolled_back
deprecated -> rolled_back
```

The registry records the lifecycle decision only.

Actual production deployment or model replacement must be handled by the appropriate deployment workflow.

---

# Model Artifact Storage

Large model weights must not be committed to the Git repository as part of the model registry.

The registry stores metadata about the model artifact instead.

The model record contains:

```text
artifact filename
approved storage location
SHA-256 checksum
```

For example:

```json
{
  "artifact": {
    "filename": "navigation-v2.pt",
    "location": "approved-model-storage/navigation-v2.pt",
    "sha256": "..."
  }
}
```

This keeps the registry version-controlled while allowing large binary artifacts to remain in approved external or project-controlled model storage.

The repository `.gitignore` also excludes `.pt` model-weight files.

---

# Dependency Setup

The model registry uses `jsonschema` for machine-readable metadata validation.

Model-free ML workflow dependencies are declared in:

```text
ML_side/requirements-ci.txt
```

Install them from the repository root using:

```bash
python -m pip install -r ML_side/requirements-ci.txt
```

The requirements include:

```text
pytest
PyYAML
jsonschema
```

---

# JSON Schema Validation

The registry uses JSON Schema Draft 2020-12.

The schema is located at:

```text
ML_side/model_registry/schema/model.schema.json
```

Validation is implemented using:

```python
Draft202012Validator
```

with:

```python
FormatChecker
```

The format checker ensures schema formats such as:

```json
{
  "format": "date"
}
```

are actually enforced.

---

# Automated Tests

Registry tests are located in:

```text
ML_side/model_registry/tests/
```

Run them with:

```bash
python -m pytest ML_side/model_registry/tests -v
```

The registry test suite covers:

- valid legacy metadata
- valid navigation-candidate metadata
- missing required fields
- invalid lifecycle states
- malformed SHA-256 values
- malformed training dates
- canonical taxonomy enforcement
- missing lineage
- successful experimental-to-candidate transition
- matching PASS evidence for production
- FAIL production blocking
- REVIEW production blocking
- missing promotion evidence
- SHA mismatch
- filename mismatch
- taxonomy mismatch
- evaluation-lineage mismatch
- unapproved promotion policy
- failed candidate validation
- invalid lifecycle transitions
- rejection
- deprecation
- rollback

---

# Integration Regression Tests

Because production lifecycle validation integrates with the existing candidate-validation and model-evaluation workflow, changes to this integration should also run the relevant existing tests.

Candidate validator:

```bash
python -m pytest ML_side/tests/test_validate_candidate_model.py -v
```

Model comparison and promotion gating:

```bash
python -m pytest ML_side/tests/test_compare_model_evaluations.py -v
```

Model evaluation:

```bash
python -m pytest ML_side/tests/test_evaluate_current_model.py -v
```

All relevant suites can be run together:

```bash
python -m pytest ML_side/model_registry/tests ML_side/tests/test_validate_candidate_model.py ML_side/tests/test_compare_model_evaluations.py ML_side/tests/test_evaluate_current_model.py -v
```

---

# Model Registry vs Deployment

The meaning of `production` in this registry is:

> the registered model has satisfied the required metadata, lineage, validation, evaluation, and approved promotion-evidence checks required for the production lifecycle state.

Changing a registry record to:

```text
production
```

does **not**:

- copy model weights
- replace `best.pt`
- update the backend
- restart a service
- deploy a model
- change frontend behaviour
- modify detection thresholds
- change hazard policies
- modify datasets

Deployment remains a separate project responsibility.

---

# Responsibilities of Existing ML Workflows

The model registry intentionally does not duplicate functionality already implemented elsewhere.

## Dataset validation and taxonomy

Handled by existing dataset tooling including:

```text
ML_side/tools/validate_dataset_manifest.py
```

The registry consumes the canonical taxonomy from this workflow.

## Candidate artifact validation

Handled by:

```text
ML_side/tools/validate_candidate_model.py
```

## Model evaluation

Handled by:

```text
ML_side/tools/evaluate_current_model.py
```

## Comparison and promotion recommendation

Handled by:

```text
ML_side/tools/compare_model_evaluations.py
```

## Model registry

The registry is responsible for:

- recording model metadata
- recording dataset and training lineage
- recording artifact identity
- recording evaluation references
- validating registry structure
- controlling metadata lifecycle transitions
- requiring matching promotion evidence for production

---

# End-to-End Workflow

The intended overall workflow is:

```text
Approved dataset release
        |
        v
Model training
        |
        v
Model artifact created
        |
        v
Registry record created/completed
        |
        v
Registry schema validation
        |
        v
Candidate artifact validation
        |
        v
Experimental -> Candidate
        |
        v
Versioned labelled evaluation
        |
        v
Compatible baseline comparison
        |
        v
PASS / FAIL / REVIEW
        |
        +----------------------+
        |                      |
       FAIL                  REVIEW
        |                      |
        v                      v
Production blocked      Production blocked

               PASS
                |
                v
Verify exact model lineage
                |
                v
Candidate -> Production
                |
                +----------------+
                |                |
                v                v
           Deprecated        Rolled back
```

---

# Important Rules

1. Do not invent unknown model metadata.

2. Use `null` for information that has not yet been verified when the schema permits it.

3. Do not commit large model weights to the model registry.

4. Record the exact model artifact using filename, location, and SHA-256.

5. Do not maintain a separate independent approved taxonomy in registry validation logic.

6. Use the project's canonical taxonomy source.

7. Validate every registry record before changing lifecycle state.

8. Do not treat the existence of an evaluation file as proof that a model passed evaluation.

9. Only a matching `PASS` recommendation using an approved promotion policy can support `candidate -> production`.

10. `FAIL` and `REVIEW` always block the production transition.

11. Promotion evidence must belong to the same model artifact recorded in the registry.

12. Registry lifecycle changes do not deploy or replace model weights.

13. Historical model metadata must remain clearly distinguished from verified current lineage.

---

# Summary

The WalkBuddy Model Registry provides a controlled and traceable way to manage object-detection model metadata and lifecycle state.

It links together:

```text
Model identity
+
Canonical taxonomy
+
Dataset lineage
+
Training lineage
+
Artifact SHA-256
+
Evaluation lineage
+
Existing PASS / FAIL / REVIEW evidence
+
Lifecycle state
```

This ensures that a model cannot be represented as production-ready solely because a model file or evaluation reference exists.

Production lifecycle status requires validated metadata, complete required lineage, the canonical WalkBuddy taxonomy, and matching approved promotion evidence for the exact model artifact.