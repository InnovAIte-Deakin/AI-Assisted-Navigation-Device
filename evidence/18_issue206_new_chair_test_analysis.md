# Issue #206 — New Chair Hazard Feedback Test

## Test input

- Video: `74a669fecdf72cc551c3f670445feb9.mp4`
- Duration: approximately 17.4 seconds
- Format: portrait mobile screen recording

## Voice feedback recognised

The recording contains the following clear English phrases:

- “Not safe to move forward.” — 向前移动不安全。
- “Path clear.” — 路径畅通。
- “Chair moving.” — 椅子正在移动。
- “Chair on your left.” — 你的左边有椅子。
- “Hazard ahead: chair.” — 前方有危险：椅子。

The warning phrase is repeated during the test, indicating that the app generated voice guidance rather than only displaying a detection box.

## Model confirmation

Running the repository model against sampled video frames produced detections including:

- `office-chair` at approximately 1–5 seconds and 12 seconds
- confidence values above 0.50 in several frames, including approximately 0.58, 0.53, 0.62, and 0.55
- `table`, `monitor`, and `books` were also detected in some frames

## Result

**PASS — chair hazard feedback scenario.**

The test provides evidence that the camera view detected an `office-chair` and the app produced an audible safety warning: “Not safe to move forward” / “Hazard ahead: chair.”

This passes the supported-chair scenario. It does not prove that unsupported objects such as a kitchen knife are covered; the earlier knife test remains a documented limitation/failure case.

No paired backend terminal log was supplied with this recording, so a backend-log screenshot should be attached separately if the issue requires explicit server-side evidence.
