"""
Slow Lane package: deterministic safety gate + memory + local LLM wrapper.
"""

from .slowlanellm import SlowLaneLLM
from .memorybuffer import NavigationMemory
from .prompts import build_prompt
from .safetygate import extract_hazards, safe_or_stop_recommendation

__all__ = [
    "SlowLaneLLM",
    "NavigationMemory",
    "build_prompt",
    "extract_hazards",
    "safe_or_stop_recommendation",
]

__version__ = "1.0.0"
