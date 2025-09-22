# WalkBuddy - AI-Assisted Navigation Device

![WalkBuddy Logo](frontend_reactNative/assets/images/company_logo.png)

WalkBuddy is an innovative AI-powered navigation assistant designed to help users navigate indoor spaces using computer vision, optical character recognition (OCR), and voice assistance technologies. Built with React Native and Python, it provides real-time object detection, text scanning, and voice-guided assistance.

Video Demo: https://deakin.au.panopto.com/Panopto/Pages/Sessions/List.aspx?folderID=22f426e4-d55b-44cd-ad71-b35f016984b2

## 🚀 Features

### Core Capabilities
- **🎯 Vision Assist**: Real-time object detection using YOLO v8 model
  - Identifies books, monitors, office chairs, and other objects
  - Provides audio feedback for detected objects
  - Custom-trained model for indoor navigation

- **🎤 Voice Assist**: Speech recognition and text-to-speech
  - Voice commands for mode switching
  - Audio feedback for detected objects
  - Cross-platform speech support

- **📖 Text Scanning**: Live OCR capabilities
  - Real-time text detection from camera feed
  - EasyOCR integration with GPU acceleration
  - Text-to-speech for detected content

### Technical Features
- **📱 Cross-Platform**: React Native app supporting iOS, Android, and Web
- **🐳 Dockerized**: Complete containerized deployment
- **🔄 Model Switching**: Dynamic switching between AI models
- **⚡ Real-time Processing**: Live camera feed processing
- **🎨 Modern UI**: Clean, accessible interface with haptic feedback

## 🏗️ Project Structure

```
walkbuddy_reactNative/
├── frontend_reactNative/          # React Native/Expo app
│   ├── app/                       # App screens and navigation
│   ├── components/                # Reusable UI components
│   ├── src/                      # Source code and utilities
│   ├── assets/                   # Images, fonts, and static assets
│   └── android/                  # Android-specific configuration
├── backend/                      # Python FastAPI server
│   ├── main.py                   # Main API server
│   └── requirements.txt          # Python dependencies
├── ML_models/                    # AI/ML model implementations
│   ├── yolo_nav/                 # YOLO object detection
│   │   ├── dataset/              # Training data
│   │   ├── weights/              # Model weights
│   │   └── *.py                  # Model scripts
│   └── live ocr/                 # OCR implementation
│       └── live_ocr_tts.py       # Live OCR with TTS
├── docker-compose.yml            # Container orchestration
└── README.md                     # This file
```

## 🛠️ Technology Stack

### Frontend
- **React Native** with Expo
- **TypeScript** for type safety
- **Expo Camera** for camera access
- **Expo Speech** for TTS/STT
- **React Navigation** for routing
- **Vector Icons** for UI elements

### Backend
- **FastAPI** for API server
- **Uvicorn** as ASGI server
- **CORS** middleware for cross-origin requests

### AI/ML
- **YOLO v8** (Ultralytics) for object detection
- **EasyOCR** for text recognition
- **OpenCV** for computer vision
- **PyTorch** for deep learning
- **Gradio** for model interfaces

### Infrastructure
- **Docker** for containerization
- **Docker Compose** for orchestration
- **ngrok** for tunneling (optional)

## 🚀 Quick Start

### Prerequisites
- Node.js (v18 or higher)
- Python 3.9+
- Docker and Docker Compose
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd walkbuddy_reactNative
   ```

2. **Install dependencies**
   ```bash
   # Install frontend dependencies
   cd frontend_reactNative
   npm install
   cd ..

   # Install backend dependencies
   cd backend
   pip install -r requirements.txt
   cd ..
   ```

3. **Start with Docker Compose**
   ```bash
   docker-compose up --build
   ```

   This will start:
   - Backend API server on `http://localhost:8000`
   - Frontend development server on `http://localhost:19000`
   - Gradio interface on `http://localhost:7860`

### Manual Setup (Alternative)

1. **Start the backend**
   ```bash
   cd backend
   python main.py
   ```

2. **Start the frontend**
   ```bash
   cd frontend_reactNative
   npm start
   ```

3. **Access the application**
   - Mobile: Use Expo Go app to scan QR code
   - Web: Open `http://localhost:19006`
   - API: `http://localhost:8000`

## 📱 Usage

