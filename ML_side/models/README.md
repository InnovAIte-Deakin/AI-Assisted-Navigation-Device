# Models

This directory uses the **v1** models stored in SharePoint at:

`AI Assisted Navigation Device > AIAND_REPO > ML_side > T2_2026 > Models > navigation > WB-OD-NAV-001 > 0.1.0`

## Files

| File      | Description           |
| --------- | --------------------- |
| `best.pt` | PyTorch model weights |

These files are not tracked in git. Download them from the SharePoint path above and place them in this directory before running inference.

The single source of truth for the currently active candidate's identity is the deployment manifest:
`ML_side/deployment/manifests/navigation_candidate_56c445bb8c85.json`. If this README and the manifest
ever disagree, trust the manifest and update this file.

## Verified Active Model Artifact

The following record applies only to the local artifact whose SHA-256 checksum
matches this value:

- Candidate: `WB-OD-NAV-001` v0.1.0
- Run: `navigation-mvp-full-candidate-56c445bb8c85`
- File: `ML_side/models/best.pt`
- File size: 5,364,741 bytes
- SHA-256:
  `3cbdadd14b018573803d31f3c7bd5683bf7abd19649aff6da7c1f1ea1d78cc5f`
- Verified class count: 8
- Verified `model.names` mapping:
  - 0: `person`
  - 1: `stairs`
  - 2: `door`
  - 3: `chair`
  - 4: `table`
  - 5: `pole`
  - 6: `bicycle`
  - 7: `vehicle`

Lifecycle status: **candidate**. Production authorization is **not granted**. No automatic
promotion is performed by setup, readiness, or CI tooling — see the deployment manifest and the
Teams-shared `WalkBuddy_Local_Setup_Tutorial_Windows_macOS_v1.2.pdf` setup guide for current
governance details.

Do not modify or replace the model as part of this task. Members must compare the SHA-256
checksum locally before assuming their `best.pt` matches this record.

## Inspecting Active Model Metadata

`ML_side/tools/inspect_active_model.py` is a read-only utility for verifying the
local `best.pt` file's resolved path, file size, SHA-256 checksum, and
`model.names` class mapping. It does not download, train, export, replace, or
otherwise modify a model.

Run it from the repository root after creating the backend virtual environment
by following `docs/LOCAL_SETUP.md`:

```powershell
& ".\software_side\walkbuddy_reactNative\backend\.venv\Scripts\python.exe" ".\ML_side\tools\inspect_active_model.py"
```

On macOS or Linux, use a backend virtual environment with Ultralytics installed:

```bash
software_side/walkbuddy_reactNative/backend/.venv/bin/python ML_side/tools/inspect_active_model.py
```

Pass a local model path to inspect a different file:

```text
python ML_side/tools/inspect_active_model.py /path/to/model.pt
```

The repository training configuration does not prove that a locally supplied
`best.pt` has the same class mapping. Inspect metadata locally before relying on
the model's labels in ML, deployment, or safety work.

> **Warning:** Never commit model weights, including `.pt`, `.tflite`, or
> `.gguf` files.
>
> **Security warning:** Inspect `.pt` files only when they come from a trusted
> project source, because loading model weights involves model deserialization.

Maintenance: Update this README whenever the active model changes — include the new version, SharePoint path, and file list.
