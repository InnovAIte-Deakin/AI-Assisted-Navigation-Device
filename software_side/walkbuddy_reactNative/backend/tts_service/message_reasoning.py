"""
Message Reasoning Module - Converts Detection/OCR Results to Guidance Messages

This module converts standardized detection and OCR outputs into simple,
clear guidance messages suitable for Text-to-Speech.

Rules:
- No LLM usage (rule-based only)
- Short, clear messages
- Spatial information (left/right/ahead)
- Risk assessment based on proximity and object type

Author: ML Engineering Team
Purpose: Sprint 2 - TTS Integration
"""

from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

# Import RiskLevel from tts_service (relative import)
try:
    from .tts_service import RiskLevel
except ImportError:
    # Fallback for direct execution
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from tts_service import RiskLevel


@dataclass
class Detection:
    """Standardized detection from adapter."""
    category: str
    confidence: float
    bbox: Dict[str, int]  # {x_min, y_min, x_max, y_max}


@dataclass
class GuidanceMessage:
    """A guidance message ready for TTS."""
    message: str
    risk_level: RiskLevel
    priority: int  # Higher = more important (for sorting)


class ObjectType(Enum):
    """Categories of objects for risk assessment."""
    OBSTACLE = "obstacle"  # Chairs, tables, etc.
    SIGN = "sign"  # Text signs, labels
    SAFE = "safe"  # Non-hazardous objects
    NAVIGATION = "navigation"  # Navigation aids


# Object type mapping (from detection categories)
OBJECT_TYPE_MAP = {
    # Obstacles (high priority)
    "chair": ObjectType.OBSTACLE,
    "office-chair": ObjectType.OBSTACLE,
    "table": ObjectType.OBSTACLE,
    "desk": ObjectType.OBSTACLE,
    "monitor": ObjectType.OBSTACLE,
    "tv": ObjectType.OBSTACLE,
    "books": ObjectType.OBSTACLE,
    "bookshelf": ObjectType.OBSTACLE,
    "whiteboard": ObjectType.OBSTACLE,
    
    # Signs (medium priority)
    "exit": ObjectType.SIGN,
    "entrance": ObjectType.SIGN,
    "restroom": ObjectType.SIGN,
    "toilet": ObjectType.SIGN,
    "history": ObjectType.SIGN,
    "science": ObjectType.SIGN,
    "arts": ObjectType.SIGN,
    
    # Safe objects (low priority)
    "book": ObjectType.SAFE,
    "person": ObjectType.SAFE,
}


def calculate_spatial_position(bbox: Dict[str, int], image_width: int) -> str:
    """
    Calculate spatial position (left/right/ahead) from bounding box.
    
    Args:
        bbox: Bounding box {x_min, y_min, x_max, y_max}
        image_width: Width of the image
    
    Returns:
        Spatial position: "left", "right", or "ahead"
    """
    # Calculate center X of bounding box
    center_x = (bbox["x_min"] + bbox["x_max"]) / 2
    
    # Divide image into thirds
    left_threshold = image_width / 3
    right_threshold = 2 * image_width / 3
    
    if center_x < left_threshold:
        return "left"
    elif center_x > right_threshold:
        return "right"
    else:
        return "ahead"


def calculate_proximity(bbox: Dict[str, int], image_width: int, image_height: int) -> str:
    """
    Calculate proximity (nearby/far) based on bounding box size.
    
    Args:
        bbox: Bounding box {x_min, y_min, x_max, y_max}
        image_width: Width of the image
        image_height: Height of the image
    
    Returns:
        Proximity: "nearby" or "ahead"
    """
    # Calculate bounding box area
    bbox_width = bbox["x_max"] - bbox["x_min"]
    bbox_height = bbox["y_max"] - bbox["y_min"]
    bbox_area = bbox_width * bbox_height
    
    # Calculate image area
    image_area = image_width * image_height
    
    # If bbox covers more than 10% of image, it's nearby
    area_ratio = bbox_area / image_area
    if area_ratio > 0.10:
        return "nearby"
    else:
        return "ahead"


