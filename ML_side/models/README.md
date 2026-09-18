# Models

This directory uses the **v1** models stored in SharePoint at:

`AI Assisted Navigation Device > AIAND_REPO > ML_side > 2026 Trimester 1 > models > v1`

## Files

| File      | Description           |
| --------- | --------------------- |
| `best.pt` | PyTorch model weights |

These files are not tracked in git. Download them from the SharePoint path above and place them in this directory before running inference.

## Verified Active Model Artifact

The following record applies only to the local artifact whose SHA-256 checksum
matches this value:

- File: `ML_side/models/best.pt`
- File size: 6,244,458 bytes
- SHA-256:
  `198df54da4f6aa071b342bee77b100e78f243df785b325ec364036e106572238`
- Verified class count: 7
- Verified `model.names` mapping:
  - 0: `book`
  - 1: `books`
  - 2: `monitor`
  - 3: `office-chair`
  - 4: `whiteboard`
  - 5: `table`
  - 6: `tv`

The repository configuration lists an eighth class, `couch`, but `couch` is not
present in this specific `best.pt` artifact. This suggests that the active model
artifact and repository training configuration may come from different versions
or training runs; the cause has not yet been confirmed. Members must compare
the SHA-256 checksum before assuming their local `best.pt` is the same artifact.

Do not modify or replace the model as part of this task. Resolving the
model/configuration lineage mismatch is separate follow-up work.

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
