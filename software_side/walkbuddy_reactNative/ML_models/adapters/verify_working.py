#!/usr/bin/env python3
"""
Quick Verification Script for ML Adapters

This script quickly checks if the adapters are working correctly.
Run this to verify your setup is correct.

Usage: python verify_working.py
"""

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent

def check_files():
    """Check if required files exist."""
    print("="*60)
    print("FILE CHECK")
    print("="*60)
    
    required_files = [
        "yolo_adapter.py",
        "ocr_adapter.py",
        "test_adapters.py"
    ]
    
    all_exist = True
    for file in required_files:
        path = THIS_DIR / file
        if path.exists():
            print(f"✓ {file}")
        else:
            print(f"✗ {file} - MISSING")
            all_exist = False
    
    # Check directories
    dirs = ["sample_images", "raw_outputs", "sample_outputs"]
    for dir_name in dirs:
        path = THIS_DIR / dir_name
        if path.exists():
            print(f"✓ {dir_name}/")
        else:
            print(f"✗ {dir_name}/ - MISSING")
            all_exist = False
    
    return all_exist


def check_imports():
    """Check if adapters can be imported."""
    print("\n" + "="*60)
    print("IMPORT CHECK")
    print("="*60)
    
    try:
        from yolo_adapter import vision_adapter
        print("✓ yolo_adapter imported successfully")
    except Exception as e:
        print(f"✗ yolo_adapter import failed: {e}")
        return False
    
    try:
        from ocr_adapter import ocr_adapter
        print("✓ ocr_adapter imported successfully")
    except Exception as e:
        print(f"✗ ocr_adapter import failed: {e}")
        return False
    
    return True


def check_dependencies():
    """Check if required dependencies are installed."""
    print("\n" + "="*60)
    print("DEPENDENCY CHECK")
    print("="*60)
    
    dependencies = {
        "ultralytics": "YOLO model",
        "easyocr": "OCR model",
        "cv2": "OpenCV (opencv-python)",
        "numpy": "NumPy",
        "PIL": "Pillow"
    }
    
    all_installed = True
    for module, description in dependencies.items():
        try:
            if module == "cv2":
                import cv2
            elif module == "PIL":
                from PIL import Image
            else:
                __import__(module)
            print(f"✓ {module} ({description})")
        except ImportError:
            print(f"✗ {module} ({description}) - NOT INSTALLED")
            all_installed = False
    
    return all_installed


def check_model_files():
    """Check if model files exist."""
    print("\n" + "="*60)
    print("MODEL FILES CHECK")
    print("="*60)
    
    # Check YOLO weights
    yolo_weights = THIS_DIR.parent / "yolo_nav" / "weights" / "yolov8s.pt"
    if yolo_weights.exists():
        size_mb = yolo_weights.stat().st_size / (1024 * 1024)
        print(f"✓ YOLO weights found: {yolo_weights}")
        print(f"  Size: {size_mb:.1f} MB")
    else:
        print(f"✗ YOLO weights not found: {yolo_weights}")
        return False
    
    # EasyOCR doesn't need pre-downloaded weights
    print("✓ EasyOCR (will download models on first use)")
    
    return True


def run_quick_test():
    """Run a quick test with the test image."""
    print("\n" + "="*60)
    print("QUICK FUNCTIONALITY TEST")
    print("="*60)
    
    test_image = THIS_DIR / "sample_images" / "test_image.png"
    
    if not test_image.exists():
        print(f"✗ Test image not found: {test_image}")
        print("  Run the test script first to create a test image")
        return False
    
    print(f"Using test image: {test_image}")
    
    # Test YOLO adapter
    print("\n1. Testing YOLO Adapter...")
    try:
        from yolo_adapter import vision_adapter
        result = vision_adapter(str(test_image))
        print(f"   ✓ YOLO adapter executed successfully")
        print(f"   ✓ Found {len(result['detections'])} detections")
        print(f"   ✓ Output format: {list(result.keys())}")
        if len(result['detections']) > 0:
            print(f"   ✓ Sample detection: {result['detections'][0]}")
    except Exception as e:
        print(f"   ✗ YOLO adapter failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test OCR adapter
    print("\n2. Testing OCR Adapter...")
    try:
        from ocr_adapter import ocr_adapter
        result = ocr_adapter(str(test_image))
        print(f"   ✓ OCR adapter executed successfully")
        print(f"   ✓ Found {len(result['detections'])} text detections")
        print(f"   ✓ Output format: {list(result.keys())}")
        if len(result['detections']) > 0:
            det = result['detections'][0]
            print(f"   ✓ Sample detection: '{det['category']}' (conf: {det['confidence']:.4f})")
    except Exception as e:
        print(f"   ✗ OCR adapter failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def check_output_files():
    """Check if output files were created."""
    print("\n" + "="*60)
    print("OUTPUT FILES CHECK")
    print("="*60)
    
    test_image_id = "test_image"
    files_to_check = [
        (THIS_DIR / "raw_outputs" / f"{test_image_id}_yolo_raw.json", "YOLO raw output"),
        (THIS_DIR / "raw_outputs" / f"{test_image_id}_ocr_raw.json", "OCR raw output"),
        (THIS_DIR / "sample_outputs" / f"{test_image_id}_yolo_clean.json", "YOLO clean output"),
        (THIS_DIR / "sample_outputs" / f"{test_image_id}_ocr_clean.json", "OCR clean output"),
    ]
    
    all_exist = True
    for file_path, description in files_to_check:
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"✓ {description}: {file_path.name} ({size} bytes)")
        else:
            print(f"✗ {description}: {file_path.name} - NOT FOUND")
            all_exist = False
    
    return all_exist


def main():
    """Run all verification checks."""
    print("\n" + "="*60)
    print("ML ADAPTERS VERIFICATION")
    print("="*60)
    print(f"Working directory: {THIS_DIR}\n")
    
    results = {
        "Files": check_files(),
        "Imports": check_imports(),
        "Dependencies": check_dependencies(),
        "Model Files": check_model_files(),
    }
    
    # Only run functional tests if everything else passes
    if all(results.values()):
        results["Functionality"] = run_quick_test()
        results["Output Files"] = check_output_files()
    else:
        print("\n" + "="*60)
        print("SKIPPING FUNCTIONALITY TEST")
        print("="*60)
        print("Please fix the issues above before running functionality tests.")
        results["Functionality"] = False
        results["Output Files"] = False
    
    # Final summary
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)
    
    all_passed = True
    for check_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{check_name:<20} {status}")
        if not passed:
            all_passed = False
    
    print("="*60)
    
    if all_passed:
        print("\n🎉 ALL CHECKS PASSED! Your adapters are working correctly.")
        print("\nNext steps:")
        print("  1. Add your own test images to sample_images/")
        print("  2. Run: python test_adapters.py <image_path>")
        print("  3. Check the before/after comparison")
        return 0
    else:
        print("\n⚠️  SOME CHECKS FAILED. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

