# backend/Dockerfile
FROM python:3.11-slim

# System deps: CV/ML + TTS (eSpeak-ng + ALSA)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    curl \
    git \
    espeak-ng \
    libespeak-ng1 \
    libasound2 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# App code + models
COPY backend /app
COPY ML_models /app/ML_models

# Helpful defaults for pyttsx3/espeak in containers
ENV PYTTSX3_DRIVER=espeak
ENV TTS_RATE=170

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD curl -f http://localhost:8000/docs || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
