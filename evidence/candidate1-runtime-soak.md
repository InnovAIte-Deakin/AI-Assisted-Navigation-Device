# WalkBuddy Candidate Runtime Soak Validation

- Evidence mode: **real_candidate_runtime**
- Real Candidate runtime validated: **YES**
- Candidate: `WB-OD-NAV-001`
- Run: `navigation-mvp-full-candidate-56c445bb8c85`
- Runtime soak result: **PASS**
- Performance threshold gate: **NOT CONFIGURED**

## Frame and connection summary

- Configured frames: 500
- Attempted valid frames: 496
- Successful valid responses: 496
- Inference failures (public errors): 4
- Deliberate reconnects: 9 / 9
- Unexpected disconnects: 0
- Malformed input injections: 4
- Malformed stable public errors: 4
- Malformed-input recovery: PASS

## Runtime environment

- PyTorch: `2.9.1+cu130`
- CUDA usable: `True`
- Device: `cuda:0`
- GPU: `NVIDIA GeForce RTX 3050 Laptop GPU`

## Client end-to-end WebSocket latency

| Count | Mean ms | P50 ms | P95 ms | P99 ms | Min ms | Max ms | Throughput FPS |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 500 | 161.78389659931418 | 110.16574998211581 | 467.75480000069365 | 743.2396730058822 | 14.157400000840425 | 1184.9959999963176 | 2.356876791751912 |

Client end-to-end WebSocket latency is distinct from aggregate backend inference latency; this report does not compare them as equivalent.

## Backend metric reconciliation

- Reconciliation: **PASS**
- Final active inferences: 0

## Governance boundary

- Lifecycle state: `candidate`
- Production authorization: **NOT GRANTED**
- Automatic promotion performed: **NO**

Technical soak validation is read-only. It does not alter lifecycle state, authorize production, promote a model, retrain, or create a new candidate.
