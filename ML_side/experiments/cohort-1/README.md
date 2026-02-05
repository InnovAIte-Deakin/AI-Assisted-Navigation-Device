# Cohort 1 — Object Detection & OCR Experiments (YOLO)

This README documents the **actual, reproducible state** of Cohort 1 experiments.  
Where discrepancies exist, **`results.csv` and `args.yaml` are treated as the source of truth**.  
PDF reports are retained as historical artifacts but are not authoritative.

---

## Scope

- Evaluated **5 YOLO variants**: v5n, v5s, v8n, v8s, v11n  
- Task: object detection on a custom dataset (Deakin Library images + Roboflow dataset)  
- Secondary work: OCR integration (not reflected in performance reports)

---

## Artifacts Produced

### PDF Reports (Non-authoritative)
- `YOLOv11n_Customset_Report.pdf`
- `YOLOv8n_Customset_by224770542 1.pdf`
- `YOLOv5s_Customset_Atharva.pdf`
- `performance metrics.pdf`

> These reports contain multiple metric, dataset, and configuration mismatches relative to logged experiment outputs.

### Notebooks
- `01_data_processing.ipynb` — dataset preparation
- `02_object_detection_training.ipynb` — YOLO training + evaluation
- `03_ocr_integration.ipynb` — OCR pipeline integration (functional, undocumented in reports)

### Generated Artifacts
- YOLO experiment folders (images, predictions, logs)
- `results.csv` — **authoritative metrics**
- `args.yaml` — **authoritative configuration**
- Model weights (e.g. `best.pt`)

---

## Known Drift & Integrity Issues

### Metric Inflation / Misinterpretation
| Model | Reported mAP50 | Actual mAP50 | Discrepancy |
|------|---------------|--------------|-------------|
| v5s  | 0.950 | 0.852 | +9.8% |
| v8n  | 0.934 | 0.857 | +7.7% |
| v8n (mAP50-95) | 0.826 | 0.626 | +20% |
| v11n | 0.848 | 0.830 | +1.8% |
| v8s  | 0.845 | 0.835 | +1.0% |

Likely causes:
- Misreading per-class metrics as aggregate
- Copying intermediate rather than final epoch values
- Manual transcription errors

### Dataset Mismatch
- Reports cite **147 office chairs**
- Repository `/data` contains **20 chairs**
- `args.yaml` references a **“Combined Dataset” / Roboflow export** not present in repo

### Training Run Inconsistencies
- v8s report claims **250 epochs**
- Actual training **stopped at epoch 169**

### Documentation Gaps
- OCR work exists and functions (`03_ocr_integration.ipynb`)
- Entirely omitted from all performance reports

---

## Experiment Configuration (Actual)

Derived from `args.yaml`.

| Model | Base Weights | Img Size | Target Epochs | Batch | lr0 | Augmentations |
|-----|-------------|----------|---------------|-------|-----|---------------|
| v5n | yolov5n.pt | 640 | 100 | 32 | 0.01 | Mosaic (1.0) |
| v5s | yolov5s.pt | 640 | 100 | 32 | 0.01 | Mosaic (1.0) |
| v8n | yolov8n.pt | 640 | 100 | 32 | 0.01 | Mosaic (1.0) |
| v8s | yolov8s.pt | 640 | 250 | 16 | 0.003 | Mosaic (0.8), MixUp (0.15) |
| v11n | yolo11n.pt | 640 | 100 | 32 | 0.01 | Mosaic (1.0) |

---

## Experiment Results (Actual)

Derived from `results.csv`.

| Model | Final Epoch | Precision | Recall | mAP50 | mAP50-95 | Status |
|-----|-------------|----------|--------|-------|---------|--------|
| v5n | 92 | 0.870 | 0.803 | 0.859 | 0.588 | Converged |
| v5s | 100 | 0.869 | 0.820 | 0.852 | 0.603 | Stable |
| v8n | 100 | 0.853 | 0.841 | 0.857 | 0.626 | Top balanced |
| v8s | 169 | 0.867 | 0.791 | 0.835 | 0.581 | Stopped early |
| v11n | 99 | 0.833 | 0.846 | 0.830 | 0.557 | Stable |

---

## Interpretation Notes

- **v8n** offers the best precision–recall balance and strongest mAP50-95.
- **v5n** converged early with competitive mAP50 but weaker recall.
- **v8s** underperformed relative to its heavier augmentation and longer target run, likely due to early termination.
- **v11n** stable but not competitive on mAP50-95.

---

## Source-of-Truth Policy

When discrepancies arise:
1. `results.csv` overrides reports
2. `args.yaml` overrides narrative descriptions
3. PDFs are treated as interpretive summaries only

---

## Status

Cohort 1 results are **not reproducible end-to-end** due to:
- missing dataset exports
- manual artifact copying
- undocumented experiment lineage

This README reflects the **maximum defensible reconstruction** from available logs and configs.
