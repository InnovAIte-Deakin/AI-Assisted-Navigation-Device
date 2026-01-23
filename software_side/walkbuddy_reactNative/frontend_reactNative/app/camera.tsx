// app/camera.tsx
import { MaterialIcons } from "@expo/vector-icons";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as Haptics from "expo-haptics";
import * as Speech from "expo-speech";
import React, {
  useCallback,
  useEffect,
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
  ActivityIndicator,
} from "react-native";

import { askTwoBrain, detectObject } from "../src/api/client";

const GOLD = "#f9b233";
const { height: SCREEN_H } = Dimensions.get("window");

type Mode = "idle" | "vision" | "voice" | "ocr";

export default function CameraAssistScreen() {
  const [mode, setMode] = useState<Mode>("vision");
  const [perm, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);

  // Thinking state
  const [processing, setProcessing] = useState(false);
  const [lastSpoken, setLastSpoken] = useState<string>("");

  // Voice Assist State
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const recognitionRef = useRef<any>(null);

  // --- TTS Helper ---
  const speak = useCallback((msg: string) => {
    Speech.stop();
    Speech.speak(msg, { rate: 1.0 });
  }, []);

  // --- API Functions ---

  const processFrame = async (blob: Blob) => {
    try {
      if (mode === "vision") {
        const res = await detectObject(blob);
        // Basic logic: Find highest confidence object close by
        // Filter repeats
        const best = res.events
          .filter(e => e.confidence > 0.5)
          .sort((a, b) => b.confidence - a.confidence)[0];

        if (best) {
          const msg = `${best.label} ${best.direction}`;
          if (msg !== lastSpoken) {
            speak(msg);
            setLastSpoken(msg);
            Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
          }
        }
      }
    } catch (e) {
      console.error("Vision error:", e);
    }
  };

  const processQuery = async (blob: Blob, question: string) => {
    try {
      setProcessing(true);
      speak("Thinking...");
      const res = await askTwoBrain(blob, question);
      setProcessing(false);

      if (!res.safe) {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
        speak(res.answer || "Unsafe to proceed.");
      } else {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        speak(res.answer || "I see nothing notable.");
      }
    } catch (e) {
      console.error("TwoBrain error:", e);
      setProcessing(false);
      speak("Sorry, I had trouble thinking.");
    }
  };

  // --- Vision Loop ---
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (mode === "vision" && !processing) {
      interval = setInterval(async () => {
        if (cameraRef.current) {
          try {
            // Take picture
            const photo = await cameraRef.current.takePictureAsync({ quality: 0.5, skipProcessing: true });
            if (photo?.uri) {
              // Convert to Blob
              const response = await fetch(photo.uri);
              const blob = await response.blob();
              await processFrame(blob);
            }
          } catch (err) {
            console.log("Vision loop err", err);
          }
        }
      }, 2000); // Every 2 seconds
    }
    return () => clearInterval(interval);
  }, [mode, processing, lastSpoken]);

  // --- Voice Logic ---
  const startListening = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setTranscript("");

    // Web Shim
    if (Platform.OS === "web") {
      const W = globalThis as any;
      const SR = W.SpeechRecognition || W.webkitSpeechRecognition;
      if (!SR) return alert("No Speech API");

      const rec = new SR();
      recognitionRef.current = rec;
      rec.lang = "en-US";
      rec.onresult = (e: any) => {
        const t = e.results[0][0].transcript;
        setTranscript(t);
      };
      rec.onend = () => {
        setIsListening(false);
        // Auto-send on end
        if (transcript) handleSendQuery(transcript);
      };
      rec.start();
      setIsListening(true);
    } else {
      // Native would use expo-speech-recognition or similar libs not installed.
      // Retaining original "alert" behavior or assuming dev client.
      // For MVP, we simulated with "Stop" button trigger.
      Alert.alert("Native STT", "Not fully implemented in this demo code. Use Web or tap 'Scan Text' for simulation.");
      // Simulating a query for testing
      setTranscript("What is ahead?");
      setIsListening(true);
      setTimeout(() => {
        setIsListening(false);
        handleSendQuery("What is in front of me?");
      }, 1500);
    }
  }, []);

  const handleSendQuery = async (text: string) => {
    if (!text) return;
    if (cameraRef.current) {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.5 });
      if (photo?.uri) {
        const response = await fetch(photo.uri);
        const blob = await response.blob();
        await processQuery(blob, text);
      }
    }
  };

  const stopListening = () => {
    if (recognitionRef.current) recognitionRef.current.stop();
    setIsListening(false);
    if (transcript) handleSendQuery(transcript);
  };

  // --- Permissions ---
  if (!perm || !perm.granted) {
    return (
      <View style={styles.centerDark}>
        <Text style={{ color: "white" }}>Camera Permission Required</Text>
        <Pressable onPress={requestPermission} style={styles.primaryBtn}><Text>Grant</Text></Pressable>
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>
          {mode === "vision" ? "VISION (Two-Brain)" : "VOICE ASSIST"}
        </Text>
        {processing && <ActivityIndicator color={GOLD} />}
      </View>

      <View style={styles.previewBox}>
        <CameraView ref={cameraRef} style={StyleSheet.absoluteFill} facing="back" />
        {/* Overlay for feedback */}
        <View style={styles.overlay}>
          <Text style={styles.overlayText}>{processing ? "Thinking..." : lastSpoken}</Text>
        </View>
      </View>

      <View style={styles.modeBar}>
        <ModeBtn label="Vision" active={mode === "vision"} onPress={() => { setMode("vision"); Haptics.selectionAsync(); }} />
        <ModeBtn label="Voice" active={mode === "voice"} onPress={() => { setMode("voice"); Haptics.selectionAsync(); }} />
      </View>

      {mode === "voice" && (
        <View style={styles.voiceRow}>
          <Pressable onPress={isListening ? stopListening : startListening} style={[styles.micBtn, isListening && styles.micBtnActive]}>
            <MaterialIcons name={isListening ? "mic" : "mic-none"} size={28} color={isListening ? "#1B263B" : GOLD} />
          </Pressable>
          <Text style={{ color: "white", flex: 1, marginLeft: 10 }}>
            {transcript || (processing ? "Processing..." : "Tap mic to ask")}
          </Text>
        </View>
      )}
    </View>
  );
}

function ModeBtn({ label, active, onPress }: any) {
  return (
    <Pressable onPress={onPress} style={[styles.modeBtn, active && styles.modeBtnActive]}>
      <Text style={[styles.modeBtnText, active && styles.modeBtnTextActive]}>{label}</Text>
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
    paddingTop: 40,
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
    backgroundColor: "#000",
    position: 'relative'
  },
  overlay: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: 'rgba(0,0,0,0.5)',
    padding: 10
  },
  overlayText: { color: 'white', textAlign: 'center', fontSize: 16 },
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
    padding: 20,
  },
  micBtn: {
    width: 60, height: 60, borderRadius: 30, borderWidth: 2, borderColor: GOLD,
    alignItems: 'center', justifyContent: 'center'
  },
  micBtnActive: { backgroundColor: GOLD },
  centerDark: { flex: 1, backgroundColor: "#1B263B", alignItems: 'center', justifyContent: 'center' },
  primaryBtn: { marginTop: 20, backgroundColor: GOLD, padding: 10, borderRadius: 5 }
});
