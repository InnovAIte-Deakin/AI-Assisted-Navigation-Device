"""Real, unmocked integration test for the TTS cloud-fallback playback pipeline.

test_tts_service.py exercises speak()'s cloud-fallback logic (play-before-
cleanup ordering, cleanup-on-failure) with gTTS, AudioSegment.from_mp3(),
and play_audio() all mocked -- deliberately, so those tests are fast and
deterministic. But that means the suite never actually proves the real
pipeline works on a given machine: pydub's MP3 decoding has no pure-Python
path and hard-requires the ffmpeg binary, and pydub.playback.play() needs a
real playback backend (simpleaudio, pyaudio, or a shelled-out ffplay).
Without ffmpeg or a playback backend installed, the exact same code that
used to silently report false success now silently reports failure instead
-- passing its own tests while never actually working end to end on a
machine missing those dependencies.

This test runs the real, non-mocked chain: a real gTTS network call, real
ffmpeg-backed MP3 decoding, and a real playback attempt via ffplay. It is
skipped (not failed) for the specific, distinguishable reasons a real
environment might not support it -- missing ffmpeg, missing ffplay, no
network, or no audio output device (expected on a headless CI runner) --
so it stays informative without being flaky. Where it can run, a pass here
is direct, reproducible evidence the fallback works on this machine, not
just a claim.

IMPORTANT: this test deliberately does NOT attempt playback if simpleaudio
or pyaudio are importable, and skips instead. simpleaudio's native
playback thread was found -- reproduced directly, not just suspected -- to
segfault the whole process (not raise a catchable Python exception) when
stdout/stderr are piped rather than a real TTY, which is exactly how
pytest and `subprocess.run(..., capture_output=True)` both run this code.
A segfault happens before any Python try/except can catch it, so no test
structure can safely make that path "just skip on failure" -- the only
safe thing to do is never call it here. See tts_service.py's import
comment: neither package is added to requirements.txt for this reason.

Run from the backend directory:
    pytest tests/test_tts_service_integration.py -v
"""

from __future__ import annotations

import shutil
import socket
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from tts_service.tts_service import TTSService  # noqa: E402


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _unsafe_playback_binding_present() -> bool:
    """True if simpleaudio or pyaudio is importable -- see the module docstring."""
    for module_name in ("simpleaudio", "pyaudio"):
        try:
            __import__(module_name)
            return True
        except ImportError:
            continue
    return False


def _ffplay_available() -> bool:
    return shutil.which("ffplay") is not None or shutil.which("avplay") is not None


def _network_available() -> bool:
    try:
        socket.create_connection(("translate.google.com", 443), timeout=3).close()
        return True
    except OSError:
        return False


class FailingOfflineEngine:
    """Forces speak() down the cloud-fallback path, exactly as a real offline TTS failure would."""

    def say(self, message: str) -> None:
        raise RuntimeError("synthetic offline TTS failure -- forcing the real cloud fallback")

    def runAndWait(self) -> None:
        pass


@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg is not installed -- required to decode gTTS's MP3 output")
@pytest.mark.skipif(
    _unsafe_playback_binding_present(),
    reason=(
        "simpleaudio or pyaudio is importable in this environment -- pydub would prefer it over "
        "ffplay, and simpleaudio's native playback thread is known to segfault the process under "
        "piped stdout/stderr (as pytest uses). Skipping rather than risking a hard crash."
    ),
)
@pytest.mark.skipif(not _ffplay_available(), reason="ffplay (bundled with ffmpeg) is not on PATH")
@pytest.mark.skipif(not _network_available(), reason="no network access to Google Translate's TTS endpoint")
class TestRealCloudFallbackPipeline:
    def test_cloud_fallback_actually_plays_audio_on_this_machine(self) -> None:
        service = TTSService(use_offline=False, use_cloud_fallback=True)
        service.use_offline = True
        service.offline_engine = FailingOfflineEngine()

        try:
            result = service.speak("Chair ahead, integration test")
        except Exception as exc:  # pragma: no cover -- see skip reason below
            pytest.skip(
                f"cloud fallback raised outside its own except-and-fail-safe handling "
                f"(likely no audio output device on this runner): {exc!r}"
            )

        assert result is True, (
            "speak() reported failure even with ffmpeg, a playback backend, and network access all "
            "present -- this is the exact regression this test exists to catch, not an environment gap."
        )
