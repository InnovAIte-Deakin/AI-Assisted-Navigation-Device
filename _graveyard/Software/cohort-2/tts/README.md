# Text-to-Speech (TTS) Service - Sprint 2

This module provides Text-to-Speech functionality for the AI-Assisted Navigation Device with anti-spam logic and offline support.

## Features

- ✅ **Offline TTS**: Uses device-based TTS (pyttsx3 for Python, expo-speech for React Native)
- ✅ **Anti-Spam Logic**: Prevents audio spam with cooldown and message change detection
- ✅ **Risk-Based Priority**: Speaks immediately when risk level increases
- ✅ **Message Reasoning**: Converts detection/OCR outputs to clear guidance messages
- ✅ **Rule-Based**: No LLM required, purely rule-based for reliability

## Architecture

```
Detection/OCR Output → Message Reasoning → TTS Service → Audio Output
     (JSON)              (GuidanceMessage)    (Anti-spam)     (Speech)
```

## Components

### 1. TTS Service (`tts_service.py`)

Core TTS service with anti-spam logic.

**Features:**
- Cooldown between messages (default: 3 seconds)
- Only speaks when message changes
- Immediate speaking when risk level increases
- Offline support via pyttsx3
- Optional cloud fallback via gTTS

**Usage:**
```python
from ML_models.tts_service import TTSService, RiskLevel

# Create service
service = TTSService(cooldown_seconds=3.0)

# Speak a message
service.speak("Chair on your left, nearby", RiskLevel.MEDIUM)

# Speak asynchronously (non-blocking)
service.speak_async("Path ahead is clear", RiskLevel.CLEAR)
```

### 2. Message Reasoning (`message_reasoning.py`)

Converts detection/OCR outputs to guidance messages.

**Features:**
- Spatial position calculation (left/right/ahead)
- Proximity assessment (nearby/ahead)
- Risk level assessment
- Object type classification
- Natural language formatting

**Usage:**
```python
from ML_models.tts_service import process_adapter_output
from ML_models.adapters.yolo_adapter import vision_adapter

# Process image and get guidance messages
vision_result = vision_adapter("image.jpg")
messages = process_adapter_output(vision_result, max_messages=1)

# Speak the message
if messages:
    service.speak(messages[0].message, messages[0].risk_level)
```

### 3. React Native TTS Service (`frontend_reactNative/src/services/TTSService.ts`)

React Native TTS service using expo-speech.

**Usage:**
```typescript
import { getTTSService, RiskLevel } from '@/services/TTSService';

const tts = getTTSService({ cooldownSeconds: 3.0 });

// Speak a message
await tts.speak("Chair on your left, nearby", RiskLevel.MEDIUM);

// Speak asynchronously
tts.speakAsync("Path ahead is clear", RiskLevel.CLEAR);
```

## API Endpoints

### POST `/tts/speak`
Speak a text message.

**Request:**
```json
{
  "message": "Chair on your left, nearby",
  "risk_level": "MEDIUM",
  "force": false
}
```

**Response:**
```json
{
  "success": true,
  "message": "Message spoken",
  "status": {
    "cooldown_seconds": 3.0,
    "time_since_last_message": 0.5,
    "cooldown_active": true,
    "last_message": "Chair on your left, nearby",
    "last_risk_level": "MEDIUM"
  }
}
```

### POST `/vision/tts`
Process image with vision detection and speak guidance.

**Request:** Multipart form with image file

**Response:**
```json
{
  "detections": [...],
  "guidance_messages": [
    {
      "message": "Chair on your left, nearby",
      "risk_level": "MEDIUM",
      "priority": 35
    }
  ],
  "spoken": true,
  "spoken_message": "Chair on your left, nearby"
}
```

### POST `/ocr/tts`
Process image with OCR and speak detected text.

**Request:** Multipart form with image file

**Response:** Same format as `/vision/tts`

### GET `/tts/status`
Get TTS service status.

