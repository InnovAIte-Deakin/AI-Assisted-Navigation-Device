# WalkBuddy ML Evidence Index

This index identifies the current, repository-controlled evidence for a new
teammate. It is a navigation aid, not a lifecycle action or production
authorization.

| Topic | Canonical evidence | What it establishes |
| --- | --- | --- |
| Candidate registry and lifecycle | `ML_side/model_registry/records/navigation_candidate.json` | Candidate ID, run ID, artifact identity, controlled split counts, and `candidate` lifecycle. |
| Controlled dataset lineage | Registry `dataset` section; controlled manifest reference `external-local/manifest.json` | Release `walkbuddy-navigation-v5`, sequence-aware counts, and that held-out data is evaluation-only. The controlled source manifest remains external rather than being copied into Git. |
| Training run/configuration | `ML_side/config/training_navigation_full_candidate_56c445bb8c85.yaml` | Candidate training settings and the candidate-only boundary. |
| Canonical taxonomy | `software_side/walkbuddy_reactNative/backend/ml_contract/navigation_semantics.py` | The ordered eight-class navigation contract. `ML_side/evaluation/taxonomy.py` consumes this contract. |
| Deployment identity/preflight contract | `ML_side/deployment/manifests/navigation_candidate_56c445bb8c85.json`; `ML_side/deployment/tools/check_candidate_readiness.py` | Required Candidate artifact, SHA, size, taxonomy, and read-only deployment readiness checks. |
| Corrected held-out evaluation | `ML_side/evaluation/candidates/navigation-mvp-full-candidate-56c445bb8c85-heldout-test-corrected/summary.json` | Labelled evaluation on 3,497 held-out test images. Evaluation only, never tuning. |
| Historical comparison | `ML_side/evaluation/baselines/historical_7class_baseline.json` | Clearly historical seven-class qualitative evidence; not comparable to Candidate 1 and never an automatic promotion gate. |
| Formal inference benchmark | `ML_side/benchmark_results/inference_performance.json` | Candidate identity, recorded environment, latency and throughput measurements, with held-out data excluded. |
| Runtime acceptance | `ML_side/evaluation/candidates/navigation-mvp-full-candidate-56c445bb8c85-runtime-acceptance/README.md` | Real candidate backend/router and WebSocket acceptance context. Smoke observations are not benchmark guarantees. |
| Issue #74 safety acceptance | `ML_side/evaluation/candidates/navigation-mvp-full-candidate-56c445bb8c85-runtime-acceptance/issue-74-real-candidate-safety-validation.json` | Controlled launch, operational endpoints, real hazard/non-trigger cases, deterministic chat safety, and depth semantics. |
| Navigation safety contract | `software_side/walkbuddy_reactNative/backend/slow_lane/safetygate.py`; `software_side/walkbuddy_reactNative/backend/ml_contract/navigation_semantics.py` | Canonical detection meaning and deterministic safety behavior. |
| Relative-depth semantics | `software_side/walkbuddy_reactNative/backend/adapters/depth_adapter.py`; Issue #74 safety evidence | `relative_depth` is unitless, not metres. It must not populate `distance_m`. |
| Pole/geometry investigation | Candidate registry limitations and corrected held-out evaluation | Existing evidence identifies a pole weakness. No unmerged geometry implementation is treated as evidence. |
| Formal model card | `ML_side/model_registry/model_cards/WB-OD-NAV-001.md` | Human-readable Candidate 1 handover summary. |
| Release-readiness system | `ML_side/tools/release_readiness.py`; `ML_side/release_readiness_lib/` | Repeatable offline checks and optional live endpoint identity verification. |

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
