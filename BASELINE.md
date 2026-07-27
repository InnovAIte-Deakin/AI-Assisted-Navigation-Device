# WalkBuddy Project Baseline

> **Status:** Living document  
> **Last updated:** 27 July 2026  
> **Official repository:** `InnovAIte-Deakin/AI-Assisted-Navigation-Device`  
> **Working branch:** `t2-2026-development`

## Purpose

This document records the currently verified baseline for the WalkBuddy project.

It is intended to give contributors the information required to understand the project, prepare their environment, select a task, make changes safely, and submit work through the correct Git workflow.

Information in this document is separated into:

- **Verified:** Confirmed through the repository, local testing, or project files.
- **Reported:** Provided by a previous member but not yet independently verified.
- **Unknown:** Requires further investigation.

## Official Git Workflow

1. Fork the official organisation repository.
2. Clone your personal fork.
3. Add the official organisation repository as the `upstream` remote.
4. Keep your local `t2-2026-development` branch updated from `upstream`.
5. Create a separate feature branch for each task.
6. Do not push directly to `main` or `t2-2026-development`.
7. Push your feature branch to your fork.
8. Open a pull request into the organisation repository's `t2-2026-development` branch.
9. Keep each pull request focused on one task or one closely related group of changes.

## Repository Structure

- `ML_side/` — machine-learning code, models, experiments, testing, and documentation.
- `software_side/` — React Native frontend and FastAPI backend.
- `docs/` — current setup and onboarding documentation.
- `BASELINE.md` — current verified project baseline.

## Required External Files

Some required files are not stored in GitHub and must be downloaded from Teams or SharePoint.

### Runtime model files

| File | Purpose | Local destination | Status |
|---|---|---|---|
| `best.pt` | YOLO object detection | `ML_side/models/best.pt` | Required |
| `llama-3.2-1b-instruct-q4_k_m.gguf` | Local language model | `ML_side/models/llama-3.2-1b-instruct-q4_k_m.gguf` | Required for local language-model features |

Known SharePoint model location:

`AIAND_REPO/ML_side/2026 Trimester 1/models/v1`

These files must not be committed to normal Git history.

## Current Object-Detection Classes

The currently identified model classes are:

| Class ID | Class name |
|---:|---|
| 0 | book |
| 1 | books |
| 2 | monitor |
| 3 | office-chair |
| 4 | whiteboard |
| 5 | table |
| 6 | tv |
| 7 | couch |

The exact metadata should still be verified directly from the active `best.pt` file.

## Current Known Issues

### Predictive Path imports

Predictive Path reportedly fails with HTTP 500 because some Python files use imports such as:

```python
from ml_predictor import MLPredictor
```

These may need package-relative imports:

```python
from .ml_predictor import MLPredictor
```

This should be fixed and verified through a focused pull request.

### Missing YOLO model

Without `ML_side/models/best.pt`, YOLO cannot load and Vision Assist cannot perform object detection.

### Vision Assist request mismatch

The frontend reportedly sends a GET request to `/vision`, while the backend expects POST. This currently causes HTTP 405.

### Safety-gate class mismatch

The safety gate checks for classes such as stairs, door, and person, but these classes are not included in the currently identified eight-class model.

### Incorrect class mapping

Some navigation code reportedly treats class ID 7 as `door`, while the current model identifies class ID 7 as `couch`.

This mapping must not be relied upon until corrected and tested.

### Audiobooks

An HTTP 502 error has been reported. This may involve the external LibriVox service and requires separate verification.

## Current Dataset Status

The previous dataset is stored in Teams or SharePoint and is considered legacy reference material.

Known concerns include:

- inconsistent image formats;
- inconsistent naming;
- duplicate or overlapping class names;
- possible image and label mismatches;
- unclear dataset lineage;
- limited navigation-hazard classes.

The legacy dataset must not be modified directly.

A new dataset standard and controlled pilot dataset should be created before full retraining begins.

## Current Model and Training Status

The repository contains notebooks, experiments, reports, and model-related files from previous trimesters.

The exact training run that produced the active `best.pt` model has not yet been fully verified.

Do not claim that a notebook produced the active model unless matching configuration, output, and model evidence are available.

## Current Priorities

1. Verify the official baseline on Windows and macOS.
2. Complete and test `docs/LOCAL_SETUP.md`.
3. Confirm every required external file and its exact location.
4. Verify the active model's class metadata.
5. Record known defects as GitHub issues or Planner tasks.
6. Audit the legacy dataset.
7. Define a new dataset and annotation standard.
8. Define suitable navigation-hazard classes.
9. Merge small, tested fixes through pull requests.
10. Begin retraining only after the dataset pipeline is approved.

## Safe Contribution Rules

Before changing code:

1. Update your local `t2-2026-development` branch from `upstream`.
2. Create a new feature branch.
3. Confirm the task owner and expected deliverable.
4. Avoid unrelated changes.
5. Do not commit model files, datasets, `.env` files, virtual environments, or `node_modules`.
6. Test the change.
7. Record evidence.
8. Push the feature branch to your fork.
9. Open a pull request into `t2-2026-development`.

## Information Still Required

- Confirmed training history of the active models.
- Exact SharePoint location of every required runtime file.
- Active model checksum and file size.
- Verified Windows dependency installation process.
- Verified macOS dependency installation process.
- Current status of every frontend feature.
- Current status of every backend route.
- Current dataset image and annotation counts.
- Final approved hazard-class taxonomy.
- Historical implementation details from previous project members.

## Updating This Document

Update this document whenever:

- the baseline commit changes;
- required files change;
- a feature is verified or repaired;
- the active model changes;
- dataset standards are approved;
- setup instructions change;
- a previously unknown fact is confirmed.

Every update should be supported by repository evidence, test output, project files, or clearly labelled historical information.
