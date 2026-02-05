# Quick Start Guide - ML Adapters

## 🚀 Getting Started in 3 Steps

### Step 1: Add a Test Image

Place any image file (jpg, png, etc.) in the `sample_images/` directory:

```bash
cd adapters
cp /path/to/your/image.jpg sample_images/
```

### Step 2: Run the Test

```bash
python test_adapters.py sample_images/your_image.jpg
```

Or test with all images in the directory:

```bash
python test_adapters.py
```

### Step 3: View Results

The script will automatically:
- ✅ Run raw model inference
- ✅ Save raw output to `raw_outputs/`
- ✅ Run adapter processing
- ✅ Save clean output to `sample_outputs/`
- ✅ Display before/after comparison in console

## 📊 What You'll See

### Console Output

1. **BEFORE**: Raw model output (complex, model-specific)
2. **AFTER**: Clean standardized output (simple, consistent)
3. **METRICS**: Quantitative comparison (size reduction, etc.)
4. **IMPROVEMENT SUMMARY**: Key benefits explained

### Generated Files

- `raw_outputs/<image_id>_yolo_raw.json` - Raw YOLO output
- `raw_outputs/<image_id>_ocr_raw.json` - Raw OCR output
- `sample_outputs/<image_id>_yolo_clean.json` - Clean YOLO output
- `sample_outputs/<image_id>_ocr_clean.json` - Clean OCR output

## 💡 Example Usage

### Test YOLO Adapter Only

```python
from yolo_adapter import vision_adapter

result = vision_adapter("sample_images/test.jpg")
print(f"Found {len(result['detections'])} objects")
```

### Test OCR Adapter Only

```python
from ocr_adapter import ocr_adapter

result = ocr_adapter("sample_images/test.jpg")
print(f"Found {len(result['detections'])} text detections")
```

## 📝 Requirements

Make sure you have the dependencies installed:

```bash
pip install ultralytics easyocr opencv-python numpy
```

## 🎯 Next Steps

1. Add your own test images
2. Run the test script
3. Compare the before/after outputs
4. Use the adapters in your application code

For detailed documentation, see `README.md`

