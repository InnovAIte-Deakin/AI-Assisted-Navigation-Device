# backend/Dockerfile  (build context: backend/)
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    curl \
    git \
    espeak-ng \
    libespeak-ng1 \
    libasound2 \
    ffmpeg \
  && rm -rf /var/lib/apt/lists/*
# ffmpeg is required by pydub (tts_service.py's cloud-TTS fallback path):
# - it decodes gTTS's MP3 output (no pure-Python MP3 decoder exists), and
# - it provides ffplay, which pydub.playback.play() shells out to for
#   actual audio output.
# Without ffmpeg, AudioSegment.from_mp3() raises and the fallback silently
# reports failure (caught by its own except-and-fail-safe handling)
# without ever playing audio, even though the offline espeak path above
# still works. Deliberately no Python playback binding (simpleaudio,
# pyaudio) is installed: simpleaudio's native playback thread was found to
# segfault the whole process when stdout/stderr are piped rather than a
# real TTY (as they are under a test runner, and as a container's log
# driver pipes them) -- see test_tts_service_integration.py. ffplay runs
# as a fully separate OS process, so it is not vulnerable to that failure
# mode, and is the playback path this app relies on.

WORKDIR /app

COPY requirements.txt .
# Filter out macOS-only packages (pyobjc*) that can't build on Linux.
# Remove this grep when requirements.txt is regenerated on Linux/CI.
RUN pip install --no-cache-dir --upgrade pip && \
    grep -iv "pyobjc" requirements.txt > /tmp/requirements-linux.txt && \
    pip install --no-cache-dir -r /tmp/requirements-linux.txt

# llama-cpp-python is excluded from requirements.txt because it compiles
# differently per platform (Metal on macOS, CPU here). Kept as a separate
# cached layer so other dep changes don't trigger a recompile.
RUN pip install --no-cache-dir llama-cpp-python==0.3.16

COPY . .

ENV PYTTSX3_DRIVER=espeak
ENV TTS_RATE=170

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD curl -f http://localhost:8000/ml/ready || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
