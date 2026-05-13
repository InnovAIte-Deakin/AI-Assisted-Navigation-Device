// frontend_reactNative/src/api/client.ts
import { API_BASE, API_KEY } from "../config";

const NGROK_HEADERS: Record<string, string> = API_BASE.includes("ngrok")
  ? { "ngrok-skip-browser-warning": "true" }
  : {};

export interface Detection {
  category: string;
  confidence: number;
  bbox: { x_min: number; y_min: number; x_max: number; y_max: number };
}

export interface VisionResponse {
  detections: Detection[];
  guidance_message: string;
  image_id: string;
}

export interface OcrResponse {
  detections: Detection[];
  guidance_message: string;
}

export interface ChatResponse {
  response: string;
}

export async function fetchStatus() {
  try {
    const res = await fetch(`${API_BASE}/ping`, { headers: { ...NGROK_HEADERS } });
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
    return { status: "ok" };
  } catch (err) {
    console.error("Error fetching status:", err);
    throw err;
  }
}

export async function detectObject(imageBlob: Blob): Promise<VisionResponse> {
  const formData = new FormData();
  formData.append("file", imageBlob as any, "frame.jpg");

  const res = await fetch(`${API_BASE}/vision`, {
    method: "POST",
    body: formData,
    headers: {
      "Accept": "application/json",
      "X-API-Key": API_KEY,
      ...NGROK_HEADERS,
    },
  });

  if (!res.ok) {
    throw new Error(`Vision failed: ${res.status}`);
  }
  return await res.json();
}

export async function recognizeText(imageBlob: Blob): Promise<OcrResponse> {
  const formData = new FormData();
  formData.append("file", imageBlob as any, "frame.jpg");

  const res = await fetch(`${API_BASE}/ocr`, {
    method: "POST",
    body: formData,
    headers: {
      "Accept": "application/json",
      "X-API-Key": API_KEY,
      ...NGROK_HEADERS,
    },
  });

  if (!res.ok) {
    throw new Error(`OCR failed: ${res.status}`);
  }
  return await res.json();
}

export async function askTwoBrain(
  imageBlob: Blob,
  question: string
): Promise<ChatResponse> {
  const formData = new FormData();
  formData.append("file", imageBlob as any, "frame.jpg");

  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    body: formData,
    headers: {
      "Accept": "application/json",
      "X-API-Key": API_KEY,
      ...NGROK_HEADERS,
    },
  });

  if (!res.ok) {
    throw new Error(`Chat failed: ${res.status}`);
  }
  return await res.json();
}

export async function askChat(question: string): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...NGROK_HEADERS,
    },
    body: JSON.stringify({ query: question }),
  });

  if (!res.ok) {
    throw new Error(`Chat failed: ${res.status}`);
  }
  return await res.json();
}
