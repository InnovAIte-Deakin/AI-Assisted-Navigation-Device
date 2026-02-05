# Before/After Comparison Endpoints

## 🎯 Purpose

These endpoints allow you to compare the **RAW** ML model output (before adapter) with the **CLEAN** standardized output (after adapter) to demonstrate the improvement.

## 📍 Available Endpoints

### RAW Endpoints (Before Adapter)
These return the original, unprocessed ML model output:

- **POST http://localhost:8000/vision_raw** - Raw YOLO output
- **POST http://localhost:8000/ocr_raw** - Raw EasyOCR output

### CLEAN Endpoints (After Adapter)
These return standardized, cleaned JSON from the adapters:

- **POST http://localhost:8000/vision** - Clean YOLO output (via adapter)
- **POST http://localhost:8000/ocr** - Clean OCR output (via adapter)

## 🧪 How to Test

### Method 1: FastAPI Docs (Recommended)

1. Open **http://localhost:8000/docs** in your browser
2. Test the RAW endpoint first:
   - Find **POST /vision_raw** or **POST /ocr_raw**
   - Click "Try it out"
   - Upload an image
   - Click "Execute"
   - See the messy raw output
3. Test the CLEAN endpoint:
   - Find **POST /vision** or **POST /ocr**
   - Click "Try it out"
   - Upload the same image
   - Click "Execute"
   - See the clean standardized output
4. Compare the two responses side-by-side!

### Method 2: Using curl

```bash
# Test RAW vision endpoint
curl -X POST "http://localhost:8000/vision_raw" \
  -F "file=@/path/to/image.jpg" | python3 -m json.tool

# Test CLEAN vision endpoint
curl -X POST "http://localhost:8000/vision" \
  -F "file=@/path/to/image.jpg" | python3 -m json.tool

# Test RAW OCR endpoint
curl -X POST "http://localhost:8000/ocr_raw" \
  -F "file=@/path/to/image.jpg" | python3 -m json.tool

# Test CLEAN OCR endpoint
curl -X POST "http://localhost:8000/ocr" \
  -F "file=@/path/to/image.jpg" | python3 -m json.tool
```

## 📁 Saved Raw Output Files

Raw outputs are automatically saved to:
```
ML_models/adapters/raw_outputs/<timestamp>_yolo_raw.json
ML_models/adapters/raw_outputs/<timestamp>_ocr_raw.json
```

Example filenames:
- `20241207_193045_yolo_raw.json`
- `20241207_193045_ocr_raw.json`

## 🔍 What to Compare

### RAW Output (Before Adapter)
- ❌ Float coordinates (not integers)
- ❌ 4-corner bbox format (OCR) or raw array format (YOLO)
- ❌ Class IDs mixed with names
- ❌ Extra metadata and internal model data
- ❌ Inconsistent structure
- ❌ Unrounded confidence scores

### CLEAN Output (After Adapter)
- ✅ Integer pixel coordinates
- ✅ Standardized bbox format (x_min, y_min, x_max, y_max)
- ✅ Clean category names (no class IDs)
- ✅ Only essential detection data
- ✅ Consistent structure across both models
- ✅ Rounded confidence scores (4 decimals)

## 📸 Screenshot Guide

1. **Open http://localhost:8000/docs**
   - Screenshot: Shows all 4 endpoints (2 raw + 2 clean)

2. **Test POST /vision_raw**
   - Screenshot: Shows messy raw YOLO output

3. **Test POST /vision**
   - Screenshot: Shows clean standardized output
   - Place side-by-side with raw output

4. **Repeat for OCR endpoints**
   - Screenshot: Raw vs Clean OCR comparison

5. **Check saved files**
   - Screenshot: File explorer showing timestamped raw output files

## 🚀 Running the Backend

```bash
cd software_side/walkbuddy_reactNative/backend
source venv/bin/activate
python main.py
```

Then open: **http://localhost:8000/docs**

