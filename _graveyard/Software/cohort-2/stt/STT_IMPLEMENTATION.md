# STT Implementation Summary

## Files Created/Modified

### 1. **src/services/STTService.ts** (NEW)
- Cross-platform STT service
- Web: Uses Web Speech API
- Native: Uses expo-av for recording, sends to backend for transcription
- Handles permissions and error states

### 2. **app/camera.tsx** (MODIFIED)
- Integrated STT service
- Added `processQuery` function to handle transcribed text
- Updated `startListening` to use STT service
- Updated `stopListening` to process transcription and query
- Added `isProcessing` state for loading indicator
- Microphone button already exists and is functional

### 3. **backend/main.py** (MODIFIED)
- Added `/stt/transcribe` endpoint (POST) - accepts audio files
- Added `/query` endpoint (POST) - processes text queries and returns guidance
- Both endpoints documented in API root

### 4. **package.json** (MODIFIED)
- Added `expo-av: ~15.0.1` dependency

## How It Works

### Web Platform:
1. User taps microphone button
2. Web Speech API starts listening
3. As user speaks, interim results show in transcript
4. When speech ends (isFinal), automatically processes query
5. Query sent to `/query` endpoint
6. Response spoken via TTS

### Native Platform (iOS/Android):
1. User taps microphone button
2. expo-av starts recording audio
3. Shows "Recording..." status
4. User taps again to stop
5. Audio sent to `/stt/transcribe` endpoint
6. Transcribed text sent to `/query` endpoint
7. Response spoken via TTS

## Usage

The microphone button is already on the camera screen in "Voice Assist" mode. Simply:
1. Tap to start listening/recording
2. Speak your query (e.g., "Where is the exit?")
3. On web: automatically processes when you stop speaking
4. On native: tap again to stop and process
5. App speaks the response via TTS

## Backend Endpoints

### POST `/stt/transcribe`
- Accepts audio file (multipart/form-data)
- Returns: `{ "text": "...", "confidence": 0.95 }`
- Note: Currently returns placeholder. Integrate with actual STT service for production.

### POST `/query`
- Accepts: `{ "query": "Where is the exit?" }`
- Returns: `{ "response": "...", "guidance": "...", "tts_message": "..." }`
- Rule-based responses (can be replaced with LLM)

## Next Steps for Production

1. **STT Transcription**: Integrate with Google Cloud Speech-to-Text, AWS Transcribe, or similar
2. **Query Processing**: Replace rule-based responses with LLM integration
3. **Error Handling**: Add retry logic and better error messages
4. **Testing**: Test on physical devices with various network conditions

