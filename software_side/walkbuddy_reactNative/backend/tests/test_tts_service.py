"""Tests for tts_service.py — anti-spam logic and the speak() dispatch path.

Neither the real offline engine (pyttsx3, touches system TTS) nor the real
cloud fallback (gTTS, needs network) are used here — both are replaced with
fakes, matching the dependency-injection pattern already used for OCR in
test_ocr_adapter.py, so these tests are fast and fully offline/deterministic.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from tts_service import tts_service as tts_service_module
from tts_service.tts_service import RiskLevel, TTSService


class FakeEngine:
    """Stands in for pyttsx3's engine object."""

    def __init__(self, raise_on_say=False):
        self.raise_on_say = raise_on_say
        self.spoken = []

    def say(self, message):
        if self.raise_on_say:
            raise RuntimeError("synthetic offline TTS failure")
        self.spoken.append(message)

    def runAndWait(self):
        pass


class FakeGTTS:
    """Stands in for gtts.gTTS — writes fake bytes instead of calling Google's API."""

    def __init__(self, text, lang, slow):
        self.text = text

    def write_to_fp(self, fp):
        fp.write(b"fake mp3 bytes")


def make_service(**kwargs):
    # use_offline=False at construction time skips the real pyttsx3.init()
    # call entirely; tests that need a working "offline" path inject a
    # FakeEngine afterward instead.
    kwargs.setdefault("use_offline", False)
    kwargs.setdefault("use_cloud_fallback", False)
    return TTSService(**kwargs)


class TestGenerateMessageId:
    def test_same_message_same_case_same_id(self):
        service = make_service()
        assert service._generate_message_id("Chair ahead") == service._generate_message_id("Chair ahead")

    def test_case_and_whitespace_are_normalized(self):
        service = make_service()
        assert service._generate_message_id("  Chair Ahead  ") == service._generate_message_id("chair ahead")

    def test_different_messages_get_different_ids(self):
        service = make_service()
        assert service._generate_message_id("Chair ahead") != service._generate_message_id("Table ahead")


class TestShouldSpeak:
    def test_force_always_speaks_regardless_of_state(self):
        service = make_service(cooldown_seconds=100)
        service.last_message = "Chair ahead"
        service.last_risk_level = RiskLevel.CRITICAL
        service.last_spoken_time = tts_service_module.time.time()
        assert service._should_speak("Chair ahead", RiskLevel.LOW, force=True) is True

    def test_different_message_after_cooldown_expires_speaks(self):
        service = make_service(cooldown_seconds=0)
        service.last_message = "Chair ahead"
        service.last_risk_level = RiskLevel.LOW
        service.last_spoken_time = 0.0  # long ago -> cooldown definitely expired
        assert service._should_speak("Table ahead", RiskLevel.LOW) is True

    def test_new_message_within_cooldown_and_non_increasing_risk_is_suppressed(self):
        # Real behavior: the cooldown check runs before the "did the message
        # change" check, so even a genuinely different message is suppressed
        # if we're still within cooldown and risk hasn't increased.
        service = make_service(cooldown_seconds=100)
        service.last_message = "Chair ahead"
        service.last_risk_level = RiskLevel.MEDIUM
        service.last_spoken_time = tts_service_module.time.time()
        assert service._should_speak("Table ahead", RiskLevel.MEDIUM) is False

    def test_risk_escalation_within_cooldown_overrides_suppression(self):
        service = make_service(cooldown_seconds=100)
        service.last_message = "Chair ahead"
        service.last_risk_level = RiskLevel.LOW
        service.last_spoken_time = tts_service_module.time.time()
        assert service._should_speak("Stairs ahead", RiskLevel.CRITICAL) is True

    def test_same_message_same_risk_within_cooldown_is_suppressed(self):
        service = make_service(cooldown_seconds=100)
        service.last_message = "Chair ahead"
        service.last_risk_level = RiskLevel.MEDIUM
        service.last_spoken_time = tts_service_module.time.time()
        assert service._should_speak("Chair ahead", RiskLevel.MEDIUM) is False


