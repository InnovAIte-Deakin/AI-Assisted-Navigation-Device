# Backend API - Quick Start

## 🚀 Running the Backend Server

### From the backend directory:

```bash
cd backend
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate     # On Windows

python main.py
```

### From the project root:

```bash
cd software_side/walkbuddy_reactNative
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Using uvicorn directly (if venv is activated):

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 📍 API Endpoints

### Interactive Documentation
- **http://localhost:8000/docs** - Swagger UI (try endpoints here!)

### Health & Status
- **GET http://localhost:8000/health** - Health check
- **GET http://localhost:8000/status** - Backend status

### ML Adapter Endpoints (NEW!)
- **POST http://localhost:8000/vision** - Upload image for object detection (returns clean JSON)
- **POST http://localhost:8000/ocr** - Upload image for text recognition (returns clean JSON)

### Gradio UI (existing)
- **http://localhost:8000/vision/** - YOLO vision interface
- **http://localhost:8000/ocr/** - OCR interface

## 🧪 Testing the Adapter Endpoints

### Using the FastAPI Docs (Recommended)

1. Open http://localhost:8000/docs
2. Find **POST /vision** or **POST /ocr**
3. Click "Try it out"
4. Upload an image file
5. Click "Execute"
6. See the clean JSON response!

### Using curl

```bash
# Test vision endpoint
curl -X POST "http://localhost:8000/vision" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/image.jpg"

# Test OCR endpoint
curl -X POST "http://localhost:8000/ocr" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/image.jpg"
```

### Using Python requests

```python
import requests

# Test vision endpoint
with open('image.jpg', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/vision',
        files={'file': f}
    )
    print(response.json())

# Test OCR endpoint
with open('image.jpg', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/ocr',
        files={'file': f}
    )
    print(response.json())
```

## 📋 Response Format

Both endpoints return standardized JSON:

```json
{
    "image_id": "image_filename",
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

## 🔧 Requirements

Make sure you have:
- Python 3.8+
- Virtual environment activated
- All dependencies installed: `pip install -r requirements.txt`
- YOLO model weights at: `../ML_models/yolo_nav/weights/yolov8s.pt`

