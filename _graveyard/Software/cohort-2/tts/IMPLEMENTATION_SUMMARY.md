# TTS Implementation Summary - Sprint 2

## Overview

A complete Text-to-Speech (TTS) system has been implemented for the AI-Assisted Navigation Device with the following features:

- ✅ Offline-friendly TTS (device-based, no cloud required)
- ✅ Anti-spam logic (cooldown, message change detection, risk escalation)
- ✅ Message reasoning (converts detection/OCR to guidance messages)
- ✅ Rule-based (no LLM, reliable and predictable)
- ✅ Easy integration (Python backend + React Native frontend)

## Files Created

### Python Backend

1. **`tts_service/tts_service.py`** (350+ lines)
   - Core TTS service with anti-spam logic
   - Offline support via pyttsx3
   - Optional cloud fallback via gTTS
   - Thread-safe, async support

2. **`tts_service/message_reasoning.py`** (400+ lines)
   - Converts detection/OCR outputs to guidance messages
   - Spatial position calculation (left/right/ahead)
   - Proximity assessment (nearby/ahead)
   - Risk level assessment
   - Natural language formatting

3. **`tts_service/__init__.py`**
   - Package initialization and exports

4. **`tts_service/example_usage.py`**
   - Comprehensive examples demonstrating all features

5. **`tts_service/README.md`**
   - Complete documentation

6. **`tts_service/QUICKSTART.md`**
   - Quick start guide

### React Native Frontend

1. **`frontend_reactNative/src/services/TTSService.ts`** (250+ lines)
   - React Native TTS service using expo-speech
   - Same anti-spam logic as Python version
   - TypeScript with full type safety

2. **`frontend_reactNative/src/examples/TTSExample.tsx`**
   - Example React Native component showing usage

### Backend Integration

1. **`backend/main.py`** (updated)
   - Added TTS endpoints:
     - `POST /tts/speak` - Speak a text message
     - `GET /tts/status` - Get TTS service status
     - `POST /vision/tts` - Vision detection + TTS
     - `POST /ocr/tts` - OCR detection + TTS

## Key Features

### 1. Anti-Spam Logic

Prevents audio spam using three rules:

1. **Cooldown**: Minimum time between messages (default: 3 seconds)
2. **Message Change**: Only speaks if message is different from last
3. **Risk Escalation**: Speaks immediately if risk level increases

**Example:**
```python
tts.speak("Chair on your left", RiskLevel.MEDIUM)  # ✅ Spoken
tts.speak("Chair on your left", RiskLevel.MEDIUM)  # ❌ Suppressed (same message)
tts.speak("Table ahead", RiskLevel.LOW)            # ✅ Spoken (different)
tts.speak("Table ahead", RiskLevel.HIGH)           # ✅ Spoken (risk increased)
```

### 2. Message Reasoning

Converts detection/OCR outputs to natural guidance messages:

**Input (Detection):**
```json
{
  "category": "office-chair",
  "confidence": 0.85,
  "bbox": {"x_min": 50, "y_min": 100, "x_max": 200, "y_max": 300}
}
```

**Output (Guidance Message):**
```
"Chair on your left, nearby" (RiskLevel.MEDIUM)
```

### 3. Risk Levels

- **CLEAR**: Path is clear
- **LOW**: Minor objects (signs, distant objects)
- **MEDIUM**: Obstacles (chairs, tables)
- **HIGH**: Nearby obstacles requiring attention
- **CRITICAL**: Immediate danger (for future use)

### 4. Offline Support

- **Python**: Uses `pyttsx3` (device-based TTS engine)
- **React Native**: Uses `expo-speech` (device TTS engine)
- No internet connection required

## Usage Examples

### Python Backend

```python
from ML_models.tts_service import get_tts_service, process_adapter_output
from ML_models.adapters.yolo_adapter import vision_adapter

# Process image and speak
result = vision_adapter("image.jpg")
messages = process_adapter_output(result, max_messages=1)
if messages:
    tts = get_tts_service()
    tts.speak_async(messages[0].message, messages[0].risk_level)
```

### React Native Frontend

