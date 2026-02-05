"""
ML Adapters Package for AI-Assisted Navigation Device

This package provides adapter functions to standardize ML model outputs.
"""

from .yolo_adapter import vision_adapter
from .ocr_adapter import ocr_adapter

__all__ = ['vision_adapter', 'ocr_adapter']
__version__ = '1.0.0'