### Getting Started
1. Launch the WalkBuddy app
2. Grant camera permissions when prompted
3. Choose your preferred mode:
   - **Vision Assist**: For object detection
   - **Voice Assist**: For voice commands
   - **Scan Text**: For OCR text recognition

### Voice Commands
- Say "help" to open help
- Say "scan text" to switch to OCR mode
- Voice feedback provides audio descriptions of detected objects

### Object Detection
The app can detect and announce:
- Books and book collections
- Computer monitors
- Office chairs
- Other objects (based on training data)

## 🔧 Configuration

### Environment Variables
Create a `.env` file in the root directory:
```env
EXPO_PUBLIC_API_BASE_URL=http://your-ip:8000
NGROK_AUTHTOKEN=your-ngrok-token
```

### Model Configuration
- Update `ML_models/yolo_nav/data.yaml` for custom object classes
- Modify confidence thresholds in model scripts
- Add new training data to `dataset/` folders

### Network Configuration
For mobile testing, update the API URL in `docker-compose.yml`:
```yaml
environment:
  - EXPO_PUBLIC_API_BASE_URL=http://YOUR_IP:8001
```

## 🧪 Development

### Frontend Development
```bash
cd frontend_reactNative
npm run android    # Run on Android
npm run ios        # Run on iOS
npm run web        # Run on web
npm run lint       # Run linter
```

### Backend Development
```bash
cd backend
python main.py     # Start development server
```

### Model Training
```bash
cd ML_models/yolo_nav
python train_yolov8.py    # Train YOLO model
python infer_and_tts.py   # Test inference
```

## 📊 API Endpoints

### Backend API (`http://localhost:8000`)
- `GET /healthz` - Health check
- `GET /status` - Current model status
- `GET /logs` - Recent logs
- `GET /switch/{mode}` - Switch AI model (gradio/ocr)
- `GET /stop` - Stop current model

### Model Interfaces
- **Gradio Interface**: `http://localhost:7860` (YOLO object detection)
- **OCR Interface**: `http://localhost:7860` (when OCR mode is active)

## 🎯 Model Training

### YOLO Object Detection
1. Prepare your dataset in YOLO format
2. Update `data.yaml` with your classes
3. Run training:
   ```bash
   cd ML_models/yolo_nav
   python train_yolov8.py
   ```
4. Model weights will be saved in `runs/detect/train/weights/`

### Dataset Structure
```
dataset/
├── train/
│   ├── images/     # Training images
│   └── labels/     # YOLO format labels
├── valid/
│   ├── images/     # Validation images
│   └── labels/     # Validation labels
└── test/
    ├── images/     # Test images
    └── labels/     # Test labels
```

## 🐛 Troubleshooting

### Common Issues

1. **Camera not working**
   - Ensure camera permissions are granted
   - Check if camera is being used by another app
   - Try restarting the app

2. **Models not loading**
   - Check if backend server is running
   - Verify model files exist in correct locations
   - Check Docker logs: `docker-compose logs backend`

3. **Network connectivity**
   - Ensure mobile device and computer are on same network
   - Update IP address in configuration
   - Check firewall settings

4. **Performance issues**
   - Reduce camera resolution
   - Lower confidence thresholds
   - Use GPU acceleration if available

### Debug Mode
Enable debug logging by setting environment variables:
```bash
export PYTHONUNBUFFERED=1
export EXPO_DEBUG=1
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Add tests if applicable
5. Commit your changes: `git commit -m 'Add feature'`
6. Push to the branch: `git push origin feature-name`
7. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👥 Team

- **Project**: SIT378_782 - Team Project (B) - Execution and Delivery
- **Course**: AI-Assisted Navigation Device
- **Institution**: Deakin University

## 📚 Resources

- [React Native Documentation](https://reactnative.dev/)
- [Expo Documentation](https://docs.expo.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [YOLO v8 Documentation](https://docs.ultralytics.com/)
- [EasyOCR Documentation](https://github.com/JaidedAI/EasyOCR)

## 🔮 Future Enhancements

- [ ] Indoor mapping and navigation
- [ ] Multi-language support
- [ ] Offline mode capabilities
- [ ] Advanced object recognition
- [ ] Integration with building management systems
- [ ] Accessibility improvements
- [ ] Cloud model deployment

