"""
Test Script for ML Adapters - Before/After Comparison

This script demonstrates the value of the adapter functions by showing:
1. Raw model output (BEFORE adapter)
2. Clean standardized output (AFTER adapter)
3. Quantitative improvements (size reduction, format consistency, etc.)

Author: ML Engineering Team
Purpose: Demonstrate adapter improvements to team
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

# Import the adapter functions
from yolo_adapter import vision_adapter
from ocr_adapter import ocr_adapter

# ============================================================================
# CONFIGURATION
# ============================================================================

THIS_DIR = Path(__file__).resolve().parent
SAMPLE_IMAGES_DIR = THIS_DIR / "sample_images"
RAW_OUTPUTS_DIR = THIS_DIR / "raw_outputs"
SAMPLE_OUTPUTS_DIR = THIS_DIR / "sample_outputs"

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def load_json(file_path: Path) -> Dict[str, Any]:
    """Load JSON file and return as dictionary."""
    with open(file_path, 'r') as f:
        return json.load(f)


def calculate_json_complexity(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate complexity metrics for JSON data.
    Returns metrics like size, nesting depth, number of keys, etc.
    """
    json_str = json.dumps(data, indent=2)
    size_bytes = len(json_str.encode('utf-8'))
    size_lines = len(json_str.split('\n'))
    
    def count_keys(obj, depth=0, max_depth=0):
        """Recursively count keys and find max depth."""
        if isinstance(obj, dict):
            key_count = len(obj)
            for value in obj.values():
                if isinstance(value, (dict, list)):
                    sub_count, sub_depth = count_keys(value, depth + 1, max_depth)
                    key_count += sub_count
                    max_depth = max(max_depth, sub_depth)
            return key_count, max(depth, max_depth)
        elif isinstance(obj, list):
            key_count = 0
            for item in obj:
                if isinstance(item, (dict, list)):
                    sub_count, sub_depth = count_keys(item, depth + 1, max_depth)
                    key_count += sub_count
                    max_depth = max(max_depth, sub_depth)
            return key_count, max(depth, max_depth)
        return 0, depth
    
    key_count, max_depth = count_keys(data)
    
    return {
        "size_bytes": size_bytes,
        "size_lines": size_lines,
        "num_keys": key_count,
        "max_depth": max_depth,
        "num_detections": len(data.get("detections", [])) if isinstance(data, dict) else 0
    }


def print_comparison_table(before_metrics: Dict, after_metrics: Dict):
    """Print a formatted comparison table."""
    print("\n" + "="*70)
    print("METRICS COMPARISON")
    print("="*70)
    print(f"{'Metric':<30} {'BEFORE':<20} {'AFTER':<20}")
    print("-"*70)
    
    # Size comparison
    size_reduction = ((before_metrics["size_bytes"] - after_metrics["size_bytes"]) / 
                     before_metrics["size_bytes"] * 100) if before_metrics["size_bytes"] > 0 else 0
    print(f"{'File Size (bytes)':<30} {before_metrics['size_bytes']:<20} {after_metrics['size_bytes']:<20}")
    print(f"{'Size Reduction':<30} {'':<20} {size_reduction:.1f}%")
    
    # Lines comparison
    lines_reduction = ((before_metrics["size_lines"] - after_metrics["size_lines"]) / 
                      before_metrics["size_lines"] * 100) if before_metrics["size_lines"] > 0 else 0
    print(f"{'Number of Lines':<30} {before_metrics['size_lines']:<20} {after_metrics['size_lines']:<20}")
    print(f"{'Lines Reduction':<30} {'':<20} {lines_reduction:.1f}%")
    
    # Keys comparison
    keys_reduction = ((before_metrics["num_keys"] - after_metrics["num_keys"]) / 
                     before_metrics["num_keys"] * 100) if before_metrics["num_keys"] > 0 else 0
    print(f"{'Number of Keys':<30} {before_metrics['num_keys']:<20} {after_metrics['num_keys']:<20}")
    print(f"{'Keys Reduction':<30} {'':<20} {keys_reduction:.1f}%")
    
    # Depth comparison
    print(f"{'Max Nesting Depth':<30} {before_metrics['max_depth']:<20} {after_metrics['max_depth']:<20}")
    
    # Detections count
    print(f"{'Number of Detections':<30} {before_metrics['num_detections']:<20} {after_metrics['num_detections']:<20}")
    
    print("="*70)


