import { MaterialIcons } from "@expo/vector-icons";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as Haptics from "expo-haptics";
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
  LayoutChangeEvent,
} from "react-native";

import { getTTSService, RiskLevel } from "../../src/services/TTSService";
import { getSTTService } from "../../src/services/STTService";

const API_BASE = "http://127.0.0.1:8000";

const GOLD = "#f9b233";
const { height: SCREEN_H } = Dimensions.get("window");

const AUTO_SCAN_INTERVAL_MS = 2500;
const AUTO_SCAN_TIMEOUT_MS = 12000;

type CamMode = "vision" | "ocr";

type BBox = { x_min: number; y_min: number; x_max: number; y_max: number };

type Detection = {
  category: string;
  confidence: number;
  bbox: BBox;
};

type AdapterResponse = {
  image_id: string;
  detections: Detection[];
};

async function buildImageFormData(photoUri: string) {
  const form = new FormData();

  if (Platform.OS === "web") {
    const resp = await fetch(photoUri);
    const blob = await resp.blob();
    const file = new File([blob], "frame.jpg", {
      type: blob.type || "image/jpeg",
    });
    form.append("file", file);
  } else {
    form.append("file", {
      uri: photoUri,
      type: "image/jpeg",
      name: "frame.jpg",
    } as any);
  }

  return form;
}

function clamp(n: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, n));
}

// Reading order heuristic: top-to-bottom; then right-to-left within rows (tune if needed)
function sortReadingOrder(ds: Detection[]) {
  const items = ds.map((d) => {
    const cy = (d.bbox.y_min + d.bbox.y_max) / 2;
    const cx = (d.bbox.x_min + d.bbox.x_max) / 2;
    const h = d.bbox.y_max - d.bbox.y_min;
    return { d, cy, cx, h };
  });

  items.sort((a, b) => a.cy - b.cy);

  const rows: (typeof items)[] = [];
  for (const it of items) {
    const lastRow = rows[rows.length - 1];
    if (!lastRow) {
      rows.push([it]);
      continue;
    }
    const rowCy = lastRow.reduce((s, x) => s + x.cy, 0) / lastRow.length;
    const tol = Math.max(12, it.h * 0.6);
    if (Math.abs(it.cy - rowCy) <= tol) lastRow.push(it);
    else rows.push([it]);
  }

  for (const row of rows) row.sort((a, b) => b.cx - a.cx);

  return rows.flat().map((x) => x.d);
}

function buildVisionSpeakMessage(ds: Detection[]) {
  const top = [...ds]
    .filter((d) => (d.confidence ?? 0) >= 0.35)
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 5);

  if (top.length === 0) return "";

  const counts = new Map<string, number>();
  for (const d of top) {
    const k = (d.category || "").trim().toLowerCase();
    if (!k) continue;
    counts.set(k, (counts.get(k) || 0) + 1);
  }

  const parts = [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([k, n]) => (n === 1 ? k : `${n} ${k}s`));

  return parts.length ? `Detected: ${parts.join(", ")}.` : "";
}

