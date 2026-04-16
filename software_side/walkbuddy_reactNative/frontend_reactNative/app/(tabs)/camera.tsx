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
  Animated,
  Dimensions,
  Easing,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
  LayoutChangeEvent,
  ScrollView,
} from "react-native";

import { getTTSService, RiskLevel } from "../../src/services/TTSService";
import { getSTTService } from "../../src/services/STTService";
import { API_BASE } from "../../src/config";

const GOLD = "#f9b233";
const GREEN = "#22c55e";
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
    form.append(
      "file",
      {
        uri: photoUri,
        type: "image/jpeg",
        name: "frame.jpg",
      } as any,
    );
  }

  return form;
}

function clamp(n: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, n));
}

export default function CameraAssistScreen() {
  const [camMode, setCamMode] = useState<CamMode>("vision");
  const tts = useMemo(() => getTTSService({ cooldownSeconds: 1.2 }), []);
  const [perm, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);

  const slideAnim = useRef(new Animated.Value(0)).current;
  const [modeBarWidth, setModeBarWidth] = useState(0);

  const sttService = useMemo(() => getSTTService({ language: "en-US" }), []);
  const [sttAvailable, setSttAvailable] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [isVoiceProcessing, setIsVoiceProcessing] = useState(false);

  const [isAutoScanning, setIsAutoScanning] = useState(false);
  const scanIntervalRef = useRef<number | null>(null);
  const isRequestInFlight = useRef(false);
  const detectAbortRef = useRef<AbortController | null>(null);
  const modeVersionRef = useRef(0);

  const [detections, setDetections] = useState<Detection[]>([]);
  const [ocrTextDisplay, setOcrTextDisplay] = useState("");
  const [frameMeta, setFrameMeta] = useState<{ w: number; h: number } | null>(
    null,
  );
  const [previewLayout, setPreviewLayout] = useState<{ w: number; h: number }>({
    w: 1,
    h: 1,
  });

  const lastSpokenMessage = useRef<string>("");
  const lastSpokenAt = useRef<number>(0);
  const micLockRef = useRef(false);

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

    if (scanIntervalRef.current) {
      clearInterval(scanIntervalRef.current);
    }

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

  useEffect(() => {
    if (!perm?.granted) return;

    const id = setTimeout(() => {
      setIsAutoScanning(true);
    }, 250);

    return () => clearTimeout(id);
  }, [perm?.granted]);

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

  useEffect(() => {
    const target = camMode === "vision" ? 0 : 1;

    Animated.timing(slideAnim, {
      toValue: target,
      duration: 500,
      easing: Easing.bezier(0.22, 1, 0.36, 1),
      useNativeDriver: true,
    }).start();
  }, [camMode, slideAnim]);

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

        if (!response.ok) {
          throw new Error(`Query failed: ${response.status}`);
        }

        const data = await response.json();

        await maybeSpeak(
          data.response || "I didn't catch that.",
          RiskLevel.LOW,
        );
      } catch (err: any) {
        if (err.name !== "AbortError") {
          Alert.alert("Query Error", err.message);
        }
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
        quality: 0.5,
        base64: false,
        skipProcessing: true,
      });

      const timeoutPromise = new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error("takePictureAsync timeout")), 7000),
      );

      const photo = await Promise.race([photoPromise, timeoutPromise]);

      if (!cameraRef.current) {
        isRequestInFlight.current = false;
        return;
      }

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

      if (!res.ok) throw new Error("Server Error");

      const data = (await res.json()) as AdapterResponse;

      if (!data || modeVersionRef.current !== myModeVersion) return;

      setDetections(data.detections || []);

      if (myMode === "ocr") {
        setOcrTextDisplay(data.guidance_message || "");
      } else {
        setOcrTextDisplay("");
      }

      if (data.guidance_message) {
        await maybeSpeak(data.guidance_message, RiskLevel.LOW);
      }
    } catch (e: any) {
      if (e?.name !== "AbortError") {
        console.log("[Detect] error:", e?.message);
      }
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
    } else {
      Alert.alert("Recording Error", "Failed to start");
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

      if (!wasCmd) {
        await processQuery(text);
      }
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

  useEffect(() => {
    return () => {
      stopScanLoop();
      stopListeningHard();
    };
  }, [stopScanLoop, stopListeningHard]);

  if (!perm) {
    return <View style={{ flex: 1, backgroundColor: "#1B263B" }} />;
  }

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
      <View style={styles.headerCard}>
        <View style={styles.headerContent}>
          <Text style={styles.headerSmall}>Camera</Text>
          <Text style={styles.headerMain}>
            {camMode === "ocr" ? "SCAN TEXT" : "VISION"}
          </Text>
        </View>
      </View>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View
          style={[
            styles.previewBox,
            {
              borderColor: isAutoScanning
                ? "rgba(34,197,94,0.9)"
                : "rgba(249,178,51,0.9)",

              shadowColor: isAutoScanning ? GREEN : GOLD,
              shadowOpacity: isAutoScanning ? 0.85 : 0.7,
              shadowRadius: isAutoScanning ? 30 : 25,
              elevation: isAutoScanning ? 20 : 16,
            },
          ]}
        >
          <CameraView
            ref={cameraRef}
            style={StyleSheet.absoluteFill}
            facing="back"
          />

          <View style={styles.cameraStatusBadge}>
            <Text style={styles.cameraStatusText}>
              {isAutoScanning ? "Live camera active" : "Camera ready"}
            </Text>
          </View>

          <View
            pointerEvents="none"
            style={[
              StyleSheet.absoluteFill,
              Platform.OS === "web" && { transform: [{ scaleX: -1 }] },
            ]}
          >
            {detections.slice(0, 20).map((d, idx) => {
              const mapped = mapBBoxToPreview(d.bbox);
              if (!mapped || mapped.width <= 1 || mapped.height <= 1) {
                return null;
              }

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
                    {d.category} {Math.round(d.confidence * 100)}%
                  </Text>
                </View>
              );
            })}
          </View>
        </View>

        <View
          style={styles.modeBar}
          onLayout={(e) => setModeBarWidth(e.nativeEvent.layout.width)}
        >
          {modeBarWidth > 0 && (
            <Animated.View
              pointerEvents="none"
              style={[
                styles.modeSlider,
                {
                  width: modeBarWidth / 2 - 6,
                  transform: [
                    {
                      translateX: slideAnim.interpolate({
                        inputRange: [0, 1],
                        outputRange: [3, modeBarWidth / 2 - 3],
                      }),
                    },
                  ],
                },
              ]}
            />
          )}

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
            <View style={styles.ocrTopRow}>
              <Text style={styles.ocrTitle}>Detected text</Text>

              <Pressable
                onPress={manualOCRScan}
                style={({ pressed }) => [
                  styles.ocrCameraBtn,
                  pressed && styles.ocrCameraBtnPressed,
                ]}
              >
                <MaterialIcons name="camera-alt" size={20} color="#1B263B" />
              </Pressable>
            </View>

            {!ocrTextDisplay ? (
              <Text style={styles.ocrEmpty}>
                No text yet. Tap the camera icon to scan.
              </Text>
            ) : (
              <View style={styles.ocrOneBox}>
                <Text style={styles.ocrBlock}>{ocrTextDisplay}</Text>
              </View>
            )}
          </View>
        )}

        <View style={styles.controlsCard}>
          <Pressable
            style={({ pressed }) => [
              styles.controlBtn,
              isAutoScanning && styles.autoScanButtonActive,
              pressed && styles.controlBtnPressed,
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
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <MaterialIcons
                name={isAutoScanning ? "stop-circle" : "play-circle-fill"}
                size={22}
                color="#1B263B"
              />
              <Text style={styles.controlBtnText}>
                {isAutoScanning ? "Stop Live Scan" : "Start Live Scan"}
              </Text>
            </View>
          </Pressable>
        </View>

        <View style={styles.micContainer}>
          <Pressable
            onPressIn={micStart}
            onPressOut={micStop}
            style={({ pressed }) => [
              styles.micBtn,
              isListening && styles.micBtnActive,
              pressed && styles.micBtnPressed,
            ]}
            disabled={
              (Platform.OS !== "web" && !sttAvailable) || isVoiceProcessing
            }
          >
            <MaterialIcons
              name={isListening ? "mic" : "mic-none"}
              size={32}
              color={isListening ? "#1B263B" : GOLD}
            />
          </Pressable>

          <Text style={styles.micHint}>
            {isVoiceProcessing
              ? "Processing..."
              : isListening
                ? "Listening..."
                : "Hold mic to speak"}
          </Text>

          {!!transcript && !isVoiceProcessing && (
            <Text style={styles.micTranscript} numberOfLines={2}>
              {transcript}
            </Text>
          )}
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
      style={({ pressed }) => [
        styles.modeBtn,
        pressed && styles.modeBtnPressed,
      ]}
    >
      <Text style={[styles.modeBtnText, active && styles.modeBtnTextActive]}>
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    backgroundColor: "#1B263B",
  },

  scrollContent: {
    paddingBottom: 120,
    paddingTop: 10,
  },

  headerCard: {
    marginHorizontal: 16,
    marginTop: 14,
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderRadius: 20,
    backgroundColor: "#12304d",
    shadowColor: "#000",
    shadowOpacity: 0.22,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 },
    elevation: 8,
  },

  headerContent: {
    alignItems: "center",
    justifyContent: "center",
  },

  headerSmall: {
    color: "#d1d5db",
    fontSize: 15,
    fontWeight: "700",
    marginBottom: 6,
  },

  headerMain: {
    color: GOLD,
    fontSize: 22,
    fontWeight: "900",
    letterSpacing: 0.8,
  },


  previewBox: {
    height: SCREEN_H * 0.52,
    marginHorizontal: 16,
    marginTop: 16,
    borderRadius: 22,
    overflow: "hidden",
    backgroundColor: "#243247",
    borderWidth: 2,
    shadowOpacity: 0.7,
    shadowRadius: 25,
    shadowOffset: { width: 0, height: 0 },
    elevation: 16,
  },

  cameraStatusBadge: {
    position: "absolute",
    top: 12,
    left: 12,
    zIndex: 10,
    backgroundColor: "rgba(16,35,61,0.85)",
    borderWidth: 1,
    borderColor: "rgba(249,178,51,0.5)",
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },

  cameraStatusText: {
    color: "#fff",
    fontSize: 12,
    fontWeight: "700",
  },

  modeBar: {
    flexDirection: "row",
    marginHorizontal: 16,
    marginTop: 16,
    height: 72,
    padding: 3,
    borderRadius: 999,
    backgroundColor: "#0b2342",
    borderWidth: 1.5,
    borderColor: "rgba(249,178,51,0.38)",
    position: "relative",
  },

  modeSlider: {
    position: "absolute",
    top: 3,
    bottom: 3,
    left: 0,
    borderRadius: 999,
    backgroundColor: GOLD,
    shadowColor: GOLD,
    shadowOpacity: 0.45,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 4 },
    elevation: 8,
  },

  modeBtn: {
    flex: 1,
    borderRadius: 999,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 2,
  },

  modeBtnPressed: {
    opacity: 0.9,
  },

  modeBtnText: {
    color: GOLD,
    fontWeight: "800",
    fontSize: 16,
  },

  modeBtnTextActive: {
    color: "#1B263B",
  },

  ocrPanel: {
    marginHorizontal: 16,
    marginTop: 16,
    padding: 14,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "rgba(249,178,51,0.35)",
    backgroundColor: "#10233d",
  },

  ocrTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },

  ocrTitle: {
    color: GOLD,
    fontWeight: "800",
    fontSize: 17,
  },

  ocrCameraBtn: {
    backgroundColor: GOLD,
    padding: 10,
    borderRadius: 12,
  },

  ocrCameraBtnPressed: {
    opacity: 0.9,
    transform: [{ scale: 0.96 }],
  },

  ocrEmpty: {
    color: "#fff",
    opacity: 0.82,
    fontSize: 15,
    lineHeight: 22,
  },

  ocrBlock: {
    color: "#fff",
    fontSize: 17,
    lineHeight: 24,
  },

  ocrOneBox: {
    borderWidth: 1,
    borderColor: "rgba(249,178,51,0.4)",
    borderRadius: 14,
    padding: 12,
    backgroundColor: "rgba(249,178,51,0.10)",
  },

  controlsCard: {
    marginHorizontal: 16,
    marginTop: 16,
  },

  controlBtn: {
    paddingVertical: 18,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",

    backgroundColor: GOLD,

    shadowColor: GOLD,
    shadowOpacity: 0.45,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 6 },
    elevation: 10,

    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.15)",
  },

  controlBtnPressed: {
    transform: [{ scale: 0.96 }],
    opacity: 0.9,
  },

  controlBtnText: {
    color: "#1B263B",
    fontWeight: "900",
    fontSize: 18,
    letterSpacing: 0.4,
  },

  autoScanButtonActive: {
    backgroundColor: "#ff5a5a",

    shadowColor: "#ff5a5a",
    shadowOpacity: 0.5,
    shadowRadius: 16,
    elevation: 12,
  },

  centerDark: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#1B263B",
  },

  primaryBtn: {
    backgroundColor: GOLD,
    padding: 12,
    borderRadius: 12,
  },

  primaryBtnText: {
    color: "#1B263B",
    fontWeight: "800",
  },

  box: {
    position: "absolute",
    borderWidth: 2,
    borderColor: GOLD,
    borderRadius: 8,
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
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },

  micContainer: {
    alignItems: "center",
    justifyContent: "center",
    marginTop: 24,
    marginBottom: 30,
  },

  micHint: {
    marginTop: 12,
    color: GOLD,
    fontWeight: "700",
    fontSize: 15,
  },

  micTranscript: {
    marginTop: 6,
    color: "#fff",
    fontSize: 13,
    opacity: 0.85,
    textAlign: "center",
    paddingHorizontal: 20,
  },

  micBtn: {
    width: 58,
    height: 58,
    borderRadius: 29,
    borderWidth: 2,
    borderColor: GOLD,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "transparent",
  },

  micBtnActive: {
    backgroundColor: GOLD,
  },

  micBtnPressed: {
    opacity: 0.9,
    transform: [{ scale: 0.96 }],
  },


});