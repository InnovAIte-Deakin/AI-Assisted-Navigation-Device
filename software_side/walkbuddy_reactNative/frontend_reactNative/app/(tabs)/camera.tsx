import { MaterialIcons } from "@expo/vector-icons";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as Haptics from "expo-haptics";
import * as FileSystem from "expo-file-system/legacy";
import { useFocusEffect } from "expo-router";
import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Alert,
  Dimensions,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { getTTSService, RiskLevel, riskLevelFromString } from "../../src/services/TTSService";
import { getSTTService } from "../../src/services/STTService";
import { API_BASE } from "../../src/config";

const GOLD = "#f9b233";
const { width: SCREEN_W, height: SCREEN_H } = Dimensions.get("window");

// /ws/vision WebSocket URL derived from REST base (http→ws, https→wss)
const WS_VISION_URL = API_BASE.replace(/^http/, "ws") + "/ws/vision";

type BBox = { x_min: number; y_min: number; x_max: number; y_max: number };
type Detection = { category: string; confidence: number; bbox: BBox; direction?: string };

// Module-level frame ID counter (no import needed)
let _frameCounter = 0;
const nextFrameId = () => `f${Date.now()}_${(_frameCounter++) & 0xffff}`;

async function buildImageFormData(photoUri: string) {
  const form = new FormData();
  if (Platform.OS === "web") {
    const resp = await fetch(photoUri);
    const blob = await resp.blob();
    form.append("file", new File([blob], "frame.jpg", { type: blob.type || "image/jpeg" }));
  } else {
    form.append("file", { uri: photoUri, type: "image/jpeg", name: "frame.jpg" } as any);
  }
  return form;
}

function clamp(n: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, n));
}

