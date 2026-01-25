# ML → Software JSON Integration

## Overview

This directory contains the standardized JSON output format for ML detections that the Software team will consume.

## Quick Start

### Generate Real Sample JSON

1. **Install dependencies** (if not already done):
   ```bash
   cd software_side/walkbuddy_reactNative/ML_models/yolo_nav
   pip install -r requirements.txt
   ```

2. **Run the export script**:
   ```bash
   python export_sample_json.py
   ```

   This will:
   - Use the trained model from `ML_side/models/object_detection/best.pt` (if available)
   - Or fall back to base `yolov8s.pt`
   - Run inference on a validation image
   - Generate `sample_detections.json` with real detections

### Current Sample

A mock `sample_detections.json` is included to demonstrate the format. Replace it with real output after running the script above.

## JSON Schema

### Top-Level Structure

```json
{
  "timestamp": "ISO-8601 UTC timestamp",
  "frame_id": "UUID v4",
  "source": "model_name_or_pipeline",
  "detections": [ ... ]
}
```

### Detection Object

Each detection in the `detections` array has:

```json
{
  "id": 0,                    // Sequential ID within this frame
  "label": "office-chair",    // Class name (from your 7 classes)
  "confidence": 0.82,         // Float 0.0-1.0
  "bbox_norm": {              // Normalized coordinates (0.0-1.0)
    "cx": 0.53,               // Center X
    "cy": 0.61,               // Center Y
    "w": 0.24,                // Width
    "h": 0.35                 // Height
  },
  "severity": "near",         // "near" | "mid" | "far" | "none"
  "side": "left",            // "left" | "center" | "right"
  "distance_m": null         // Reserved for future depth estimation
}
```

### Field Definitions

- **`timestamp`**: ISO-8601 format in UTC (e.g., `2025-11-29T14:30:00.123456789Z`)
- **`frame_id`**: Unique UUID per frame for tracking
- **`source`**: Model identifier (e.g., `"yolov8s_indoor_v1_trained"`)
- **`label`**: One of: `book`, `books`, `monitor`, `office-chair`, `whiteboard`, `table`, `tv`
- **`confidence`**: Detection confidence score (0.0 to 1.0)
- **`bbox_norm`**: All coordinates normalized to [0.0, 1.0] relative to image dimensions
  - `cx`, `cy`: Center point of bounding box
  - `w`, `h`: Width and height of bounding box
- **`severity`**: Coarse distance estimate based on bounding box area:
  - `"near"`: Object fills ≥14% of frame (immediate obstacle)
  - `"mid"`: Object fills ~7.7-14% of frame (approaching)
  - `"far"`: Object fills ~4.5-7.7% of frame (distant)
  - `"none"`: Too small to be relevant
- **`side`**: Horizontal position in frame:
  - `"left"`: Center X < 0.4
  - `"center"`: 0.4 ≤ Center X ≤ 0.6
  - `"right"`: Center X > 0.6
- **`distance_m`**: Currently `null`; reserved for future depth estimation integration

## Integration Points

### For ML Team

- Use `ml_to_software_json.py` to convert YOLO results:
  ```python
  from ml_to_software_json import yolo_result_to_json
  from ultralytics import YOLO
  
  model = YOLO("weights/best.pt")
  result = model.predict(image, conf=0.3)[0]
  json_payload = yolo_result_to_json(result, source_name="yolov8s_indoor_v1")
  ```

### For Software Team

- Expect one JSON payload per frame
- Parse `detections` array and filter by `severity` (ignore `"none"`)
- Use `side` for directional audio/haptic feedback
- Use `confidence` for additional filtering if needed

## Validation Status

✅ **JSON structure validated with Software team**  
✅ **Seven detection categories confirmed for Sprint 1**  
🔄 **Sample detections generation in progress** (run `export_sample_json.py`)

## Files

- `ml_to_software_json.py` - Core conversion utility
- `export_sample_json.py` - Script to generate sample JSON from real model
- `sample_detections.json` - Example output (mock or real)
- `README_JSON_INTEGRATION.md` - This file

