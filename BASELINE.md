# WalkBuddy Project Baseline

> **Status:** Living document  
> **Last updated:** 27 July 2026  
> **Official repository:** `InnovAIte-Deakin/AI-Assisted-Navigation-Device`  
> **Working branch:** `t2-2026-development`

## Purpose

This document records the currently verified baseline for the WalkBuddy project.

It gives contributors the information required to understand the project, prepare their environment, select a task, make changes safely, and submit work through the correct Git workflow.

Information is labelled as:

- **Verified:** Confirmed through repository inspection or local testing.
- **Reported:** Provided by a project member but not yet independently verified.
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

Some runtime files are not stored in GitHub and must be downloaded from Teams or SharePoint.

For easier team access, copies of the required runtime files are shared in the project Teams folder:

`T2 2026 Setup Assets`

The original `AIAND_REPO` location remains the archive source. Do not place the private Teams sharing link inside this public repository.

Known SharePoint location:

`AIAND_REPO/ML_side/2026 Trimester 1/models/v1`

| File | Purpose | Local destination | Verified Windows size |
|---|---|---|---:|
| `best.pt` | YOLO object detection | `ML_side/models/best.pt` | 6,244,458 bytes |
| `llama-3.2-1b-instruct-q4_k_m.gguf` | Local language model | `ML_side/models/llama-3.2-1b-instruct-q4_k_m.gguf` | 807,694,464 bytes |

These files must not be committed to normal Git history.

## Verified Windows Baseline

The following environment was tested successfully:

- Windows
- Git `2.51.0.windows.1`
- Python `3.11.9`
- Node.js `22.19.0`
- npm `10.9.3`
- Android device using Expo Go

Verified results:

- `/ping` returned HTTP 200 with `{"ok":true}`.
- YOLO loaded successfully from `best.pt`.
- EasyOCR loaded successfully in CPU mode.
- the local GGUF language model loaded successfully.
- Faster Whisper loaded successfully.
- the React Native application opened through Expo Go.
- object detection and spoken guidance produced output.
- speech-to-text sent audio to `/stt/transcribe` and returned HTTP 200.

The backend displayed OpenTelemetry export warnings because no local collector was running on port `4317`. These warnings did not prevent the application from running.

## Windows Dependency Findings

The current backend `requirements.txt` is not directly Windows-compatible.

Verified problems:

- it contains 162 macOS-only `pyobjc` entries;
- it includes `uvloop`, which does not support Windows;
- `llama-cpp-python==0.3.16` attempted to compile from source and failed without Microsoft C/C++ build tools;
- the available prebuilt Windows CPU wheel `llama-cpp-python==0.3.34` installed and imported successfully.

The tested Windows setup therefore filters out `pyobjc*` and `uvloop`, then installs the `0.3.34` prebuilt CPU wheel separately.

This is a setup workaround, not yet a permanent dependency-file correction.

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

The active model metadata should still be extracted and recorded directly from `best.pt`.

## Current Known Issues

### Predictive Path

Predictive Path has been reported as unstable and may return HTTP 500. Incorrect package imports have been identified in related Python files.

### Vision Assist

Vision Assist has been reported as unstable and may return HTTP 405 because the frontend and backend request methods do not match.

### Safety guidance is not aligned with navigation hazards

The safety gate does trigger, but current testing showed ordinary detected objects such as books and office chairs being assigned HIGH or CRITICAL risk levels.

The current model does not include several expected navigation-safety classes such as stairs, person, or door. The existing risk logic and the active model classes therefore need to be reviewed together.

### Incorrect class mapping

Some navigation code reportedly treats class ID 7 as `door`, while the identified model class at index 7 is `couch`.

This mapping must not be relied upon until corrected and tested.

### Audiobooks

Audiobooks failed during local testing with a rejected request. The exact failing dependency or external request still needs to be isolated.

### Frontend dependencies

`npm install` completed, but npm reported deprecated packages and 38 vulnerabilities:

- 2 low
- 22 moderate
- 12 high
- 2 critical

Do not run `npm audit fix --force` without a dedicated task, testing, and review because it may introduce breaking dependency changes.

Expo also reported several package-version compatibility warnings.

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

1. Review and merge the verified Windows local setup documentation.
2. Test and document the setup on macOS.
3. Confirm every required external file and its exact SharePoint location.
4. Extract and record the active model metadata.
5. Record known defects as GitHub issues or Planner tasks.
6. Audit the legacy dataset.
7. Define a new dataset and annotation standard.
8. Define suitable navigation-hazard classes and risk rules.
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
7. Record evidence without exposing personal addresses, IP addresses, tokens, or private data.
8. Push the feature branch to your fork.
9. Open a pull request into `t2-2026-development`.

## Information Still Required

- Confirmed training history of the active models.
- Exact SharePoint location of every required runtime file.
- Active model checksum.
- Verified macOS dependency installation process.
- Current status of each unstable frontend feature.
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
