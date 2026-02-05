# ML Adapters for AI-Assisted Navigation Device

This directory contains adapter functions that standardize ML model outputs into clean, consistent JSON formats for the navigation device.

## 📁 Folder Structure

```
adapters/
├── yolo_adapter.py          # YOLO vision model adapter
├── ocr_adapter.py           # EasyOCR text recognition adapter
├── test_adapters.py         # Test script with before/after comparison
├── sample_images/           # Place your test images here
├── raw_outputs/             # Raw model outputs (before adapter)
└── sample_outputs/          # Clean standardized outputs (after adapter)
```

## 🎯 Purpose

The adapters convert raw ML model outputs into a **standardized JSON format** that:
- ✅ Is consistent across different models (YOLO, EasyOCR)
- ✅ Is easy to parse and consume by downstream applications
- ✅ Includes only essential detection data
- ✅ Uses standardized bounding box format
- ✅ Provides clean, readable category names

## 📋 Standardized JSON Schema

All adapters output data in this format:

```json
{
    "image_id": "test_image",
    "detections": [
        {
            "category": "chair",
            "confidence": 0.8542,
            "bbox": {
                "x_min": 100,
                "y_min": 150,
                "x_max": 250,
                "y_max": 300
            }
        }
    ]
}
```

### Schema Details:
- **image_id**: Filename without extension
- **category**: Object class name (for YOLO) or detected text (for OCR)
- **confidence**: Probability score between 0 and 1
- **bbox**: Bounding box coordinates in pixels
  - `x_min`, `y_min`: Top-left corner
  - `x_max`, `y_max`: Bottom-right corner

## 🚀 Usage

### Testing the Adapters

1. **Add test images** to `sample_images/` directory:
   ```bash
   cp /path/to/your/image.jpg sample_images/
   ```

2. **Run the test script**:
   ```bash
   cd adapters
   python test_adapters.py
   ```

   Or test with a specific image:
   ```bash
   python test_adapters.py sample_images/my_image.jpg
   ```

3. **View the results**:
   - Raw outputs saved to `raw_outputs/`
   - Clean outputs saved to `sample_outputs/`
   - Console shows before/after comparison

### Using Adapters in Your Code

#### YOLO Vision Adapter

```python
from yolo_adapter import vision_adapter

# Process an image
result = vision_adapter("path/to/image.jpg")

# Access detections
for detection in result["detections"]:
    print(f"Found {detection['category']} with confidence {detection['confidence']}")
    bbox = detection["bbox"]
    print(f"  Location: ({bbox['x_min']}, {bbox['y_min']}) to ({bbox['x_max']}, {bbox['y_max']})")
```

#### OCR Adapter

```python
from ocr_adapter import ocr_adapter

# Process an image
result = ocr_adapter("path/to/image.jpg")

# Access text detections
for detection in result["detections"]:
    print(f"Found text: '{detection['category']}' with confidence {detection['confidence']}")
    bbox = detection["bbox"]
    print(f"  Location: ({bbox['x_min']}, {bbox['y_min']}) to ({bbox['x_max']}, {bbox['y_max']})")
```

## 📊 Before vs After Comparison

The test script automatically shows:

1. **Raw Model Output** (BEFORE):
   - Complex nested structures
   - Model-specific formats
   - Internal metadata
   - Inconsistent coordinate systems

2. **Clean Standardized Output** (AFTER):
   - Simple, flat structure
   - Consistent format
   - Only essential data
   - Standardized coordinates

3. **Quantitative Metrics**:
   - File size reduction
   - Lines of code reduction
   - Key count reduction
   - Nesting depth reduction

## 🔧 Requirements

- Python 3.8+
- ultralytics (for YOLO)
- easyocr
- opencv-python
- numpy

Install dependencies:
```bash
pip install ultralytics easyocr opencv-python numpy
```

## 📝 Example Output

### Before (Raw YOLO Output):
```json
{
  "image_id": "test",
  "model_type": "YOLOv8",
  "raw_detections": [
    {
      "detection_id": 0,
      "bbox_raw": [100.5, 150.2, 250.8, 300.1],
      "confidence": 0.854234,
      "class_id": 56,
      "class_name": "office-chair"
    }
  ],
  "num_detections": 1,
  "image_shape": [640, 480]
}
```

### After (Clean Output):
```json
{
  "image_id": "test",
  "detections": [
    {
      "category": "office-chair",
      "confidence": 0.8542,
      "bbox": {
        "x_min": 100,
        "y_min": 150,
        "x_max": 250,
        "y_max": 300
      }
    }
  ]
}
```

## 🎓 Key Improvements

1. **Standardization**: Both adapters use the same JSON schema
2. **Simplicity**: Removed unnecessary metadata and nesting
3. **Readability**: Clean category names instead of class IDs
4. **Consistency**: Unified bounding box format (x_min, y_min, x_max, y_max)
5. **Precision**: Confidence scores rounded to 4 decimal places
6. **Sorting**: Detections sorted by confidence (highest first)

## 📧 Support

For questions or issues, contact the ML Engineering Team.

