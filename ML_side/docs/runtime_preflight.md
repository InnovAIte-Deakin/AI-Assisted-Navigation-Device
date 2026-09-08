# Runtime Preflight for Navigation Candidates

`ML_side/tools/runtime_preflight.py` is a read-only deployment check for a
locally supplied navigation candidate. It exists because the physical Android
test exposed a material runtime distinction: the same real candidate and phone
path was initially run through CPU-only PyTorch, then through CUDA-enabled
PyTorch with substantially lower observed latency.

The tool never trains, copies, promotes, or changes a candidate lifecycle
record. A PASS is runtime evidence only; it is not a model-quality evaluation
and does not authorize production promotion.

## CPU and CUDA policy

CPU remains a supported developer configuration. A CPU-only runtime produces a
clear `WARNING` and exits successfully by default. Use `--require-cuda` for a
phone-performance preflight: CUDA being unavailable or unusable then produces
`FAIL` and a non-zero exit code. The command separately records CUDA
availability and a minimal CUDA allocation, operation, and synchronization
check; it does not require a specific GPU model.
developers without CUDA must not install a GPU build just to use the project.

Do not pin a CUDA wheel in the cross-platform backend requirements. On Windows,
install the appropriate PyTorch/torchvision CUDA wheel only in the local backend
environment, following the official PyTorch selector for the installed driver.
Then verify with the preflight before a device run. CPU and macOS developers can
continue using their compatible runtime.

## Candidate configuration

The CLI has no built-in Candidate 1 path or checksum. Supply future-candidate
identity through arguments, or use a model-registry JSON record for its filename,
SHA-256, and ordered taxonomy. Size is intentionally an explicit argument when
the record does not carry one.

Candidate 1 worked example (PowerShell, from repository root):

```powershell
& ".\software_side\walkbuddy_reactNative\backend\.venv\Scripts\python.exe" `
  ".\ML_side\tools\runtime_preflight.py" `
  --model "C:\path\to\navigation-mvp-full-candidate-56c445bb8c85\weights\best.pt" `
  --candidate-record ".\ML_side\model_registry\records\navigation_candidate.json" `
  --expected-size 5364741 `
  --base-url "http://10.0.0.10:8000" `
  --require-cuda `
  --json-out ".\evidence\runtime-preflight-candidate1.json" `
  --markdown-out ".\evidence\runtime-preflight-candidate1.md"
```

The expected Candidate 1 SHA-256 is
`3cbdadd14b018573803d31f3c7bd5683bf7abd19649aff6da7c1f1ea1d78cc5f`.
The supplied registry record preserves its lifecycle status as `candidate`.

For a candidate without a registry record, repeat `--expected-class` in exact
ID order and supply `--expected-filename`, `--expected-sha256`, and
`--expected-size` explicitly.

When `--model` is supplied with only some of those expected fields, the result
is at least `WARNING`: the tool reports exactly which identity evidence was not
checked. This keeps generic future-candidate use possible without presenting a
partial identity check as a fully verified model.

## Safe report destinations

`--json-out` and `--markdown-out` are the only write operations. Before any
runtime or backend work, the CLI resolves the paths and rejects a report path
that is the model itself, is under the supplied model's directory, is inside the
repository's known model/artifact directories, or is shared by both report
formats. Put durable evidence in a sibling evidence directory, such as the
paths in the example above. These protections leave model files and candidate
lifecycle records untouched.

## What is checked

- Python, torch, optional torchvision, CUDA build, availability, usability,
  selected device, GPU name, and GPU memory where safe to retrieve. Missing
  torchvision is recorded but does not prevent a CPU developer from running.
- Local model existence, filename, byte size, SHA-256, and exact taxonomy when
  an expected taxonomy is supplied.
- Backend `/ml/model-info`, `/ml/ready`, `/ml/health`, and `/ml/metrics` when
  `--base-url` is supplied. Backend model identity and taxonomy must agree with
  supplied expectations.

Backend failures are reported as transport (including invalid URL, refusal, or
timeout), HTTP-status, response-parsing (including empty, non-UTF-8, or invalid
JSON), or response-contract failures. No API key is placed into either report.

The JSON report uses `null` where a value is unavailable. The Markdown report
contains runtime environment, compute device, model identity, backend status,
metrics, warnings, and overall result. Avoid passing secrets with `--api-key`
when saving reports to shared evidence locations.

## Result interpretation

- `PASS`: all requested checks passed.
- `WARNING`: no requested check failed, but a non-blocking condition exists,
  such as CPU-only execution without `--require-cuda`.
- `FAIL`: a requested identity/backend check failed, the backend was malformed
  or unreachable, CUDA was reported available but could not execute a minimal
  operation, or CUDA was required but unavailable or unusable.

The preflight complements physical phone testing. It does not replace visual
overlay/TTS observation, formal held-out evaluation, or model-promotion gates.

## WebSocket lifecycle follow-up

The physical test also observed a focus-loss race: a camera WebSocket can close
while an inference is still in flight, after which the backend may attempt
`websocket.send_text`. This can log `WebSocketDisconnect` or `Cannot call
"send" once a close message has been sent.` Completed inference results remain
valid; the race concerns delivery to a connection that has already closed.

The smallest likely backend-owned fix is to catch disconnect/send-state errors
around the result send, stop processing that connection, and clean up the frame
without treating completed inference as a model failure. Add a regression test
that closes a WebSocket after binary-frame receipt but before result delivery.
This task intentionally does not modify `backend/routers/ai_service.py`.