def assess_risk_level(
    object_type: ObjectType,
    confidence: float,
    proximity: str
) -> RiskLevel:
    """
    Assess risk level based on object type, confidence, and proximity.
    
    Args:
        object_type: Type of object detected
        confidence: Detection confidence (0.0 to 1.0)
        proximity: "nearby" or "ahead"
    
    Returns:
        Risk level for the detection
    """
    # Base risk on object type
    if object_type == ObjectType.OBSTACLE:
        base_risk = RiskLevel.MEDIUM
    elif object_type == ObjectType.SIGN:
        base_risk = RiskLevel.LOW
    else:
        base_risk = RiskLevel.CLEAR
    
    # Increase risk if nearby
    if proximity == "nearby":
        if base_risk == RiskLevel.MEDIUM:
            base_risk = RiskLevel.HIGH
        elif base_risk == RiskLevel.LOW:
            base_risk = RiskLevel.MEDIUM
    
    # Increase risk if low confidence (uncertainty)
    if confidence < 0.5:
        if base_risk.value < RiskLevel.HIGH.value:
            base_risk = RiskLevel(base_risk.value + 1)
    
    return base_risk


def format_object_name(category: str) -> str:
    """
    Format object category name for natural speech.
    
    Examples:
        "office-chair" -> "chair"
        "whiteboard" -> "whiteboard"
        "EXIT" -> "exit sign"
    """
    # Normalize to lowercase
    category_lower = category.lower().strip()
    
    # Handle compound names
    if "chair" in category_lower:
        return "chair"
    elif "table" in category_lower:
        return "table"
    elif "monitor" in category_lower:
        return "monitor"
    elif "book" in category_lower:
        return "books" if category_lower.endswith("s") else "book"
    elif "whiteboard" in category_lower:
        return "whiteboard"
    elif "exit" in category_lower or "entrance" in category_lower:
        return f"{category_lower} sign"
    elif category_lower.isupper() or len(category_lower) <= 5:
        # Likely a sign text
        return f"{category_lower} sign"
    
    return category_lower


def generate_guidance_message(
    detection: Detection,
    image_width: int = 640,
    image_height: int = 480
) -> Optional[GuidanceMessage]:
    """
    Generate a guidance message from a single detection.
    
    Args:
        detection: Standardized detection from adapter
        image_width: Width of the image (for spatial calculation)
        image_height: Height of the image (for proximity calculation)
    
    Returns:
        GuidanceMessage or None if detection should be ignored
    """
    # Get object type
    category_lower = detection.category.lower().strip()
    object_type = None
    
    # Check direct mapping
    if category_lower in OBJECT_TYPE_MAP:
        object_type = OBJECT_TYPE_MAP[category_lower]
    else:
        # Try partial matching
        for key, obj_type in OBJECT_TYPE_MAP.items():
            if key in category_lower or category_lower in key:
                object_type = obj_type
                break
    
    # Default to OBSTACLE if unknown (safer assumption)
    if object_type is None:
        object_type = ObjectType.OBSTACLE
    
    # Calculate spatial information
    position = calculate_spatial_position(detection.bbox, image_width)
    proximity = calculate_proximity(detection.bbox, image_width, image_height)
    
    # Assess risk
    risk_level = assess_risk_level(object_type, detection.confidence, proximity)
    
    # Format object name
    object_name = format_object_name(detection.category)
    
    # Generate message based on position and proximity
    if position == "ahead":
        if proximity == "nearby":
            message = f"{object_name} ahead, nearby"
        else:
            message = f"{object_name} ahead"
    elif position == "left":
        if proximity == "nearby":
            message = f"{object_name} on your left, nearby"
        else:
            message = f"{object_name} on your left"
    else:  # right
        if proximity == "nearby":
            message = f"{object_name} on your right, nearby"
        else:
            message = f"{object_name} on your right"
    
    # Priority: higher risk = higher priority
    priority = risk_level.value * 10 + int(detection.confidence * 10)
    
    return GuidanceMessage(
        message=message,
        risk_level=risk_level,
        priority=priority
    )


