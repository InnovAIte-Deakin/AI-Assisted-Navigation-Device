// app/helper.tsx
// Helper / Guide interface — runs in any web browser.
// Enter the session code to see the user's camera and send guidance.

import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams } from "expo-router";
import { collaborationService, normalizeCode } from "@/src/utils/collaboration";
import { API_BASE } from "@/src/config";

type Stage = "join" | "connecting" | "session";

export default function HelperScreen() {
  const params = useLocalSearchParams<{ code?: string }>();
  const [stage, setStage] = useState<Stage>("join");
  const [codeInput, setCodeInput] = useState(
    params.code ? normalizeCode(params.code) : ""
  );
  const [nameInput, setNameInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [userConnected, setUserConnected] = useState(false);

  // Latest frame from user
  const [frameUri, setFrameUri] = useState<string | null>(null);
  const frameCountRef = useRef(0);
  const [frameCount, setFrameCount] = useState(0);

  // Guidance
  const [guidanceText, setGuidanceText] = useState("");
  const [sentMessages, setSentMessages] = useState<string[]>([]);

  const wsServiceRef = useRef(collaborationService);

  // ── Register message handlers on mount ───────────────────────────────────
  useEffect(() => {
    const ws = wsServiceRef.current;

    const unsubConnected = ws.onMessage("connected", (msg) => {
      clearTimeout((ws as any)._helperJoinTimeout);
      const alreadyHasUser = (msg as any).user_connected;
      setUserConnected(!!alreadyHasUser);
      setStage("session");
      setError(null);
    });

    const unsubUserConnected = ws.onMessage("user_connected", () => {
      setUserConnected(true);
    });

    const unsubUserDisconnected = ws.onMessage("user_disconnected", () => {
      setUserConnected(false);
      setFrameUri(null);
    });

    const unsubFrame = ws.onMessage("frame", (msg) => {
      const img = (msg as any).image || (msg as any).data;
      if (img) {
        setFrameUri(img.startsWith("data:") ? img : `data:image/jpeg;base64,${img}`);
        frameCountRef.current += 1;
        // Update displayed counter only every 10 frames to avoid re-render spam
        if (frameCountRef.current % 10 === 0) {
          setFrameCount(frameCountRef.current);
        }
      }
    });

    return () => {
      unsubConnected();
      unsubUserConnected();
      unsubUserDisconnected();
      unsubFrame();
      ws.disconnect();
    };
  }, []);

  // ── Join session ──────────────────────────────────────────────────────────
  const handleJoin = async () => {
    const code = normalizeCode(codeInput.trim());
    if (code.length !== 8) {
      setError("Session code must be 8 characters.");
      return;
    }

    setError(null);
    setStage("connecting");
    setSessionId(code);

    // If we don't receive the "connected" confirmation within 5s, the session doesn't exist
    const timeout = setTimeout(() => {
      wsServiceRef.current.disconnect();
      setError("Session not found. Make sure the WalkBuddy user has the app open.");
      setStage("join");
      setSessionId(null);
    }, 5000);

    // Store timeout so the "connected" handler can cancel it
    (wsServiceRef.current as any)._helperJoinTimeout = timeout;

    try {
      await wsServiceRef.current.connect(code, "guide");
      const helperName = nameInput.trim() || "Helper";
      wsServiceRef.current.sendMessage("helper_info", { helper_name: helperName });
    } catch (err: any) {
      clearTimeout(timeout);
      setError("Session not found. Make sure the WalkBuddy user has the app open.");
      setStage("join");
      setSessionId(null);
    }
  };

  // ── Send guidance ─────────────────────────────────────────────────────────
  const handleSendGuidance = () => {
    const text = guidanceText.trim();
    if (!text) return;
    wsServiceRef.current.sendGuidance(text);
    setSentMessages((prev) => [text, ...prev].slice(0, 20));
    setGuidanceText("");
  };

  // ── Disconnect ────────────────────────────────────────────────────────────
  const handleDisconnect = () => {
    wsServiceRef.current.disconnect();
    setStage("join");
    setSessionId(null);
    setFrameUri(null);
    setUserConnected(false);
    setSentMessages([]);
    frameCountRef.current = 0;
    setFrameCount(0);
  };

  // ─────────────────────────────────────────────────────────────────────────
  // JOIN SCREEN
  // ─────────────────────────────────────────────────────────────────────────
  if (stage === "join" || stage === "connecting") {
    return (
      <View style={s.screen}>
        <View style={s.joinCard}>
          <Ionicons name="people-outline" size={48} color="#F9A826" style={{ marginBottom: 8 }} />
          <Text style={s.title}>Join as Helper</Text>
          <Text style={s.subtitle}>
            Enter the session code shown on the WalkBuddy user's phone.
          </Text>

          <Text style={s.label}>Your name (optional)</Text>
          <TextInput
            style={s.input}
            value={nameInput}
            onChangeText={setNameInput}
            placeholder="e.g. Alex"
            placeholderTextColor="#555"
            autoCapitalize="words"
            returnKeyType="next"
          />

          <Text style={s.label}>Session code</Text>
          <TextInput
            style={[s.input, s.codeInput]}
            value={codeInput}
            onChangeText={(v) => setCodeInput(v.toUpperCase())}
            placeholder="A1B2C3D4"
            placeholderTextColor="#555"
            autoCapitalize="characters"
            maxLength={8}
            returnKeyType="go"
            onSubmitEditing={handleJoin}
          />

          {!!error && (
            <View style={s.errorRow}>
              <Ionicons name="alert-circle" size={16} color="#FF6B6B" />
              <Text style={s.errorText}>{error}</Text>
            </View>
          )}

          <Pressable
            style={[s.joinBtn, stage === "connecting" && s.joinBtnDisabled]}
            onPress={handleJoin}
            disabled={stage === "connecting"}
          >
            {stage === "connecting" ? (
              <ActivityIndicator color="#1B263B" />
            ) : (
              <>
                <Ionicons name="log-in-outline" size={20} color="#1B263B" />
                <Text style={s.joinBtnText}>Join Session</Text>
              </>
            )}
          </Pressable>
        </View>
      </View>
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // SESSION SCREEN
  // ─────────────────────────────────────────────────────────────────────────
  return (
    <View style={s.screen}>
      {/* Header */}
      <View style={s.header}>
        <Pressable onPress={handleDisconnect} style={s.backBtn}>
          <Ionicons name="log-out-outline" size={22} color="#FF6B6B" />
        </Pressable>
        <Text style={s.headerTitle}>Helping — {sessionId}</Text>
        <View style={[s.dot, userConnected ? s.dotGreen : s.dotGray]} />
      </View>

      {/* User status */}
      <View style={s.statusBar}>
        <Text style={s.statusText}>
          {userConnected
            ? `User connected · ${frameCount} frames received`
            : "Waiting for user to connect…"}
        </Text>
      </View>

      {/* Camera feed */}
      <View style={s.feedBox}>
        {frameUri ? (
          Platform.OS === "web" ? (
            // On web use an <img> for low-latency updates
            <img
              src={frameUri}
              style={{ width: "100%", height: "100%", objectFit: "contain" }}
              alt="User camera"
            />
          ) : (
            <Image
              source={{ uri: frameUri }}
              style={s.feedImage}
              resizeMode="contain"
            />
          )
        ) : (
          <View style={s.feedPlaceholder}>
            <Ionicons name="videocam-off-outline" size={48} color="#444" />
            <Text style={s.feedPlaceholderText}>
              {userConnected ? "Waiting for camera frames…" : "No user connected yet"}
            </Text>
          </View>
        )}
      </View>

      {/* Send guidance */}
      <View style={s.guidanceRow}>
        <TextInput
          style={s.guidanceInput}
          value={guidanceText}
          onChangeText={setGuidanceText}
          placeholder="Type guidance… (e.g. Turn left, Stop)"
          placeholderTextColor="#555"
          returnKeyType="send"
          onSubmitEditing={handleSendGuidance}
        />
        <Pressable
          style={[s.sendBtn, !guidanceText.trim() && s.sendBtnDisabled]}
          onPress={handleSendGuidance}
          disabled={!guidanceText.trim()}
        >
          <Ionicons name="send" size={20} color="#1B263B" />
        </Pressable>
      </View>

      {/* Sent message history */}
      {sentMessages.length > 0 && (
        <ScrollView style={s.historyBox} contentContainerStyle={{ padding: 12, gap: 6 }}>
          <Text style={s.historyLabel}>SENT MESSAGES</Text>
          {sentMessages.map((msg, i) => (
            <View key={i} style={s.historyItem}>
              <Ionicons name="checkmark-circle" size={14} color="#4CAF50" />
              <Text style={s.historyText}>{msg}</Text>
            </View>
          ))}
        </ScrollView>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#1B263B",
  },
  // ── Join ──
  joinCard: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 32,
  },
  title: {
    color: "#FFF",
    fontSize: 24,
    fontWeight: "800",
    marginBottom: 8,
  },
  subtitle: {
    color: "#888",
    fontSize: 14,
    textAlign: "center",
    marginBottom: 24,
    maxWidth: 320,
  },
  label: {
    color: "#AAA",
    fontSize: 12,
    fontWeight: "700",
    alignSelf: "flex-start",
    marginBottom: 4,
    width: "100%",
    maxWidth: 360,
  },
  input: {
    backgroundColor: "#2A2A2A",
    borderRadius: 8,
    color: "#FFF",
    fontSize: 16,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 16,
    width: "100%",
    maxWidth: 360,
  },
  codeInput: {
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: 6,
    color: "#F9A826",
    textAlign: "center",
  },
  errorRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: 12,
  },
  errorText: {
    color: "#FF6B6B",
    fontSize: 13,
  },
  joinBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F9A826",
    paddingVertical: 14,
    paddingHorizontal: 32,
    borderRadius: 10,
    gap: 8,
    marginTop: 4,
    minWidth: 200,
    justifyContent: "center",
  },
  joinBtnDisabled: {
    opacity: 0.6,
  },
  joinBtnText: {
    color: "#1B263B",
    fontSize: 16,
    fontWeight: "800",
  },
  // ── Session ──
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingTop: Platform.OS === "ios" ? 52 : 16,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: "#2A2A2A",
    gap: 10,
  },
  backBtn: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    flex: 1,
    color: "#FFF",
    fontSize: 16,
    fontWeight: "700",
    letterSpacing: 1,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  dotGreen: { backgroundColor: "#4CAF50" },
  dotGray: { backgroundColor: "#555" },
  statusBar: {
    backgroundColor: "#0d1b2a",
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  statusText: {
    color: "#888",
    fontSize: 12,
  },
  feedBox: {
    flex: 1,
    backgroundColor: "#000",
    margin: 12,
    borderRadius: 12,
    overflow: "hidden",
    minHeight: 240,
  },
  feedImage: {
    width: "100%",
    height: "100%",
  },
  feedPlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
  },
  feedPlaceholderText: {
    color: "#555",
    fontSize: 14,
    textAlign: "center",
  },
  guidanceRow: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: 12,
    marginBottom: 8,
    gap: 8,
  },
  guidanceInput: {
    flex: 1,
    backgroundColor: "#2A2A2A",
    borderRadius: 10,
    color: "#FFF",
    fontSize: 15,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  sendBtn: {
    backgroundColor: "#F9A826",
    width: 46,
    height: 46,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  sendBtnDisabled: {
    opacity: 0.4,
  },
  historyBox: {
    maxHeight: 160,
    marginHorizontal: 12,
    marginBottom: 8,
    backgroundColor: "#0d1b2a",
    borderRadius: 10,
  },
  historyLabel: {
    color: "#444",
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 1,
    marginBottom: 6,
  },
  historyItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  historyText: {
    color: "#CCC",
    fontSize: 13,
  },
});
