# WalkBuddy Local Setup Guide

> **Status:** Windows setup verified; macOS setup still requires validation  
> **Last updated:** 27 July 2026  
> **Official repository:** `InnovAIte-Deakin/AI-Assisted-Navigation-Device`  
> **Working branch:** `t2-2026-development`

## 1. Complete the Git Setup First

Before using this guide, follow the Code Integration contribution guide to:

1. Fork the official repository.
2. Clone your personal fork.
3. Add the organisation repository as `upstream`.
4. Confirm that your local base branch is `t2-2026-development`.
5. Create a feature branch before making changes.

Confirm your branch:

```bash
git branch --show-current
```

Expected base branch:

```text
t2-2026-development
```

## 2. Required Software

Install:

- Git
- Python 3.11
- Node.js 18 or newer
- npm
- Visual Studio Code
- Expo Go on an Android or iOS phone

Tested Windows versions:

```text
Git 2.51.0.windows.1
Python 3.11.9
Node.js 22.19.0
npm 10.9.3
```

Check your versions:

```powershell
git --version
py -3.11 --version
node --version
npm --version
```

## 3. Download the Required Model Files

The following runtime files are not stored in GitHub:

| File | Purpose | Local destination |
|---|---|---|
| `best.pt` | YOLO object detection | `ML_side/models/best.pt` |
| `llama-3.2-1b-instruct-q4_k_m.gguf` | Local language model | `ML_side/models/llama-3.2-1b-instruct-q4_k_m.gguf` |

Known SharePoint location:

### Where to download the model files

For easier access, the required files are shared in the project Teams chat inside:

`T2 2026 Setup Assets`

The folder link is shared or pinned in Teams.

The original archive location remains:

`AIAND_REPO/ML_side/2026 Trimester 1/models/v1`

Download both files and place them in:

`ML_side/models/`

Do not rename or commit them.

### Windows verification

From the repository root:

```powershell
Test-Path ".\ML_side\models\best.pt"
Test-Path ".\ML_side\models\llama-3.2-1b-instruct-q4_k_m.gguf"
```

Both commands must return:

```text
True
```

Check their sizes:

```powershell
Get-Item ".\ML_side\models\best.pt" | Select-Object Name,Length
Get-Item ".\ML_side\models\llama-3.2-1b-instruct-q4_k_m.gguf" | Select-Object Name,Length
```

Verified file sizes:

```text
best.pt                             6244458
llama-3.2-1b-instruct-q4_k_m.gguf 807694464
```

Confirm Git ignores them:

```powershell
git check-ignore -v ".\ML_side\models\best.pt"
git check-ignore -v ".\ML_side\models\llama-3.2-1b-instruct-q4_k_m.gguf"
```

## 4. Create the Windows Backend Environment

From the repository root:

```powershell
cd ".\software_side\walkbuddy_reactNative\backend"
```

Create and activate the virtual environment:

```powershell
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Your PowerShell prompt should now begin with:

```text
(.venv)
```

## 5. Install Windows-Compatible Backend Dependencies

The current `requirements.txt` contains macOS-only `pyobjc` packages and `uvloop`, which does not support Windows.

Create a temporary Windows-compatible file:

```powershell
Get-Content ".\requirements.txt" |
Where-Object {
    ($_ -notmatch "^(?i)pyobjc") -and
    ($_ -notmatch "^(?i)uvloop==")
} |
Set-Content "$env:TEMP\walkbuddy-requirements-windows.txt"
```

Confirm the excluded packages are absent:

```powershell
Select-String `
-Path "$env:TEMP\walkbuddy-requirements-windows.txt" `
-Pattern "pyobjc|^uvloop=="
```

The command should print nothing.

Install the remaining dependencies:

```powershell
python -m pip install -r "$env:TEMP\walkbuddy-requirements-windows.txt"
```

Verify the main imports:

```powershell
python -c "import fastapi, uvicorn, ultralytics, easyocr, faster_whisper; print('Core backend imports OK')"
```

Expected result:

```text
Core backend imports OK
```

## 6. Install the Windows LLM Runtime

The pinned `llama-cpp-python==0.3.16` source build requires Windows C/C++ build tools.

The following prebuilt CPU wheel was tested successfully:

```powershell
python -m pip install llama-cpp-python==0.3.34 `
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu `
  --only-binary=:all:
