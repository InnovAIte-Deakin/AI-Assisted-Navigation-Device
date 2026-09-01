# Issue #206 — Voice Feedback Transcription

## Source

- Video: `d93e9c53e098960260e974161f692a95.mp4`
- Audio duration: approximately 28.2 seconds
- Transcription method: local Whisper speech-to-text, English detection confidence approximately 0.98

## Recognised English speech

The audio is repetitive because the app announces the detected object several times while the camera moves. The clearest recognised phrases are:

- “Chair on your right.” — 你的右边有椅子。
- “Chair ahead.” — 前方有椅子。
- “Chair moving away from you.” — 椅子正在远离你。
- “Not safe to move forward.” — 向前移动不安全。
- “Try moving left.” — 尝试向左移动。
- “Chair moving left.” — 椅子正在向左移动。
- “Chair moving right.” — 椅子正在向右移动。
- “Half clear.” — 前方部分畅通/基本畅通。
- “Chair approaching.” — 椅子正在靠近。
- “Chair on your left.” — 你的左边有椅子。

## Test interpretation

The voice feedback is working for the detected `office-chair` objects. However, the recording does not contain a clear warning for a kitchen knife. Together with the reported knife test in which no warning was produced, the hazard-feedback test for the knife scenario should be recorded as **FAIL**.

This is consistent with the current repository coverage: `knife` is not included in the documented YOLO model classes or the backend hazard taxonomy. The failure is therefore most likely a model/class-coverage and safety-policy gap, rather than a phone-to-backend connectivity failure.
