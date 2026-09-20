# Candidate Runtime Soak Validation

`runtime_soak` is a bounded, read-only WebSocket reliability check for a
technically ready candidate. It exercises the deployed `/ws/vision` protocol,
including reconnects and controlled malformed input, and records runtime
metric reconciliation. It is separate from model-performance benchmarking,
one-shot acceptance evidence, and physical end-to-end validation.

It does not replace Uvin's formal inference benchmark: that benchmark measures
controlled model inference, while this tool measures the integrated runtime
protocol. It also does not replace the one-shot Candidate acceptance record;
this is repeatable sustained-runtime evidence.

## Evidence boundary

The runner resolves the candidate from the authoritative
[`navigation_candidate_56c445bb8c85.json`](../deployment/manifests/navigation_candidate_56c445bb8c85.json)
manifest and verifies the linked registry identity and canonical taxonomy. It
then checks `/ml/model-info`, `/ml/ready`, `/ml/health`, and `/ml/metrics`.
It does not use the legacy seven-class taxonomy or substitute a hard-coded
candidate identity.

## Real-runtime invocation

Use only a user-provided controlled or synthetic fixture directory that is not
a test split or held-out set:

```powershell
python -m ML_side.tools.runtime_soak `
  --candidate WB-OD-NAV-001 `
  --base-url http://<backend-host>:8000 `
  --fixture-dir .\fixtures\validation `
  --frames 500 --interval-ms 250 --reconnect-every 50 --malformed-every 100 `
  --out-dir .\evidence\runtime-soak
```

The runner sends `frame_meta` followed by binary image data, verifies the
current response contract for every sampled frame, and deliberately closes and
reopens the socket at the requested cadence. A malformed `frame_meta` message
is ignored by the current server; malformed image bytes are expected to use the
existing public `inference_failed` error shape. A subsequent valid frame must
still complete successfully.

No fixture path, image bytes, request secret, or raw backend URL is written to
the reports.

## Synthetic CI mode

Use mock mode where a backend, model weights, dataset, CUDA, or network are
unavailable:

```powershell
python -m ML_side.tools.runtime_soak --mock --frames 50 `
  --out-dir .\evidence\runtime-soak-mock
```

In mock mode, the default reconnect and malformed-image cadences are both 10,
so this command exercises reconnect accounting and malformed-input recovery.
Mock output is explicitly labelled `synthetic/mock`; it is never real-candidate
evidence and cannot be used for release approval.

## Metrics and interpretation

The report records per-frame protocol outcomes and client-observed latency
statistics (P50, P95, P99). These are distinct from backend inference-latency
metrics. It validates the documented counter relationships over the soak
window: attempts equal successful plus failed inference, processed frames equal
successful inference, counters do not regress, and active inference returns to
zero. Dropped frames remain informational because they are tracked separately.

There are no invented performance thresholds. The report therefore records
`performance_threshold_gate: NOT CONFIGURED` while still reporting the measured
latency distribution and any runtime-contract failures.

## Governance

- A passing soak run is runtime reliability evidence only.
- It does not promote, deploy, or register a model.
- It does not grant production approval.
- Candidate lifecycle state remains `candidate` unless separately governed.