export default function CameraAssistScreen() {
  const [camMode, setCamMode] = useState<CamMode>("vision");

  // Keep some cooldown so autoscan doesn't spam continuously
  const tts = useMemo(() => getTTSService({ cooldownSeconds: 1.2 }), []);

  const [perm, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);

  // STT (persistent)
  const sttService = useMemo(() => getSTTService({ language: "en-US" }), []);
  const [sttAvailable, setSttAvailable] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [isVoiceProcessing, setIsVoiceProcessing] = useState(false);

  // Scan loop
  const [isAutoScanning, setIsAutoScanning] = useState(false);
  const scanIntervalRef = useRef<number | null>(null);

  // One in-flight chain guard + abort controller
  const isRequestInFlight = useRef(false);
  const detectAbortRef = useRef<AbortController | null>(null);

  // Mode version token: increments on mode switch to ignore stale results
  const modeVersionRef = useRef(0);

  // Overlay
  const [detections, setDetections] = useState<Detection[]>([]);
  const [frameMeta, setFrameMeta] = useState<{ w: number; h: number } | null>(
    null,
  );
  const [previewLayout, setPreviewLayout] = useState<{ w: number; h: number }>({
    w: 1,
    h: 1,
  });

  // Dedup speech
  const lastSpokenMessage = useRef<string>("");
  const lastSpokenAt = useRef<number>(0);

  // Mic lock to prevent press-in/out races
  const micLockRef = useRef(false);

  useEffect(() => {
    setSttAvailable(sttService.isAvailable());
  }, [sttService]);

  const clearOverlay = useCallback(() => {
    setDetections([]);
    setFrameMeta(null);
  }, []);

  const stopScanLoop = useCallback(() => {
    setIsAutoScanning(false);
    if (scanIntervalRef.current) clearInterval(scanIntervalRef.current);
    scanIntervalRef.current = null;

    // Abort in-flight request (if any)
    try {
      detectAbortRef.current?.abort();
    } catch {}
    detectAbortRef.current = null;

    isRequestInFlight.current = false;
  }, []);

  const stopListeningHard = useCallback(() => {
    try {
      sttService.stopListening();
    } catch {}
    setIsListening(false);
  }, [sttService]);

  // Auto-start scanning on mount (once permission is granted)
  useEffect(() => {
    if (!perm?.granted) return;
    // start after first render so cameraRef exists
    const id = setTimeout(() => {
      setIsAutoScanning(true);
    }, 250);
    return () => clearTimeout(id);
  }, [perm?.granted]);

  // Clean mode switching:
  // - increment mode version
  // - abort current request
  // - clear overlays
  // - keep scanning running, but "restart" tick so the loop uses new mode
  useEffect(() => {
    modeVersionRef.current += 1;

    // Abort and clear in-flight so next interval tick can run immediately
    try {
      detectAbortRef.current?.abort();
    } catch {}
    detectAbortRef.current = null;
    isRequestInFlight.current = false;

    clearOverlay();

    // Force an immediate scan when switching modes if autoscan is enabled.
    // (Otherwise user experiences a "dead" period until next interval tick.)
    if (isAutoScanning) {
      // Let state settle, then run a scan
      const id = setTimeout(() => {
        captureAndDetectRef.current?.();
      }, 80);
      return () => clearTimeout(id);
    }
  }, [camMode, clearOverlay, isAutoScanning]);

  const orderedOcrDetections = useMemo(() => {
    if (camMode !== "ocr") return [];
    return sortReadingOrder(detections).filter((d) => d.confidence >= 0.5);
  }, [camMode, detections]);

  const ocrText = useMemo(() => {
    if (camMode !== "ocr") return "";
    return orderedOcrDetections
      .map((d) => (d.category || "").trim())
      .filter(Boolean)
      .join(" ");
  }, [camMode, orderedOcrDetections]);

  const maybeSpeak = useCallback(
    async (msg: string, risk: RiskLevel = RiskLevel.LOW) => {
      const m = (msg || "").trim();
      if (!m) return;

      const now = Date.now();
      const isDup =
        m === lastSpokenMessage.current && now - lastSpokenAt.current < 2500;
      if (isDup) return;

      await tts.speak(m, risk, false);
      lastSpokenMessage.current = m;
      lastSpokenAt.current = now;
    },
    [tts],
  );

  // ---- bbox mapping ----
  const mapBBoxToPreview = useCallback(
    (bbox: BBox) => {
      if (!frameMeta) return null;

      const imgW = frameMeta.w;
      const imgH = frameMeta.h;
      const viewW = previewLayout.w;
      const viewH = previewLayout.h;

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

      const left = clamp(x1, 0, viewW);
      const top = clamp(y1, 0, viewH);
      const right = clamp(x2, 0, viewW);
      const bottom = clamp(y2, 0, viewH);

      const w = Math.max(0, right - left);
      const h = Math.max(0, bottom - top);

      return { left, top, width: w, height: h };
    },
    [frameMeta, previewLayout],
  );

  // ---- /query ----
  const processQuery = useCallback(
    async (queryText: string) => {
      const q = queryText.trim();
      if (!q) return;

      setIsVoiceProcessing(true);
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 9000);

        let response: Response;
        try {
          response = await fetch(`${API_BASE}/query`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: q }),
            signal: controller.signal,
          });
          clearTimeout(timeoutId);
        } catch (e: any) {
          clearTimeout(timeoutId);
          if (e?.name === "AbortError") throw new Error("Request timed out");
          throw e;
        }

        if (!response.ok) throw new Error(`Query failed: ${response.status}`);

        const data = await response.json();
        const ttsMessage =
          data.tts_message || data.response || "Query processed";
        await maybeSpeak(ttsMessage, RiskLevel.LOW);
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : "Failed to process query";
        Alert.alert("Query Error", msg);
      } finally {
        setIsVoiceProcessing(false);
      }
    },
    [maybeSpeak],
  );

  // ---- voice commands ----
  const handleVoiceCommand = useCallback(
    (tRaw: string): boolean => {
      const t = tRaw.toLowerCase().trim();
      if (!t) return false;

      if (t.includes("scan text") || t === "ocr") {
        setCamMode("ocr");
        return true;
      }
      if (t.includes("vision")) {
        setCamMode("vision");
        return true;
      }

      if (t.includes("start") && t.includes("scan")) {
        setIsAutoScanning(true);
        return true;
      }
      if (t.includes("stop") && (t.includes("scan") || t.includes("overlay"))) {
        stopScanLoop();
        clearOverlay();
        return true;
      }

      return false;
    },
    [stopScanLoop, clearOverlay],
  );

  // ---- capture + detect ----
  const captureAndDetect = useCallback(async () => {
    if (!cameraRef.current) return;
    if (isRequestInFlight.current) return;

    // Snapshot mode version to ignore stale async completions after mode switches
    const myModeVersion = modeVersionRef.current;
    const myMode = camMode;

    isRequestInFlight.current = true;

    // Cancel any previous controller defensively (shouldn't happen with isRequestInFlight, but safe)
    try {
      detectAbortRef.current?.abort();
    } catch {}
    const controller = new AbortController();
    detectAbortRef.current = controller;

    let timeoutId: NodeJS.Timeout | null = null;

    try {
      const photoPromise = cameraRef.current.takePictureAsync({
        quality: 1,
        base64: false,
        skipProcessing: false,
      });

      const timeoutPromise = new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error("takePictureAsync timeout")), 7000),
      );

      const photo = await Promise.race([photoPromise, timeoutPromise]);
      if (!photo?.uri) return;

      if (typeof photo.width === "number" && typeof photo.height === "number") {
        setFrameMeta({ w: photo.width, h: photo.height });
      }

      const formData = await buildImageFormData(photo.uri);
      const endpoint =
        myMode === "ocr" ? `${API_BASE}/ocr` : `${API_BASE}/vision`;

      timeoutId = setTimeout(() => controller.abort(), AUTO_SCAN_TIMEOUT_MS);

      const res = await fetch(endpoint, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });

      if (!res.ok) {
        const txt = await res.text().catch(() => "");
        console.log("[Detect] non-OK", res.status, txt);
        return;
      }

      const data = (await res.json()) as AdapterResponse;
      if (!data || !Array.isArray(data.detections)) {
        console.log("[Detect] unexpected shape:", data);
        return;
      }

      // Ignore stale responses (mode switched while request was in flight)
      if (modeVersionRef.current !== myModeVersion) return;

      setDetections(data.detections);

      // Speak:
      if (myMode === "vision") {
        const msg = buildVisionSpeakMessage(data.detections);
        await maybeSpeak(msg, RiskLevel.LOW);
      } else {
        const ordered = sortReadingOrder(data.detections).filter(
          (d) => d.confidence >= 0.5,
        );
        const text = ordered
          .map((d) => (d.category || "").trim())
          .filter(Boolean)
          .join(" ");
        await maybeSpeak(text, RiskLevel.LOW);
      }
    } catch (e: any) {
      if (e?.name !== "AbortError") {
        console.log("[Detect] error:", e?.message || String(e));
      }
    } finally {
      if (timeoutId) clearTimeout(timeoutId);

      // Only clear if we're still the active controller
      if (detectAbortRef.current === controller) {
        detectAbortRef.current = null;
      }
      isRequestInFlight.current = false;
    }
  }, [camMode, maybeSpeak]);

  // Ref to allow calling captureAndDetect from effects without dependency churn
  const captureAndDetectRef = useRef<(() => void) | null>(null);
  useEffect(() => {
    captureAndDetectRef.current = () => {
      captureAndDetect();
    };
  }, [captureAndDetect]);

  const manualOCRScan = useCallback(async () => {
    // 1. Give haptic feedback
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);

    // 2. Stop the auto-loop so it doesn't interfere
    stopScanLoop();

    // 3. Trigger a single detection
    await captureAndDetect();

    // 4. Optionally restart loop or stay static
    console.log("Manual OCR Scan Complete");
  }, [captureAndDetect, stopScanLoop]);

  // ---- scan loop ----
  useEffect(() => {
    if (!isAutoScanning) {
      if (scanIntervalRef.current) clearInterval(scanIntervalRef.current);
      scanIntervalRef.current = null;
      return;
    }

    // clear any old interval before starting
    if (scanIntervalRef.current) clearInterval(scanIntervalRef.current);

    // fire one immediately, then interval
    captureAndDetectRef.current?.();

    scanIntervalRef.current = setInterval(() => {
      captureAndDetectRef.current?.();
    }, AUTO_SCAN_INTERVAL_MS) as unknown as number;

    return () => {
      if (scanIntervalRef.current) clearInterval(scanIntervalRef.current);
      scanIntervalRef.current = null;
    };
  }, [isAutoScanning]);

  // ---- STT press/hold ----
  const startListening = useCallback(async () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

    // Always clear transcript on a new press
    setTranscript("");

    if (Platform.OS === "web") {
      const success = sttService.startListening(
        (text, isFinal) => {
          setTranscript(text);

          const trimmed = text.trim();
          if (!trimmed) return;

          // Execute obvious commands early (interim is OK)
          const wasCmd = handleVoiceCommand(trimmed);
          if (wasCmd) {
            stopListeningHard();
            return;
          }

          if (isFinal) {
            stopListeningHard();
            processQuery(trimmed);
          }
        },
        (error) => {
          Alert.alert("Speech Recognition Error", error);
          stopListeningHard();
        },
      );

      if (success) setIsListening(true);
      return;
    }

    const success = await sttService.startRecordingNative();
    if (success) {
      setIsListening(true);
      setTranscript("Recording...");
    } else {
      Alert.alert("Recording Error", "Failed to start audio recording");
    }
  }, [sttService, handleVoiceCommand, processQuery, stopListeningHard]);

  const stopListening = useCallback(async () => {
    if (Platform.OS === "web") {
      stopListeningHard();
      return;
    }

    setIsVoiceProcessing(true);
    try {
      const result = await sttService.stopRecordingNative();

      if (result.error) {
        Alert.alert("Transcription Error", result.error);
        return;
      }

      const text = (result.text || "").trim();
      if (!text) {
        Alert.alert("Transcription", "No speech detected.");
        return;
      }

      setTranscript(text);

      const wasCmd = handleVoiceCommand(text);
      if (!wasCmd) await processQuery(text);
    } catch {
      Alert.alert("Recording Error", "Failed to process recording");
    } finally {
      setIsVoiceProcessing(false);
      setIsListening(false);
    }
  }, [sttService, handleVoiceCommand, processQuery, stopListeningHard]);

  const micStart = useCallback(async () => {
    if (micLockRef.current) return;
    if (isVoiceProcessing) return;
    if (isListening) return;

    micLockRef.current = true;
    try {
      setIsListening(true);
      await startListening();
    } finally {
      setTimeout(() => {
        micLockRef.current = false;
      }, 120);
    }
  }, [startListening, isListening, isVoiceProcessing]);

  const micStop = useCallback(async () => {
    if (micLockRef.current) return;
    if (isVoiceProcessing) return;
    if (!isListening) return;

    micLockRef.current = true;
    try {
      await stopListening();
    } finally {
      setTimeout(() => {
        micLockRef.current = false;
      }, 120);
    }
  }, [stopListening, isListening, isVoiceProcessing]);

  // Stop timers on unmount
  useEffect(() => {
    return () => {
      stopScanLoop();
      stopListeningHard();
    };
  }, [stopScanLoop, stopListeningHard]);

  // ---- Permission gate ----
  if (!perm) return <View style={{ flex: 1, backgroundColor: "#1B263B" }} />;

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

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>
          {camMode === "ocr" ? "SCAN TEXT" : "VISION"}
        </Text>
      </View>

      <View
        style={styles.previewBox}
        onLayout={(e: LayoutChangeEvent) => {
          const { width, height } = e.nativeEvent.layout;
          setPreviewLayout({ w: width, h: height });
        }}
      >
        <CameraView
          ref={cameraRef}
          style={StyleSheet.absoluteFill}
          facing="back"
        />

        {/* Overlay boxes (both modes) */}
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
                key={`${idx}-${d.category}-${d.confidence}`}
                style={[
                  styles.box,
                  {
                    left: mapped.left,
                    top: mapped.top,
                    width: mapped.width,
                    height: mapped.height,
                  },
                ]}
              >
                <Text
                  style={[styles.boxLabel, { transform: [{ scaleX: -1 }] }]}
                  numberOfLines={1}
                >
                  {d.category} {Math.round(d.confidence * 100)}%
                </Text>
              </View>
            );
          })}
        </View>
      </View>

      {/* Mode bar */}
      <View style={styles.modeBar}>
        <ModeBtn
          label="Vision"
          active={camMode === "vision"}
          onPress={() => setCamMode("vision")}
        />
        <ModeBtn
          label="Scan Text"
          active={camMode === "ocr"}
          onPress={() => setCamMode("ocr")}
        />
      </View>

      {/* OCR panel */}
      {camMode === "ocr" && (
        <View style={styles.ocrPanel}>
          <View
            style={{
              flexDirection: "row",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <Text style={styles.ocrTitle}>Detected text</Text>

            {/* NEW MANUAL SCAN BUTTON */}
            <Pressable
              onPress={manualOCRScan}
              style={({ pressed }) => [
                {
                  backgroundColor: pressed ? "#fff" : GOLD,
                  padding: 8,
                  borderRadius: 8,
                },
              ]}
            >
              <MaterialIcons name="camera-alt" size={20} color="#1B263B" />
            </Pressable>
          </View>

          {detections.length === 0 ? (
            <Text style={styles.ocrEmpty}>
              No text yet. Tap camera to scan.
            </Text>
          ) : (
            <View style={styles.ocrOneBox}>
              <Text style={styles.ocrBlock}>{ocrText || "—"}</Text>
            </View>
          )}
        </View>
      )}

      {/* Controls */}
      <View style={styles.controls}>
        <Pressable
          style={[
            styles.controlBtn,
            isAutoScanning && styles.autoScanButtonActive,
          ]}
          onPress={() => {
            if (isAutoScanning) {
              stopScanLoop();
              clearOverlay();
              Haptics.selectionAsync();
              return;
            }

            setIsAutoScanning(true);
            Haptics.selectionAsync();
          }}
        >
          <Text style={styles.controlBtnText}>
            {isAutoScanning ? "Stop Live Scan" : "Start Live Scan"}
          </Text>
        </Pressable>
      </View>

      {/* Persistent voice bar */}
      <View style={styles.voiceRow}>
        <Pressable
          onPressIn={micStart}
          onPressOut={micStop}
          style={[styles.micBtn, isListening && styles.micBtnActive]}
          disabled={
            (Platform.OS !== "web" && !sttAvailable) || isVoiceProcessing
          }
        >
          <MaterialIcons
            name={isListening ? "mic" : "mic-none"}
            size={28}
            color={isListening ? "#1B263B" : GOLD}
          />
        </Pressable>

        <View style={styles.voiceTextWrap}>
          <Text style={styles.voiceHint}>
            {isVoiceProcessing
              ? "Processing..."
              : sttAvailable || Platform.OS === "web"
                ? isListening
                  ? Platform.OS === "web"
                    ? "Listening… speak now"
                    : "Recording... release to stop"
                  : "Hold mic: command or ask a question"
                : "Mic requires native STT (Dev Client)"}
          </Text>

          {!!transcript && !isVoiceProcessing && (
            <Text style={styles.voiceTranscript} numberOfLines={2}>
              {transcript}
            </Text>
          )}
        </View>
      </View>
    </View>
  );
}