**Response:**
```json
{
  "cooldown_seconds": 3.0,
  "time_since_last_message": 1.5,
  "cooldown_active": true,
  "last_message": "Chair on your left, nearby",
  "last_risk_level": "MEDIUM",
  "offline_available": true,
  "cloud_fallback_available": false,
  "message_history_count": 5
}
```

## Anti-Spam Logic

The TTS service prevents audio spam using the following rules:

1. **Cooldown**: Minimum time between messages (default: 3 seconds)
2. **Message Change**: Only speaks if message is different from last
3. **Risk Escalation**: Speaks immediately if risk level increases
4. **Force Override**: Can force speaking (use sparingly)

**Example:**
```python
# First message - will speak
service.speak("Chair on your left", RiskLevel.MEDIUM)  # ✅ Spoken

# Same message within cooldown - suppressed
service.speak("Chair on your left", RiskLevel.MEDIUM)  # ❌ Suppressed

# Different message - will speak
service.speak("Table ahead", RiskLevel.LOW)  # ✅ Spoken

# Risk escalation - speaks immediately
service.speak("Obstacle ahead", RiskLevel.HIGH)  # ✅ Spoken (risk increased)
```

## Risk Levels

- **CLEAR**: Path is clear, no obstacles
- **LOW**: Minor objects detected (signs, distant objects)
- **MEDIUM**: Obstacles detected (chairs, tables)
- **HIGH**: Nearby obstacles requiring attention
- **CRITICAL**: Immediate danger (rare, for future use)

## Message Examples

### Object Detection Messages
- "Chair on your left, nearby"
- "Table ahead"
- "Monitor on your right"
- "Books ahead"

### OCR Messages
- "Exit sign detected ahead"
- "History section detected ahead"
- "Restroom sign on your left"

### Clear Path
- "Path ahead is clear"

## Integration Examples

### Python Backend
```python
from ML_models.tts_service import get_tts_service, process_adapter_output
from ML_models.adapters.yolo_adapter import vision_adapter

# Initialize
tts = get_tts_service()

# Process image and speak
result = vision_adapter("image.jpg")
messages = process_adapter_output(result, max_messages=1)
if messages:
    tts.speak_async(messages[0].message, messages[0].risk_level)
```

### React Native Frontend
```typescript
import { getTTSService, RiskLevel } from '@/services/TTSService';

const tts = getTTSService();

// From API response
const response = await fetch('/api/vision/tts', {
  method: 'POST',
  body: formData,
});
const data = await response.json();

if (data.spoken_message) {
  // Message already spoken by backend, or speak locally
  await tts.speak(data.spoken_message, RiskLevel.MEDIUM);
}
```

## Configuration

### Python TTS Service
```python
service = TTSService(
    cooldown_seconds=3.0,      # Cooldown between messages
    use_offline=True,          # Use pyttsx3 (offline)
    use_cloud_fallback=False,  # Fallback to gTTS if offline fails
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

## Dependencies

### Python
- `pyttsx3` - Offline TTS engine
- `gtts` (optional) - Cloud TTS fallback

### React Native
- `expo-speech` - Device-based TTS (already in package.json)

## Testing

### Python
```bash
cd software_side/walkbuddy_reactNative/ML_models/tts_service
python tts_service.py  # Run example
python message_reasoning.py  # Run example
```

### React Native
```typescript
import { getTTSService, RiskLevel } from '@/services/TTSService';

const tts = getTTSService();
await tts.speak("Test message", RiskLevel.LOW);
```

## Future Enhancements

- [ ] Voice customization (male/female, speed)
- [ ] Multi-language support
- [ ] Priority queue for multiple messages
- [ ] Audio file caching
- [ ] Integration with navigation system
- [ ] Context-aware messages (e.g., "same chair" vs "new chair")

## Notes

- TTS is designed for accessibility and real-time performance
- Messages should be short and clear (max 10-15 words)
- Anti-spam logic is critical for user experience
- Offline support ensures reliability without internet
- Rule-based approach ensures predictable behavior