def print_json_sample(data: Dict[str, Any], title: str, max_lines: int = 30):
    """Print a sample of JSON data with truncation if too long."""
    json_str = json.dumps(data, indent=2)
    lines = json_str.split('\n')
    
    print(f"\n{title}")
    print("="*70)
    if len(lines) <= max_lines:
        print(json_str)
    else:
        print('\n'.join(lines[:max_lines]))
        print(f"\n... ({len(lines) - max_lines} more lines) ...")
    print("="*70)


# ============================================================================
# TEST FUNCTIONS
# ============================================================================

def test_yolo_adapter(image_path: str):
    """
    Test YOLO adapter and show before/after comparison.
    
    Args:
        image_path: Path to test image
    """
    print("\n" + "="*70)
    print("TESTING YOLO VISION ADAPTER")
    print("="*70)
    print(f"Image: {image_path}")
    
    # Run the adapter (this will save both raw and clean outputs)
    try:
        clean_output = vision_adapter(image_path)
    except Exception as e:
        print(f"ERROR: Failed to run YOLO adapter: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Get image ID for finding output files
    image_id = Path(image_path).stem
    
    # Load raw output
    raw_output_path = RAW_OUTPUTS_DIR / f"{image_id}_yolo_raw.json"
    if not raw_output_path.exists():
        print(f"WARNING: Raw output file not found: {raw_output_path}")
        return
    
    raw_output = load_json(raw_output_path)
    
    # Load clean output (we already have it, but load from file for consistency)
    clean_output_path = SAMPLE_OUTPUTS_DIR / f"{image_id}_yolo_clean.json"
    if not clean_output_path.exists():
        print(f"WARNING: Clean output file not found: {clean_output_path}")
        return
    
    clean_output_file = load_json(clean_output_path)
    
    # Calculate metrics
    raw_metrics = calculate_json_complexity(raw_output)
    clean_metrics = calculate_json_complexity(clean_output_file)
    
    # Print BEFORE (raw output)
    print_json_sample(raw_output, "BEFORE: Raw YOLO Model Output", max_lines=40)
    
    # Print AFTER (clean output)
    print_json_sample(clean_output_file, "AFTER: Clean Standardized Output", max_lines=40)
    
    # Print comparison metrics
    print_comparison_table(raw_metrics, clean_metrics)
    
    # Print improvement summary
    print("\n" + "="*70)
    print("IMPROVEMENT SUMMARY")
    print("="*70)
    print("✓ Standardized JSON schema (consistent format across all detections)")
    print("✓ Simplified bounding box format (x_min, y_min, x_max, y_max)")
    print("✓ Clean category names (no class IDs, just readable names)")
    print("✓ Consistent confidence format (0-1 range, 4 decimal places)")
    print("✓ Removed internal model metadata (only essential detection data)")
    print("✓ Sorted by confidence (highest first for easy reading)")
    print("="*70)


def test_ocr_adapter(image_path: str):
    """
    Test OCR adapter and show before/after comparison.
    
    Args:
        image_path: Path to test image
    """
    print("\n" + "="*70)
    print("TESTING OCR ADAPTER")
    print("="*70)
    print(f"Image: {image_path}")
    
    # Run the adapter (this will save both raw and clean outputs)
    try:
        clean_output = ocr_adapter(image_path)
    except Exception as e:
        print(f"ERROR: Failed to run OCR adapter: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Get image ID for finding output files
    image_id = Path(image_path).stem
    
    # Load raw output
    raw_output_path = RAW_OUTPUTS_DIR / f"{image_id}_ocr_raw.json"
    if not raw_output_path.exists():
        print(f"WARNING: Raw output file not found: {raw_output_path}")
        return
    
    raw_output = load_json(raw_output_path)
    
    # Load clean output
    clean_output_path = SAMPLE_OUTPUTS_DIR / f"{image_id}_ocr_clean.json"
    if not clean_output_path.exists():
        print(f"WARNING: Clean output file not found: {clean_output_path}")
        return
    
    clean_output_file = load_json(clean_output_path)
    
    # Calculate metrics
    raw_metrics = calculate_json_complexity(raw_output)
    clean_metrics = calculate_json_complexity(clean_output_file)
    
    # Print BEFORE (raw output)
    print_json_sample(raw_output, "BEFORE: Raw EasyOCR Model Output", max_lines=40)
    
    # Print AFTER (clean output)
    print_json_sample(clean_output_file, "AFTER: Clean Standardized Output", max_lines=40)
    
    # Print comparison metrics
    print_comparison_table(raw_metrics, clean_metrics)
    
    # Print improvement summary
    print("\n" + "="*70)
    print("IMPROVEMENT SUMMARY")
    print("="*70)
    print("✓ Standardized JSON schema (consistent with YOLO adapter)")
    print("✓ Converted 4-corner bbox to standard x_min/y_min/x_max/y_max format")
    print("✓ Clean text extraction (removed extra whitespace)")
    print("✓ Consistent confidence format (0-1 range, 4 decimal places)")
    print("✓ Unified format with vision adapter (same schema)")
    print("✓ Sorted by confidence (highest first for easy reading)")
    print("="*70)


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    """Main test runner - tests both adapters if images are available."""
    print("\n" + "="*70)
    print("ML ADAPTER TEST SUITE")
    print("="*70)
    print(f"Sample images directory: {SAMPLE_IMAGES_DIR}")
    print(f"Raw outputs directory: {RAW_OUTPUTS_DIR}")
    print(f"Clean outputs directory: {SAMPLE_OUTPUTS_DIR}")
    
    # Check if sample_images directory exists and has images
    if not SAMPLE_IMAGES_DIR.exists():
        print(f"\nWARNING: Sample images directory not found: {SAMPLE_IMAGES_DIR}")
        print("Creating directory. Please add test images to this folder.")
        SAMPLE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        return
    
    # Find image files
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
    image_files = []
    for ext in image_extensions:
        image_files.extend(list(SAMPLE_IMAGES_DIR.glob(f"*{ext}")))
        image_files.extend(list(SAMPLE_IMAGES_DIR.glob(f"*{ext.upper()}")))
    
    if not image_files:
        print(f"\nNo test images found in {SAMPLE_IMAGES_DIR}")
        print("Please add test images (jpg, png, etc.) to this directory.")
        print("\nExample usage:")
        print("  python test_adapters.py <path_to_image>")
        return
    
    # If image path provided as argument, use it
    if len(sys.argv) > 1:
        image_path = Path(sys.argv[1])
        if not image_path.exists():
            print(f"ERROR: Image not found: {image_path}")
            return
        
        # Test both adapters on the provided image
        print(f"\nTesting with provided image: {image_path}")
        test_yolo_adapter(str(image_path))
        test_ocr_adapter(str(image_path))
    else:
        # Test with first available image
        test_image = image_files[0]
        print(f"\nTesting with first available image: {test_image}")
        test_yolo_adapter(str(test_image))
        test_ocr_adapter(str(test_image))
        
        if len(image_files) > 1:
            print(f"\nNote: {len(image_files) - 1} more image(s) available for testing.")
            print("Run with specific image: python test_adapters.py <image_path>")


if __name__ == "__main__":
    main()

