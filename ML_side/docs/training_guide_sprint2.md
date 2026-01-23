# Sprint 2 Model Training Guide

## Overview
Train YOLOv8s with 15 object classes for comprehensive navigation assistance.

---

## Prerequisites

### 1. Dataset Ready ✅
You should have:
- **2400+ training images** with labels
- **300+ validation images** with labels
- Data in YOLO format (normalized bounding boxes)
- All 15 classes annotated:
  - Sprint 1: book, books, monitor, office-chair, whiteboard, table, tv
  - Sprint 2: door, stairs, elevator, person, handrail, signage, fire-extinguisher, emergency-exit

### 2. GPU Recommended
- **Minimum**: 6GB VRAM (GTX 1060, RTX 2060)
- **Recommended**: 8GB+ VRAM (RTX 3060, RTX 3070)
- **Training time**:
  - GPU: ~6-10 hours (150 epochs)
  - CPU: ~40-60 hours (not recommended)

### 3. Dependencies Installed
```bash
pip install ultralytics torch opencv-python pyyaml pandas
```

---

## Quick Start

### Step 1: Verify Dataset Structure

Your dataset should be organized as:
```
ML_side/data/processed/
├── train_dataset/train/
│   ├── images/  (2400+ .jpg files)
│   └── labels/  (2400+ .txt files)
└── val_dataset/val/
    ├── images/  (300+ .jpg files)
    └── labels/  (300+ .txt files)
```

**Verify paths in `config/data_config.yaml`:**
```yaml
train: /path/to/train/images
val: /path/to/val/images
nc: 15
names: [book, books, monitor, office-chair, whiteboard, table, tv,
        door, stairs, elevator, person, handrail, signage,
        fire-extinguisher, emergency-exit]
```

### Step 2: Start Training

```bash
cd ML_side
python scripts/train_yolov8_sprint2.py
```

The script will:
1. ✅ Verify dataset (check images and labels)
2. ✅ Load Sprint 1 model for transfer learning (if available)
3. ✅ Ask for confirmation
4. 🚀 Start training (150 epochs, ~6-10 hours)

### Step 3: Monitor Training

Watch the console output for:
- **Epoch progress**: Shows current epoch/150
- **Loss values**: Should decrease over time
- **mAP metrics**: Should increase (target: 80%+)
- **ETA**: Estimated time remaining

**Training logs**:
- Console: Real-time progress
- File: `experiments/object_detection/yolo_v8s_15class_sprint2/results.csv`

### Step 4: Validate Model

After training completes:

```bash
python scripts/validate_sprint2_model.py
```

This will:
- Test on validation set
- Show per-class performance
- Compare with Sprint 1 (if available)
- Test inference speed

### Step 5: Export Model

```bash
# Export to models directory
python scripts/train_yolov8_sprint2.py
# When prompted, choose 'y' to export
```

Or manually:
```bash
cp experiments/object_detection/yolo_v8s_15class_sprint2/weights/best.pt \
   models/object_detection/sprint2_best.pt
```

### Step 6: Test with Visual Demo

```bash
python quick_visual_demo.py \
  --model models/object_detection/sprint2_best.pt \
  --image data/processed/val_dataset/val/images/test_image.jpg
```

---

## Training Configuration

### Default Parameters (Optimized from Sprint 1)

```python
{
    'epochs': 150,           # Reduced from 250 (transfer learning)
    'patience': 30,          # Early stopping
    'batch': 16,             # Batch size
    'imgsz': 640,            # Image size
    'lr0': 0.01,             # Initial learning rate
    'augment': True,         # Heavy augmentation
    'mosaic': 1.0,           # Mosaic augmentation
    'mixup': 0.15,           # Mixup augmentation
    'cache': True,           # Cache images (faster)
}
```

### Augmentation Settings (Proven Effective)

| Parameter | Value | Description |
|-----------|-------|-------------|
| hsv_h | 0.015 | Hue shift |
| hsv_s | 0.7 | Saturation shift |
| hsv_v | 0.4 | Value (brightness) shift |
| degrees | 15.0 | Rotation range |
| translate | 0.1 | Translation range |
| scale | 0.5 | Scale range |
| fliplr | 0.5 | Horizontal flip probability |
| mosaic | 1.0 | Mosaic augmentation |
| mixup | 0.15 | Mixup augmentation |

---

## Performance Targets

### Sprint 2 Goals

| Metric | Target | Sprint 1 Baseline |
|--------|--------|-------------------|
| Overall mAP@0.5 | **80%+** | 85.7% (6 classes) |
| Per-class mAP | **75%+** | - |
| Critical classes* | **85%+** | - |
| Inference speed | **<30ms** | ~25ms |

*Critical classes: door, stairs, elevator (navigation essentials)

### Acceptable Performance