function ModeBtn({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.modeBtn, active && styles.modeBtnActive]}
    >
      <Text style={[styles.modeBtnText, active && styles.modeBtnTextActive]}>
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: "#1B263B" },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 8,
    borderBottomWidth: 2,
    borderBottomColor: GOLD,
  },
  headerTitle: { color: GOLD, fontSize: 20, fontWeight: "800" },

  previewBox: {
    height: SCREEN_H * 0.55,
    margin: 12,
    borderRadius: 10,
    overflow: "hidden",
    backgroundColor: "#1B263B",
  },

  modeBar: {
    flexDirection: "row",
    gap: 10,
    justifyContent: "space-around",
    paddingHorizontal: 12,
    paddingTop: 8,
  },
  modeBtn: {
    flex: 1,
    borderWidth: 1,
    borderColor: GOLD,
    borderRadius: 10,
    paddingVertical: 10,
    alignItems: "center",
  },
  modeBtnActive: { backgroundColor: GOLD },
  modeBtnText: { color: GOLD, fontWeight: "700" },
  modeBtnTextActive: { color: "#1B263B" },

  controls: {
    paddingHorizontal: 16,
    paddingBottom: 10,
    gap: 10,
  },
  controlBtn: {
    backgroundColor: GOLD,
    marginTop: 12,
    paddingVertical: 12,
    paddingHorizontal: 18,
    borderRadius: 12,
    alignItems: "center",
  },
  controlBtnText: { color: "#1B263B", fontWeight: "800" },
  autoScanButtonActive: { backgroundColor: "#ff6b6b" },

  centerDark: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#1B263B",
  },
  primaryBtn: {
    backgroundColor: GOLD,
    paddingVertical: 12,
    paddingHorizontal: 18,
    borderRadius: 12,
  },
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
    maxWidth: 220,
    paddingHorizontal: 6,
    paddingVertical: 2,
    fontSize: 12,
    color: "#1B263B",
    backgroundColor: GOLD,
    borderRadius: 6,
    overflow: "hidden",
    fontWeight: "800",
  },

  voiceRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: "rgba(249,178,51,0.35)",
  },
  micBtn: {
    width: 56,
    height: 56,
    borderRadius: 28,
    borderWidth: 2,
    borderColor: GOLD,
    alignItems: "center",
    justifyContent: "center",
  },
  micBtnActive: { backgroundColor: GOLD },
  voiceTextWrap: { flex: 1 },
  voiceHint: { color: GOLD, fontWeight: "700" },
  voiceTranscript: { color: "#fff", marginTop: 6 },

  ocrPanel: {
    marginHorizontal: 12,
    marginTop: 10,
    marginBottom: 4,
    padding: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: GOLD,
    backgroundColor: "rgba(0,0,0,0.10)",
  },
  ocrTitle: { color: GOLD, fontWeight: "800", marginBottom: 8 },
  ocrEmpty: { color: "#fff", opacity: 0.8 },
  ocrBlock: {
    color: "#fff",
    fontSize: 18,
    lineHeight: 24,
    paddingVertical: 8,
  },
  ocrOneBox: {
    borderWidth: 1,
    borderColor: GOLD,
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: "rgba(249,178,51,0.10)",
  },
});
