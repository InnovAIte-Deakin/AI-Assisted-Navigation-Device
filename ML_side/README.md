# AI-Assisted Navigation Device - Machine Learning Component

## Overview

This folder contains the machine learning component of the AI-Assisted Navigation Device project. It focuses on implementing computer vision capabilities for object detection and recognition to provide contextual awareness for navigation assistance.

## Purpose

The ML component provides "contextual awareness" for the navigation device by handling complex tasks like object and text recognition. It enables the device to identify and locate common objects in indoor environments to assist users with navigation.

## Key Features

- **Object Detection**: Identifies and locates common indoor objects
- **Text Recognition (OCR)**: Extracts and reads text from camera feed
- **Real-time Processing**: Optimized for live camera feed processing
- **Text-to-Speech Integration**: Provides audio feedback for detected objects and text
- **Performance Metrics**: Tracks accuracy with CER, WER, and BLEU scores
- **Privacy-Focused**: Designed for on-device processing to protect user privacy

## Dataset

### Object Classes
The model is trained to detect 7 different object classes:
- `book` - Individual books
- `books` - Multiple books or book collections
- `monitor` - Computer monitors and displays
- `office-chair` - Office chairs and seating
- `whiteboard` - Whiteboards and writing surfaces
- `table` - Tables and work surfaces
- `tv` - Television screens and displays

### Dataset Structure
- **Training Set**: 675 images with corresponding YOLO format labels
- **Validation Set**: 80 images with corresponding YOLO format labels
- **Combined Dataset**: Merged custom dataset with Roboflow dataset (684 train, 82 val, 42 test images)

### Data Format
- **Images**: JPG format, various resolutions
- **Labels**: YOLO format with normalized coordinates
  - Format: `class_id center_x center_y width height`
  - All coordinates are normalized (0-1 range)

## Model Architecture

### YOLO Models Used
1. **YOLOv8s** - Primary model for object detection (heavy augmentation)
2. **YOLOv8n** - Lightweight model for comparison
3. **YOLOv11n** - Latest YOLO version
4. **YOLOv5n** - Ultra-lightweight model
5. **YOLOv5s** - Small model variant

### Training Configuration
- **Epochs**: 100-250 (depending on model)
- **Image Size**: 640x640 pixels
- **Batch Size**: 16-32
- **Optimizer**: Adam with learning rate 0.003
- **Data Augmentation**: Mosaic, mixup, HSV adjustments, perspective transforms

## Performance Metrics

### Best Model Results (YOLOv8s)
- **mAP50**: 0.857 (85.7%)
- **mAP50-95**: 0.612 (61.2%)
- **Precision**: 0.826
- **Recall**: 0.823

### Per-Class Performance
- **Books**: 73.2% mAP50-95
- **Monitor**: 89.5% mAP50-95
- **Office-chair**: 53.7% mAP50-95
- **Whiteboard**: 50.5% mAP50-95
- **Table**: 25.4% mAP50-95
- **TV**: 74.8% mAP50-95

## File Structure

```
ML_side/
├── README.md                           # This file
├── requirements.txt                    # Python dependencies
├── config/                            # Configuration files
│   ├── data_config.yaml              # Dataset configuration
│   ├── model_config.yaml             # Model parameters
│   └── app_config.yaml               # Application settings
├── notebooks/                         # Jupyter notebooks
│   ├── 01_data_preparation.ipynb     # Data processing
│   ├── 02_object_detection_training.ipynb  # YOLO training
│   ├── 03_ocr_integration.ipynb      # OCR + TTS implementation
│   └── 04_model_evaluation.ipynb     # Performance analysis
├── src/                              # Source code
│   ├── models/                       # Model implementations
│   ├── audio/                        # Audio processing
│   └── utils/                        # Utility functions
├── data/                             # Datasets
│   ├── processed/                    # Processed datasets
│   └── external/                     # External datasets
├── models/                           # Trained models
│   ├── object_detection/             # YOLO models
│   └── text_recognition/             # OCR models
├── experiments/                      # Training results
│   ├── object_detection/             # YOLO experiments
│   │   ├── yolo_v8s_heavy_aug/      # YOLOv8s with heavy augmentation
│   │   ├── yolo_v8n/                # YOLOv8n standard training
│   │   ├── yolo_v11n/               # YOLOv11n standard training
│   │   ├── yolo_v5n/                # YOLOv5n standard training
│   │   └── yolo_v5s/                # YOLOv5s standard training
│   └── ocr_integration/              # OCR experiments
└── docs/                             # Documentation
    └── performance_reports/           # Performance reports
```

