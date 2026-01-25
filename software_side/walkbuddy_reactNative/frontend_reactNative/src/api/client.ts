// frontend_reactNative/src/api/client.ts
 
import Constants from "expo-constants";

const API = (Constants.expoConfig?.extra?.apiBaseUrl as string | undefined) ?? "";
 
 
// Simple health/status check for the backend
export async function fetchStatus() {
  try {
    const res = await fetch(`${API}/status`);
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error("Error fetching status:", err);
    throw err;
  }
}
 
// Frame object passed from your camera/vision code
export type CapturedFrame = {
  frameId: string;       
  timestamp: string;     // new Date().toISOString()
  source: string;        // "rear_camera"
  imageBase64: string;   // base64-encoded image
  width: number;         // width in pixels
  height: number;        // height in pixels
};
 
export type Detection = {
  id: number;
  label: string;
  confidence: number;
  bbox_norm: {
    cx: number;
    cy: number;
    w: number;
    h: number;
  };
  side: "left" | "center" | "right";
  severity: "near" | "medium" | "far";
  distance_m: number | null;
};
 
export type VisionResult = {
  frame_id: string;
  timestamp: string;
  source: string;
  detections: Detection[];
};
 
export type OcrBlock = {
  id: number;
  text: string;
  confidence: number;
  bbox_norm: {
    cx: number;
    cy: number;
    w: number;
    h: number;
  };
};
 
export type OcrResult = {
  frame_id: string;
  timestamp: string;
  source: string;
  blocks: OcrBlock[];
};
 

// Helper for drawing bboxes 
export type BboxPixels = {
  x: number;      // left
  y: number;      // top
  width: number;
  height: number;
};
 
/**
 * Frontend responsibility: convert normalized bbox (0–1)
 * to pixel coordinates for drawing overlays.
 */
export function bboxNormToPixels(
  bbox: { cx: number; cy: number; w: number; h: number },
  frameWidth: number,
  frameHeight: number
): BboxPixels {
  const width = bbox.w * frameWidth;
  const height = bbox.h * frameHeight;
 
  const x = (bbox.cx - bbox.w / 2) * frameWidth;
  const y = (bbox.cy - bbox.h / 2) * frameHeight;
 
  return { x, y, width, height };
}
 
// InferenceClient interface
// (RN UI should only depend on this)

export interface InferenceClient {
  detectVision(frame: CapturedFrame): Promise<VisionResult>;
  readText(frame: CapturedFrame): Promise<OcrResult>;
}

// HTTP implementation
/**
 * HTTP-based implementation that talks to your FastAPI backend.
 * UI code should use it via the InferenceClient interface.
 */
export class HttpInferenceClient implements InferenceClient {
  // TODO: make sure these match your real FastAPI routes
  private readonly visionPath = "/vision/detect";
  private readonly ocrPath = "/vision/ocr";
 
  constructor(private baseUrl: string = API) {}
 
  private url(path: string) {
    if (this.baseUrl.endsWith("/") && path.startsWith("/")) {
      return this.baseUrl.slice(0, -1) + path;
    }
    return `${this.baseUrl}${path}`;
  }
 
  
  //Helper to POST JSON and parse the response.
  private async postJson<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(this.url(path), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
 
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
 
    const data = (await res.json()) as T;
    return data;
  }
 
  //Send a frame to the vision detection endpoint.
  async detectVision(frame: CapturedFrame): Promise<VisionResult> {
    const payload = {
      frame_id: frame.frameId,
      timestamp: frame.timestamp,
      source: frame.source,
      image: frame.imageBase64, // change key if your backend expects something else
    };
 
    const result = await this.postJson<VisionResult>(
      this.visionPath,
      payload
    );
    return result;
  }
 
  /**
   * Send a frame to the OCR endpoint.
   */
  async readText(frame: CapturedFrame): Promise<OcrResult> {
    const payload = {
      frame_id: frame.frameId,
      timestamp: frame.timestamp,
      source: frame.source,
      image: frame.imageBase64,
    };
 
    const result = await this.postJson<OcrResult>(this.ocrPath, payload);
    return result;
  }
}
 
export class MockInferenceClient implements InferenceClient {
  async detectVision(frame: CapturedFrame): Promise<VisionResult> {
    const now = new Date().toISOString();
    return {
      frame_id: frame.frameId,
      timestamp: now,
      source: frame.source,
      detections: [
        {
          id: 1,
          label: "mock_obstacle",
          confidence: 0.95,
          bbox_norm: { cx: 0.5, cy: 0.5, w: 0.3, h: 0.3 },
          side: "center",
          severity: "near",
          distance_m: 1.2,
        },
      ],
    };
  }
 
  async readText(frame: CapturedFrame): Promise<OcrResult> {
    const now = new Date().toISOString();
    return {
      frame_id: frame.frameId,
      timestamp: now,
      source: frame.source,
      blocks: [
        {
          id: 1,
          text: "Mock text",
          confidence: 0.9,
          bbox_norm: { cx: 0.5, cy: 0.5, w: 0.4, h: 0.2 },
        },
      ],
    };
  }
}
 
 