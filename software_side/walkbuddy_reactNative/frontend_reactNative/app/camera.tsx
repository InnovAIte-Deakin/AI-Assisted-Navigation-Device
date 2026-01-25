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
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
  ScrollView,
  useWindowDimensions,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter, useLocalSearchParams } from "expo-router";

import ModelWebView from "../src/components/ModelWebView";
import { API_BASE } from "../src/config";
import HomeHeader from "./HomeHeader";
import Footer from "./Footer";

const tokens = {
  bg: "#0D1B2A",
  card: "#111",
  gold: "#FCA311",
  text: "#E0E1DD",
};

type Mode = "idle" | "vision" | "voice" | "ocr";

export default function CameraAssistScreen() {
  const router = useRouter();
  const { width, height } = useWindowDimensions();

  const contentWidth = useMemo(() => {
    const padding = 24;
    const max = 720;
    return Math.min(max, Math.max(320, width - padding * 2));
  }, [width]);

  const [mode, setMode] = useState<Mode>("voice");
  const { mode: modeParam } =
    useLocalSearchParams<{ mode?: "vision" | "voice" | "ocr" }>();

  useEffect(() => {
    if (modeParam === "vision" || modeParam === "voice" || modeParam === "ocr") {
      setMode(modeParam);
    }
  }, [modeParam]);

  const [perm, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);

  const [loading, setLoading] = useState(false);
  const [rev, setRev] = useState(0);

  const url = useMemo(() => {
    if (mode === "vision") return `${API_BASE}/vision/?v=${rev}`;
    if (mode === "ocr") return `${API_BASE}/ocr/?v=${rev}`;
    return "";
  }, [mode, rev]);

  useEffect(() => {
    if (mode === "vision" || mode === "ocr") {
      setLoading(true);
      setRev((x) => x + 1);
      const t = setTimeout(() => setLoading(false), 800);
      return () => clearTimeout(t);
    }
    setLoading(false);
  }, [mode]);

  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [sttAvailable, setSttAvailable] = useState(false);
  const recognitionRef = useRef<any>(null);

  const speakingRef = useRef(false);
  const speak = useCallback((msg: string) => {
    if (speakingRef.current) return;
    speakingRef.current = true;
    Speech.stop();
    Speech.speak(msg, {
      onDone: () => (speakingRef.current = false),
      onStopped: () => (speakingRef.current = false),
      onError: () => (speakingRef.current = false),
    });
  }, []);

  useEffect(() => {
    if (Platform.OS === "web") {
      const W = globalThis as any;
      setSttAvailable(!!(W.SpeechRecognition || W.webkitSpeechRecognition));
    }
  }, []);

  useEffect(() => {
    return () => {
      try {
        Speech.stop();
      } catch {}
    };
  }, []);

  const startListening = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

    if (Platform.OS === "web") {
      const W = globalThis as any;
      const SR = W.SpeechRecognition || W.webkitSpeechRecognition;
      if (!SR) {
        Alert.alert("Speech recognition not available.");
        return;
      }

      const rec = new SR();
      recognitionRef.current = rec;
      rec.lang = "en-US";
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
        "Speech recognition requires a custom dev client."
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

  useEffect(() => {
    const t = transcript.toLowerCase();
    if (!t) return;
    if (t.includes("help")) speak("Help opened.");
    if (t.includes("scan text")) setMode("ocr");
  }, [transcript, speak]);

  const previewHeight = useMemo(() => {
    const h = Math.round(height * 0.52);
    return Math.max(260, Math.min(520, h));
  }, [height]);

  if (!perm) {
    return <View style={{ flex: 1, backgroundColor: tokens.bg }} />;
  }

  if (!perm.granted) {
    return (
      <SafeAreaView style={styles.screen} edges={["top"]}>
        <View style={[styles.content, { width: contentWidth }]}>
          <HomeHeader
            greeting="Hi!"
            appTitle="WalkBuddy"
            onPressProfile={() => router.push("/profile")}
            showDivider
            showLocation
          />

          <View style={styles.centerCard}>
            <Text style={styles.centerText}>
              Camera access is required for Voice Assist.
            </Text>

            <Pressable style={styles.primaryBtn} onPress={requestPermission}>
              <Text style={styles.primaryBtnText}>Grant Permission</Text>
            </Pressable>
          </View>

          <Footer />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.screen} edges={["top"]}>
      <View style={[styles.content, { width: contentWidth }]}>
        <HomeHeader
          greeting="Hi!"
          appTitle="WalkBuddy"
          onPressProfile={() => router.push("/profile")}
          showDivider
          showLocation
        />

        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.modeTitleRow}>
            <Text style={styles.modeTitle}>
              {mode === "ocr"
                ? "SCAN TEXT"
                : mode === "voice"
                ? "VOICE ASSIST"
                : mode === "vision"
                ? "VISION ASSIST"
                : "ASSISTANT"}
            </Text>
          </View>

          <View style={[styles.previewBox, { height: previewHeight }]}>
            {mode === "voice" ? (
              <CameraView
                ref={cameraRef}
                style={StyleSheet.absoluteFill}
                facing="back"
              />
            ) : mode === "vision" || mode === "ocr" ? (
              <ModelWebView url={url} loading={loading} />
            ) : null}
          </View>

          <View style={styles.modeBar}>
            <ModeBtn
              label="Vision"
              active={mode === "vision"}
              onPress={() => setMode("vision")}
            />
            <ModeBtn
              label="Voice Assist"
              active={mode === "voice"}
              onPress={() => {
                if (isListening) stopListening();
                setMode("voice");
              }}
            />
            <ModeBtn
              label="Scan Text"
              active={mode === "ocr"}
              onPress={() => setMode("ocr")}
            />
          </View>

          {mode === "voice" && (
            <View style={styles.voiceRow}>
              <Pressable
                onPress={isListening ? stopListening : startListening}
                style={[styles.micBtn, isListening && styles.micBtnActive]}
              >
                <MaterialIcons
                  name={isListening ? "mic" : "mic-none"}
                  size={28}
                  color={isListening ? tokens.bg : tokens.gold}
                />
              </Pressable>

              <View style={styles.voiceTextWrap}>
                <Text style={styles.voiceHint}>
                  {isListening ? "Listening…" : "Tap the mic and speak"}
                </Text>
                {!!transcript && (
                  <Text style={styles.voiceTranscript}>{transcript}</Text>
                )}
              </View>
            </View>
          )}
        </ScrollView>

        <Footer />
      </View>
    </SafeAreaView>
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
  screen: {
    flex: 1,
    backgroundColor: tokens.bg,
    alignItems: "center",
  },
  content: {
    flex: 1,
    paddingHorizontal: 12,
    paddingTop: 8,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 16,
  },
  modeTitleRow: {
    paddingHorizontal: 14,
    paddingTop: 2,
    paddingBottom: 10,
  },
  modeTitle: {
    color: tokens.gold,
    fontSize: 18,
    fontWeight: "900",
  },
  previewBox: {
    width: "100%",
    borderRadius: 14,
    overflow: "hidden",
    backgroundColor: tokens.card,
    borderWidth: 2,
    borderColor: tokens.gold,
  },
  modeBar: {
    flexDirection: "row",
    gap: 10,
    paddingTop: 12,
    paddingBottom: 8,
  },
  modeBtn: {
    flex: 1,
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 12,
    paddingVertical: 10,
    alignItems: "center",
    backgroundColor: tokens.card,
  },
  modeBtnActive: { backgroundColor: tokens.gold },
  modeBtnText: { color: tokens.gold, fontWeight: "800" },
  modeBtnTextActive: { color: tokens.bg },
  voiceRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  micBtn: {
    width: 56,
    height: 56,
    borderRadius: 28,
    borderWidth: 2,
    borderColor: tokens.gold,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: tokens.card,
  },
  micBtnActive: { backgroundColor: tokens.gold },
  voiceTextWrap: { flex: 1 },
  voiceHint: { color: tokens.gold, fontWeight: "800" },
  voiceTranscript: { color: tokens.text, marginTop: 6 },
  centerCard: {
    flex: 1,
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 14,
    backgroundColor: tokens.card,
    padding: 16,
    marginTop: 14,
    justifyContent: "center",
    alignItems: "center",
    gap: 12,
  },
  centerText: { color: tokens.text, fontWeight: "700", textAlign: "center" },
  primaryBtn: {
    backgroundColor: tokens.gold,
    paddingVertical: 12,
    paddingHorizontal: 18,
    borderRadius: 12,
  },
  primaryBtnText: { color: tokens.bg, fontWeight: "900" },
});
