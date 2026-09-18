# Model Card — WB-OD-NAV-001

## Identity and intended use

| Field | Value |
| --- | --- |
| Candidate ID | `WB-OD-NAV-001` |
| Version | `0.1.0` |
| Training run | `navigation-mvp-full-candidate-56c445bb8c85` |
| Task | WalkBuddy navigation object detection |
| Lifecycle state | `candidate` |
| Production status | Not authorized; technical evidence does not grant production authorization. |

This model is an eight-class navigation candidate for the WalkBuddy backend. It
is not a production model, a canonical baseline, or an authorization to retrain
or tune against held-out data.

## Artifact identity

| Field | Value |
| --- | --- |
| Artifact | `best.pt` |
| SHA-256 | `3cbdadd14b018573803d31f3c7bd5683bf7abd19649aff6da7c1f1ea1d78cc5f` |
| Size | 5,364,741 bytes |
| Approved storage reference | `Teams SharePoint/AIAND_REPO/ML_side/T2_2026/Models/navigation/WB-OD-NAV-001/0.1.0/best.pt` |

The weights are deliberately not source-controlled. The artifact identity,
including byte size, is recorded in the model registry and Candidate deployment
manifest.

## Ordered taxonomy

`person`, `stairs`, `door`, `chair`, `table`, `pole`, `bicycle`, `vehicle`

The order must exactly match the canonical navigation contract in
`software_side/walkbuddy_reactNative/backend/ml_contract/navigation_semantics.py`.

## Training data and configuration

The registry records controlled release `walkbuddy-navigation-v5` and its
controlled external manifest reference. Its recorded sequence-aware split is:

| Split | Images | Allowed use |
| --- | ---: | --- |
| Train | 24,480 | Training |
| Validation | 6,994 | Validation |
| Held-out test | 3,497 | Evaluation only; never a tuning source |

The reviewed configuration uses a full training fraction, 20 epochs, image size
640, batch size 16, seed 42, AdamW, learning rate 0.001, automatic device
selection, and validation enabled. It records a candidate-only output boundary.
The committed configuration does not contain a per-epoch training validation
summary, so this card does not invent one.

## Corrected held-out evaluation

The corrected, versioned labelled evaluation is on the held-out `test` split.
It is evaluation evidence, not a tuning source.

| Metric | Value |
| --- | ---: |
| Precision | 0.6960 |
| Recall | 0.6122 |
| mAP@50 | 0.6685 |
| mAP@50:95 | 0.4357 |
| Images | 3,497 |

The evaluation reports the following timing components in milliseconds per
image: preprocessing 3.5567, inference 4.1700, postprocessing 0.2419. These
are evaluator-recorded values, not an end-to-end mobile latency claim.

## Formal inference benchmark

The formal performance benchmark used one repository test fixture, five warm-up
runs, and 50 measured runs per device. It did not use held-out test data and
does not measure accuracy.

| Metric | CPU | Apple MPS |
| --- | ---: | ---: |
| Mean warm latency | 59.729 ms | 55.203 ms |
| p95 warm latency | 60.010 ms | 60.541 ms |
| Throughput | 16.742 FPS | 18.114 FPS |

The results apply only to the recorded macOS arm64 environment (Python 3.11.15,
PyTorch 2.9.1, Ultralytics 8.4.7); they are not device requirements or a
platform-wide performance guarantee.

## Deployment and runtime evidence

The candidate deployment manifest requires the exact artifact identity and the
canonical taxonomy. Its compute policy is `cuda_preferred`; this does not change
the lifecycle state. The Issue #74 real-candidate record documents a controlled,
non-mock runtime launch with usable CUDA, successful `/ml/model-info`,
`/ml/ready`, and `/ml/health` checks, and matching Candidate identity.

## Safety acceptance and depth semantics

Issue #74 records a real validation-only stairs hazard case, a non-trigger case,
and a deterministic `/chat` safety override before the LLM path. It records the
observed `relative_depth` as a **unitless relative score**. It is not calibrated
physical distance and must not be represented as metres. `distance_m` must not
be populated from the relative score; the recorded acceptance observation has
`distance_m: null`.

## Limitations and pole investigation

The corrected held-out evaluation reports `pole` as the weakest class: precision
0.0548, recall 0.5184, mAP@50 0.1755, and mAP@50:95 0.1476. Existing registry
evidence also records recall limitations for small normalized-area boxes and
extreme height-to-width buckets. This is observational evidence, not a causal
diagnosis. No merged Candidate 1 geometry-analysis implementation is claimed by
this card.

The historical seven-class baseline is not comparable to this eight-class
candidate and cannot be used as an automatic promotion gate.

## Reproducibility and evidence

Run the read-only handover check from the repository root:

```powershell
python -m ML_side.tools.release_readiness --candidate WB-OD-NAV-001
```

Authoritative repository evidence:

- `ML_side/model_registry/records/navigation_candidate.json`
- `ML_side/deployment/manifests/navigation_candidate_56c445bb8c85.json`
- `ML_side/config/training_navigation_full_candidate_56c445bb8c85.yaml`
- `ML_side/evaluation/candidates/navigation-mvp-full-candidate-56c445bb8c85-heldout-test-corrected/summary.json`
- `ML_side/benchmark_results/inference_performance.json`
- `ML_side/evaluation/candidates/navigation-mvp-full-candidate-56c445bb8c85-runtime-acceptance/issue-74-real-candidate-safety-validation.json`

See `ML_side/docs/ML_EVIDENCE_INDEX.md` for the full handover map. A technical
PASS remains distinct from lifecycle transition and production authorization.