```

Verify it:

```powershell
python -c "from llama_cpp import Llama; print('llama_cpp import OK')"
python -m pip show llama-cpp-python
```

Expected version:

```text
0.3.34
```

## 7. Start the Backend on Windows

Remain inside:

```text
software_side/walkbuddy_reactNative/backend
```

Set the model directory:

```powershell
$env:WALKBUDDY_MODEL_DIR = (Resolve-Path "../../../ML_side/models").Path
```

Confirm the models are visible:

```powershell
Get-ChildItem $env:WALKBUDDY_MODEL_DIR | Select-Object Name,Length
```

Start the backend:

```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

A fully ready backend should show:

```text
YOLO ready
EasyOCR ready
LLM ready
Whisper STT ready
Application startup complete
Uvicorn running on http://0.0.0.0:8000
```

The first Whisper startup may download the `tiny` model.

OpenTelemetry may report that it cannot export traces to `localhost:4317`. This did not prevent the application from running during Windows testing.

Keep this terminal open.

## 8. Verify the Backend

Open a second PowerShell window:

```powershell
Invoke-WebRequest http://localhost:8000/ping -UseBasicParsing |
Select-Object StatusCode,Content
```

Expected result:

```text
StatusCode : 200
Content    : {"ok":true}
```

Open the API documentation:

```powershell
Start-Process "http://localhost:8000/docs"
```

## 9. Find Your Windows LAN Address

In the second PowerShell window:

```powershell
$ip = (Get-NetIPConfiguration |
    Where-Object {
        $_.NetAdapter.Status -eq "Up" -and
        $_.IPv4DefaultGateway -ne $null
    }).IPv4Address.IPAddress |
    Select-Object -First 1
```

Display it:

```powershell
$ip
```

Test the backend through that address:

```powershell
Invoke-WebRequest "http://${ip}:8000/ping" -UseBasicParsing |
Select-Object StatusCode,Content
```

This must also return HTTP 200 before continuing.

## 10. Install the Frontend

Navigate to the frontend:

```powershell
cd "PATH_TO_REPOSITORY\software_side\walkbuddy_reactNative\frontend_reactNative"
```

Set the backend address for the current terminal:

```powershell
$env:EXPO_PUBLIC_API_BASE = "http://${ip}:8000"
```

Confirm it:

```powershell
$env:EXPO_PUBLIC_API_BASE
```

Install dependencies:

```powershell
npm install
```

During the verified Windows setup, npm reported deprecated packages, Expo compatibility warnings, and 38 vulnerabilities.

Do not run:

```text
npm audit fix
npm audit fix --force
```

Dependency upgrades must be handled through a separate reviewed task.

## 11. Start the Frontend

Run:

```powershell
npm run dev
```

Wait for the Expo QR code.

If Windows Firewall asks for access:

1. Allow **Private networks**.
2. Leave **Public networks** unticked.
3. Click **Allow access**.

On the phone:

1. Connect to the same Wi-Fi network as the computer.
2. Open Expo Go.
3. Scan the QR code.
4. Allow the required camera, microphone, and location permissions.
5. Wait for the application to load.

Keep both terminals open:

- the backend terminal running Uvicorn;
- the frontend terminal running Expo.

## 12. Verified Windows Results

The following were verified:

- the backend health check returned HTTP 200;
- YOLO loaded;
- EasyOCR loaded in CPU mode;
- the local GGUF language model loaded;
- Faster Whisper loaded;
- the Android application opened through Expo Go;
- object detection and spoken guidance produced output;
- speech-to-text returned HTTP 200 from `/stt/transcribe`.

## 13. Known Unstable Features

The following features remain unstable and are not required to confirm that the basic local setup succeeded:

- Predictive Path;
- Vision Assist;
- Audiobooks.

The safety guidance also needs review because ordinary objects such as books and office chairs may be assigned HIGH or CRITICAL risk levels.

## 14. Reporting a Setup Problem

Send:

```text
Operating system:
Repository:
Branch:
Commit:
Python version:
Node version:
Command that failed:
Full error:
Required model files present:
Backend logs:
Frontend logs:
Screenshot:
```

Get the current commit:

```bash
git rev-parse --short HEAD
```

Get the current branch:

```bash
git branch --show-current
```

Remove or hide personal addresses, precise location data, IP addresses, tokens, and other private details before sharing logs or screenshots.

## 15. Stop the Application

In the frontend terminal, press:

```text
Ctrl + C
```

In the backend terminal, press:

```text
Ctrl + C
```

## 16. macOS Status

The old macOS instructions are not yet considered verified against this baseline.

A macOS tester must confirm:

- dependency installation;
- `llama-cpp-python` installation;
- model loading;
- backend health check;
- Expo connection;
- basic object detection and speech-to-text.

Until then, macOS-specific steps should be treated as provisional.