## Training Process

### 1. Data Preparation
- Converted HEIC images to JPG format
- Split dataset into train/validation/test sets (70%/20%/10%)
- Merged custom dataset with Roboflow dataset for increased diversity
- Combined book and books classes for better performance

### 2. Model Training
- Used transfer learning with pre-trained YOLO models
- Implemented data augmentation techniques
- Applied heavy augmentation for improved generalization
- Monitored training with validation metrics

### 3. Evaluation
- Generated confusion matrices and precision-recall curves
- Calculated per-class and overall mAP metrics
- Tested on validation and test sets
- Implemented real-time inference testing

## Real-Time Implementation

### Object Detection + OCR Integration
- **Dual-mode processing**: Object detection and text recognition simultaneously
- **EasyOCR integration**: Real-time text extraction from camera feed
- **Performance metrics**: CER, WER, and BLEU scores for OCR evaluation
- **Threaded processing**: Non-blocking TTS with queue-based architecture

### Text-to-Speech Integration
- **Multiple TTS engines**: Google TTS (online) and pyttsx3 (offline)
- **Confidence thresholds**: Per object class and text confidence filtering
- **Persistence logic**: Avoids repetitive announcements
- **Cooldown periods**: Configurable delays between announcements

### Live Camera Processing
- **Real-time detection**: Object detection and OCR on webcam feed
- **Visual annotations**: Bounding boxes for both objects and text
- **Audio feedback**: Spoken descriptions of detected objects and text
- **Configurable thresholds**: Adjustable confidence levels

## Usage

### Training a New Model
1. Prepare your dataset in YOLO format
2. Update `data.yaml` with your dataset paths
3. Run the training cells in `objectdetection_yolo.ipynb`
4. Monitor training progress and adjust hyperparameters

### Using the Trained Model
```python
from ultralytics import YOLO

# Load the trained model
model = YOLO('best.pt')

# Run inference on an image
results = model.predict('path/to/image.jpg', conf=0.5)

# Display results
results[0].show()
```

### Real-Time Detection with OCR
```python
# For live camera detection with both object detection and OCR
from src.models.object_detector import ObjectDetector
from src.models.text_recognizer import TextRecognizer
from src.audio.tts_engine import TTSEngine

# Initialize components
detector = ObjectDetector('models/object_detection/best.pt')
ocr = TextRecognizer(['en'])
tts = TTSEngine()

# Run live detection
# This provides real-time object detection + OCR + TTS
```

### OCR-Only Mode
```python
# For text recognition only
import cv2
import easyocr

reader = easyocr.Reader(['en'])
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    results = reader.readtext(frame)
    # Process OCR results
```

## Technical Requirements

### Core Dependencies
- Python 3.8+
- PyTorch
- Ultralytics YOLO
- OpenCV
- EasyOCR
- Pillow (for image processing)

### Audio Processing
- pyttsx3 (offline TTS)
- Google Text-to-Speech (gTTS) - optional
- jiwer (OCR metrics)

### Additional Libraries
- NLTK (BLEU scoring)
- Gradio (for web interface)
- NumPy, Pandas (data processing)

## Privacy and Ethics

This implementation is designed with privacy in mind:
- **On-device processing**: All inference runs locally
- **No data transmission**: Images are not sent to external servers
- **Local storage**: Model weights and data remain on the device
- **User control**: Users can disable features or adjust sensitivity

## Future Improvements
- [ ] Add support for more object classes
- [ ] Optimize model for mobile deployment
- [ ] Add support for depth estimation
- [ ] Implement object tracking across frames
- [ ] Add support for multiple languages in TTS
- [ ] Integrate object detection and OCR for unified navigation
- [ ] Add confidence-based filtering for better accuracy
- [ ] Implement custom vocabulary for navigation-specific terms
- [ ] Add support for handwritten text recognition

## Contributing

When contributing to this ML component:
1. Follow the existing code structure and naming conventions
2. Add appropriate documentation for new features
3. Test changes with the validation dataset
4. Update performance metrics if model changes are made
5. Ensure privacy considerations are maintained

## Contact

For questions about the ML component, please refer to the main project documentation or contact the development team.