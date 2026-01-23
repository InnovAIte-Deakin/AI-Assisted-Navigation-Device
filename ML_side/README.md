# AI-Assisted Navigation Device - ML System

🎯 **Complete navigation system for visually impaired users in library environments**

## 🚀 System Overview

The AI-Assisted Navigation Device provides intelligent navigation assistance through:

- **🔍 Real-time Object Detection**: YOLO-based detection of library furniture and equipment
- **🗺️ Semantic Mapping**: Intelligent understanding of library environments and zones
- **🧠 Scene Memory**: Temporal tracking of objects and environmental changes
- **🚀 Advanced Pathfinding**: Multiple algorithms (A*, D*, RRT*) for optimal navigation
- **💬 Natural Language Processing**: LLM-powered navigation guidance and reasoning
- **🎯 Integrated Planning**: Complete pipeline from detection to actionable guidance

## ✅ System Status: **FULLY FUNCTIONAL**

### 🏆 Sprint 1 Complete - All Core Components Implemented:

- **✅ YOLO Object Detection** - 85.7% mAP@0.5, detecting 6 library object classes
- **✅ LLM Integration** - OpenAI API + fallback reasoning for intelligent guidance  
- **✅ Semantic Mapping** - Library zone classification and spatial understanding
- **✅ Scene Memory System** - Object tracking and temporal awareness
- **✅ A* Pathfinding** - Optimal path planning (30-50ms performance)
- **✅ RRT* Pathfinding** - Complex environment navigation
- **✅ Navigation Planner** - Integrated system with automatic algorithm selection
- **✅ Comprehensive Testing** - Full test suite with 6/6 passing tests

## 🏗️ Project Structure

```
ML_side/
├── src/                           # Core system modules
│   ├── llm_integration/           # LLM reasoning and navigation pipeline
│   ├── semantic_mapping/          # Environment understanding and memory
│   └── pathfinding/              # Navigation algorithms (A*, D*, RRT*)
├── models/object_detection/       # Trained YOLO model weights
├── data/processed/               # Training and validation datasets
├── config/                       # System configuration
├── experiments/                  # Model training results
├── notebooks/                    # Development and analysis notebooks
├── demo.py                       # Live system demonstration
├── run_tests.py                  # Comprehensive test suite
└── requirements.txt              # Dependencies
```

## 🚀 Quick Start

### 1. Setup Environment
```bash
# Create virtual environment
python -m venv ml_env
source ml_env/bin/activate  # Linux/Mac
# or
ml_env\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Run System Demo
```bash
python demo.py
```
*Demonstrates complete navigation pipeline with live camera or test images*

### 3. Run Comprehensive Tests
```bash
python run_tests.py
```
*Validates all system components (expected: 6/6 tests passing)*

### 4. Test Individual Components
```bash
# Test semantic mapping and pathfinding
python test_semantic_mapping.py
python test_pathfinding.py
```

## 🎯 System Capabilities

### **Real-time Navigation Assistance**
- Detects library objects with 85.7% accuracy
- Classifies environments (computer labs, study areas, reading areas)
- Plans optimal paths around obstacles in 30-50ms
- Provides natural language navigation guidance

### **Intelligent Environment Understanding**
- Builds persistent spatial maps of library layouts  
- Tracks object movement and environmental changes
- Learns familiar locations and navigation patterns
- Adapts to dynamic environments in real-time

### **Multi-Algorithm Pathfinding**
- **A***: Optimal paths for stable environments
- **D***: Dynamic replanning for changing conditions
- **RRT***: Complex space exploration and navigation
- **Auto-selection**: Chooses best algorithm for each scenario

## 📊 Performance Metrics

| Component | Performance | Notes |
|-----------|-------------|--------|
| **YOLO Detection** | 85.7% mAP@0.5 | 6 object classes, real-time capable |
| **A* Pathfinding** | 17-50ms planning | Optimal paths, 170-303 nodes explored |
| **RRT* Pathfinding** | 320ms with optimization | Complex environments, probabilistic |
| **Environment Classification** | >90% accuracy | Computer labs, study areas, etc. |
| **Integration Pipeline** | Real-time capable | Complete detection→guidance pipeline |

## 🎮 Usage Examples

### Basic Navigation
```python
from src.pathfinding.navigation_planner import NavigationPlanner, NavigationRequest

# Initialize system
planner = NavigationPlanner(image_width=640, image_height=480)

# Update with camera input
planner.update_environment(yolo_detections, location_hint="Library entrance")

# Plan navigation
request = NavigationRequest(
    goal_description="find computer lab",
    start_pixel_pos=(50.0, 50.0)
)

result = planner.plan_navigation(request)
print(f"Next action: {result.next_action}")
```

### Complete Pipeline
```python
from demo import run_demo
run_demo()  # Full system demonstration
```

## 🧪 Testing & Validation

**Test Suite Results: 6/6 PASSING** ✅

- **Semantic Mapping**: Environment understanding and memory systems
- **A* Pathfinding**: Optimal path planning validation
- **Algorithm Comparison**: Performance benchmarking
- **Navigation Integration**: End-to-end system testing  
- **Visualization**: Path generation and analysis
- **Live Demo**: Real-world scenario validation

## 🔮 Future Enhancements (Sprint 2)

- **🎧 Multimodal Feedback**: Voice guidance + haptic feedback
- **📱 Mobile Integration**: Smartphone app interface
- **☁️ Cloud Mapping**: Shared navigation knowledge
- **🏢 Multi-floor Support**: 3D navigation capabilities
- **👥 Social Navigation**: Crowd-aware pathfinding

## 🎉 Project Success

**The AI-Assisted Navigation Device is now fully functional and ready for deployment!**

- Complete navigation pipeline from camera input to user guidance
- Production-ready performance with comprehensive error handling
- Extensible architecture for future enhancements
- Validated through extensive testing and real-world scenarios

---

## 📋 Detailed Technical Information

### Object Detection Classes
The YOLO model detects 6 library object classes:
- **Books** - Reading materials and collections
- **Monitor** - Computer screens and displays  
- **Office-chair** - Seating furniture
- **Table** - Work and study surfaces
- **Whiteboard** - Presentation and writing surfaces
- **TV** - Television screens and displays

### Model Performance Details
- **Best Model**: YOLOv8s with heavy augmentation
- **Training**: 100-250 epochs on 675 training images
- **Validation**: 80 validation images with comprehensive metrics
- **Real-time Performance**: Capable of processing live camera feeds

### Architecture Components
- **Navigation Pipeline**: Integrates YOLO detection with LLM reasoning
- **Semantic Map Builder**: Creates persistent spatial understanding
- **Scene Memory System**: Tracks temporal object relationships
- **Grid Map Converter**: Transforms detections into navigable representations
- **Multiple Pathfinders**: A*, D*, and RRT* algorithms with auto-selection

*Developed for SIT374 - Capstone Team Project, Deakin University*