```typescript
import { getTTSService, RiskLevel } from '@/services/TTSService';

const tts = getTTSService();
await tts.speak("Chair on your left, nearby", RiskLevel.MEDIUM);
```

### API Endpoint

```bash
curl -X POST http://localhost:8000/tts/speak \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Chair on your left, nearby",
    "risk_level": "MEDIUM"
  }'
```

## Integration Points

### 1. With Vision Detection

```python
# Backend endpoint: POST /vision/tts
# Processes image → detections → guidance → TTS
```

### 2. With OCR Detection

```python
# Backend endpoint: POST /ocr/tts
# Processes image → text → guidance → TTS
```

### 3. With React Native App

```typescript
// Call backend API or use local TTS
const response = await fetch('/api/vision/tts', { method: 'POST', body: formData });
const data = await response.json();
if (data.spoken_message) {
  await tts.speak(data.spoken_message, RiskLevel.MEDIUM);
}
```

## Message Examples

### Object Detection
- "Chair on your left, nearby"
- "Table ahead"
- "Monitor on your right"
- "Books ahead"

### OCR/Signs
- "Exit sign detected ahead"
- "History section detected ahead"
- "Restroom sign on your left"

### Clear Path
- "Path ahead is clear"

## Configuration

### Python TTS Service
```python
service = TTSService(
    cooldown_seconds=3.0,      # Cooldown between messages
    use_offline=True,          # Use pyttsx3 (offline)
    use_cloud_fallback=False, # Fallback to gTTS
    language="en"              # Language code
)
```

### React Native TTS Service
```typescript
const tts = new TTSService({
  cooldownSeconds: 3.0,
  language: 'en',
  pitch: 1.0,
  rate: 0.9,    // Slightly slower for clarity
  volume: 1.0,
});
```

## Testing

### Run Examples

```bash
# Python examples
cd ML_models/tts_service
python example_usage.py

# Test individual modules
python tts_service.py
python message_reasoning.py
```

### Test API Endpoints

```bash
# Test TTS speak
curl -X POST http://localhost:8000/tts/speak \
  -H "Content-Type: application/json" \
  -d '{"message": "Test message", "risk_level": "LOW"}'

# Test vision + TTS
curl -X POST http://localhost:8000/vision/tts \
  -F "file=@test_image.jpg"

# Check status
curl http://localhost:8000/tts/status
```

## Dependencies

### Python
- `pyttsx3` - Offline TTS (already in requirements.txt)
- `gtts` - Cloud TTS fallback (optional, already in requirements.txt)

### React Native
- `expo-speech` - Device TTS (already in package.json)

## Architecture

```
┌─────────────────┐
│ Detection/OCR   │
│   (Adapters)    │
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│ Message         │
│ Reasoning       │
│ (Rule-based)    │
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│ TTS Service     │
│ (Anti-spam)     │
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│ Audio Output    │
│ (Speech)        │
└─────────────────┘
```

## Next Steps

1. **Integration**: Connect to camera feed in React Native app
2. **Customization**: Adjust messages for specific use cases
3. **Testing**: Test with real navigation scenarios
4. **Optimization**: Fine-tune cooldown and risk levels
5. **Enhancement**: Add voice customization, multi-language support

## Notes

- TTS is designed for accessibility and real-time performance
- Messages should be short and clear (max 10-15 words)
- Anti-spam logic is critical for user experience
- Offline support ensures reliability without internet
- Rule-based approach ensures predictable behavior
- No LLM required (as per requirements)

## Files Modified

- `backend/main.py` - Added TTS endpoints and imports

## Files Created

- `ML_models/tts_service/tts_service.py`
- `ML_models/tts_service/message_reasoning.py`
- `ML_models/tts_service/__init__.py`
- `ML_models/tts_service/example_usage.py`
- `ML_models/tts_service/README.md`
- `ML_models/tts_service/QUICKSTART.md`
- `ML_models/tts_service/IMPLEMENTATION_SUMMARY.md`
- `frontend_reactNative/src/services/TTSService.ts`
- `frontend_reactNative/src/examples/TTSExample.tsx`

## Status

✅ **Complete** - All deliverables implemented and documented.



