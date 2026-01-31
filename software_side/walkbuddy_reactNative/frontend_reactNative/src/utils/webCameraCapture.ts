// src/utils/webCameraCapture.ts
// Web-specific camera capture using getUserMedia API

export interface WebCameraCapture {
  video: HTMLVideoElement | null;
  stream: MediaStream | null;
  start: (videoElement: HTMLVideoElement) => Promise<void>;
  stop: () => void;
  captureFrame: () => Promise<string | null>; // Returns base64 JPEG
}

/**
 * Initialize web camera using getUserMedia
 * Now requires video element to be passed in (React ref pattern)
 */
export function initWebCamera(): WebCameraCapture {
  let video: HTMLVideoElement | null = null;
  let stream: MediaStream | null = null;

  const start = async (videoElement: HTMLVideoElement): Promise<void> => {
    try {
      // Guard: ensure video element exists
      if (!videoElement) {
        throw new Error("Video element is required");
      }

      // Stop any existing stream first
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
        stream = null;
      }

      console.log("[Camera] Requesting camera access...");
      
      // Request camera access
      stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "environment", // Back camera
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });

      console.log("[Camera] Camera access granted, attaching to video element");

      // Attach stream to provided video element
      video = videoElement;
      video.srcObject = stream;
      video.muted = true;
      video.playsInline = true;
      video.setAttribute("playsinline", "true");
      video.setAttribute("webkit-playsinline", "true");
      
      // Wait for video metadata to load
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error("Video metadata timeout - camera may not be responding"));
        }, 10000); // 10 second timeout
        
        const onLoadedMetadata = () => {
          clearTimeout(timeout);
          video!.removeEventListener("loadedmetadata", onLoadedMetadata);
          video!.removeEventListener("error", onError);
          console.log("[Camera] Video metadata loaded");
          resolve();
        };
        
        const onError = (err: Event) => {
          clearTimeout(timeout);
          video!.removeEventListener("loadedmetadata", onLoadedMetadata);
          video!.removeEventListener("error", onError);
          reject(new Error("Video element error"));
        };
        
        video!.addEventListener("loadedmetadata", onLoadedMetadata);
        video!.addEventListener("error", onError);
      });
      
      // Start playing video
      console.log("[Camera] Starting video playback...");
      try {
        await video.play();
        console.log("[Camera] Video is playing");
      } catch (playError) {
        console.warn("[Camera] Video play error (may be expected):", playError);
        // Try again after a short delay
        await new Promise((resolve) => setTimeout(resolve, 100));
        await video.play();
      }
    } catch (error) {
      console.error("[Camera] Error accessing camera:", error);
      // Clean up on error
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
        stream = null;
      }
      if (video) {
        video.srcObject = null;
        video = null;
      }
      throw error;
    }
  };

  const stop = (): void => {
    console.log("[Camera] Stopping camera...");
    if (stream) {
      stream.getTracks().forEach((track) => {
        track.stop();
        console.log("[Camera] Stopped track:", track.kind);
      });
      stream = null;
    }
    if (video) {
      video.srcObject = null;
      video.pause();
      video = null;
    }
  };

  const captureFrame = async (): Promise<string | null> => {
    if (!video || !stream || video.readyState < 2) {
      // readyState: 0=HAVE_NOTHING, 1=HAVE_METADATA, 2=HAVE_CURRENT_DATA, 3=HAVE_FUTURE_DATA, 4=HAVE_ENOUGH_DATA
      return null;
    }

    try {
      // Create canvas
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        return null;
      }

      // Draw video frame to canvas
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      // Convert to base64 JPEG with compression (quality 0.5 for smaller size)
      const base64 = canvas.toDataURL("image/jpeg", 0.5);
      
      // Return full data URL (includes "data:image/jpeg;base64," prefix)
      return base64;
    } catch (error) {
      console.error("[Camera] Error capturing frame:", error);
      return null;
    }
  };

  return {
    video,
    stream,
    start,
    stop,
    captureFrame,
  };
}

/**
 * Create a frame capture handler that captures frames at specified interval
 */
export function createWebFrameCaptureHandler(
  camera: WebCameraCapture,
  onFrame: (base64Image: string) => void,
  intervalMs: number = 500
): () => void {
  let intervalId: NodeJS.Timeout | null = null;
  let isCapturing = false;

  const captureLoop = async () => {
    if (isCapturing) return;
    isCapturing = true;

    try {
      const frame = await camera.captureFrame();
      if (frame) {
        onFrame(frame);
      }
    } catch (error) {
      console.error("Error in capture loop:", error);
    } finally {
      isCapturing = false;
    }
  };

  intervalId = setInterval(captureLoop, intervalMs);

  // Return cleanup function
  return () => {
    if (intervalId) {
      clearInterval(intervalId);
      intervalId = null;
    }
  };
}
