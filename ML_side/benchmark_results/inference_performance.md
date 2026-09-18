# Candidate 1 Inference Performance Benchmark

## Model

- Candidate ID: `WB-OD-NAV-001`
- Candidate run: `navigation-mvp-full-candidate-56c445bb8c85`
- Artifact: `ML_side/models/best.pt`
- SHA-256: `3cbdadd14b018573803d31f3c7bd5683bf7abd19649aff6da7c1f1ea1d78cc5f`
- Size: 5,364,741 bytes
- Classes: person, stairs, door, chair, table, pole, bicycle, vehicle

The model identity matches the Candidate 1 deployment manifest.

## Benchmark setup

The benchmark uses the repository test fixture:

`ML_side/testing_pipeline/test_assets/test.png`

This benchmark measures inference performance only. It does not evaluate accuracy, tune model parameters, or use the held-out test set.

Configuration:

- 5 warm-up runs per device
- 50 measured inference runs per device
- Confidence threshold: 0.25
- IoU threshold: 0.45
- CPU and Apple MPS tested
- CUDA unavailable on the benchmark machine

Software:

- Python 3.11.15
- PyTorch 2.9.1
- Ultralytics 8.4.7
- macOS arm64

## Results

| Metric | CPU | Apple MPS |
| --- | ---: | ---: |
| Cold inference | 101.526 ms | 462.322 ms |
| Mean warm latency | 59.729 ms | 55.203 ms |
| Median warm latency | 59.739 ms | 55.518 ms |
| p95 warm latency | 60.010 ms | 60.541 ms |
| Throughput | 16.742 FPS | 18.114 FPS |

Apple MPS produced slightly better mean warm inference latency and throughput on this machine. However, its cold inference latency was substantially higher than CPU, showing the importance of model warm-up before latency-sensitive use.

Full per-run measurements, model identity, environment information, model-load timing and warm-up timing are recorded in `inference_performance.json`.

## Reproduce

From the repository root with the project Python environment active:

```bash
python ML_side/tools/benchmark_inference_performance.py --device all
