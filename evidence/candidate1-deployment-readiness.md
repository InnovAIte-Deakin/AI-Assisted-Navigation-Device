# Candidate Deployment Readiness

## Candidate

- ID: `WB-OD-NAV-001`
- Run: `navigation-mvp-full-candidate-56c445bb8c85`

## Manifest

- Reference: `ML_side/deployment/manifests/navigation_candidate_56c445bb8c85.json`

## Registry Lineage

- Reference: `ML_side/model_registry/records/navigation_candidate.json`

## Artifact Identity

- Filename: `best.pt`
- SHA-256: `3cbdadd14b018573803d31f3c7bd5683bf7abd19649aff6da7c1f1ea1d78cc5f`

## Runtime Environment

- Python: `3.11.9`
- Torch: `2.9.1+cu130`

## Compute

- CUDA available: `True`
- CUDA usable: `True`

## Backend Contract

- Base URL: `http://<LAN_IP>:8000`

## Metrics Snapshot

```json
{
  "active_inferences": 0,
  "dropped_frames": 0,
  "failed_inferences": 0,
  "last_inference_at": null,
  "latency_window_capacity": 256,
  "latency_window_size": 0,
  "latest_latency_ms": null,
  "max_latency_ms": null,
  "mean_latency_ms": null,
  "p50_latency_ms": null,
  "p95_latency_ms": null,
  "processed_frames": 0,
  "successful_inferences": 0,
  "total_attempts": 0
}
```

## Warnings


## Failures


## Overall Result

**PASS**

## Governance Note

This read-only deployment-readiness evidence is not a held-out model-quality evaluation, not production authorization, does not change lifecycle, and does not replace human review or physical-device acceptance testing.