export default function CameraAssistScreen() {
  const tts = useMemo(() => getTTSService({ cooldownSeconds: 1.2 }), []);
  const [perm, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);

  // ── STT ─────────────────────────────────────────────────────────────────
  const sttService = useMemo(() => getSTTService({ language: "en-US" }), []);
  const [isListening, setIsListening] = useState(false);
  const [isVoiceProcessing, setIsVoiceProcessing] = useState(false);
  const isVoiceProcessingRef = useRef(false);
  const micLockRef = useRef(false);

  useEffect(() => {
    isVoiceProcessingRef.current = isVoiceProcessing;
  }, [isVoiceProcessing]);

  // ── WebSocket vision streaming ────────────────────────────────────────
  const wsRef = useRef<WebSocket | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const wsReconnectDelay = useRef(500);
  const wsReconnectCount = useRef(0);
  const wsReconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef(true);
  const isFocusedRef = useRef(false); // tracks screen focus; prevents reconnect when blurred

  // Frame flow control
  const pendingFrame = useRef(false);       // frame sent, awaiting server response
  const isCaptureInProgress = useRef(false); // takePictureAsync in progress
  const nextFrameTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const frameWatchdogTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── UI state ────────────────────────────────────────────────────────────
  const [detections, setDetections] = useState<Detection[]>([]);
  const [frameMeta, setFrameMeta] = useState<{ w: number; h: number } | null>(null);
  const [previewLayout, setPreviewLayout] = useState({ w: SCREEN_W, h: SCREEN_H });
  const [ocrResult, setOcrResult] = useState("");
  const [isOcrCapturing, setIsOcrCapturing] = useState(false);
  const ocrDismissTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // ── Bounding-box mapping ────────────────────────────────────────────────
  const mapBBoxToPreview = useCallback(
    (bbox: BBox) => {
      if (!frameMeta) return null;
      const { w: imgW, h: imgH } = frameMeta;
      const { w: viewW, h: viewH } = previewLayout;
      if (imgW <= 0 || imgH <= 0 || viewW <= 0 || viewH <= 0) return null;

      const scale = Math.max(viewW / imgW, viewH / imgH);
      const scaledW = imgW * scale;
      const scaledH = imgH * scale;
      const offsetX = (scaledW - viewW) / 2;
      const offsetY = (scaledH - viewH) / 2;

      const x1 = bbox.x_min * scale - offsetX;
      const y1 = bbox.y_min * scale - offsetY;
      const x2 = bbox.x_max * scale - offsetX;
      const y2 = bbox.y_max * scale - offsetY;

      return {
        left: clamp(x1, 0, viewW),
        top: clamp(y1, 0, viewH),
        width: Math.max(0, clamp(x2, 0, viewW) - clamp(x1, 0, viewW)),
        height: Math.max(0, clamp(y2, 0, viewH) - clamp(y1, 0, viewH)),
      };
    },
    [frameMeta, previewLayout],
  );

  // ── Frame watchdog: resets pendingFrame if server goes silent ───────────
  const clearFrameWatchdog = useCallback(() => {
    if (frameWatchdogTimer.current) {
      clearTimeout(frameWatchdogTimer.current);
      frameWatchdogTimer.current = null;
    }
  }, []);

  // ── Schedule next frame capture (event-driven, not timer-driven) ────────
  const captureAndSendFrameRef = useRef<(() => Promise<void>) | null>(null);

  const scheduleNextFrame = useCallback((delayMs: number) => {
    if (nextFrameTimer.current) clearTimeout(nextFrameTimer.current);
    nextFrameTimer.current = setTimeout(
      () => { captureAndSendFrameRef.current?.(); },
      Math.max(0, delayMs),
    );
  }, []);

  const setFrameWatchdog = useCallback(() => {
    clearFrameWatchdog();
    frameWatchdogTimer.current = setTimeout(() => {
      pendingFrame.current = false;
      scheduleNextFrame(500);
    }, 12000);
  }, [clearFrameWatchdog, scheduleNextFrame]);

  // ── WebSocket connection ────────────────────────────────────────────────
  const connectWebSocketRef = useRef<() => void>(() => {});

  const connectWebSocket = useCallback(() => {
    if (wsReconnectTimer.current) {
      clearTimeout(wsReconnectTimer.current);
      wsReconnectTimer.current = null;
    }

    const ws = new WebSocket(WS_VISION_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      wsReconnectDelay.current = 500;
      wsReconnectCount.current = 0;
      // Web camera needs ~2s to warm up its video stream before takePictureAsync works
      scheduleNextFrame(Platform.OS === "web" ? 2000 : 300);
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string);

        if (data.type === "detection_result") {
          pendingFrame.current = false;
          clearFrameWatchdog();
          setDetections(data.detections || []);

          if (data.guidance_message && !isVoiceProcessingRef.current) {
            tts.speakAsync(data.guidance_message, riskLevelFromString(data.risk_level));
          }

          // Pace next frame: 20% of inference time, floored at 150 ms
          scheduleNextFrame(Math.max(150, (data.inference_time_ms || 500) * 0.2));

        } else if (data.type === "frame_dropped") {
          pendingFrame.current = false;
          clearFrameWatchdog();
          scheduleNextFrame(200);

        } else if (data.type === "error") {
          pendingFrame.current = false;
          clearFrameWatchdog();
          scheduleNextFrame(1000);

        } else if (data.type === "ping") {
          ws.send(JSON.stringify({ type: "pong" }));
        }
      } catch (e) {
        console.error("[WS Vision] parse error:", e);
      }
    };

    ws.onerror = (e: Event) => {
      console.warn("[WS Vision] Error event:", JSON.stringify(e));
    };

    ws.onclose = (_e: CloseEvent) => {
      // Don't reconnect if navigated away or unmounted
      if (!isMountedRef.current || !isFocusedRef.current) return;
      if (wsRef.current === ws) wsRef.current = null;
      setWsConnected(false);
      setDetections([]);
      pendingFrame.current = false;
      clearFrameWatchdog();

      wsReconnectCount.current += 1;
      if (wsReconnectCount.current === 3) {
        tts.speakAsync("Vision disconnected. Reconnecting.", RiskLevel.MEDIUM);
      }

      const delay = wsReconnectDelay.current;
      wsReconnectDelay.current = Math.min(delay * 2, 8000);
      wsReconnectTimer.current = setTimeout(
        () => { connectWebSocketRef.current(); },
        delay,
      );
    };
  }, [tts, scheduleNextFrame, clearFrameWatchdog]);

  useEffect(() => {
    connectWebSocketRef.current = connectWebSocket;
  }, [connectWebSocket]);

  // Connect on screen focus, disconnect on blur (tab screens stay mounted in background)
  useFocusEffect(
    useCallback(() => {
      if (!perm?.granted) return;
      isFocusedRef.current = true;
      connectWebSocket();
      return () => {
        isFocusedRef.current = false;
        if (wsReconnectTimer.current) clearTimeout(wsReconnectTimer.current);
        if (nextFrameTimer.current) clearTimeout(nextFrameTimer.current);
        if (frameWatchdogTimer.current) clearTimeout(frameWatchdogTimer.current);
        if (ocrDismissTimer.current) clearTimeout(ocrDismissTimer.current);
        pendingFrame.current = false;
        const ws = wsRef.current;
        wsRef.current = null;
        ws?.close(1000, "blur");
      };
    // connectWebSocket is stable; perm.granted is the only meaningful dep here
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [perm?.granted]),
  );

  // ── Frame capture & send ────────────────────────────────────────────────
  const captureAndSendFrame = useCallback(async () => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    if (pendingFrame.current || isCaptureInProgress.current) return;
    if (!cameraRef.current) return;

    isCaptureInProgress.current = true;
    const frameId = nextFrameId();

    try {
      const photo = await Promise.race([
        cameraRef.current.takePictureAsync({
          quality: 0.4,
          base64: false,
          skipProcessing: true,
        }),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error("takePictureAsync timeout")), 5000),
        ),
      ]);

      if (!photo?.uri || !cameraRef.current) return;

      if (photo.width && photo.height) {
        setFrameMeta({ w: photo.width, h: photo.height });
      }

      // Re-check WS after the async capture — it may have closed
      const ws2 = wsRef.current;
      if (!ws2 || ws2.readyState !== WebSocket.OPEN) return;

      ws2.send(JSON.stringify({
        type: "frame_meta",
        frame_id: frameId,
        width: photo.width ?? 0,
        height: photo.height ?? 0,
        timestamp_ms: Date.now(),
      }));

      if (Platform.OS === "web") {
        const resp = await fetch(photo.uri);
        const buffer = await resp.arrayBuffer();
        ws2.send(buffer);
      } else {
        const b64 = await FileSystem.readAsStringAsync(photo.uri, {
          encoding: FileSystem.EncodingType.Base64,
        });
        const binaryStr = atob(b64);
        const bytes = new Uint8Array(binaryStr.length);
        for (let i = 0; i < binaryStr.length; i++) {
          bytes[i] = binaryStr.charCodeAt(i);
        }
        ws2.send(bytes.buffer);
      }

      pendingFrame.current = true;
      setFrameWatchdog();

    } catch (e: any) {
      const msg: string = e?.message ?? "";
      if (msg.includes("not enough camera data") || msg.includes("camera data")) {
        // Web camera still warming up — retry after a longer delay
        scheduleNextFrame(1500);
      } else if (msg !== "takePictureAsync timeout") {
        console.warn("[WS Frame] capture error:", msg);
      }
    } finally {
      isCaptureInProgress.current = false;
    }
  }, [setFrameWatchdog, scheduleNextFrame]);

  useEffect(() => {
    captureAndSendFrameRef.current = captureAndSendFrame;
  }, [captureAndSendFrame]);

  // ── OCR: on-demand single capture via REST ──────────────────────────────
  const captureOCR = useCallback(async () => {
    if (isOcrCapturing || !cameraRef.current) return;
    // Wait for any in-flight WS frame capture to finish (max 2s)
    const deadline = Date.now() + 2000;
    while (isCaptureInProgress.current && Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 50));
    }
    if (isCaptureInProgress.current) return; // still busy, give up
    isCaptureInProgress.current = true;      // block WS captures during OCR

    // Cancel the next scheduled WS frame so YOLO is idle during OCR
    if (nextFrameTimer.current) { clearTimeout(nextFrameTimer.current); nextFrameTimer.current = null; }
    // Give any in-flight YOLO inference ~300ms to finish before OCR hits the backend
    if (pendingFrame.current) await new Promise((r) => setTimeout(r, 300));

    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    setIsOcrCapturing(true);
    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.6,
        base64: false,
        skipProcessing: true,
      });
      if (!photo?.uri) return;

      const formData = await buildImageFormData(photo.uri);
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 15000);

      const res = await fetch(`${API_BASE}/ocr`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });
      clearTimeout(timeout);

      if (!res.ok) throw new Error(`OCR HTTP ${res.status}`);
      const data = await res.json();
      const text = data.guidance_message || "No text detected.";
      setOcrResult(text);
      tts.speakAsync(text, RiskLevel.LOW);

      if (ocrDismissTimer.current) clearTimeout(ocrDismissTimer.current);
      ocrDismissTimer.current = setTimeout(() => setOcrResult(""), 8000);

    } catch (e: any) {
      console.error(`[OCR] failed: name=${e?.name} message=${e?.message}`);
      if (e?.name !== "AbortError") tts.speakAsync("OCR failed.", RiskLevel.LOW);
    } finally {
      isCaptureInProgress.current = false;
      pendingFrame.current = false;
      setIsOcrCapturing(false);
      // Resume WS vision streaming after OCR
      scheduleNextFrame(300);
    }
  }, [isOcrCapturing, tts, scheduleNextFrame]);

  // ── Voice / chat ────────────────────────────────────────────────────────
  const processQuery = useCallback(async (queryText: string) => {
    const q = queryText.trim();
    if (!q) return;
    setIsVoiceProcessing(true);
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 9000);
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q }),
        signal: controller.signal,
      });
      clearTimeout(timeout);
      if (!res.ok) throw new Error(`Chat ${res.status}`);
      const data = await res.json();
      tts.speakAsync(data.response || "I didn't catch that.", RiskLevel.LOW);
    } catch (err: any) {
      if (err.name !== "AbortError") Alert.alert("Query Error", err.message);
    } finally {
      setIsVoiceProcessing(false);
    }
  }, [tts]);

  const stopListeningHard = useCallback(() => {
    try { sttService.stopListening(); } catch {}
    setIsListening(false);
  }, [sttService]);

  const startListening = useCallback(async () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    if (Platform.OS === "web") {
      const ok = sttService.startListening(
        (text, isFinal) => {
          const t = text.trim();
          if (!t) return;
          if (isFinal) {
            stopListeningHard();
            processQuery(t);
          }
        },
        (error) => {
          Alert.alert("STT Error", error);
          stopListeningHard();
        },
      );
      if (ok) setIsListening(true);
      return;
    }
    const ok = await sttService.startRecordingNative();
    if (ok) setIsListening(true);
    else Alert.alert("Recording Error", "Failed to start recording.");
  }, [sttService, processQuery, stopListeningHard]);

  const stopListening = useCallback(async () => {
    if (Platform.OS === "web") {
      stopListeningHard();
      return;
    }
    setIsVoiceProcessing(true);
    try {
      const result = await sttService.stopRecordingNative();
      if (result.error) { Alert.alert("Transcription Error", result.error); return; }
      const text = (result.text || "").trim();
      if (!text) { Alert.alert("Transcription", "No speech detected."); return; }
      await processQuery(text);
    } catch {
      Alert.alert("Error", "Processing failed.");
    } finally {
      setIsVoiceProcessing(false);
      setIsListening(false);
    }
  }, [sttService, processQuery, stopListeningHard]);

  const micStart = useCallback(async () => {
    if (micLockRef.current || isVoiceProcessing || isListening) return;
    micLockRef.current = true;
    tts.stop(); // interrupt any ongoing guidance speech
    try {
      setIsListening(true);
      await startListening();
    } finally {
      setTimeout(() => { micLockRef.current = false; }, 120);
    }
  }, [startListening, isListening, isVoiceProcessing, tts]);

  const micStop = useCallback(async () => {
    if (micLockRef.current || isVoiceProcessing || !isListening) return;
    micLockRef.current = true;
    try { await stopListening(); }
    finally { setTimeout(() => { micLockRef.current = false; }, 120); }
  }, [stopListening, isListening, isVoiceProcessing]);

  // Cleanup STT on unmount
  useEffect(() => {
    return () => { stopListeningHard(); };
  }, [stopListeningHard]);

  // ── Permission gates ────────────────────────────────────────────────────
  if (!perm) return <View style={{ flex: 1, backgroundColor: "#000" }} />;
  if (!perm.granted) {
    return (
      <View style={styles.centerDark}>
        <Text style={{ color: "#fff", marginBottom: 12 }}>
          Camera access is required.
        </Text>
        <Pressable style={styles.primaryBtn} onPress={requestPermission}>
          <Text style={styles.primaryBtnText}>Grant Permission</Text>
        </Pressable>
      </View>
    );
  }

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <View
      style={styles.root}
      onLayout={(e) => {
        const { width, height } = e.nativeEvent.layout;
        setPreviewLayout({ w: width, h: height });
      }}
    >
      {/* Full-screen camera */}
      <CameraView
        ref={cameraRef}
        style={StyleSheet.absoluteFill}
        facing="back"
      />

      {/* Bounding-box overlay */}
      <View
        pointerEvents="none"
        style={[
          StyleSheet.absoluteFill,
          Platform.OS === "web" && { transform: [{ scaleX: -1 }] },
        ]}
      >
        {detections.slice(0, 20).map((d, idx) => {
          const mapped = mapBBoxToPreview(d.bbox);
          if (!mapped || mapped.width <= 1 || mapped.height <= 1) return null;
          return (
            <View
              key={`${idx}-${d.category}`}
              style={[styles.box, { left: mapped.left, top: mapped.top, width: mapped.width, height: mapped.height }]}
            >
              <Text
                style={[styles.boxLabel, Platform.OS === "web" && { transform: [{ scaleX: -1 }] }]}
                numberOfLines={1}
              >
                {d.category} {Math.round(d.confidence * 100)}%
              </Text>
            </View>
          );
        })}
      </View>

      {/* WS connection status dot (top-left) */}
      <View style={[styles.statusDot, { backgroundColor: wsConnected ? "#4CAF50" : "#ff4444" }]} />

      {/* OCR result overlay — tap to dismiss */}
      {!!ocrResult && (
        <Pressable style={styles.ocrOverlay} onPress={() => setOcrResult("")}>
          <Text style={styles.ocrText}>{ocrResult}</Text>
          <Text style={styles.ocrDismiss}>Tap to dismiss</Text>
        </Pressable>
      )}

      {/* Processing indicator */}
      {isVoiceProcessing && (
        <View style={styles.processingBadge}>
          <Text style={styles.processingText}>Processing…</Text>
        </View>
      )}

      {/* Bottom controls: mic (left) + camera/OCR (right) */}
      <View style={styles.bottomControls}>
        <Pressable
          onPressIn={micStart}
          onPressOut={micStop}
          disabled={isVoiceProcessing}
          style={[styles.floatingBtn, isListening && styles.floatingBtnActive]}
        >
          <MaterialIcons
            name={isListening ? "mic" : "mic-none"}
            size={32}
            color={isListening ? "#1B263B" : GOLD}
          />
        </Pressable>

        <Pressable
          onPress={captureOCR}
          disabled={isOcrCapturing}
          style={[styles.floatingBtn, isOcrCapturing && styles.floatingBtnActive]}
        >
          <MaterialIcons
            name="camera-alt"
            size={32}
            color={isOcrCapturing ? "#1B263B" : GOLD}
          />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#000",
  },
  statusDot: {
    position: "absolute",
    top: 52,
    left: 16,
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  ocrOverlay: {
    position: "absolute",
    left: 24,
    right: 24,
    top: "28%",
    backgroundColor: "rgba(27,38,59,0.93)",
    borderWidth: 1.5,
    borderColor: GOLD,
    borderRadius: 16,
    padding: 20,
    alignItems: "center",
  },
  ocrText: {
    color: "#fff",
    fontSize: 18,
    lineHeight: 26,
    textAlign: "center",
  },
  ocrDismiss: {
    color: GOLD,
    fontSize: 11,
    marginTop: 10,
    opacity: 0.8,
  },
  processingBadge: {
    position: "absolute",
    top: 52,
    alignSelf: "center",
    backgroundColor: "rgba(27,38,59,0.85)",
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 6,
  },
  processingText: {
    color: GOLD,
    fontWeight: "700",
    fontSize: 13,
  },
  bottomControls: {
    position: "absolute",
    bottom: 48,
    left: 24,
    right: 24,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  floatingBtn: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: "rgba(27,38,59,0.85)",
    borderWidth: 2,
    borderColor: GOLD,
    alignItems: "center",
    justifyContent: "center",
  },
  floatingBtnActive: {
    backgroundColor: GOLD,
  },
  centerDark: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#1B263B",
  },
  primaryBtn: { backgroundColor: GOLD, padding: 12, borderRadius: 12 },
  primaryBtnText: { color: "#1B263B", fontWeight: "800" },
  box: {
    position: "absolute",
    borderWidth: 2,
    borderColor: GOLD,
    borderRadius: 6,
    backgroundColor: "rgba(0,0,0,0.15)",
  },
  boxLabel: {
    position: "absolute",
    left: 0,
    top: -18,
    fontSize: 11,
    color: "#1B263B",
    backgroundColor: GOLD,
    fontWeight: "800",
    paddingHorizontal: 2,
  },
});
