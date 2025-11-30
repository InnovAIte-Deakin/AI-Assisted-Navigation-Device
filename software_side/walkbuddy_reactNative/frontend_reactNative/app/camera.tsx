// app/camera.tsx
import { MaterialIcons } from "@expo/vector-icons";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as Haptics from "expo-haptics";
import * as Speech from "expo-speech";
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

import ModelWebView from "../src/components/ModelWebView";
import { GRADIO_URL } from "../src/config";
import { switchMode, stopAll } from "../src/utils/api";
import { fetchStatus } from "../src/api/client";

const GOLD = "#f9b233";
const { height: SCREEN_H } = Dimensions.get("window");

type Mode = "idle" | "vision" | "voice" | "ocr";

// helper: resolves if we can reach Gradio at all
async function ping(url: string) {
  await fetch(url, { cache: "no-store" });
}

export default function CameraAssistScreen() {
  // default mode = voice (camera only, no Gradio)
  const [mode, setMode] = useState<Mode>("voice");

  // camera for voice assist
  const [perm, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);

  // WebView state
  const [loading, setLoading] = useState(false);
  const [rev, setRev] = useState(0);
  const url = useMemo(() => `${GRADIO_URL}?v=${rev}`, [rev]);

  // timers
  const retryTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const attemptsRef = useRef(0);

  // voice assist
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [sttAvailable, setSttAvailable] = useState(false);
  const recognitionRef = useRef<any>(null);

  // text-to-speech guard
  const speakingRef = useRef(false);
  const speak = useCallback((msg: string) => {
    if (speakingRef.current) return;
    speakingRef.current = true;
    Speech.stop();
    Speech.speak(msg, {
      rate: 1.0,
      pitch: 1.0,
      onDone: () => {
        speakingRef.current = false;
      },
      onStopped: () => {
        speakingRef.current = false;
      },
      onError: () => {
        speakingRef.current = false;
      },
    });
  }, []);

  // browser STT availability
  useEffect(() => {
    if (Platform.OS === "web") {
      const W = globalThis as any;
      const SR = W.SpeechRecognition || W.webkitSpeechRecognition;
      setSttAvailable(!!SR);
    }
  }, []);

  // global cleanup on unmount
  useEffect(() => {
    return () => {
      try {
        Speech.stop();
      } catch {}
      stopAll().catch(() => {});
      stopAutoReload();
    };
  }, []);

  // --------- reload helpers ----------

  const stopAutoReload = () => {
    if (retryTimerRef.current) {
      clearInterval(retryTimerRef.current);
      retryTimerRef.current = null;
    }
  };

  // Only reload iframe when Gradio is actually reachable
  const kickAutoReload = (maxAttempts = 30, intervalMs = 700) => {
    stopAutoReload();
    attemptsRef.current = 0;

    const tick = async () => {
      attemptsRef.current += 1;
      try {
        await ping(GRADIO_URL); // just reachability
        stopAutoReload();
        setRev((x) => x + 1); // single reload
        setLoading(false);
      } catch (err) {
        if (attemptsRef.current >= maxAttempts) {
          stopAutoReload();
          setLoading(false);
          Alert.alert(
            "Gradio not reachable",
            "Could not connect to the model server on localhost:7860. Is it running?"
          );
        }
      }
    };

    // run immediately, then repeat
    tick();
    retryTimerRef.current = setInterval(tick, intervalMs);
  };

  // --------- backend mode switching ----------

  useEffect(() => {
    let cancelled = false;

    async function boot(kind: "gradio" | "ocr") {
      setLoading(true);
      stopAutoReload();
      try {
        await switchMode(kind);
        const status = await fetchStatus();
        console.log("Backend status:", status);
      } catch (e) {
        console.error("switchMode failed:", e);
        if (!cancelled) {
          setLoading(false);
          Alert.alert(
            "Error",
            `Could not start ${
              kind === "gradio" ? "Vision Assist" : "Scan Text"
            }. Make sure the backend is running on localhost:8000.`
          );
        }
        return;
      }
      if (!cancelled) {
        // now wait for Gradio port to be reachable, then reload iframe once
        kickAutoReload();
      }
    }

    if (mode === "vision") {
      boot("gradio");
    } else if (mode === "ocr") {
      boot("ocr");
    } else if (mode === "voice" || mode === "idle") {
      stopAll().catch(() => {});
      stopAutoReload();
      setLoading(false);
    }

    return () => {
      cancelled = true;
    };
  }, [mode]);

  // --------- voice assist ----------

  const startListening = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

    if (Platform.OS === "web") {
      const W = globalThis as any;
      const SR = W.SpeechRecognition || W.webkitSpeechRecognition;
      if (!SR) {
        Alert.alert("Speech recognition not available in this browser.");
        return;
      }
      const rec = new SR();
      recognitionRef.current = rec;
      rec.lang = "en-US";
      rec.continuous = false;
      rec.interimResults = true;
      rec.onresult = (e: any) => {
        let text = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
          text += e.results[i][0].transcript;
        }
        setTranscript(text.trim());
      };
      rec.onend = () => setIsListening(false);
      rec.onerror = () => setIsListening(false);
      setTranscript("");
      setIsListening(true);
      rec.start();
    } else {
      Alert.alert(
        "Voice Assist",
        "Speech recognition isn’t enabled in Expo Go. It will work in a custom dev client / production build."
      );
    }
  }, []);

  const stopListening = useCallback(() => {
    if (Platform.OS === "web" && recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
    }
    setIsListening(false);
  }, []);

  // simple command: "scan text" → OCR mode
  useEffect(() => {
    const t = transcript.toLowerCase();
    if (!t) return;
    if (t.includes("help")) speak("Help opened.");
    if (t.includes("scan text")) setMode("ocr");
  }, [transcript, speak]);

  // --------- permission gate for voice camera ----------

  if (!perm) {
    return <View style={{ flex: 1, backgroundColor: "#1B263B" }} />;
  }

  if (!perm.granted) {
    return (
      <View style={styles.centerDark}>
        <Text style={{ color: "#fff", marginBottom: 12 }}>
          Camera access is required for Voice Assist.
        </Text>
        <Pressable style={styles.primaryBtn} onPress={requestPermission}>
          <Text style={styles.primaryBtnText}>Grant Permission</Text>
        </Pressable>
      </View>
    );
  }

  // --------- UI ----------

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>
          {mode === "ocr"
            ? "SCAN TEXT"
            : mode === "voice"
            ? "VOICE ASSIST"
            : mode === "vision"
            ? "VISION ASSIST"
            : "ASSISTANT"}
        </Text>
      </View>

      <View style={styles.previewBox}>
        {mode === "voice" ? (
          <CameraView
            ref={cameraRef}
            style={StyleSheet.absoluteFill}
            facing="back"
          />
        ) : mode === "vision" || mode === "ocr" ? (
          <ModelWebView url={url} loading={loading} />
        ) : (
          <View style={{ flex: 1, backgroundColor: "#1B263B" }} />
        )}
      </View>

      <View style={styles.modeBar}>
        <ModeBtn
          label="Vision"
          active={mode === "vision"}
          onPress={() => {
            Haptics.selectionAsync();
            setMode("vision");
          }}
        />

        <ModeBtn
          label="Voice Assist"
          active={mode === "voice"}
          onPress={async () => {
            Haptics.selectionAsync();
            if (isListening) stopListening();
            await stopAll().catch(() => {});
            setMode("voice");
          }}
        />

        <ModeBtn
          label="Scan Text"
          active={mode === "ocr"}
          onPress={() => {
            Haptics.selectionAsync();
            setMode("ocr");
          }}
        />
      </View>

      {mode === "voice" && (
        <View style={styles.voiceRow}>
          <Pressable
            onPress={isListening ? stopListening : startListening}
            style={[styles.micBtn, isListening && styles.micBtnActive]}
            disabled={!sttAvailable && Platform.OS !== "web"}
          >
            <MaterialIcons
              name={isListening ? "mic" : "mic-none"}
              size={28}
              color={isListening ? "#1B263B" : GOLD}
            />
          </Pressable>

          <View style={styles.voiceTextWrap}>
            <Text style={styles.voiceHint}>
              {sttAvailable || Platform.OS === "web"
                ? isListening
                  ? "Listening… speak now"
                  : "Tap the mic and speak"
                : "Mic requires native STT (Dev Client)"}
            </Text>
            {!!transcript && (
              <Text style={styles.voiceTranscript}>{transcript}</Text>
            )}
          </View>
        </View>
      )}
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
  voiceRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
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
});
