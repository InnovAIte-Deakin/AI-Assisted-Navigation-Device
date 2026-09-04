# macOS Setup Validation

**Date:** 21 August 2026

## Environment

- macOS 26.5.2
- Python 3.11.15
- Node.js 24.11.1
- npm 11.6.2
- Backend virtual environment: present
- Required model files: present locally; not committed to GitHub

## Dependency checks

The following checks passed in the backend virtual environment:

```text
Core backend imports OK
llama_cpp import OK
faster-whisper 1.2.1
llama-cpp-python 0.3.34
```

## Backend and device checks

The backend was started on port 8000 and returned HTTP 200 from the local
health endpoint:

```text
GET /ping -> {"ok":true}
```

Expo was started with LAN hosting enabled. The physical iPhone loaded the app
when the phone and Mac were connected to a reachable common network.

## Issues recorded and resolved locally

1. The first STT test returned HTTP 503 because `faster-whisper` was missing
   from the active Python environment. Installing the backend requirements in
   the virtual environment resolved this.
2. The phone could not use a developer-specific API address after the network
   changed. Setting `EXPO_PUBLIC_API_BASE` to the Mac's current LAN address and
   restarting Expo resolved the connection issue.
3. The Vision Assist preview produced HTTP 405 because it loaded the REST
   `/vision` endpoint as a webpage. This is an application integration issue,
   not a macOS installation failure; it is tracked separately in Issue #200.

## Model handling

The model files were downloaded from the project Teams/SharePoint setup assets.
They are intentionally excluded from GitHub. The local `best.pt` matched the
artifact record in `ML_side/models/README.md`:

```text
Size: 6,244,458 bytes
SHA-256: 198df54da4f6aa071b342bee77b100e78f243df785b325ec364036e106572238
```

No API keys, tokens, exact LAN addresses, or other private credentials are
recorded in this evidence.