def process_detections(
    detections: List[Detection],
    image_width: int = 640,
    image_height: int = 480,
    max_messages: int = 1
) -> List[GuidanceMessage]:
    """
    Process multiple detections and generate guidance messages.
    
    This function:
    1. Converts each detection to a guidance message
    2. Filters out low-priority messages
    3. Sorts by priority (highest first)
    4. Returns top N messages
    
    Args:
        detections: List of standardized detections
        image_width: Width of the image
        image_height: Height of the image
        max_messages: Maximum number of messages to return (default: 1)
    
    Returns:
        List of GuidanceMessage objects, sorted by priority
    """
    guidance_messages = []
    
    for detection in detections:
        # Skip low confidence detections
        if detection.confidence < 0.3:
            continue
        
        message = generate_guidance_message(detection, image_width, image_height)
        if message:
            guidance_messages.append(message)
    
    # Sort by priority (highest first)
    guidance_messages.sort(key=lambda m: m.priority, reverse=True)
    
    # Return top N messages
    return guidance_messages[:max_messages]


def process_adapter_output(
    adapter_output: Dict[str, Any],
    image_width: int = 640,
    image_height: int = 480,
    max_messages: int = 1
) -> List[GuidanceMessage]:
    """
    Process adapter output (from vision_adapter or ocr_adapter) and generate guidance messages.
    
    This is the main entry point for converting adapter outputs to TTS messages.
    
    Args:
        adapter_output: Output from vision_adapter() or ocr_adapter()
        image_width: Width of the image (optional, defaults to 640)
        image_height: Height of the image (optional, defaults to 480)
        max_messages: Maximum number of messages to return (default: 1)
    
    Returns:
        List of GuidanceMessage objects ready for TTS
    
    Example:
        vision_result = vision_adapter("image.jpg")
        messages = process_adapter_output(vision_result)
        for msg in messages:
            tts_service.speak(msg.message, msg.risk_level)
    """
    # Extract detections from adapter output
    detections = []
    if "detections" in adapter_output:
        for det_dict in adapter_output["detections"]:
            detection = Detection(
                category=det_dict.get("category", ""),
                confidence=det_dict.get("confidence", 0.0),
                bbox=det_dict.get("bbox", {})
            )
            detections.append(detection)
    
    # Get image dimensions from metadata if available
    if "image_shape" in adapter_output.get("metadata", {}):
        shape = adapter_output["metadata"]["image_shape"]
        if len(shape) >= 2:
            image_height, image_width = shape[0], shape[1]
    
    return process_detections(detections, image_width, image_height, max_messages)


def generate_clear_path_message() -> GuidanceMessage:
    """Generate a message for when path is clear."""
    return GuidanceMessage(
        message="Path ahead is clear",
        risk_level=RiskLevel.CLEAR,
        priority=0
    )


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Message Reasoning Example")
    print("=" * 70)
    
    # Example detections (simulating adapter output)
    example_detections = [
        Detection(
            category="office-chair",
            confidence=0.85,
            bbox={"x_min": 50, "y_min": 100, "x_max": 200, "y_max": 300}
        ),
        Detection(
            category="table",
            confidence=0.75,
            bbox={"x_min": 400, "y_min": 150, "x_max": 600, "y_max": 250}
        ),
        Detection(
            category="EXIT",
            confidence=0.95,
            bbox={"x_min": 300, "y_min": 50, "x_max": 350, "y_max": 100}
        ),
    ]
    
    print("\nProcessing detections:")
    for det in example_detections:
        print(f"  - {det.category} (conf: {det.confidence:.2f})")
    
    print("\nGenerated guidance messages:")
    messages = process_detections(example_detections, image_width=640, image_height=480)
    for msg in messages:
        print(f"  - '{msg.message}' (risk: {msg.risk_level.name}, priority: {msg.priority})")
    
    print("\n" + "=" * 70)



