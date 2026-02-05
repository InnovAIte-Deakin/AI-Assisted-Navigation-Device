# WalkBuddy - AI-Assisted Navigation Device

## 🎯 Project Overview

**WalkBuddy** is an Android application designed to assist visually impaired users with navigation through real-time object detection and audio feedback. This project integrates computer vision, machine learning, and accessibility features to create a comprehensive navigation aid.

Video Demo: https://deakin.au.panopto.com/Panopto/Pages/Viewer.aspx?id=2e24e0f6-17bf-4002-960f-b35f005845bc

## ✨ Key Features

### 🗺️ **Offline Mapping System**
- **OpenStreetMap (OSMDroid)**: Complete offline mapping solution
- **No API Keys Required**: Fully self-contained mapping
- **Smart Search**: Intelligent location search with debounced input and priority-based matching
- **Real-time Location Tracking**: GPS-based positioning with distance and duration calculations
- **Android Geocoder**: Built-in address lookup (no external API needed)

### 📱 **Camera-Based Object Detection**
- **Real-time Computer Vision**: Live camera feed with object detection overlay
- **Custom YOLOv8 Model**: Trained PyTorch model for specific object classes:
  - `book`, `books`, `monitor`, `office-chair`, `whiteboard`, `table`, `tv`
- **Bounding Box Visualization**: Color-coded detection boxes with confidence scores
- **Non-Maximum Suppression (NMS)**: Intelligent filtering to reduce overlapping detections

### **Accessibility Features**
- **Text-to-Speech (TTS)**: Audio announcements for detected objects and navigation instructions
- **Voice-guided Navigation**: Step-by-step audio directions to destinations
- **Repeat Functionality**: Replay last announcement on demand
- **Pause/Resume Controls**: User control over detection and announcements

### 🎛️ **User Interface**
- **Modern Material Design**: Clean, accessible interface with high contrast colors
- **Intuitive Navigation**: Simple flow from search to camera navigation
- **Real-time Status Updates**: Live display of distance, steps, and detected objects
- **Responsive Layout**: Optimized for various screen sizes

## 🏗️ Technical Architecture

### **Frontend (Android)**
- **Language**: Java
- **Minimum SDK**: API 24 (Android 7.0)
- **Target SDK**: API 35 (Android 15)
- **Architecture**: MVVM pattern with Activity-based navigation

### **Key Dependencies**
```kotlin
// Core Android
implementation("androidx.appcompat:appcompat:1.6.1")
implementation("com.google.android.material:material:1.11.0")

// Location Services (GPS only - no API key needed)
implementation("com.google.android.gms:play-services-location:21.3.0")

// Camera & Image Processing
implementation("androidx.camera:camera-core:1.3.0")
implementation("androidx.camera:camera-camera2:1.3.0")

// Offline Mapping
implementation("org.osmdroid:osmdroid-android:6.1.17")
```

### **Machine Learning Pipeline**
1. **Model Conversion**: YOLOv8 PyTorch model → PyTorch Lite (.ptl) format
2. **Image Preprocessing**: 640x640 RGB normalization with 0-1 scaling
3. **Real-time Inference**: CameraX integration with tensor processing
4. **Post-processing**: Bounding box extraction, confidence filtering, NMS

## 📱 Usage Guide

### **Basic Navigation Flow**
1. **Launch App**: Start from splash screen
2. **Search Destination**: Use search bar to find locations
3. **Select Location**: Choose from suggestions or search results
4. **Start Camera Navigation**: Tap "Start Camera Navigation" button
5. **Follow Audio Guidance**: Listen to TTS announcements and object detection

### **Camera Navigation Features**
- **Object Detection**: Point camera at objects to hear audio descriptions
- **Bounding Boxes**: Visual feedback with color-coded detection boxes
- **Confidence Filtering**: Only high-confidence detections are announced
- **Distance Tracking**: Real-time distance to destination

## ⚠️ Known Limitations & Current Issues

### **Object Detection Accuracy**
- **Confidence Threshold**: Currently set to 0.4 (lowered from 0.7) due to model limitations
- **Detection Consistency**: Model sometimes produces uniform 0.500 confidence scores
- **False Positives**: Occasional incorrect object classifications
- **Environmental Sensitivity**: Performance varies with lighting and object positioning

### **Technical Challenges**
- **Model Conversion**: PyTorch to PyTorch Lite conversion can introduce precision loss
- **Mobile Performance**: Real-time inference on mobile devices is computationally intensive
- **Memory Management**: Large model files require careful memory optimization
- **Native Library Loading**: PyTorch Lite native libraries require specific ABI configuration

### **Platform Limitations**
- **Android Emulator**: Limited camera functionality and performance
- **Device Compatibility**: Requires devices with sufficient processing power
- **Battery Usage**: Continuous camera and ML processing drains battery quickly

## 🔧 Development Notes

### **Model Training Considerations**
- **Dataset Quality**: Model performance directly correlates with training data quality
- **Class Imbalance**: Some object classes may be underrepresented in training data
- **Environmental Adaptation**: Model may need retraining for specific use environments

### **Performance Optimization**
- **Inference Speed**: Current FPS ranges from 1-3 on mid-range devices
- **Memory Usage**: Model loading requires ~50MB RAM
- **Battery Optimization**: Consider implementing detection intervals for battery life

### **Future Improvements**
- **Model Quantization**: Further optimize model size and speed
- **Confidence Calibration**: Improve confidence score accuracy
- **Multi-object Tracking**: Track objects across frames for better stability
- **Offline Mode**: Complete offline functionality for areas without internet

## Academic Context

This project was developed as part of a **SIT378 Capstone Unit** at Deakin University, demonstrating:
- **Machine Learning Integration**: Custom YOLOv8 model implementation
- **Mobile Development**: Android app architecture and optimization
- **Accessibility Design**: User-centered design for visually impaired users
- **Real-world Problem Solving**: Addressing navigation challenges for accessibility

## 📊 Performance Metrics

### **Current Performance**
- **Detection Accuracy**: ~60-70% for trained object classes
- **Inference Speed**: 1-3 FPS on mid-range Android devices
- **Memory Usage**: ~50MB for model + ~30MB for app
- **Battery Impact**: High (continuous camera + ML processing)

### **Detection Classes**
| Class | Training Status | Detection Rate | Notes |
|-------|----------------|----------------|-------|
| `book` | ✅ Trained | ~70% | Good performance |
| `books` | ✅ Trained | ~65% | Similar to book |
| `office-chair` | ✅ Trained | ~60% | Most common false positive |
| `table` | ✅ Trained | ~75% | Best performance |
| `monitor` | ✅ Trained | ~55% | Lighting sensitive |
| `whiteboard` | ✅ Trained | ~60% | Size dependent |
| `tv` | ✅ Trained | ~50% | Least reliable |

## 🚀 Quick Start

1. **Open in Android Studio** (Arctic Fox or later)
2. **Add Model File**: Place `best_lite_fixed.ptl` (or pytorch lite file) in `app/src/main/assets/models/`
3. **Build & Run**: Use a physical device for best camera performance
4. **Grant Permissions**: Allow camera and location access when prompted

## Contributing

This is an ongoing project, thus, all interested in the project are welcome to make contributions to:
- Model accuracy improvements
- Performance optimizations
- UI/UX enhancements
- Documentation updates

## 📄 License

This project is developed for AI-Assisted Navigation Device project of InnovAlte

## 👥 Team

- **Developer**: HAYES (HAYDEN) DUONG
- **ML Team**: VIVADA THANUDARIE LOKUGAMAGE & T2/2025 ML Team
- **Company**: InnovAlte (Deakin University)
