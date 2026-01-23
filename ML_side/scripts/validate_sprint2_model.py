"""
Model Validation Script - Sprint 2
Tests trained model performance on validation set
"""

from ultralytics import YOLO
import yaml
from pathlib import Path
import pandas as pd
import sys

sys.path.append(str(Path(__file__).parent.parent))

def validate_model(model_path, config_path='config/data_config.yaml'):
    """Validate trained model"""

    print("=" * 70)
    print("SPRINT 2 MODEL VALIDATION")
    print("=" * 70)
    print()

    # Load model
    print(f"📦 Loading model: {model_path}")
    model = YOLO(model_path)

    # Load config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    print(f"✅ Model loaded")
    print(f"   Classes: {config['nc']}")
    print()

    # Validate
    print("🔍 Running validation on test set...")
    print()

    results = model.val(
        data=config_path,
        batch=16,
        imgsz=640,
        plots=True,
        save_json=True,
        verbose=True
    )

    print()
    print("=" * 70)
    print("VALIDATION RESULTS")
    print("=" * 70)
    print()

    # Overall metrics
    print("Overall Performance:")
    print(f"  mAP@0.5:      {results.box.map50:.3f} ({results.box.map50*100:.1f}%)")
    print(f"  mAP@0.5-0.95: {results.box.map:.3f} ({results.box.map*100:.1f}%)")
    print(f"  Precision:    {results.box.mp:.3f} ({results.box.mp*100:.1f}%)")
    print(f"  Recall:       {results.box.mr:.3f} ({results.box.mr*100:.1f}%)")
    print()

    # Per-class performance
    print("Per-Class Performance:")
    print("-" * 70)
    print(f"{'Class':<20} {'mAP@0.5':<12} {'Precision':<12} {'Recall':<12}")
    print("-" * 70)

    for i, class_name in enumerate(config['names']):
        if i < len(results.box.maps):
            map50 = results.box.maps[i]
            # Note: per-class precision/recall not directly available in results
            marker = "🆕" if i >= 7 else "📦"
            print(f"{marker} {class_name:<18} {map50:.3f} ({map50*100:.0f}%)")

    print("-" * 70)
    print()

    # Performance assessment
    target_map = 0.80  # 80% target for Sprint 2
    if results.box.map50 >= target_map:
        print(f"✅ Target achieved! mAP@0.5 = {results.box.map50:.1%} (target: {target_map:.0%})")
    else:
        print(f"⚠️  Below target: mAP@0.5 = {results.box.map50:.1%} (target: {target_map:.0%})")
        print("   Consider:")
        print("   - Training for more epochs")
        print("   - Collecting more training data")
        print("   - Adjusting augmentation parameters")

    print()

    # Speed test
    print("Inference Speed Test:")
    import time
    import numpy as np

    # Create dummy image
    dummy_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)

    # Warm-up
    model.predict(dummy_image, verbose=False)

    # Timing
    times = []
    for _ in range(10):
        start = time.time()
        model.predict(dummy_image, verbose=False)
        times.append(time.time() - start)

    avg_time = np.mean(times) * 1000  # Convert to ms
    print(f"  Average inference: {avg_time:.1f} ms")
    print(f"  FPS: {1000/avg_time:.1f}")

    if avg_time < 30:
        print("  ✅ Real-time capable (<30ms)")
    elif avg_time < 100:
        print("  ⚠️  Acceptable for navigation (<100ms)")
    else:
        print("  ❌ Too slow for real-time navigation")

    print()

    return results

def compare_models(sprint1_model, sprint2_model, config_path='config/data_config.yaml'):
    """Compare Sprint 1 vs Sprint 2 models"""

    print("=" * 70)
    print("MODEL COMPARISON: Sprint 1 vs Sprint 2")
    print("=" * 70)
    print()

    results = {}

    # Validate Sprint 1 model (if exists)
    if Path(sprint1_model).exists():
        print("📦 Testing Sprint 1 model (6 classes)...")
        model1 = YOLO(sprint1_model)
        results['sprint1'] = model1.val(data=config_path, verbose=False)
        print(f"   mAP@0.5: {results['sprint1'].box.map50:.3f}")
        print()

    # Validate Sprint 2 model
    if Path(sprint2_model).exists():
        print("🆕 Testing Sprint 2 model (15 classes)...")
        model2 = YOLO(sprint2_model)
        results['sprint2'] = model2.val(data=config_path, verbose=False)
        print(f"   mAP@0.5: {results['sprint2'].box.map50:.3f}")
        print()

    # Comparison
    if len(results) == 2:
        print("Comparison:")
        print(f"  Sprint 1 (6 classes):  mAP@0.5 = {results['sprint1'].box.map50:.3f}")
        print(f"  Sprint 2 (15 classes): mAP@0.5 = {results['sprint2'].box.map50:.3f}")

        diff = results['sprint2'].box.map50 - results['sprint1'].box.map50
        if diff >= 0:
            print(f"  ✅ Improved by {diff:.3f} ({diff*100:.1f}%)")
        else:
            print(f"  ⚠️  Decreased by {abs(diff):.3f} ({abs(diff)*100:.1f}%)")
            print("     Note: Some decrease expected with more classes")

        print()

def main():
    """Main validation function"""
    import argparse

    parser = argparse.ArgumentParser(description='Validate Sprint 2 model')
    parser.add_argument('--model', type=str,
                       default='experiments/object_detection/yolo_v8s_15class_sprint2/weights/best.pt',
                       help='Path to model weights')
    parser.add_argument('--compare', action='store_true',
                       help='Compare with Sprint 1 model')

    args = parser.parse_args()

    # Validate model
    results = validate_model(args.model)

    # Comparison
    if args.compare:
        print()
        compare_models(
            'models/object_detection/best.pt',
            args.model
        )

    print()
    print("Validation complete!")
    print()

if __name__ == "__main__":
    main()
