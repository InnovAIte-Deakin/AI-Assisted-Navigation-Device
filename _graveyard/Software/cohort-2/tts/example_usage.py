"""
Example Usage of TTS Service

This script demonstrates how to use the TTS service with detection/OCR adapters
to provide spoken guidance for navigation.

Author: ML Engineering Team
Purpose: Sprint 2 - TTS Examples
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ML_models.tts_service import (
    TTSService,
    RiskLevel,
    get_tts_service,
    process_adapter_output,
    generate_clear_path_message
)
from ML_models.adapters.yolo_adapter import vision_adapter
from ML_models.adapters.ocr_adapter import ocr_adapter


def example_basic_tts():
    """Example 1: Basic TTS usage"""
    print("=" * 70)
    print("Example 1: Basic TTS Usage")
    print("=" * 70)
    
    # Create TTS service
    service = TTSService(cooldown_seconds=2.0)
    
    # Speak some messages
    messages = [
        ("Path ahead is clear", RiskLevel.CLEAR),
        ("Chair on your left, nearby", RiskLevel.MEDIUM),
        ("Table ahead", RiskLevel.LOW),
        ("Obstacle detected ahead", RiskLevel.HIGH),
    ]
    
    print("\nSpeaking messages:")
    for message, risk in messages:
        print(f"  Speaking: '{message}' (risk: {risk.name})")
        service.speak(message, risk)
        import time
        time.sleep(0.5)  # Small delay
    
    service.shutdown()
    print("\n✓ Example 1 complete\n")


def example_anti_spam():
    """Example 2: Anti-spam logic demonstration"""
    print("=" * 70)
    print("Example 2: Anti-Spam Logic")
    print("=" * 70)
    
    service = TTSService(cooldown_seconds=3.0)
    
    print("\nDemonstrating anti-spam logic:")
    print("  - Cooldown: 3 seconds")
    print("  - Same message within cooldown: suppressed")
    print("  - Different message: spoken")
    print("  - Risk escalation: always spoken\n")
    
    # First message
    print("1. First message:")
    result1 = service.speak("Chair on your left", RiskLevel.MEDIUM)
    print(f"   Result: {'SPOKEN' if result1 else 'SUPPRESSED'}")
    
    # Same message immediately (should be suppressed)
    print("\n2. Same message immediately (within cooldown):")
    result2 = service.speak("Chair on your left", RiskLevel.MEDIUM)
    print(f"   Result: {'SPOKEN' if result2 else 'SUPPRESSED'}")
    
    # Different message (should be spoken)
    print("\n3. Different message:")
    result3 = service.speak("Table ahead", RiskLevel.LOW)
    print(f"   Result: {'SPOKEN' if result3 else 'SUPPRESSED'}")
    
    # Risk escalation (should be spoken even if same message)
    print("\n4. Risk escalation (same message, higher risk):")
    result4 = service.speak("Table ahead", RiskLevel.HIGH)
    print(f"   Result: {'SPOKEN' if result4 else 'SUPPRESSED'}")
    
    # Status
    print("\n5. Service status:")
    status = service.get_status()
    print(f"   Cooldown active: {status['cooldown_active']}")
    print(f"   Last message: {status['last_message']}")
    print(f"   Last risk level: {status['last_risk_level']}")
    
    service.shutdown()
    print("\n✓ Example 2 complete\n")


def example_vision_integration():
    """Example 3: Integration with vision adapter"""
    print("=" * 70)
    print("Example 3: Vision Adapter Integration")
    print("=" * 70)
    
    # Check if sample image exists
    sample_images_dir = PROJECT_ROOT / "ML_models" / "adapters" / "sample_images"
    image_files = list(sample_images_dir.glob("*.jpg")) + list(sample_images_dir.glob("*.png"))
    
    if not image_files:
        print("\n⚠ No sample images found. Skipping vision integration example.")
        print(f"   Add images to: {sample_images_dir}")
        return
    
    # Use first available image
    test_image = image_files[0]
    print(f"\nProcessing image: {test_image.name}")
    
    try:
        # Run vision adapter
        print("Running vision detection...")
        vision_result = vision_adapter(str(test_image))
        
        print(f"Found {len(vision_result.get('detections', []))} detections")
        
        # Process to guidance messages
        print("Generating guidance messages...")
        guidance_messages = process_adapter_output(
            vision_result,
            max_messages=3  # Get top 3 messages
        )
        
        if not guidance_messages:
            print("No guidance messages generated. Using clear path message.")
            guidance_messages = [generate_clear_path_message()]
        
        # Display messages
        print(f"\nGenerated {len(guidance_messages)} guidance message(s):")
        for i, msg in enumerate(guidance_messages, 1):
            print(f"  {i}. '{msg.message}' (risk: {msg.risk_level.name}, priority: {msg.priority})")
        
        # Speak top message
        if guidance_messages:
            print(f"\nSpeaking top message: '{guidance_messages[0].message}'")
            service = get_tts_service()
            service.speak(
                guidance_messages[0].message,
                guidance_messages[0].risk_level
            )
        
        print("\n✓ Example 3 complete\n")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


def example_ocr_integration():
    """Example 4: Integration with OCR adapter"""
    print("=" * 70)
    print("Example 4: OCR Adapter Integration")
    print("=" * 70)
    
    # Check if sample image exists
    sample_images_dir = PROJECT_ROOT / "ML_models" / "adapters" / "sample_images"
    image_files = list(sample_images_dir.glob("*.jpg")) + list(sample_images_dir.glob("*.png"))
    
    if not image_files:
        print("\n⚠ No sample images found. Skipping OCR integration example.")
        print(f"   Add images to: {sample_images_dir}")
        return
    
    # Use first available image
    test_image = image_files[0]
    print(f"\nProcessing image: {test_image.name}")
    
    try:
        # Run OCR adapter
        print("Running OCR...")
        ocr_result = ocr_adapter(str(test_image))
        
        print(f"Found {len(ocr_result.get('detections', []))} text detections")
        
        # Process to guidance messages
        print("Generating guidance messages...")
        guidance_messages = process_adapter_output(
            ocr_result,
            max_messages=3  # Get top 3 messages
        )
        
        if not guidance_messages:
            print("No guidance messages generated.")
            return
        
        # Display messages
        print(f"\nGenerated {len(guidance_messages)} guidance message(s):")
        for i, msg in enumerate(guidance_messages, 1):
            print(f"  {i}. '{msg.message}' (risk: {msg.risk_level.name}, priority: {msg.priority})")
        
        # Speak top message
        if guidance_messages:
            print(f"\nSpeaking top message: '{guidance_messages[0].message}'")
            service = get_tts_service()
            service.speak(
                guidance_messages[0].message,
                guidance_messages[0].risk_level
            )
        
        print("\n✓ Example 4 complete\n")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


def example_async_usage():
    """Example 5: Asynchronous TTS usage"""
    print("=" * 70)
    print("Example 5: Asynchronous TTS Usage")
    print("=" * 70)
    
    service = get_tts_service()
    
    print("\nUsing async speak (non-blocking):")
    print("  This is useful for real-time systems where blocking")
    print("  on TTS would slow down the main processing loop.\n")
    
    # Speak multiple messages asynchronously
    messages = [
        ("Processing image", RiskLevel.CLEAR),
        ("Detecting objects", RiskLevel.CLEAR),
        ("Chair detected", RiskLevel.MEDIUM),
    ]
    
    for message, risk in messages:
        print(f"  Queuing: '{message}'")
        service.speak_async(message, risk)
        import time
        time.sleep(0.3)  # Small delay
    
    print("\n  All messages queued (non-blocking)")
    print("  Main processing can continue...")
    
    # Wait a bit for messages to complete
    import time
    time.sleep(2.0)
    
    print("\n✓ Example 5 complete\n")


def main():
    """Run all examples"""
    print("\n" + "=" * 70)
    print("TTS Service Examples")
    print("=" * 70)
    print("\nThis script demonstrates various TTS service features.")
    print("Note: Some examples require sample images.\n")
    
    # Run examples
    example_basic_tts()
    example_anti_spam()
    example_vision_integration()
    example_ocr_integration()
    example_async_usage()
    
    print("=" * 70)
    print("All examples complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()



