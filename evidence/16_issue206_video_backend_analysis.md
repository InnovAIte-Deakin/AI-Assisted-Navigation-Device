# Issue #206 — Hazard Feedback Integration Test Analysis

## Test input

- Video: `d93e9c53e098960260e974161f692a95.mp4`
- Duration: approximately 28.2 seconds
- Device recording: portrait mobile screen recording
- Related evidence image: `15_issue206_video_contact_sheet.png`

## Video observations

1. The app starts on the Home screen and then opens the Camera screen.
2. Between approximately 8 and 20 seconds, the camera view displays several detection boxes labelled `office-chair`, with visible confidence values including approximately 54% and 52%.
3. The detection boxes remain aligned with visible chairs while the camera moves, which provides evidence that the live camera-to-vision path is active.
4. From approximately 24 to 28 seconds, the camera points toward a kitchen/room area and no detection boxes are visible in the sampled frames.
5. The video primarily proves visual detection. It does not by itself prove that a spoken hazard warning was heard by the user.

## Backend log observations

- Several clients from `192.168.5.171` successfully reached `WebSocket /ws/vision` and were accepted.
- The backend logged `[WS Vision] Connected`, showing that the mobile app could reach the live vision endpoint.
- The backend also logged `Cannot call "receive" once a disconnect message has been received` when the client disconnected. This appears to be a connection-close handling issue or reconnect/teardown noise; it is not by itself proof that object detection failed.
- The backend returned `POST /ocr` with `200 OK` and `POST /routing` with `200 OK` during the same run.
- The log also contains `GET /vision/?v=...` followed by a redirect and `GET /vision?...` with `405 Method Not Allowed`. This is evidence that an old or separate WebView preview path is still trying to use `GET /vision`, while the backend route expects a different request flow. The current Camera screen uses `/ws/vision`, so this should be tracked separately from the successful live-camera detections.
- OpenTelemetry export warnings for `localhost:4317` are non-blocking observability errors and did not prevent the app requests from being served.

## Result

**Partial pass.**

The mobile Camera screen reached the backend and displayed live object detections, so the visual part of the integration is working. The complete Issue #206 acceptance criteria are not fully evidenced yet because the available backend excerpt does not show explicit `detection_result`/`guidance_message` payloads, and the video does not independently confirm voice feedback.

## Recommended follow-up

1. Repeat one controlled test with a clearly visible hazard/object and keep the backend terminal visible.
2. Capture evidence showing the detection result and `guidance_message` returned through `/ws/vision`.
3. Confirm and record whether the mobile device speaks the guidance.
4. Record the WebSocket disconnect error as a follow-up issue if it can be reproduced as a user-visible failure.
5. Keep the `/vision` GET/405 behavior separate unless the current UI still uses that preview path.