- ✅ **Excellent**: mAP@0.5 > 85%
- ✅ **Good**: mAP@0.5 = 80-85%
- ⚠️ **Acceptable**: mAP@0.5 = 75-80% (consider more training)
- ❌ **Needs improvement**: mAP@0.5 < 75%

---

## Troubleshooting

### Issue: Low mAP (<75%)

**Solutions:**
1. **More training data**: Collect 500+ images per new class
2. **Longer training**: Increase epochs to 200-250
3. **Check annotations**: Verify label quality
4. **Adjust augmentation**: Reduce if overfitting, increase if underfitting

### Issue: Overfitting (train mAP high, val mAP low)

**Solutions:**
1. **More augmentation**: Increase mixup to 0.2-0.3
2. **More data**: Expand validation set
3. **Early stopping**: Already enabled (patience=30)
4. **Regularization**: Increase dropout (if using custom model)

### Issue: Out of Memory

**Solutions:**
1. **Reduce batch size**: Try batch=8 or batch=4
2. **Reduce image size**: Try imgsz=512
3. **Clear cache**: `torch.cuda.empty_cache()`
4. **Use CPU**: Set device='cpu' (slower)

### Issue: Training too slow

**Solutions:**
1. **Enable caching**: Set cache=True (already default)
2. **Reduce workers**: Set workers=4 (if CPU bottleneck)
3. **Use mixed precision**: Add `amp=True` (automatic)
4. **Smaller model**: Try yolov8n (faster, less accurate)

---

## Advanced: Custom Training

### Modify Training Parameters

Edit `scripts/train_yolov8_sprint2.py`:

```python
self.training_params = {
    'epochs': 200,        # Change here
    'batch': 8,           # Change here
    'imgsz': 512,         # Change here
    # ... other parameters
}
```

### Resume Training

If training interrupted:

```python
from ultralytics import YOLO

model = YOLO('experiments/.../weights/last.pt')  # Resume from checkpoint
model.train(resume=True)
```

### Fine-tune Specific Layers

```python
# Freeze backbone, train only head
model = YOLO('yolov8s.pt')
for param in model.model.model[:10].parameters():
    param.requires_grad = False
```

---

## Post-Training Checklist

- [ ] Model trained successfully (150 epochs completed)
- [ ] Validation mAP@0.5 >= 80%
- [ ] Per-class mAP >= 75% for critical classes
- [ ] Inference speed < 30ms
- [ ] Model exported to `models/object_detection/sprint2_best.pt`
- [ ] Visual demo tested with new model
- [ ] Results documented in SPRINT2_PROGRESS.md
- [ ] System config updated with new model path

---

## Expected Results

### Training Progress

```
Epoch 0/150:   Loss=2.5, mAP=0.15  (initializing)
Epoch 10/150:  Loss=1.2, mAP=0.55  (learning)
Epoch 50/150:  Loss=0.6, mAP=0.75  (converging)
Epoch 100/150: Loss=0.4, mAP=0.82  (refining)
Epoch 150/150: Loss=0.35, mAP=0.85 (complete)
```

### Final Metrics (Expected)

```
Overall Performance:
  mAP@0.5:      0.82 (82%)
  mAP@0.5-0.95: 0.58 (58%)
  Precision:    0.80 (80%)
  Recall:       0.76 (76%)

Per-Class Performance:
  📦 book:              85%
  📦 books:             83%
  📦 monitor:           88%
  📦 office-chair:      81%
  📦 whiteboard:        78%
  📦 table:             84%
  📦 tv:                79%
  🆕 door:              86% ⭐
  🆕 stairs:            82% ⭐
  🆕 elevator:          80% ⭐
  🆕 person:            75%
  🆕 handrail:          72%
  🆕 signage:           77%
  🆕 fire-extinguisher: 70%
  🆕 emergency-exit:    73%
```

---

## Next Steps After Training

1. **Update System Config**:
   ```yaml
   # config/system_config.yaml
   sprint2_features:
     use_15_classes: true
     model_path: "models/object_detection/sprint2_best.pt"
   ```

2. **Test Visual Demo**:
   ```bash
   python quick_visual_demo.py --model models/object_detection/sprint2_best.pt
   ```

3. **Integrate with Ollama**:
   ```bash
   python visual_navigation_demo.py --model models/object_detection/sprint2_best.pt
   ```

4. **Run Full Test Suite**:
   ```bash
   python run_sprint2_tests.py
   ```

---

## Support

**Questions?** Check:
- Console output for errors
- `results.csv` for metrics
- TensorBoard: `tensorboard --logdir experiments/`

**Common commands:**
```bash
# Check GPU status
nvidia-smi

# Monitor training (separate terminal)
watch -n 1 tail -20 experiments/.../results.csv

# Kill training (if needed)
Ctrl+C  # Then confirm
```

---

**Good luck with training! 🚀**
