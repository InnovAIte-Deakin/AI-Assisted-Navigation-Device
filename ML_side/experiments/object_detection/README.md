# Object Detection Experiments

## Model Comparison Results

| Model | Epochs | mAP50 | mAP50-95 | Notes |
|-------|--------|-------|----------|-------|
| YOLOv8s | 250 | 85.7% | 61.2% | Best performance, heavy augmentation |
| YOLOv8n | 100 | - | - | Standard training |
| YOLOv11n | 100 | - | - | Latest YOLO version |
| YOLOv5n | 100 | - | - | Lightweight model |
| YOLOv5s | 100 | - | - | Small model |

## Folder Structure
- `yolo_v8s_heavy_aug/` - YOLOv8s with heavy data augmentation
- `yolo_v8n/` - YOLOv8n standard training
- `yolo_v11n/` - YOLOv11n standard training
- `yolo_v5n/` - YOLOv5n standard training
- `yolo_v5s/` - YOLOv5s standard training