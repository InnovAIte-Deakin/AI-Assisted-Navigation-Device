"""
YOLOv8s Training Script - Sprint 2 (15 Classes)
Trains object detection model with expanded class set
"""

import torch
from ultralytics import YOLO
import yaml
from pathlib import Path
import sys
from datetime import datetime
import os

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

class Sprint2ModelTrainer:
    def __init__(self, config_path='config/data_config.yaml'):
        """Initialize trainer with configuration"""

        print("=" * 70)
        print("SPRINT 2 - YOLOV8s TRAINING (15 CLASSES)")
        print("=" * 70)
        print()

        # Load configuration
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config not found: {config_path}")

        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        print(f"✅ Configuration loaded: {config_path}")
        print(f"   Classes: {self.config['nc']}")
        print(f"   Names: {', '.join(self.config['names'][:3])}... ({len(self.config['names'])} total)")
        print()

        # Training parameters
        self.training_params = {
            # Model
            'model': 'yolov8s.pt',  # Base model (pre-trained on COCO)
            'pretrained': True,

            # Training schedule
            'epochs': 150,  # Reduced from 250 due to transfer learning
            'patience': 30,  # Early stopping patience
            'batch': 16,
            'imgsz': 640,

            # Device
            'device': 0 if torch.cuda.is_available() else 'cpu',

            # Optimizer
            'optimizer': 'auto',  # Adam or SGD
            'lr0': 0.01,  # Initial learning rate
            'lrf': 0.01,  # Final learning rate (lr0 * lrf)
            'momentum': 0.937,
            'weight_decay': 0.0005,

            # Data augmentation (heavy - proven in Sprint 1)
            'augment': True,
            'hsv_h': 0.015,  # Hue augmentation
            'hsv_s': 0.7,    # Saturation augmentation
            'hsv_v': 0.4,    # Value augmentation
            'degrees': 15.0,  # Rotation (+/- degrees)
            'translate': 0.1, # Translation (+/- fraction)
            'scale': 0.5,     # Scale gain
            'shear': 0.0,     # Shear (+/- degrees)
            'perspective': 0.0, # Perspective (+/- fraction)
            'flipud': 0.0,    # Vertical flip probability
            'fliplr': 0.5,    # Horizontal flip probability
            'mosaic': 1.0,    # Mosaic augmentation
            'mixup': 0.15,    # Mixup augmentation
            'copy_paste': 0.0, # Copy-paste augmentation

            # Performance
            'cache': True,     # Cache images for faster training
            'workers': 8,      # DataLoader workers
            'cos_lr': True,    # Cosine learning rate scheduler
            'close_mosaic': 10, # Disable mosaic last N epochs

            # Validation
            'val': True,
            'save': True,
            'save_period': -1,  # Save checkpoint every N epochs (-1 = only best/last)

            # Output
            'project': 'experiments/object_detection',
            'name': 'yolo_v8s_15class_sprint2',
            'exist_ok': False,  # Don't overwrite existing

            # Logging
            'verbose': True,
            'plots': True,  # Save training plots
        }

        # Check for GPU
        if torch.cuda.is_available():
            print(f"✅ GPU Available: {torch.cuda.get_device_name(0)}")
            print(f"   CUDA Version: {torch.version.cuda}")
            print(f"   Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        else:
            print("⚠️  No GPU detected - training will use CPU (slower)")
        print()

        # Check if Sprint 1 model exists for transfer learning
        self.sprint1_model = Path('models/object_detection/best.pt')
        if self.sprint1_model.exists():
            print(f"✅ Found Sprint 1 model: {self.sprint1_model}")
            print("   Will use transfer learning from Sprint 1 weights")
            self.training_params['model'] = str(self.sprint1_model)
        else:
            print(f"⚠️  Sprint 1 model not found: {self.sprint1_model}")
            print("   Will train from COCO pre-trained weights")
        print()

    def verify_dataset(self):
        """Verify dataset structure and availability"""
        print("=" * 70)
        print("DATASET VERIFICATION")
        print("=" * 70)
        print()

        # Check paths
        train_images = Path(self.config['train'])
        val_images = Path(self.config['val'])

        print(f"Training path: {train_images}")
        if train_images.exists():
            train_count = len(list(train_images.glob('*.jpg'))) + len(list(train_images.glob('*.png')))
            print(f"✅ Training images found: {train_count}")
        else:
            print(f"❌ Training path not found!")
            return False

        print(f"Validation path: {val_images}")
        if val_images.exists():
            val_count = len(list(val_images.glob('*.jpg'))) + len(list(val_images.glob('*.png')))
            print(f"✅ Validation images found: {val_count}")
        else:
            print(f"❌ Validation path not found!")
            return False

        print()
        print(f"Total dataset: {train_count + val_count} images")
        print(f"Split: {train_count} train / {val_count} val ({train_count/(train_count+val_count)*100:.1f}% train)")
        print()

        # Verify class balance
        print("Classes to train:")
        for i, name in enumerate(self.config['names']):
            marker = "🆕" if i >= 7 else "📦"
            print(f"  {marker} {i}: {name}")
        print()

        return True

    def train(self):
        """Run training"""

        # Verify dataset
        if not self.verify_dataset():
            print("❌ Dataset verification failed!")
            return None

        print("=" * 70)
        print("STARTING TRAINING")
        print("=" * 70)
        print()

        # Training summary
        print("Training Configuration:")
        print(f"  Model: {self.training_params['model']}")
        print(f"  Epochs: {self.training_params['epochs']}")
        print(f"  Batch size: {self.training_params['batch']}")
        print(f"  Image size: {self.training_params['imgsz']}")
        print(f"  Device: {self.training_params['device']}")
        print(f"  Augmentation: {'Enabled' if self.training_params['augment'] else 'Disabled'}")
        print(f"  Output: {self.training_params['project']}/{self.training_params['name']}")
        print()

        # Estimated time
        estimated_time = self.training_params['epochs'] * 40 / 60  # ~40s per epoch
        print(f"⏱️  Estimated training time: {estimated_time:.1f} hours")
        print()

        # Confirmation
        response = input("Start training? (y/n): ").lower()
        if response != 'y':
            print("Training cancelled.")
            return None

        print()
        print("🚀 Starting training...")
        print()

        # Load model
        model = YOLO(self.training_params['model'])

        # Train
        results = model.train(
            data=str(self.config_path),
            **{k: v for k, v in self.training_params.items() if k != 'model'}
        )

        print()
        print("=" * 70)
        print("TRAINING COMPLETE!")
        print("=" * 70)
        print()

        # Results summary
        output_dir = Path(self.training_params['project']) / self.training_params['name']
        print(f"✅ Results saved to: {output_dir}")
        print()
        print("Key files:")
        print(f"  📊 Metrics: {output_dir}/results.csv")
        print(f"  📈 Plots: {output_dir}/results.png")
        print(f"  🏆 Best model: {output_dir}/weights/best.pt")
        print(f"  💾 Last model: {output_dir}/weights/last.pt")
        print()

        # Performance summary
        if results and hasattr(results, 'results_dict'):
            metrics = results.results_dict
            print("Performance Summary:")
            print(f"  mAP@0.5: {metrics.get('metrics/mAP50(B)', 0):.3f}")
            print(f"  mAP@0.5-0.95: {metrics.get('metrics/mAP50-95(B)', 0):.3f}")
            print(f"  Precision: {metrics.get('metrics/precision(B)', 0):.3f}")
            print(f"  Recall: {metrics.get('metrics/recall(B)', 0):.3f}")
            print()

        # Next steps
        print("Next steps:")
        print("  1. Validate model: python scripts/validate_sprint2_model.py")
        print("  2. Update system config with new model path")
        print("  3. Test with visual demo: python quick_visual_demo.py")
        print()

        return results

    def export_model(self, weights_path=None):
        """Export trained model for deployment"""

        if weights_path is None:
            output_dir = Path(self.training_params['project']) / self.training_params['name']
            weights_path = output_dir / 'weights' / 'best.pt'

        if not Path(weights_path).exists():
            print(f"❌ Model not found: {weights_path}")
            return

        print(f"📦 Exporting model: {weights_path}")

        # Copy to models directory
        dest = Path('models/object_detection/sprint2_best.pt')
        dest.parent.mkdir(parents=True, exist_ok=True)

        import shutil
        shutil.copy(weights_path, dest)

        print(f"✅ Model exported to: {dest}")
        print()
        print("To use this model:")
        print("  1. Update system_config.yaml:")
        print("     sprint2_features:")
        print("       model_path: 'models/object_detection/sprint2_best.pt'")
        print()
        print("  2. Test with demo:")
        print("     python quick_visual_demo.py --model models/object_detection/sprint2_best.pt")
        print()

def main():
    """Main training function"""

    # Create trainer
    trainer = Sprint2ModelTrainer()

    # Train model
    results = trainer.train()

    if results:
        # Export model
        print()
        response = input("Export model to models/object_detection/? (y/n): ").lower()
        if response == 'y':
            trainer.export_model()

        print()
        print("🎉 Sprint 2 model training complete!")
        print()

if __name__ == "__main__":
    main()
