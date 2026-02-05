# TTS Service Quick Start Guide

Quick guide to get started with the TTS service for Sprint 2.

## Installation

### Python Backend
Dependencies are already in `requirements.txt`:
- `pyttsx3` - Offline TTS
- `gtts` - Cloud TTS (optional)

### React Native Frontend
`expo-speech` is already in `package.json`.

## Quick Start

### Python: Basic Usage

```python
from ML_models.tts_service import get_tts_service, RiskLevel

# Get service
tts = get_tts_service()

# Speak a message
tts.speak("Chair on your left, nearby", RiskLevel.MEDIUM)
```

### React Native: Basic Usage

```typescript
import { getTTSService, RiskLevel } from '@/services/TTSService';

const tts = getTTSService();
await tts.speak("Chair on your left, nearby", RiskLevel.MEDIUM);
```

## Integration with Detection

### Python: Vision + TTS

```python
from ML_models.adapters.yolo_adapter import vision_adapter
from ML_models.tts_service import process_adapter_output, get_tts_service

# Process image
result = vision_adapter("image.jpg")

# Generate guidance messages
messages = process_adapter_output(result, max_messages=1)

# Speak
if messages:
    tts = get_tts_service()
    tts.speak_async(messages[0].message, messages[0].risk_level)
```

### React Native: API Integration

```typescript
// Call backend API
const formData = new FormData();
formData.append('file', { uri: imageUri, type: 'image/jpeg', name: 'photo.jpg' });

const response = await fetch('http://backend-url/api/vision/tts', {
  method: 'POST',
  body: formData,
});

const data = await response.json();

// Speak the message
if (data.spoken_message) {
  const tts = getTTSService();
  await tts.speak(data.spoken_message, RiskLevel.MEDIUM);
}
```

## API Endpoints

### POST `/tts/speak`
```json
{
  "message": "Chair on your left, nearby",
  "risk_level": "MEDIUM"
}
```

### POST `/vision/tts`
Upload image file, get detections + spoken guidance.

### POST `/ocr/tts`
Upload image file, get OCR + spoken text.

## Anti-Spam Rules

- **Cooldown**: 3 seconds between messages (configurable)
- **Message Change**: Only speaks if message is different
- **Risk Escalation**: Speaks immediately if risk increases

## Testing

### Python
```bash
cd ML_models/tts_service
python example_usage.py
```

### React Native
See `frontend_reactNative/src/examples/TTSExample.tsx`

## Common Messages

- "Path ahead is clear" (CLEAR)
- "Chair on your left, nearby" (MEDIUM)
- "Table ahead" (LOW)
- "Obstacle detected ahead" (HIGH)
- "Exit sign detected ahead" (LOW)

## Troubleshooting

### Python TTS not working
- Check `pyttsx3` is installed: `pip install pyttsx3`
- On Linux, may need: `sudo apt-get install espeak`

### React Native TTS not working
- Check `expo-speech` is installed: `npm install expo-speech`
- Ensure device has TTS engine (Android/iOS default)

### Messages not speaking
- Check cooldown status: `GET /tts/status`
- Try `force: true` to bypass cooldown
- Check service status in logs

## Next Steps

1. Integrate with camera feed
2. Connect to detection pipeline
3. Customize messages for your use case
4. Adjust cooldown/risk levels as needed

For more details, see `README.md`.