class TestSpeak:
    def test_empty_message_returns_false(self):
        service = make_service()
        assert service.speak("") is False

    def test_whitespace_only_message_returns_false(self):
        service = make_service()
        assert service.speak("   ") is False

    def test_no_engine_and_no_cloud_fallback_returns_false(self):
        service = make_service()  # offline disabled, cloud disabled
        assert service.speak("Chair ahead") is False

    def test_offline_success_speaks_and_updates_state(self):
        service = make_service()
        service.use_offline = True
        service.offline_engine = FakeEngine()

        result = service.speak("Chair ahead", RiskLevel.MEDIUM)

        assert result is True
        assert service.last_message == "Chair ahead"
        assert service.last_risk_level == RiskLevel.MEDIUM
        assert len(service.message_history) == 1

    def test_offline_failure_without_cloud_fallback_returns_false(self):
        service = make_service()
        service.use_offline = True
        service.offline_engine = FakeEngine(raise_on_say=True)

        assert service.speak("Chair ahead") is False
        assert service.last_message is None  # state must not update on failure

    def test_message_history_is_capped_at_max_history(self):
        service = make_service(cooldown_seconds=0)
        service.use_offline = True
        service.offline_engine = FakeEngine()
        for i in range(service.max_history + 5):
            service.speak(f"message {i}", force=True)
        assert len(service.message_history) == service.max_history


class TestCloudFallbackBug:
    """Documents a known bug (not fixed here, tracked separately): the cloud
    fallback path generates an audio file, deletes it, and reports success —
    without ever actually playing it. A user hears nothing, but speak()
    returns True as if guidance was delivered."""

    @pytest.fixture(autouse=True)
    def fake_gtts(self, monkeypatch):
        monkeypatch.setattr(tts_service_module, "GTTS_AVAILABLE", True)
        monkeypatch.setattr(tts_service_module, "gTTS", FakeGTTS)

    def test_cloud_fallback_deletes_the_audio_file_before_it_could_be_played(self, monkeypatch):
        created_paths = []
        real_named_temp_file = tts_service_module.tempfile.NamedTemporaryFile

        def recording_named_temp_file(*args, **kwargs):
            f = real_named_temp_file(*args, **kwargs)
            created_paths.append(f.name)
            return f

        monkeypatch.setattr(tts_service_module.tempfile, "NamedTemporaryFile", recording_named_temp_file)

        service = make_service(use_cloud_fallback=True)
        service.use_offline = True
        service.offline_engine = FakeEngine(raise_on_say=True)  # force fallback to cloud

        result = service.speak("Chair ahead")

        assert len(created_paths) == 1
        # The bug: by the time speak() returns, the audio file it would have
        # played is already gone, and nothing ever played it.
        assert not os.path.exists(created_paths[0])
        # Yet the service reports success, as if guidance was actually heard.
        assert result is True


class TestGetStatusResetShutdown:
    def test_get_status_reflects_current_state(self):
        service = make_service()
        service.use_offline = True
        service.offline_engine = FakeEngine()
        service.speak("Chair ahead", RiskLevel.MEDIUM)

        status = service.get_status()

        assert status["last_message"] == "Chair ahead"
        assert status["last_risk_level"] == "MEDIUM"
        assert status["message_history_count"] == 1
        assert status["offline_available"] is True

    def test_reset_clears_state(self):
        service = make_service()
        service.use_offline = True
        service.offline_engine = FakeEngine()
        service.speak("Chair ahead", RiskLevel.MEDIUM)

        service.reset()

        assert service.last_message is None
        assert service.last_risk_level == RiskLevel.CLEAR
        assert service.message_history == []

    def test_shutdown_clears_offline_engine(self):
        service = make_service()
        service.offline_engine = FakeEngine()

        service.shutdown()

        assert service.offline_engine is None
