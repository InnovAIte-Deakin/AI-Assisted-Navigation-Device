# Candidate Deployment Readiness

This ML-owned, read-only workflow turns candidate deployment checks into durable
evidence. It combines a portable deployment manifest, the authoritative model
registry, the existing `ML_side/tools/runtime_preflight.py`, and optional
backend contract checks. It never copies weights, changes a registry record,
or authorizes production.

## Boundaries and ownership

The model registry remains the authority for lifecycle. A manifest duplicates
identity fields deliberately so a candidate deployment can be checked without
guessing; the readiness tool fails when its filename, SHA-256, taxonomy,
lifecycle, training configuration reference, or evaluation evidence reference
disagrees with the registry. A readiness `PASS` is neither production approval
nor held-out model-quality evidence. It does not replace human review or the
physical-device acceptance test.

The backend owns its runtime behavior. Today it reads `WALKBUDDY_MODEL_DIR` as
a **directory** and appends `best.pt`; when it is unset it falls back to
`ML_side/models`. The deployment helper therefore requires a model named
`best.pt`, sets the directory rather than a file path, and does not alter
backend or frontend code.

## Manifest format

Schema `1.0.0` is in
`ML_side/deployment/schema/candidate-deployment-manifest.schema.json`. Manifests
are portable JSON and references must be repository-relative POSIX paths. The
required fields are candidate and run IDs, expected lifecycle, artifact name,
SHA-256, byte size, ordered taxonomy, registry record reference, and compute
policy. Optional training/evaluation references are checked when supplied.

Compute policies are:

- `cpu_allowed`: functional CPU development is supported.
- `cuda_preferred`: CPU remains usable but produces a readiness warning.
- `cuda_required`: unavailable or unusable CUDA fails readiness.

Candidate 1's example manifest records only supplied/authoritative identity and
lineage references. Its lifecycle is still `candidate`; it must not be used as
evidence of production authorization.

## Commands

From the repository root, inspect an environment without a model or network:

```powershell
python .\ML_side\deployment\tools\environment_doctor.py --port 8000 --json-out .\evidence\environment-doctor.json
```

Validate just the manifest, with human-readable output and optional JSON
diagnostics:

```powershell
python .\ML_side\deployment\tools\validate_deployment_manifest.py `
  .\ML_side\deployment\manifests\candidate.json `
  --json-out .\evidence\manifest-diagnostics.json
```

Run deployment readiness against a deliberately supplied candidate and backend:

```powershell
python .\ML_side\deployment\tools\check_candidate_readiness.py `
  --manifest .\ML_side\deployment\manifests\candidate.json `
  --model "C:\models\candidate\weights\best.pt" `
  --base-url "http://<PC_LAN_IP>:8000" `
  --json-out .\evidence\candidate-readiness.json `
  --markdown-out .\evidence\candidate-readiness.md
```

Use `--require-cuda` when the physical-device run requires usable CUDA. The
tool separately reports CUDA availability and a tiny allocation/operation/sync
usability check. It never requires an RTX 3050 or any particular GPU. CPU-only
developers can still use the tools; a CPU state is a warning unless policy or
the flag requires CUDA.

Evidence destinations are checked before writes. Reports cannot overwrite a
model, share JSON/Markdown paths, or live inside supplied model, `ML_side/models`,
or `ML_side/artifacts` directories. Use an `evidence/` directory outside model
stores. API keys are passed only to the request layer and are not written to
evidence.

Validate generated evidence:

```powershell
python .\ML_side\deployment\tools\validate_evidence.py .\evidence\candidate-readiness.json
```

## Candidate backend helper

The PowerShell helper is dry-run-first. It validates readiness, prints a safely
argumentized Uvicorn command, sets `WALKBUDDY_MODEL_DIR` and
`WALKBUDDY_ML_MOCK=0`, and only launches with `-Execute`:

```powershell
.\ML_side\deployment\scripts\start_candidate_backend.ps1 `
  -ModelPath "C:\models\candidate\weights\best.pt" `
  -ManifestPath .\ML_side\deployment\manifests\candidate.json `
  -Python python -RequireCuda
```

For a phone-accessible backend, add `-Execute -Host 0.0.0.0 -Port 8000`; phone
and PC must share Wi-Fi, Windows Firewall must allow the private-network port,
and Expo must use `http://<PC_LAN_IP>:8000`. The helper uses PowerShell argument
arrays and `Resolve-Path`, not shell string evaluation, so spaces are safe.

## Backend and troubleshooting

The preflight checks `/ml/model-info`, `/ml/ready`, `/ml/health`, and
`/ml/metrics`, including loaded state, backend identity, taxonomy, readiness,
health, finite metrics, and transport/HTTP/JSON failures. A missing Llama
artifact or unavailable OpenTelemetry collector does not by itself prove YOLO
vision is unavailable; the environment doctor classifies feature-specific
dependencies separately.

Common issues:

- **CPU-only torch:** look for a `+cpu` torch build, false CUDA availability,
  and high latency. Check the actual interpreter and CUDA usability; do not
  change universal requirements to a CUDA wheel.
- **Wrong candidate:** SHA, filename, size, or ordered taxonomy disagreement is
  a failure. Do not substitute `last.pt` or replace `best.pt`.
- **Phone cannot connect:** check LAN IPv4, `0.0.0.0` binding, same Wi-Fi,
  firewall, and Expo's backend base URL.
- **Expo mismatch:** use the project-compatible Expo workflow; do not casually
  upgrade the whole app during candidate validation.
- **WebSocket close on blur:** an in-flight result can finish after a close and
  backend send can raise a disconnect error. This is a backend-owned follow-up,
  not changed by this tooling.

## Physical-device context

Existing evidence recorded Android -> Expo -> `/ws/vision` -> exact Candidate
1 -> detections/overlays -> guidance -> TTS. The observed CPU session had 51
successful, zero failed/dropped frames and mean latency 4479.919288235525 ms.
The observed CUDA session had 61 successful, zero failed/dropped frames and
mean latency 326.9811885271099 ms (p95 418.97990001598373 ms), using torch
2.9.1+cu130, torchvision 0.24.1+cu130, CUDA 13.0, and an RTX 3050 Laptop GPU.
Those are observations, not a controlled benchmark, hardware requirement, or
production acceptance result. No screenshots are claimed by this document.
