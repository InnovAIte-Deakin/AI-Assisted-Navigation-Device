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
import { Radius, Spacing, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";

type Stage = "join" | "connecting" | "session";

export default function HelperScreen() {
  const colors = useThemeColors();
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
      <View style={[s.screen, { backgroundColor: colors.background }]}>
        <View style={s.joinCard}>
          <Ionicons name="people-outline" size={48} color={colors.accent} style={{ marginBottom: Spacing.xs }} />
          <Text style={[s.title, { color: colors.text }]}>Join as Helper</Text>
          <Text style={[s.subtitle, { color: colors.textMuted }]}>
            Enter the session code shown on the WalkBuddy user's phone.
          </Text>

          <Text style={[s.label, { color: colors.textMuted }]}>Your name (optional)</Text>
          <TextInput
            style={[s.input, { backgroundColor: colors.surfaceElevated, color: colors.text }]}
            value={nameInput}
            onChangeText={setNameInput}
            placeholder="e.g. Alex"
            placeholderTextColor={colors.textMuted}
            autoCapitalize="words"
            returnKeyType="next"
          />

          <Text style={[s.label, { color: colors.textMuted }]}>Session code</Text>
          <TextInput
            style={[s.input, { backgroundColor: colors.surfaceElevated, color: colors.text }, s.codeInput, { color: colors.accent }]}
            value={codeInput}
            onChangeText={(v) => setCodeInput(v.toUpperCase())}
            placeholder="A1B2C3D4"
            placeholderTextColor={colors.textMuted}
            autoCapitalize="characters"
            maxLength={8}
            returnKeyType="go"
            onSubmitEditing={handleJoin}
          />

          {!!error && (
            <View style={s.errorRow}>
              <Ionicons name="alert-circle" size={16} color={colors.danger} />
              <Text style={[s.errorText, { color: colors.danger }]}>{error}</Text>
            </View>
          )}

          <Pressable
            style={[s.joinBtn, { backgroundColor: colors.accent }, stage === "connecting" && s.joinBtnDisabled]}
            onPress={handleJoin}
            disabled={stage === "connecting"}
          >
            {stage === "connecting" ? (
              <ActivityIndicator color={colors.accentText} />
            ) : (
              <>
                <Ionicons name="log-in-outline" size={20} color={colors.accentText} />
                <Text style={[s.joinBtnText, { color: colors.accentText }]}>Join Session</Text>
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
    <View style={[s.screen, { backgroundColor: colors.background }]}>
      {/* Header */}
      <View style={[s.header, { borderBottomColor: colors.border }]}>
        <Pressable onPress={handleDisconnect} style={s.backBtn}>
          <Ionicons name="log-out-outline" size={22} color={colors.danger} />
        </Pressable>
        <Text style={[s.headerTitle, { color: colors.text }]}>Helping — {sessionId}</Text>
        <View style={[s.dot, { backgroundColor: userConnected ? colors.success : colors.textMuted }]} />
      </View>

      {/* User status */}
      <View style={[s.statusBar, { backgroundColor: colors.surface }]}>
        <Text style={[s.statusText, { color: colors.textMuted }]}>
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
          style={[s.guidanceInput, { backgroundColor: colors.surfaceElevated, color: colors.text }]}
          value={guidanceText}
          onChangeText={setGuidanceText}
          placeholder="Type guidance… (e.g. Turn left, Stop)"
          placeholderTextColor={colors.textMuted}
          returnKeyType="send"
          onSubmitEditing={handleSendGuidance}
        />
        <Pressable
          style={[s.sendBtn, { backgroundColor: colors.accent }, !guidanceText.trim() && s.sendBtnDisabled]}
          onPress={handleSendGuidance}
          disabled={!guidanceText.trim()}
        >
          <Ionicons name="send" size={20} color={colors.accentText} />
        </Pressable>
      </View>

      {/* Sent message history */}
      {sentMessages.length > 0 && (
        <ScrollView style={[s.historyBox, { backgroundColor: colors.surface }]} contentContainerStyle={{ padding: Spacing.md, gap: Spacing.sm }}>
          <Text style={[s.historyLabel, { color: colors.textMuted }]}>SENT MESSAGES</Text>
          {sentMessages.map((msg, i) => (
            <View key={i} style={s.historyItem}>
              <Ionicons name="checkmark-circle" size={14} color={colors.success} />
              <Text style={[s.historyText, { color: colors.textMuted }]}>{msg}</Text>
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
  },
  // ── Join ──
  joinCard: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: Spacing.xxxl,
  },
  title: {
    fontSize: Typography.size.xl,
    fontWeight: "800",
    marginBottom: Spacing.xs,
  },
  subtitle: {
    fontSize: Typography.size.sm,
    textAlign: "center",
    marginBottom: Spacing.xxl,
    maxWidth: 320,
  },
  label: {
    fontSize: Typography.size.xs,
    fontWeight: "700",
    alignSelf: "flex-start",
    marginBottom: Spacing.xs,
    width: "100%",
    maxWidth: 360,
  },
  input: {
    borderRadius: Radius.sm,
    fontSize: Typography.size.base,
    paddingHorizontal: 14,
    paddingVertical: Spacing.md,
    marginBottom: Spacing.lg,
    width: "100%",
    maxWidth: 360,
  },
  codeInput: {
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: 6,
    textAlign: "center",
  },
  errorRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: Spacing.md,
  },
  errorText: {
    fontSize: 13,
  },
  joinBtn: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: Spacing.xxxl,
    borderRadius: 10,
    gap: Spacing.xs,
    marginTop: Spacing.xs,
    minWidth: 200,
    justifyContent: "center",
  },
  joinBtnDisabled: {
    opacity: 0.6,
  },
  joinBtnText: {
    fontSize: Typography.size.base,
    fontWeight: "800",
  },
  // ── Session ──
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: Spacing.lg,
    paddingTop: Platform.OS === "ios" ? 52 : Spacing.lg,
    paddingBottom: Spacing.md,
    borderBottomWidth: 1,
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
    fontSize: Typography.size.base,
    fontWeight: "700",
    letterSpacing: 1,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  statusBar: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.xs,
  },
  statusText: {
    fontSize: Typography.size.xs,
  },
  feedBox: {
    flex: 1,
    backgroundColor: "#000",
    margin: Spacing.md,
    borderRadius: Radius.md,
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
    gap: Spacing.md,
  },
  feedPlaceholderText: {
    color: "#555",
    fontSize: Typography.size.sm,
    textAlign: "center",
  },
  guidanceRow: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.xs,
    gap: Spacing.xs,
  },
  guidanceInput: {
    flex: 1,
    borderRadius: 10,
    fontSize: 15,
    paddingHorizontal: 14,
    paddingVertical: Spacing.md,
  },
  sendBtn: {
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
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.xs,
    borderRadius: 10,
  },
  historyLabel: {
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
    fontSize: 13,
  },
});
