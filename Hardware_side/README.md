# AI-Assisted Navigation Device - Hardware Side

This folder contains the Android application that serves as the hardware interface for the AI-Assisted Navigation Device. The app provides real-time sensor data collection, computer vision-based obstacle detection, and multimodal feedback (haptic, audio, visual) to assist users with navigation.

Video Demo: https://deakin.au.panopto.com/Panopto/Pages/Viewer.aspx?id=f66f8a41-8f5c-4a97-8859-b35f00df9ae1

## Project Overview

**Purpose:** To provide a comprehensive mobile platform for testing and demonstrating AI-assisted navigation capabilities using smartphone sensors and camera.

**Key Features:**
- Real-time computer vision obstacle detection using ML Kit
- Multi-sensor data collection (accelerometer, gyroscope, magnetometer, rotation vector)
- Step counting and walking progress tracking
- Multimodal feedback system (haptic vibration, text-to-speech, visual overlays)
- Direction and orientation awareness

## Project Structure

### TestingApp/
The main Android application built with Kotlin and Jetpack Compose.

#### Core Components

**MainActivity.kt** - Main application entry point containing:
- **Obstacle Detection Screen**: Real-time camera-based object detection with ML Kit
- **Sensor Reader Screen**: Multi-sensor data collection and analysis
- **Step Counter Screen**: Walking progress tracking and milestone announcements
- **Home Menu**: Navigation hub for accessing different features

**SensorsHelpers.kt** - Utility functions for sensor data processing:
- Compass direction calculation
- Tilt status detection
- Sensor data normalization

#### UI Components

**ui/components/**
- `BottomBar.kt` - Navigation bar for switching between screens
- `StatCard.kt` - Reusable card component for displaying sensor statistics

**ui/theme/**
- `Color.kt`, `Theme.kt`, `Type.kt` - Material Design 3 theming

#### Key Features

1. **Computer Vision Obstacle Detection**
   - Uses Google ML Kit for real-time object detection
   - Configurable confidence and size thresholds
   - Visual overlay with detection bounding boxes
   - Distance-based haptic and audio feedback

2. **Multi-Sensor Integration**
   - Accelerometer, Gyroscope, Magnetometer readings
   - Rotation Vector for fused orientation data
   - Real-time compass direction (N/E/S/W)
   - Camera tilt detection and warnings

3. **Step Counting & Navigation**
   - Step counter and step detector sensor integration
   - Milestone announcements every 10 steps
   - Walking progress tracking

4. **Accessibility Features**
   - Text-to-speech announcements for directions and obstacles
   - Haptic feedback patterns for different obstacle distances
   - Visual overlays and real-time sensor data display

#### Dependencies

- **Android Jetpack Compose** - Modern UI framework
- **CameraX** - Camera integration and image analysis
- **ML Kit** - On-device object detection
- **TensorFlow Lite** - Machine learning inference (best_float32.tflite model included)
- **Android Sensors API** - Hardware sensor access

#### Permissions Required

- `CAMERA` - For obstacle detection
- `VIBRATE` - For haptic feedback
- `ACTIVITY_RECOGNITION` - For step counting (Android 10+)

#### Build Configuration

- **Target SDK**: 35 (Android 15)
- **Minimum SDK**: 24 (Android 7.0)
- **Kotlin**: 2.0.21
- **Gradle**: 8.13.0
- **Compose BOM**: 2024.09.00

## Usage

1. **Vision Mode**: Point camera forward to detect obstacles with real-time feedback
2. **Sensors Mode**: Monitor device orientation, direction, and raw sensor data
3. **Steps Mode**: Track walking progress with milestone announcements

The app provides immediate multimodal feedback to assist users in navigation, making it suitable for testing AI-assisted navigation concepts and accessibility applications.

## Output

This hardware-side application processes sensor data and provides real-time feedback to users. It can be extended to transmit processed data to external systems for higher-level analysis and navigation planning.