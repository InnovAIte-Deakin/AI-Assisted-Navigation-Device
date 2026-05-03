import { MaterialIcons } from "@expo/vector-icons";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as Haptics from "expo-haptics";
import * as Location from "expo-location";
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
  ScrollView,
} from "react-native";

// Ensure these paths match your project structure
import { getTTSService, RiskLevel } from "../../src/services/TTSService";
import { getSTTService } from "../../src/services/STTService";
import { API_BASE } from "../../src/config";

const GOLD = "#f9b233";
const { height: SCREEN_H } = Dimensions.get("window");

const AUTO_SCAN_INTERVAL_MS = 5000;
const AUTO_SCAN_TIMEOUT_MS = 12000;
const STATIONARY_THRESHOLD_MS = 12000;
const STATIONARY_MOVEMENT_M = 2;

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
  guidance_message?: string;
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

function haversineMeters(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371000;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export default function CameraAssistScreen() {
  const [camMode, setCamMode] = useState<CamMode>("vision");
  const tts = useMemo(() => getTTSService({ cooldownSeconds: 1.2 }), []);
  const [perm, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);

  // STT
  const sttService = useMemo(() => getSTTService({ language: "en-US" }), []);
  const [sttAvailable, setSttAvailable] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [isVoiceProcessing, setIsVoiceProcessing] = useState(false);

  // Scan loop
  const [isAutoScanning, setIsAutoScanning] = useState(false);
  const scanIntervalRef = useRef<number | null>(null);
  const isRequestInFlight = useRef(false);
  const detectAbortRef = useRef<AbortController | null>(null);
  const modeVersionRef = useRef(0);

  // UI State
  const [detections, setDetections] = useState<Detection[]>([]);
  const [ocrTextDisplay, setOcrTextDisplay] = useState("");
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
  const micLockRef = useRef(false);

  // Feature 1: What Changed
  const prevDetectionCategoriesRef = useRef<Set<string>>(new Set());
  const hasScannedOnceRef = useRef(false);

  // Feature 2: Lost & Recovery
  const lastPositionRef = useRef<{ lat: number; lng: number; time: number } | null>(null);
  const locationSubRef = useRef<Location.LocationSubscription | null>(null);
  const assistanceAlertShownRef = useRef(false);

  // Feature 3: Social Awareness
  const prevPersonCountRef = useRef(0);

  // Unmount guard for async callbacks
  const mountedRef = useRef(true);

  useEffect(() => {
    setSttAvailable(sttService.isAvailable());
  }, [sttService]);

  const clearOverlay = useCallback(() => {
    setDetections([]);
    setOcrTextDisplay("");
    setFrameMeta(null);
  }, []);

  const stopScanLoop = useCallback(() => {
    setIsAutoScanning(false);
    if (scanIntervalRef.current) clearInterval(scanIntervalRef.current);
    scanIntervalRef.current = null;
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

  // Auto-start scanning on mount
  useEffect(() => {
    if (!perm?.granted) return;
    const id = setTimeout(() => {
      setIsAutoScanning(true);
    }, 250);
    return () => clearTimeout(id);
  }, [perm?.granted]);

  // Reset "What Changed" and social state when mode switches
  useEffect(() => {
    prevDetectionCategoriesRef.current = new Set();
    hasScannedOnceRef.current = false;
    prevPersonCountRef.current = 0;
  }, [camMode]);

  // Mode switching
  useEffect(() => {
    modeVersionRef.current += 1;
    try {
      detectAbortRef.current?.abort();
    } catch {}
    detectAbortRef.current = null;
    isRequestInFlight.current = false;
    clearOverlay();
    if (isAutoScanning) {
      const id = setTimeout(() => {
        captureAndDetectRef.current?.();
      }, 80);
      return () => clearTimeout(id);
    }
  }, [camMode, clearOverlay, isAutoScanning]);

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
      return {
        left,
        top,
        width: Math.max(0, right - left),
        height: Math.max(0, bottom - top),
      };
    },
    [frameMeta, previewLayout],
  );

  const processQuery = useCallback(
    async (queryText: string) => {
      const q = queryText.trim();
      if (!q) return;
      setIsVoiceProcessing(true);
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 9000);
        const response = await fetch(`${API_BASE}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: q }),
          signal: controller.signal,
        });
        clearTimeout(timeoutId);
        if (!response.ok) throw new Error(`Query failed: ${response.status}`);
        const data = await response.json();
        await maybeSpeak(
          data.response || "I didn't catch that.",
          RiskLevel.LOW,
        );
      } catch (err: any) {
        if (err.name !== "AbortError") Alert.alert("Query Error", err.message);
      } finally {
        setIsVoiceProcessing(false);
      }
    },
    [maybeSpeak],
  );

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

  const captureAndDetect = useCallback(async () => {
    if (!cameraRef.current || isRequestInFlight.current) return;
    const myModeVersion = modeVersionRef.current;
    const myMode = camMode;
    isRequestInFlight.current = true;

    try {
      detectAbortRef.current?.abort();
    } catch {}
    const controller = new AbortController();
    detectAbortRef.current = controller;
    let timeoutId: NodeJS.Timeout | null = null;

    try {
      const photoPromise = cameraRef.current.takePictureAsync({
        quality: myMode === "ocr" ? 0.9 : 0.5,
        base64: false,
        skipProcessing: myMode !== "ocr",
      });
      const timeoutPromise = new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error("takePictureAsync timeout")), 7000),
      );

      // --- CRITICAL SAFETY CHECK: CAMERA UNMOUNT ---
      const photo = await Promise.race([photoPromise, timeoutPromise]);
      if (!cameraRef.current) {
        // Component unmounted while waiting for photo
        isRequestInFlight.current = false;
        return;
      }
      if (!photo?.uri) return;

      const imgW = typeof photo.width === "number" ? photo.width : 1000;
      const imgH = typeof photo.height === "number" ? photo.height : 1000;

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

      if (!res.ok) throw new Error("Server Error");
      const data = (await res.json()) as AdapterResponse;
      if (!data || modeVersionRef.current !== myModeVersion) return;

      setDetections(data.detections || []);
      if (myMode === "ocr") setOcrTextDisplay(data.guidance_message || "");
      else setOcrTextDisplay("");

      if (myMode === "vision") {
        const allDetections = data.detections || [];

        // ── Feature 1: What Changed ─────────────────────────────────────────
        const currentCategories = new Set(
          allDetections.filter(d => d.confidence >= 0.5).map(d => d.category)
        );
        const prev = prevDetectionCategoriesRef.current;
        const newItems = [...currentCategories].filter(c => !prev.has(c));
        const allCleared = currentCategories.size === 0 && prev.size > 0;
        const isFirst = !hasScannedOnceRef.current;

        hasScannedOnceRef.current = true;
        prevDetectionCategoriesRef.current = currentCategories;

        if ((isFirst || newItems.length > 0) && data.guidance_message) {
          await maybeSpeak(data.guidance_message, RiskLevel.LOW);
        } else if (allCleared) {
          await maybeSpeak("Path looks clear.", RiskLevel.LOW);
        }

        // ── Feature 3: Social Awareness ─────────────────────────────────────
        const personDetections = allDetections.filter(
          d => d.category === "person" && d.confidence >= 0.5
        );
        if (personDetections.length !== prevPersonCountRef.current) {
          prevPersonCountRef.current = personDetections.length;
          if (personDetections.length > 0) {
            const positions = personDetections.map(p => {
              const cx = (p.bbox.x_min + p.bbox.x_max) / 2;
              const ratio = cx / imgW;
              if (ratio < 0.33) return "on your left";
              if (ratio > 0.66) return "on your right";
              return "ahead";
            });
            const bboxArea = (p: Detection) =>
              (p.bbox.x_max - p.bbox.x_min) * (p.bbox.y_max - p.bbox.y_min);
            const isClose = personDetections.some(
              p => bboxArea(p) / (imgW * imgH) > 0.08
            );
            const uniquePos = [...new Set(positions)].join(", ");
            const socialMsg =
              personDetections.length === 1
                ? `Person ${isClose ? "close, " : ""}${positions[0]}`
                : `${personDetections.length} people nearby${isClose ? ", some close" : ""}: ${uniquePos}`;
            setTimeout(() => {
              if (mountedRef.current) maybeSpeak(socialMsg, RiskLevel.LOW);
            }, 2500);
          }
        }
      } else if (data.guidance_message) {
        // OCR mode — always speak
        await maybeSpeak(data.guidance_message, RiskLevel.LOW);
      }
    } catch (e: any) {
      if (e?.name !== "AbortError") console.log("[Detect] error:", e?.message);
    } finally {
      if (timeoutId) clearTimeout(timeoutId);
      if (detectAbortRef.current === controller) detectAbortRef.current = null;
      isRequestInFlight.current = false;
    }
  }, [camMode, maybeSpeak]);

  const captureAndDetectRef = useRef<(() => void) | null>(null);
  useEffect(() => {
    captureAndDetectRef.current = captureAndDetect;
  }, [captureAndDetect]);

  const manualOCRScan = useCallback(async () => {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    stopScanLoop();
    await captureAndDetect();
  }, [captureAndDetect, stopScanLoop]);

  useEffect(() => {
    if (!isAutoScanning) {
      if (scanIntervalRef.current) clearInterval(scanIntervalRef.current);
      scanIntervalRef.current = null;
      return;
    }
    if (scanIntervalRef.current) clearInterval(scanIntervalRef.current);
    captureAndDetectRef.current?.();
    scanIntervalRef.current = setInterval(() => {
      captureAndDetectRef.current?.();
    }, AUTO_SCAN_INTERVAL_MS) as unknown as number;
    return () => {
      if (scanIntervalRef.current) clearInterval(scanIntervalRef.current);
    };
  }, [isAutoScanning]);

  const startListening = useCallback(async () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setTranscript("");
    if (Platform.OS === "web") {
      const success = sttService.startListening(
        (text, isFinal) => {
          setTranscript(text);
          const trimmed = text.trim();
          if (!trimmed) return;
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
          Alert.alert("STT Error", error);
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
    } else Alert.alert("Recording Error", "Failed to start");
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
      Alert.alert("Error", "Processing failed");
    } finally {
      setIsVoiceProcessing(false);
      setIsListening(false);
    }
  }, [sttService, handleVoiceCommand, processQuery, stopListeningHard]);

  const micStart = useCallback(async () => {
    if (micLockRef.current || isVoiceProcessing || isListening) return;
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
    if (micLockRef.current || isVoiceProcessing || !isListening) return;
    micLockRef.current = true;
    try {
      await stopListening();
    } finally {
      setTimeout(() => {
        micLockRef.current = false;
      }, 120);
    }
  }, [stopListening, isListening, isVoiceProcessing]);

  // Feature 2: Lost & Recovery Mode
  useEffect(() => {
    let sub: Location.LocationSubscription | null = null;
    let cancelled = false;

    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== "granted" || cancelled) return;

      sub = await Location.watchPositionAsync(
        { accuracy: Location.Accuracy.Balanced, timeInterval: 3000, distanceInterval: 1 },
        (loc) => {
          const { latitude, longitude } = loc.coords;
          const now = Date.now();

          if (!lastPositionRef.current) {
            lastPositionRef.current = { lat: latitude, lng: longitude, time: now };
            return;
          }

          const dist = haversineMeters(
            lastPositionRef.current.lat,
            lastPositionRef.current.lng,
            latitude,
            longitude
          );

          if (dist > STATIONARY_MOVEMENT_M) {
            lastPositionRef.current = { lat: latitude, lng: longitude, time: now };
            assistanceAlertShownRef.current = false;
          } else {
            const stationaryMs = now - lastPositionRef.current.time;
            if (stationaryMs >= STATIONARY_THRESHOLD_MS && !assistanceAlertShownRef.current) {
              assistanceAlertShownRef.current = true;
              Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
              Alert.alert(
                "Are you okay?",
                "You've been in the same spot for a while. Do you need assistance?",
                [
                  {
                    text: "I'm fine",
                    onPress: () => {
                      assistanceAlertShownRef.current = false;
                      if (lastPositionRef.current) {
                        lastPositionRef.current.time = Date.now();
                      }
                    },
                  },
                  {
                    text: "Need Help",
                    onPress: () => {
                      tts.speak(
                        "Understood. Stay where you are, help is on the way.",
                        RiskLevel.HIGH,
                        false
                      );
                    },
                  },
                ]
              );
            }
          }
        }
      );
      locationSubRef.current = sub;
    })();

    return () => {
      cancelled = true;
      sub?.remove();
      locationSubRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    return () => {
      mountedRef.current = false;
      stopScanLoop();
      stopListeningHard();
      locationSubRef.current?.remove();
    };
  }, [stopScanLoop, stopListeningHard]);

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
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ paddingBottom: 120 }}
        showsVerticalScrollIndicator={false}
      >
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
          <View
            pointerEvents="none"
            style={[
              StyleSheet.absoluteFill,
              Platform.OS === "web" && { transform: [{ scaleX: -1 }] },
            ]}
          >
            {detections.filter(d => d.confidence >= 0.5).slice(0, 10).map((d, idx) => {
              const mapped = mapBBoxToPreview(d.bbox);
              if (!mapped || mapped.width <= 1 || mapped.height <= 1)
                return null;
              return (
                <View
                  key={`${idx}-${d.category}`}
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
                    {d.category}
                  </Text>
                </View>
              );
            })}
          </View>
        </View>

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
            {!ocrTextDisplay ? (
              <Text style={styles.ocrEmpty}>No text yet. Tap camera.</Text>
            ) : (
              <View style={styles.ocrOneBox}>
                <Text style={styles.ocrBlock}>{ocrTextDisplay}</Text>
              </View>
            )}
          </View>
        )}

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
                : isListening
                  ? "Listening..."
                  : "Hold mic to speak"}
            </Text>
            {!!transcript && !isVoiceProcessing && (
              <Text style={styles.voiceTranscript} numberOfLines={2}>
                {transcript}
              </Text>
            )}
          </View>
        </View>
      </ScrollView>
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
    justifyContent: "space-between",
    padding: 16,
    paddingTop: 14,
    borderBottomWidth: 2,
    borderColor: GOLD,
  },
  headerTitle: { color: GOLD, fontSize: 20, fontWeight: "800" },
  previewBox: {
    height: SCREEN_H * 0.55,
    margin: 12,
    borderRadius: 10,
    overflow: "hidden",
    backgroundColor: "#1B263B",
  },
  modeBar: { flexDirection: "row", gap: 10, padding: 12 },
  modeBtn: {
    flex: 1,
    borderWidth: 1,
    borderColor: GOLD,
    borderRadius: 10,
    padding: 10,
    alignItems: "center",
  },
  modeBtnActive: { backgroundColor: GOLD },
  modeBtnText: { color: GOLD, fontWeight: "700" },
  modeBtnTextActive: { color: "#1B263B" },
  controls: { padding: 16, gap: 10 },
  controlBtn: {
    backgroundColor: GOLD,
    marginTop: 12,
    padding: 12,
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
    fontSize: 12,
    color: "#1B263B",
    backgroundColor: GOLD,
    fontWeight: "800",
  },
  voiceRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    padding: 16,
    borderTopWidth: 1,
    borderColor: "rgba(249,178,51,0.35)",
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
    margin: 12,
    padding: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: GOLD,
    backgroundColor: "rgba(0,0,0,0.10)",
  },
  ocrTitle: { color: GOLD, fontWeight: "800", marginBottom: 8 },
  ocrEmpty: { color: "#fff", opacity: 0.8 },
  ocrBlock: { color: "#fff", fontSize: 18, lineHeight: 24 },
  ocrOneBox: {
    borderWidth: 1,
    borderColor: GOLD,
    borderRadius: 10,
    padding: 10,
    backgroundColor: "rgba(249,178,51,0.10)",
  },
});
