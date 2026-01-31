// frontend_reactNative/src/api/client.ts
import { API_BASE } from "../config";

export interface DetectionEvent {
  label: string;
  direction: string;
  distance_m: number | null;
  confidence: number;
}

export interface SlowLaneResponse {
  events: DetectionEvent[];
  answer?: string;
  safe: boolean;
  source: "safety_gate" | "slow_lane_llm";
}

export async function fetchStatus() {
  try {
    const res = await fetch(`${API_BASE}/docs`); // Check /docs as a health check
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
    return { status: "ok" };
  } catch (err) {
    console.error("Error fetching status:", err);
    throw err;
  }
}

export async function detectObject(imageBlob: Blob): Promise<{ events: DetectionEvent[] }> {
  const formData = new FormData();
  // React Native's FormData handling needs explicit type for file
  formData.append("file", imageBlob as any, "frame.jpg");

  const res = await fetch(`${API_BASE}/detect`, {
    method: "POST",
    body: formData,
    headers: {
      "Accept": "application/json",
      // Content-Type is set automatically by FormData
    },
  });

  if (!res.ok) {
    throw new Error(`Detect failed: ${res.status}`);
  }
  return await res.json();
}

export async function askTwoBrain(
  imageBlob: Blob,
  question: string
): Promise<SlowLaneResponse> {
  const formData = new FormData();
  formData.append("file", imageBlob as any, "frame.jpg");
  formData.append("question", question);

  const res = await fetch(`${API_BASE}/two_brain`, {
    method: "POST",
    body: formData,
    headers: {
      "Accept": "application/json",
    },
  });

  if (!res.ok) {
    throw new Error(`TwoBrain failed: ${res.status}`);
  }
  return await res.json();
}

