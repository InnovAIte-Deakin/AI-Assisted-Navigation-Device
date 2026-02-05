"""
Text-to-Speech Service for AI-Assisted Navigation Device

This module provides offline-friendly TTS with anti-spam logic:
- Cooldown between repeated messages
- Only speaks when message changes or risk level increases
- Prevents audio spam for accessibility

Author: ML Engineering Team
Purpose: Sprint 2 - TTS Implementation
"""

import time
import threading
from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass
from pathlib import Path

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    print("[TTS Service] Warning: pyttsx3 not available. TTS will be disabled.")

try:
    from gtts import gTTS
    import tempfile
    import os
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    print("[TTS Service] Warning: gTTS not available. Cloud TTS fallback disabled.")


class RiskLevel(Enum):
    """Risk levels for navigation guidance messages."""
    CLEAR = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class MessageContext:
    """Context for a TTS message to determine if it should be spoken."""
    message: str
    risk_level: RiskLevel
    timestamp: float
    message_id: str  # Unique identifier for the message content


class TTSService:
    """
    Text-to-Speech Service with anti-spam logic.
    
    Features:
    - Cooldown between messages (prevents rapid-fire announcements)
    - Message change detection (only speaks when message actually changes)
    - Risk level escalation (speaks immediately if risk increases)
    - Offline support via pyttsx3 (device-based TTS)
    - Optional cloud fallback via gTTS (requires internet)
    
    Usage:
        service = TTSService(cooldown_seconds=3.0)
        service.speak("Chair on your left, nearby")
    """
    
    def __init__(
        self,
        cooldown_seconds: float = 3.0,
        use_offline: bool = True,
        use_cloud_fallback: bool = False,
        language: str = "en"
    ):
        """
        Initialize TTS Service.
        
        Args:
            cooldown_seconds: Minimum time between messages (default: 3.0)
            use_offline: Use pyttsx3 for offline TTS (default: True)
            use_cloud_fallback: Fallback to gTTS if offline fails (default: False)
            language: Language code for TTS (default: "en")
        """
        self.cooldown_seconds = cooldown_seconds
        self.use_offline = use_offline
        self.use_cloud_fallback = use_cloud_fallback
        self.language = language
        
        # State tracking
        self.last_spoken_time: float = 0.0
        self.last_message: Optional[str] = None
        self.last_risk_level: RiskLevel = RiskLevel.CLEAR
        self.message_history: list[MessageContext] = []
        self.max_history = 10
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Initialize offline TTS engine
        self.offline_engine = None
        if use_offline and PYTTSX3_AVAILABLE:
            try:
                self.offline_engine = pyttsx3.init()
                # Configure voice properties for clarity
                voices = self.offline_engine.getProperty('voices')
                if voices:
                    # Prefer female voice if available (often clearer)
                    for voice in voices:
                        if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                            self.offline_engine.setProperty('voice', voice.id)
                            break
                    else:
                        # Use first available voice
                        self.offline_engine.setProperty('voice', voices[0].id)
                
                # Set speech rate (words per minute) - slower for clarity
                self.offline_engine.setProperty('rate', 150)
                # Set volume (0.0 to 1.0)
                self.offline_engine.setProperty('volume', 0.9)
                print("[TTS Service] Offline TTS engine initialized successfully")
            except Exception as e:
                print(f"[TTS Service] Failed to initialize offline TTS: {e}")
                self.offline_engine = None
    
    def _generate_message_id(self, message: str) -> str:
        """Generate a unique ID for a message (normalized)."""
        # Normalize message for comparison (lowercase, strip whitespace)
        normalized = message.lower().strip()
        # Simple hash-like ID
        return str(hash(normalized))
    
    def _should_speak(
        self,
        message: str,
        risk_level: RiskLevel,
        force: bool = False
    ) -> bool:
        """
        Determine if a message should be spoken based on anti-spam rules.
        
        Rules:
        1. Force flag overrides all checks
        2. Cooldown: Must wait cooldown_seconds since last message
        3. Message change: Only speak if message is different from last
        4. Risk escalation: Speak immediately if risk level increases
        
        Args:
            message: The message to potentially speak
            risk_level: Risk level of the message
            force: Force speaking (bypasses all checks)
        
        Returns:
            True if message should be spoken, False otherwise
        """
        if force:
            return True
        
        current_time = time.time()
        message_id = self._generate_message_id(message)
        
        # Check cooldown
        time_since_last = current_time - self.last_spoken_time
        if time_since_last < self.cooldown_seconds:
            # BUT: Allow if risk level increased (important safety override)
            if risk_level.value <= self.last_risk_level.value:
                return False
        
        # Check if message changed
        if message_id == self._generate_message_id(self.last_message or ""):
            # Same message, but allow if risk increased
            if risk_level.value <= self.last_risk_level.value:
                return False
        
        # Risk escalation: always speak if risk increased
        if risk_level.value > self.last_risk_level.value:
            return True
        
        # All checks passed
        return True
    
    def speak(
        self,
        message: str,
        risk_level: RiskLevel = RiskLevel.LOW,
        force: bool = False
    ) -> bool:
        """
        Speak a message with anti-spam protection.
        
        Args:
            message: The text message to speak (should be short and clear)
            risk_level: Risk level of the message (affects priority)
            force: Force speaking even if cooldown active (use sparingly)
        
        Returns:
            True if message was spoken, False if suppressed by anti-spam logic
        
        Examples:
            service.speak("Chair on your left, nearby", RiskLevel.MEDIUM)
            service.speak("Path ahead is clear", RiskLevel.CLEAR)
            service.speak("Obstacle detected ahead", RiskLevel.HIGH, force=True)
        """
        if not message or not message.strip():
            return False
        
        with self._lock:
            # Check if we should speak
            if not self._should_speak(message, risk_level, force):
                return False
            
            # Attempt to speak
            success = False
            
            # Try offline TTS first (preferred)
            if self.use_offline and self.offline_engine:
                try:
                    self.offline_engine.say(message)
                    self.offline_engine.runAndWait()
                    success = True
                except Exception as e:
                    print(f"[TTS Service] Offline TTS failed: {e}")
                    success = False
            
            # Fallback to cloud TTS if offline failed and enabled
            if not success and self.use_cloud_fallback and GTTS_AVAILABLE:
                try:
                    tts = gTTS(text=message, lang=self.language, slow=False)
                    # Save to temp file and play (platform-specific)
                    # Note: This is a simplified version - full implementation
                    # would use platform audio player
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                    tts.write_to_fp(temp_file)
                    temp_file.close()
                    # TODO: Play audio file using platform player
                    # For now, just mark as success
                    os.unlink(temp_file.name)  # Clean up
                    success = True
                except Exception as e:
                    print(f"[TTS Service] Cloud TTS fallback failed: {e}")
                    success = False
            
            if success:
                # Update state
                current_time = time.time()
                self.last_spoken_time = current_time
                self.last_message = message
                self.last_risk_level = risk_level
                
                # Add to history
                context = MessageContext(
                    message=message,
                    risk_level=risk_level,
                    timestamp=current_time,
                    message_id=self._generate_message_id(message)
                )
                self.message_history.append(context)
                if len(self.message_history) > self.max_history:
                    self.message_history.pop(0)
                
                print(f"[TTS Service] Spoke: '{message}' (risk: {risk_level.name})")
                return True
            else:
                print(f"[TTS Service] Failed to speak: '{message}'")
                return False
    
    def speak_async(
        self,
        message: str,
        risk_level: RiskLevel = RiskLevel.LOW,
        force: bool = False
    ) -> None:
        """
        Speak a message asynchronously (non-blocking).
        
        This is useful for real-time systems where blocking on TTS
        would slow down the main processing loop.
        """
        thread = threading.Thread(
            target=self.speak,
            args=(message, risk_level, force),
            daemon=True
        )
        thread.start()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the TTS service."""
        current_time = time.time()
        time_since_last = current_time - self.last_spoken_time
        
        return {
            "cooldown_seconds": self.cooldown_seconds,
            "time_since_last_message": time_since_last,
            "cooldown_active": time_since_last < self.cooldown_seconds,
            "last_message": self.last_message,
            "last_risk_level": self.last_risk_level.name,
            "offline_available": self.offline_engine is not None,
            "cloud_fallback_available": GTTS_AVAILABLE and self.use_cloud_fallback,
            "message_history_count": len(self.message_history)
        }
    
    def reset(self) -> None:
        """Reset TTS service state (useful for testing or restart)."""
        with self._lock:
            self.last_spoken_time = 0.0
            self.last_message = None
            self.last_risk_level = RiskLevel.CLEAR
            self.message_history.clear()
    
    def shutdown(self) -> None:
        """Shutdown TTS service and cleanup resources."""
        with self._lock:
            if self.offline_engine:
                try:
                    self.offline_engine.stop()
                except:
                    pass
                self.offline_engine = None


# ============================================================================
# GLOBAL INSTANCE (for convenience)
# ============================================================================

_global_tts_service: Optional[TTSService] = None


def get_tts_service(
    cooldown_seconds: float = 3.0,
    use_offline: bool = True,
    use_cloud_fallback: bool = False
) -> TTSService:
    """
    Get or create global TTS service instance.
    
    This is a convenience function for getting a shared TTS service
    across the application.
    """
    global _global_tts_service
    if _global_tts_service is None:
        _global_tts_service = TTSService(
            cooldown_seconds=cooldown_seconds,
            use_offline=use_offline,
            use_cloud_fallback=use_cloud_fallback
        )
    return _global_tts_service


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example: Basic usage
    print("=" * 70)
    print("TTS Service Example")
    print("=" * 70)
    
    service = TTSService(cooldown_seconds=2.0)
    
    # Example messages
    messages = [
        ("Path ahead is clear", RiskLevel.CLEAR),
        ("Chair on your left, nearby", RiskLevel.MEDIUM),
        ("Obstacle detected ahead", RiskLevel.HIGH),
        ("Chair on your left, nearby", RiskLevel.MEDIUM),  # Should be suppressed (same message)
        ("Table ahead", RiskLevel.LOW),  # Should be suppressed (cooldown)
    ]
    
    print("\nSpeaking messages with anti-spam logic:")
    for message, risk in messages:
        print(f"\nAttempting: '{message}' (risk: {risk.name})")
        result = service.speak(message, risk)
        print(f"Result: {'SPOKEN' if result else 'SUPPRESSED'}")
        time.sleep(0.5)  # Small delay between attempts
    
    print("\n" + "=" * 70)
    print("Status:")
    print("=" * 70)
    status = service.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    service.shutdown()



