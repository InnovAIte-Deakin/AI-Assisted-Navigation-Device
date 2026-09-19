# WalkBuddy ML Evidence Index

This index identifies repository-controlled evidence for a new teammate. It is
a navigation aid, not a lifecycle action or production authorization.

## Canonical evidence

| Topic | Canonical evidence | What it establishes |
| --- | --- | --- |
| Candidate registry and lifecycle | [registry record](../model_registry/records/navigation_candidate.json) | Candidate ID, artifact filename/SHA, taxonomy, controlled release reference, and `candidate` lifecycle. |
| Deployment identity/preflight contract | [Candidate manifest](../deployment/manifests/navigation_candidate_56c445bb8c85.json); [candidate-readiness tool](../deployment/tools/check_candidate_readiness.py) | The authoritative Candidate ID/run, artifact SHA/size, taxonomy, and read-only deployment checks. |
| Controlled dataset lineage | Registry `dataset` section; external controlled manifest reference `external-local/manifest.json` | Release `walkbuddy-navigation-v5`. The source manifest is intentionally external, so it is not an offline-CI input. |
| Training configuration | [candidate configuration](../config/training_navigation_full_candidate_56c445bb8c85.yaml) | Full-data candidate settings, development validation enabled, and the candidate-only output boundary. |
| Canonical taxonomy | [backend navigation contract](../../software_side/walkbuddy_reactNative/backend/ml_contract/navigation_semantics.py); [ML taxonomy adapter](../evaluation/taxonomy.py) | One ordered eight-class navigation contract. |
| Corrected held-out evaluation | [corrected summary](../evaluation/candidates/navigation-mvp-full-candidate-56c445bb8c85-heldout-test-corrected/summary.json) | Labelled evaluation on 3,497 held-out test images; evaluation evidence only, never tuning. |
| Formal inference benchmark | [benchmark JSON](../benchmark_results/inference_performance.json) | Historical recorded environment, latency, and throughput. Candidate association is derived by matching its artifact identity to the manifest; no measured value is rewritten. |
| Runtime acceptance | [acceptance README](../evaluation/candidates/navigation-mvp-full-candidate-56c445bb8c85-runtime-acceptance/README.md); [Issue #74 record](../evaluation/candidates/navigation-mvp-full-candidate-56c445bb8c85-runtime-acceptance/issue-74-real-candidate-safety-validation.json) | Controlled real-candidate launch, operational endpoints, safety cases, and depth semantics. Smoke observations are not benchmark guarantees. |
| Navigation safety and depth contract | [safety gate](../../software_side/walkbuddy_reactNative/backend/slow_lane/safetygate.py); [depth adapter](../../software_side/walkbuddy_reactNative/backend/adapters/depth_adapter.py) | Canonical detection handling. `relative_depth` is unitless and cannot populate `distance_m`. |
| Formal model card | [WB-OD-NAV-001 model card](../model_registry/model_cards/WB-OD-NAV-001.md) | Human-readable Candidate 1 handover summary. |
| Release-readiness system | [CLI](../tools/release_readiness.py); [implementation](../release_readiness_lib/core.py) | Deterministic, read-only offline checks with optional live endpoint verification. |

## Current merged tooling and operations

| Topic | Repository source | What it establishes |
| --- | --- | --- |
| Geometry evaluation tooling (merged #239) | [geometry CLI](../evaluation/run_geometry_eval.py); [pipeline guide](EVALUATION_PIPELINE.md) | Reusable size/aspect and pole-focused reports from train/validation inputs; the tool refuses held-out test inputs. Its committed evidence is synthetic tooling coverage, not a Candidate 1 re-score or causal finding. |
| Model checksum observability (merged #234) | [model-info lineage](../../software_side/walkbuddy_reactNative/backend/ml_runtime/model_info.py); [runtime readiness](../../software_side/walkbuddy_reactNative/backend/ml_runtime/state.py) | `/ml/model-info` exposes `checksum_verified`: `null` is valid when no controlled expected SHA is configured. `/ml/ready` remains the runtime technical gate; observability is not a second promotion policy. |
| Physical-device connectivity diagnostics (merged #227) | [local setup guide](../../docs/LOCAL_SETUP.md) | Phone/backend connectivity and WebSocket troubleshooting for physical-device validation; it is operational guidance, not offline model evidence. |

## Historical and pending material

The [historical seven-class baseline](../evaluation/baselines/historical_7class_baseline.json) is not comparable to Candidate 1 and cannot be an automatic promotion gate.

Pending or requested-changes work, including PR #241 pole-data-quality discussion, is not canonical evidence here. Do not infer its duplicate, leakage, or other conclusions into Candidate 1 decisions until it is merged and independently reviewed.

## Using the readiness system

Offline verification uses committed metadata and evidence only. It does not need
weights, CUDA, a backend, the held-out dataset, or internet access:

```powershell
python -m ML_side.tools.release_readiness --candidate WB-OD-NAV-001
```

Write sanitized, local reports when needed (do not commit them by default):

```powershell
python -m ML_side.tools.release_readiness --candidate WB-OD-NAV-001 --out-dir .\evidence\release-readiness
```

Optional live mode verifies the running model identity and `/ml/model-info`,
`/ml/ready`, and `/ml/health` endpoint contract. It does not launch a backend:

```powershell
python -m ML_side.tools.release_readiness --candidate WB-OD-NAV-001 --live-base-url http://<backend-host>:8000
```

`PASS` means the checked technical evidence agrees. `FAIL` means required
evidence is missing, malformed, or inconsistent. `WARNING` identifies a
non-blocking condition. `NOT_CHECKED` is used for intentionally omitted optional
verification, such as live mode. No status changes lifecycle state, authorizes
production, promotes a model, or permits held-out tuning.
