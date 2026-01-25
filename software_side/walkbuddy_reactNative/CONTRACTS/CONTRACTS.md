# **WalkBuddy Inference Pipeline — v1 Contracts**

This document defines the official interfaces between all components of the WalkBuddy architecture.  
These contracts are **binding** for all teams (Software, ML, Backend, Frontend).  
Following them ensures compatibility, scalability, and parallel development without breaking changes.

---

# **1. Vision Detection Contract (Source of Truth)**  
**Provided by:** ML Team  
**Consumed by:** Backend Adapters → FastAPI Routes → RN InferenceClient → UI  

This is the canonical v1 detection schema.  
All Vision inference responses MUST follow this exact structure.

```json
{
  "timestamp": "2025-12-02T01:35:43.206699000Z",
  "frame_id": "1f9241bd-003c-4979-9564-0c4067625abb",
  "source": "yolov8s_indoor_v1_trained",
  "detections": [
    {
      "id": 0,
      "label": "monitor",
      "confidence": 0.9648943543434143,
      "bbox_norm": {
        "cx": 0.5,
        "cy": 0.46237497329711913,
        "w": 1.0,
        "h": 0.23695821762084962
      },
      "severity": "near",
      "side": "center",
      "distance_m": null
    }
  ]
}
```

### **Contract Rules**
- `bbox_norm` uses YOLO center-normalized coordinates (`cx`, `cy`, `w`, `h`) in the range `[0,1]`.
- `side` ∈ `{ "left", "center", "right" }`.
- `severity` ∈ `{ "near", "medium", "far" }`.
- `distance_m` is always `null` in v1 (reserved for sensor fusion).
- `source` identifies the model used.
- Values MUST NOT change type or structure.

---

# **2. OCR Read Contract**

**Provided by:** ML Team  
**Consumed by:** Backend Adapters → FastAPI Routes → RN InferenceClient  

OCR results mirror the Vision schema for consistency.

```json
{
  "timestamp": "2025-12-02T01:35:43.206699000Z",
  "frame_id": "uuid",
  "source": "easyocr_en_v1",
  "blocks": [
    {
      "id": 0,
      "text": "EXIT",
      "confidence": 0.95,
      "bbox_norm": {
        "cx": 0.2,
        "cy": 0.1,
        "w": 0.15,
        "h": 0.05
      }
    }
  ]
}
```

### **Contract Rules**
- `bbox_norm` uses the same center-normalized YOLO format.
- `confidence` ∈ `[0,1]`.
- `blocks` is a list of text regions.
- No extra fields may be added without versioning.

---

# **3. Backend FastAPI Contracts**

## **3.1 Vision Detect Endpoint**
**Method:** `POST`  
**Route:** `/v1/vision/detect`  
**Request:**  
- `multipart/form-data`
- field: `image` (JPEG/PNG)

**Response:**  
- EXACT Vision Detection Contract JSON (Section 1)

**Error Response:**
```json
{
  "error": "BAD_REQUEST",
  "message": "Image missing or invalid.",
  "details": null
}
```

Possible errors:
- `BAD_REQUEST`
- `MODEL_NOT_READY`
- `INTERNAL_ERROR`

---

## **3.2 OCR Read Endpoint**
**Method:** `POST`  
**Route:** `/v1/ocr/read`  
**Request:**  
- `multipart/form-data`
- field: `image` (JPEG/PNG)

**Response:**  
- EXACT OCR Read Contract JSON (Section 2)

**Error Response:** Same structure as Vision endpoint.

---

## **3.3 Health Check**
**Method:** `GET`  
**Route:** `/v1/health`

**Success Response:**

```json
{
  "status": "ok",
  "vision_ready": true,
  "ocr_ready": true,
  "version": "backend-1.0.0",
  "timestamp": "2025-12-02T04:30:00Z"
}
```

**Degraded Response:**
```json
{
  "status": "degraded",
  "vision_ready": false,
  "ocr_ready": true
}
```

---

# **4. Backend Adapter Contracts**

Backend adapters bridge raw ML model execution and the API layer.

## **4.1 Vision Adapter**

```python
def run_vision(image: PIL.Image.Image) -> dict:
    '''
    Takes a PIL Image.
    Returns the EXACT Vision Detection Contract JSON.
    Must NOT return raw YOLO outputs.
    Must handle errors internally and return structured results.
    '''
```

## **4.2 OCR Adapter**

```python
def run_ocr(image: PIL.Image.Image) -> dict:
    '''
    Takes a PIL Image.
    Returns the OCR Read Contract JSON.
    '''
```

### Adapter Rules
- Must follow the JSON structures verbatim.
- Must load models once on startup.
- Must not mutate the image.
- Must not raise uncaught exceptions.

---

# **5. Frontend `InferenceClient` Contracts**

The RN UI interacts ONLY with this interface.  
This abstraction enables online/offline inference and future streaming.

```ts
interface InferenceClient {
  detectVision(frame: CapturedFrame): Promise<VisionResult>;
  readText(frame: CapturedFrame): Promise<OcrResult>;
}
```

## **Type Definitions**

```ts
type VisionResult = {
  frame_id: string;
  timestamp: string;
  source: string;
  detections: Detection[];
};

type Detection = {
  id: number;
  label: string;
  confidence: number;
  bbox_norm: {
    cx: number;
    cy: number;
    w: number;
    h: number;
  };
  side: "left" | "center" | "right";
  severity: "near" | "medium" | "far";
  distance_m: number | null;
};
```

```ts
type OcrResult = {
  frame_id: string;
  timestamp: string;
  source: string;
  blocks: OcrBlock[];
};

type OcrBlock = {
  id: number;
  text: string;
  confidence: number;
  bbox_norm: {
    cx: number;
    cy: number;
    w: number;
    h: number;
  };
};
```

### **Frontend Responsibilities**
- Convert `bbox_norm` to drawing coordinates.
- Handle errors gracefully.
- Send frames at a fixed interval (e.g., every 500ms).

---

# **6. Online vs On-Device Abstraction Contract**

The InferenceClient has two interchangeable implementations:

```ts
class RemoteInferenceClient implements InferenceClient {}
class OnDeviceInferenceClient implements InferenceClient {}
```

### Rules:
- Both must return the *exact same* VisionResult and OcrResult types.
- Switching between them must not break UI code.
- On-device inference is planned for v2 and beyond.

---

# **End of Contracts Document**

This contract suite allows all teams to work independently while ensuring every component integrates seamlessly.  
It is intentionally designed to support future extensions, including:
- on-device inference,
- real-time streaming,
- new models,
- additional endpoints,
- and sensor fusion.
