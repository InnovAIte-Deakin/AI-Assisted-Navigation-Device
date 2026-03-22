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
  && rm -rf /var/lib/apt/lists/*

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
  CMD curl -f http://localhost:8000/docs || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
