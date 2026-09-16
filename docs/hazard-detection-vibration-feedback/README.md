# Hazard Detection to Vibration Feedback

## 1. Overview

This document investigates how WalkBuddy's machine-learning (ML) hazard detection can be connected to vibration feedback for the user.

The existing system already provides most of the required software pathway:

**ML Detection → Risk Evaluation → `/predict-path` → React Native → Haptic Feedback**

The recommended approach is to implement the vibration logic in the React Native frontend rather than modifying the ML model or backend prediction system.

This keeps hazard detection, API communication and user feedback separated, making the system easier to maintain and extend.

---

## 2. Research Objective

### Objective

Investigate how hazards detected by the WalkBuddy ML system can trigger appropriate vibration feedback within the application/device.

### Research Question

**How can ML hazard-detection results be reliably translated into vibration feedback for a WalkBuddy user?**

The investigation considers:

* Existing hazard detection and risk evaluation
* `/predict-path` communication
* React Native result handling
* Existing haptic functionality
* Hazard-to-vibration mapping
* Repeated hazard predictions
* Confidence thresholds
* Cooldown/debouncing
* Physical-device testing
* Future external vibration hardware

---

## 3. Existing System

The relevant backend is located at:

```text
software_side/walkbuddy_reactNative/backend/predictive_path/
```

The React Native frontend is located at:

```text
software_side/walkbuddy_reactNative/frontend_reactNative/
```

The current general data flow is:

```text
Sensors
   ↓
React Native
   ↓
/predict-path
   ↓
FastAPI
   ↓
ML Prediction
   ↓
Risk Evaluation
   ↓
React Native
   ↓
User Feedback
```

The predictive-path system uses information including:

* Speed
* Heading
* Gyroscope information

### Current Hazard Classifications

| Classification | Meaning                                |
| -------------- | -------------------------------------- |
| `safe`         | No immediate hazard detected           |
| `front`        | Hazard detected ahead                  |
| `front_right`  | Hazard detected toward the front/right |

The prediction also provides confidence information.

The current risk evaluation uses a confidence threshold of approximately **0.50**. Low-confidence predictions should not automatically generate safety-critical vibration feedback.

---

## 4. Proposed Hazard-to-Vibration Architecture

The backend should continue to perform ML prediction and risk evaluation.

The `/predict-path` endpoint should return the structured prediction to the React Native application.

The frontend should then:

1. Receive the hazard result.
2. Check the hazard classification and confidence.
3. Determine whether vibration is required.
4. Select the appropriate vibration pattern.
5. Trigger the device's haptic system.

### Proposed Architecture

```text
ML Model
   ↓
Risk Evaluation
   ↓
/predict-path
   ↓
React Native
   ↓
HapticFeedbackService
   ↓
expo-haptics
   ↓
Phone Vibration
```

This approach avoids unnecessary changes to the underlying ML model.

---

## 5. Hazard-to-Vibration Mapping

An initial mapping can be used as a starting point for testing.

| ML Result       | Proposed Feedback            |
| --------------- | ---------------------------- |
| `safe`          | No vibration                 |
| `front`         | Strong warning vibration     |
| `front_right`   | Distinct warning vibration   |
| Low confidence  | No safety-critical vibration |
| Repeated hazard | Suppress during cooldown     |

The exact vibration patterns should be determined through physical-device testing.

---

## 6. Recommended Haptic Service

The vibration logic should be separated from the predictive-path screen.

Recommended location:

```text
software_side/walkbuddy_reactNative/frontend_reactNative/src/services/HapticFeedbackService.ts
```

The service could provide functions such as:

```text
triggerHazardFeedback(hazardType)
resetHazardFeedback()
```

Example behaviour:

```text
front
  → Strong warning vibration

front_right
  → Distinct warning vibration

safe
  → Reset/stop hazard feedback
```

Using a dedicated service means the haptic functionality can be reused by other parts of the application without duplicating vibration logic.

---

## 7. Repeated Predictions and Cooldown

The predictive-path system can repeatedly request predictions.

If every prediction caused a vibration, the same hazard could produce continuous alerts:

```text
front → vibrate → front → vibrate → front → vibrate
```

This could become excessive or confusing.

A cooldown/debouncing mechanism should therefore be implemented.

The haptic controller should track:

* Previous hazard type
* Time of the previous vibration
* Current risk state
* Configured cooldown period

### Recommended Behaviour

A new hazard should trigger feedback immediately.

If the same hazard continues, additional vibrations should be suppressed until the cooldown period expires.

The final cooldown period should be established through physical testing.

---

## 8. Confidence and Safety

The vibration system should consider the confidence of the ML prediction.

The recommended process is:

```text
Prediction
   ↓
Confidence Check
   ↓
Risk Classification
   ↓
Haptic Feedback
```

For example:

```text
safe
→ No vibration

front + sufficient confidence
→ Warning vibration

front_right + sufficient confidence
→ Distinct warning vibration

Hazard + insufficient confidence
→ No safety-critical vibration
```

Confidence should not be treated as proof that a prediction is correct.

Haptic feedback should remain an additional warning channel alongside other feedback such as visual or spoken feedback.

### API Failure

