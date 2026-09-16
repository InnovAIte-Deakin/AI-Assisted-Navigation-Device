# Physical Device CUDA Runtime Validation

## Scope

This document records supplied runtime and integration evidence for navigation
Candidate 1, run ID `navigation-mvp-full-candidate-56c445bb8c85`. The artifact
was `best.pt`, SHA-256
`3cbdadd14b018573803d31f3c7bd5683bf7abd19649aff6da7c1f1ea1d78cc5f`,
size `5364741` bytes, with ordered classes `person`, `stairs`, `door`, `chair`,
`table`, `pole`, `bicycle`, and `vehicle`.

The candidate remains **candidate**. This is runtime/integration evidence, not
a formal model-quality evaluation, and it does not authorize production
promotion. Screenshots may be added separately later.

## Demonstrated physical path

The supplied test used a physical Android phone and the Expo React Native app:

```text
Android phone camera -> Expo React Native app -> LAN backend -> /ws/vision
-> Candidate 1 best.pt -> YOLO inference -> detection overlays -> Expo Speech TTS
```

Detection overlays and labels were observed, along with navigation/safety
guidance and Expo Speech TTS.

## CPU run

Initial backend environment:

- `torch 2.9.1+cpu`
- `torchvision 0.24.1+cpu`
- CUDA unavailable
- CPU-only execution

| Metric | Value |
| --- | ---: |
| Total attempts | 51 |
| Successful inferences | 51 |
| Failed inferences | 0 |
| Processed frames | 51 |
| Dropped frames | 0 |
| Mean latency | 4479.919288235525 ms |
| P50 latency | 2376.695600018138 ms |
| P95 latency | 19176.259600004414 ms |
| Maximum latency | 21154.976399993757 ms |

## GPU run

After changing only the local backend environment:

- `torch 2.9.1+cu130`
- `torchvision 0.24.1+cu130`
- CUDA available, build `13.0`
- GPU: `NVIDIA GeForce RTX 3050 Laptop GPU`

| Metric | Value |
| --- | ---: |
| Total attempts | 61 |
| Successful inferences | 61 |
| Failed inferences | 0 |
| Processed frames | 61 |
| Dropped frames | 0 |
| Latest latency | 284.6477999992203 ms |
| Mean latency | 326.9811885271099 ms |
| P50 latency | 306.02380001801066 ms |
| P95 latency | 418.97990001598373 ms |
| Maximum latency | 1191.7175000126008 ms |

## Comparison

All supplied inferences succeeded: 51/51 on CPU and 61/61 on GPU. Both metric
snapshots report zero dropped frames.

Using the supplied mean latency, GPU reduced mean latency by approximately
`92.70%` (4479.92 ms to 326.98 ms), a roughly `13.70x` reduction. The supplied
P95 latency reduced by approximately `97.82%` (19176.26 ms to 418.98 ms), a
roughly `45.77x` reduction. These figures describe the supplied device/runtime
snapshots only; differing sample counts mean they are not a controlled model
benchmark.

## Follow-up

The backend may attempt to send a completed inference result after the app loses
focus and the vision WebSocket has closed. Observed errors include
`WebSocketDisconnect` and `Cannot call "send" once a close message has been
sent.` This is a WebSocket lifecycle race, not evidence that completed frames
were invalid. The recommended follow-up is a coordinated backend regression
test and guarded result-send cleanup in `backend/routers/ai_service.py`; that
file is intentionally unchanged here.
