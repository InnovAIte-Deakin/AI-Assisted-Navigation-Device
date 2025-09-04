## Software Integration

This is the core "brain" of the device. This folder contains the high-level logic that integrates input from both the `sensor_side` and `object_detection_side` to provide a unified and intelligent navigation experience.

**Purpose:** To fuse data from both sensor types, run final algorithms, and manage the user feedback system.

**Key Responsibilities:**
- Implementing data fusion algorithms from sensors and camera
- Controlling the haptic (vibration motor) and auditory (buzzer) feedback based on the fused data
- Integrating text-to-speech (TTS) services to vocalize recognized text
- Managing device configuration and overall system logic