An important distinction should be maintained between:

```text
safe prediction
```

and:

```text
prediction unavailable
```

If `/predict-path` fails or becomes unavailable, the application should **not automatically interpret the failure as a safe result**.

---

## 9. Phone-Based Haptic Feedback

The first implementation should use the phone's existing haptic capabilities.

The repository already contains the `expo-haptics` package, making this the simplest initial implementation.

The proposed pathway is:

```text
ML Hazard
   ↓
/predict-path
   ↓
React Native
   ↓
HapticFeedbackService
   ↓
expo-haptics
   ↓
Phone Vibration
```

This avoids introducing additional hardware during the initial development stage.

---

## 10. Future External Vibration Hardware

A dedicated vibration device could be investigated in a future development stage.

A possible architecture is:

```text
React Native
   ↓
Bluetooth / BLE
   ↓
Hardware Controller
   ↓
Vibration Motor
```

The current repository does not establish a completed external vibration-motor communication pathway.

Further research would therefore be required into:

* Bluetooth/BLE communication
* Hardware controllers
* Communication latency
* Connection reliability
* Battery requirements
* Vibration motor control
* Device pairing
* Hardware safety

External hardware should therefore be treated as a future development task rather than part of the initial phone-based implementation.

---

## 11. Testing Plan

The feature should be tested using physical devices.

| Test               | Input                                 | Expected Result                       |
| ------------------ | ------------------------------------- | ------------------------------------- |
| Safe Path          | `safe`                                | No vibration                          |
| Front Hazard       | `front` + sufficient confidence       | Warning vibration                     |
| Front-Right Hazard | `front_right` + sufficient confidence | Distinct vibration                    |
| Low Confidence     | Hazard below threshold                | No safety-critical vibration          |
| Repeated Hazard    | Same hazard repeatedly                | Cooldown prevents excessive vibration |
| Hazard Clears      | Risky → `safe`                        | Feedback resets                       |
| Backend Failure    | `/predict-path` unavailable           | Not treated as safe                   |

Testing should be performed on Android and, if available, iOS because haptic behaviour can vary between physical devices.

---

## 12. Recommended Implementation Steps

The recommended implementation order is:

1. Reuse the existing `expo-haptics` dependency.
2. Create `HapticFeedbackService.ts`.
3. Connect predictive-path results to the haptic service.
4. Implement feedback for `safe`, `front` and `front_right`.
5. Add confidence checking.
6. Add cooldown/debouncing for repeated hazards.
7. Test the system on physical Android/iOS devices.
8. Record the final vibration patterns and cooldown period.
9. Investigate external vibration hardware separately.

---

## 13. Suggested File Structure

After implementation, the relevant structure should look similar to:

```text
AI-Assisted-Navigation-Device/
│
├── software_side/
│   └── walkbuddy_reactNative/
│       ├── backend/
│       │   └── predictive_path/
│       │
│       └── frontend_reactNative/
│           ├── src/
│           │   └── services/
│           │       └── HapticFeedbackService.ts
│           │
│           └── app/
│               └── (tabs)/
│                   └── predictive-path.tsx
│
└── docs/
    └── hazard-detection-vibration-feedback/
        └── README.md
```

The README documents the investigation and recommended architecture. The actual implementation should be kept within the existing frontend/backend project structure.

---

## 14. Limitations

The investigation identified the following limitations:

* Predictive-path haptics are not currently connected.
* Final vibration patterns have not yet been established.
* Repeated predictions require cooldown/debouncing.
* ML confidence does not guarantee a correct prediction.
* Haptic behaviour can vary between devices.
* Physical user testing is required before finalising vibration patterns.
* External vibration hardware requires additional development.

---

## 15. Conclusion

The existing WalkBuddy architecture provides a suitable foundation for connecting ML hazard detection to vibration feedback without changing the underlying ML model.

The predictive-path system provides hazard classifications and confidence information through `/predict-path`, while the React Native application already contains `expo-haptics`.

The recommended solution is to create a dedicated frontend haptic service that converts validated hazard classifications into appropriate vibration patterns.

Cooldown/debouncing should be used to prevent repeated predictions from producing excessive alerts.

The initial implementation should focus on phone-based vibration. Dedicated external vibration hardware can be investigated as a future development stage.

---

## 16. Key Recommendation

**Keep the ML and backend responsible for detecting and classifying hazards. Keep the React Native frontend responsible for converting those validated results into user feedback.**

The recommended overall system is:

```text
┌─────────────┐
│   ML Model  │
└──────┬──────┘
       ↓
┌─────────────┐
│Risk Evaluation│
└──────┬──────┘
       ↓
┌─────────────┐
│ /predict-path│
└──────┬──────┘
       ↓
┌─────────────┐
│React Native │
└──────┬──────┘
       ↓
┌────────────────────┐
│HapticFeedbackService│
└──────┬─────────────┘
       ↓
┌─────────────┐
│expo-haptics │
└──────┬──────┘
       ↓
┌─────────────┐
│Phone Vibration│
└─────────────┘
```

This provides a clear separation of responsibilities and allows the vibration system to be developed without unnecessarily modifying the existing ML hazard-detection pipeline.
