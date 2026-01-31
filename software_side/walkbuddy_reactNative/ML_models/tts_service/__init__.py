"""
TTS Service Package

This package provides Text-to-Speech functionality for the AI-Assisted Navigation Device.

Modules:
- tts_service: Core TTS service with anti-spam logic
- message_reasoning: Converts detection/OCR outputs to guidance messages
"""

from .tts_service import TTSService, RiskLevel, get_tts_service
from .message_reasoning import (
    process_adapter_output,
    process_detections,
    generate_guidance_message,
    generate_clear_path_message,
    GuidanceMessage,
    Detection,
    ObjectType,
)

__all__ = [
    "TTSService",
    "RiskLevel",
    "get_tts_service",
    "process_adapter_output",
    "process_detections",
    "generate_guidance_message",
    "generate_clear_path_message",
    "GuidanceMessage",
    "Detection",
    "ObjectType",
]



