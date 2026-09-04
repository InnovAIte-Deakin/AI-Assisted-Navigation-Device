import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  PermissionsAndroid,
  Platform,
  Pressable,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { router, useFocusEffect } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import * as Speech from "expo-speech";
import { RtcSurfaceView } from "react-native-agora";

import { agoraCallService } from "@/services/agoraCallService";
import {
  AssistanceSession,
  createAssistanceSession,
  createHelperInviteUrl,
  endAssistanceSession,
} from "@/services/agoraSessionService";
import { Radius, Spacing, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";
import { PageHeader } from "@/components/ui/PageHeader";

type CallState = "starting" | "waiting" | "active" | "ended" | "error";

export default function AskAFriendWebScreen() {
  const colors = useThemeColors();

  const [session, setSession] = useState<AssistanceSession | null>(null);
  const [callState, setCallState] = useState<CallState>("starting");
  const [remoteUid, setRemoteUid] = useState<number | null>(null);
  const [muted, setMuted] = useState(false);
  const [frontCamera, setFrontCamera] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sessionRef = useRef<AssistanceSession | null>(null);
  const focusedRef = useRef(false);
  const mountedRef = useRef(true);
  const startingRef = useRef(false);
  const endingRef = useRef(false);

  const speak = useCallback((message: string) => {
    if (Platform.OS === "web") return;
    Speech.stop();
    Speech.speak(message, { rate: 0.85, volume: 1.0 });
  }, []);

  const requestAgoraPermissions = useCallback(async () => {
    if (Platform.OS !== "android") return true;

    const permissions = await PermissionsAndroid.requestMultiple([
      PermissionsAndroid.PERMISSIONS.CAMERA,
      PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
    ]);

    return (
      permissions[PermissionsAndroid.PERMISSIONS.CAMERA] ===
        PermissionsAndroid.RESULTS.GRANTED &&
      permissions[PermissionsAndroid.PERMISSIONS.RECORD_AUDIO] ===
        PermissionsAndroid.RESULTS.GRANTED
    );
  }, []);

  const invalidateSession = useCallback(async (current: AssistanceSession | null) => {
    if (!current) return;
    try {
      await endAssistanceSession(current);
    } catch (err) {
      console.log("[AskAFriend] Session close error:", err);
    }
  }, []);

  const teardownCall = useCallback(
    async (updateUi = true) => {
      if (endingRef.current) return;
      endingRef.current = true;

      const currentSession = sessionRef.current;
      sessionRef.current = null;

      // Release the complete engine, not only the channel. This is important
      // because a new tab focus must get a fresh engine + fresh callbacks.
      agoraCallService.cleanup();
      Speech.stop();

      if (updateUi && mountedRef.current) {
        setSession(null);
        setRemoteUid(null);
        setMuted(false);
        setFrontCamera(false);
        setError(null);
        setCallState("ended");
      }

      await invalidateSession(currentSession);
      endingRef.current = false;
    },
    [invalidateSession],
  );

  const initializeAgora = useCallback(
    async (appId: string) => {
      const granted = await requestAgoraPermissions();
      if (!granted) {
        throw new Error(
          "Camera and microphone permissions are required for an assistance call.",
        );
      }

      // Defensive reset. A previous tab visit must never leave a singleton
      // engine behind with callbacks belonging to the old screen lifecycle.
      agoraCallService.cleanup();

      agoraCallService.initialize(appId, {
        onJoined: () => {
          if (!mountedRef.current || !focusedRef.current) return;
          setCallState("waiting");
          setError(null);
          speak("Assistance call started. You can now invite a helper.");
        },

        onRemoteUserJoined: (uid) => {
          if (!mountedRef.current || !focusedRef.current) return;
          console.log("[AskAFriend] Helper joined:", uid);
          setRemoteUid(uid);
          setCallState("active");
          speak("Your helper has joined the call.");
        },

        onRemoteUserLeft: (uid) => {
          console.log("[AskAFriend] Helper left:", uid);
          if (!mountedRef.current || !focusedRef.current) return;
          setRemoteUid(null);
          setCallState("waiting");
          speak("Your helper has left. You can invite another helper.");
        },

        onFirstRemoteVideoFrame: (uid, width, height) => {
          console.log("[AskAFriend] Helper video ready:", { uid, width, height });
        },

        onError: (code, message) => {
          console.log("[AskAFriend] Agora error:", code, message);
          if (!mountedRef.current || !focusedRef.current) return;
          setError(`Video call error ${code}${message ? `: ${message}` : ""}`);
        },
      });

      // agoraCallService initializes the preview and switches once to rear.
      setFrontCamera(false);
    },
    [requestAgoraPermissions, speak],
  );

  const startAssistanceCall = useCallback(async () => {
    if (Platform.OS === "web" || startingRef.current || endingRef.current) return;

    startingRef.current = true;

    // Every start is a genuinely new secure call.
    const staleSession = sessionRef.current;
    sessionRef.current = null;
    agoraCallService.cleanup();
    if (staleSession) void invalidateSession(staleSession);

    if (mountedRef.current) {
      setSession(null);
      setRemoteUid(null);
      setMuted(false);
      setFrontCamera(false);
      setError(null);
      setCallState("starting");
    }

    try {
      console.log("[AskAFriend] Creating Agora session...");
      const newSession = await createAssistanceSession();

      // The user may have changed tabs while the network request was running.
      if (!mountedRef.current || !focusedRef.current) {
        await invalidateSession(newSession);
        return;
      }

      console.log("[AskAFriend] Session created:", newSession.sessionId);
      sessionRef.current = newSession;
      setSession(newSession);

      await initializeAgora(newSession.appId);

      if (!mountedRef.current || !focusedRef.current) {
        agoraCallService.cleanup();
        sessionRef.current = null;
        await invalidateSession(newSession);
        return;
      }

      agoraCallService.join({
        token: newSession.token,
        channelName: newSession.channelName,
        uid: newSession.uid,
      });

      console.log("[AskAFriend] Agora join requested:", newSession.channelName);
    } catch (err) {
      console.log("[AskAFriend] Start call error:", err);
      const message =
        err instanceof Error ? err.message : "Unable to start assistance call";

      agoraCallService.cleanup();
      const failedSession = sessionRef.current;
      sessionRef.current = null;
      if (failedSession) void invalidateSession(failedSession);

      if (mountedRef.current && focusedRef.current) {
        setSession(null);
        setRemoteUid(null);
        setError(message);
        setCallState("error");
        Alert.alert("Assistance Call Failed", message);
      }
    } finally {
      startingRef.current = false;
    }
  }, [initializeAgora, invalidateSession]);

  const shareHelperInvite = useCallback(async () => {
    const current = sessionRef.current;
    if (!current) {
      Alert.alert("Session Not Ready", "Please wait for the call to finish starting.");
      return;
    }

    try {
      const helperUrl = createHelperInviteUrl(current);
      console.log("[AskAFriend] Helper URL:", helperUrl);
      await Share.share({
        title: "WalkBuddy Assistance Call",
        message: `Please help me through WalkBuddy.\n\n${helperUrl}`,
      });
    } catch (err) {
      console.log("[AskAFriend] Share error:", err);
      Alert.alert("Unable to Share", "The helper invitation could not be shared.");
    }
  }, []);

  const toggleMute = useCallback(() => {
    if (callState !== "waiting" && callState !== "active") return;
    const next = !muted;
    agoraCallService.setMuted(next);
    setMuted(next);
    speak(next ? "Microphone muted." : "Microphone unmuted.");
  }, [callState, muted, speak]);

  const switchCamera = useCallback(() => {
    if (callState !== "waiting" && callState !== "active") return;
    agoraCallService.switchCamera();
    const next = !frontCamera;
    setFrontCamera(next);
    speak(next ? "Front camera selected." : "Rear camera selected.");
  }, [callState, frontCamera, speak]);

  const handleEndCall = useCallback(async () => {
    await teardownCall(true);
    speak("Assistance call ended.");
  }, [speak, teardownCall]);

  const handleBack = useCallback(async () => {
    await teardownCall(false);
    if ((router as any)?.canGoBack?.()) router.back();
    else router.replace("/" as any);
  }, [teardownCall]);

  // Expo Router tabs commonly stay mounted. Focus/blur, rather than mount/unmount,
  // therefore owns the call lifecycle.
  useFocusEffect(
    useCallback(() => {
      focusedRef.current = true;
      void startAssistanceCall();

      return () => {
        focusedRef.current = false;
        void teardownCall(false);
      };
    }, [startAssistanceCall, teardownCall]),
  );

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      focusedRef.current = false;
      Speech.stop();
      agoraCallService.cleanup();
      const current = sessionRef.current;
      sessionRef.current = null;
      if (current) void invalidateSession(current);
    };
  }, [invalidateSession]);

  if (Platform.OS === "web") {
    return (
      <View style={[styles.screen, { backgroundColor: colors.background }]}>
        <PageHeader title="Ask a Friend" onBackPress={() => router.back()} />
        <View style={[styles.webMessageCard, { backgroundColor: colors.surface }]}>
          <Ionicons name="phone-portrait-outline" size={48} color={colors.accent} />
          <Text style={[styles.webMessageTitle, { color: colors.text }]}>Start the call from WalkBuddy</Text>
          <Text style={[styles.webMessageText, { color: colors.textMuted }]}>
            The WalkBuddy user starts the secure assistance call from the mobile app. The helper joins using the temporary invitation link.
          </Text>
        </View>
      </View>
    );
  }

  const inCall = callState === "waiting" || callState === "active";
  const showStatusCard = !inCall;

  return (
    <View style={[styles.screen, { backgroundColor: colors.background }]}>
      <PageHeader title="Ask a Friend" onBackPress={handleBack} />

      <ScrollView style={styles.scroll} contentContainerStyle={styles.content} accessibilityLabel="Ask a Friend assistance call">
        {showStatusCard && (
          <View style={[styles.statusCard, { backgroundColor: colors.surface }]}>
            <View style={[styles.statusDot, { backgroundColor: callState === "error" ? colors.danger : colors.textMuted }]} />
            <View style={styles.statusTextContainer}>
              <Text style={[styles.statusTitle, { color: colors.text }]}>
                {callState === "starting"
                  ? "Starting assistance call"
                  : callState === "error"
                    ? "Unable to start call"
                    : "Assistance call ended"}
              </Text>
              <Text style={[styles.statusSubtitle, { color: colors.textMuted }]}>
                {callState === "starting"
                  ? "Preparing a secure video call..."
                  : callState === "error"
                    ? error || "The assistance call could not be started."
                    : "Call not active."}
              </Text>
            </View>
            {callState === "starting" && <ActivityIndicator color={colors.accent} />}
          </View>
        )}

        <View style={[styles.videoCard, { backgroundColor: colors.surface }]}>
          <View style={styles.cardHeader}>
            <Ionicons name="videocam-outline" size={24} color={colors.accent} />
            <Text style={[styles.cardTitle, { color: colors.text }]}>Video assistance</Text>
          </View>

          <View style={styles.videoContainer}>
            {remoteUid !== null ? (
              <RtcSurfaceView
                key={`helper-${remoteUid}`}
                style={styles.remoteVideo}
                canvas={{ uid: remoteUid }}
              />
            ) : (
              <View style={styles.waitingVideo}>
                {callState === "starting" ? (
                  <ActivityIndicator size="large" color="#888" />
                ) : (
                  <Ionicons name="person-circle-outline" size={72} color="#777" />
                )}
                <Text style={styles.waitingVideoTitle}>
                  {callState === "starting"
                    ? "Starting call"
                    : inCall
                      ? "Waiting for helper"
                      : "Call not active"}
                </Text>
                <Text style={styles.waitingVideoText}>
                  {callState === "starting"
                    ? "Preparing camera and microphone..."
                    : inCall
                      ? "Invite someone you trust to join this assistance call."
                      : "Start a new assistance call when you need help."}
                </Text>
              </View>
            )}
          </View>

          {inCall && (
            <>
              <View style={styles.cameraStatus}>
                <Ionicons name="camera-outline" size={17} color={colors.textMuted} />
                <Text style={[styles.cameraStatusText, { color: colors.textMuted }]}>
                  {frontCamera ? "Your front camera is being shared" : "Your rear camera is being shared"}
                </Text>
              </View>

              <View style={styles.inlineControls}>
                {remoteUid === null && session && (
                  <CallControl
                    label="Invite"
                    icon="share-social-outline"
                    onPress={shareHelperInvite}
                    backgroundColor={colors.accent}
                    iconColor={colors.accentText}
                    textColor={colors.text}
                    accessibilityLabel="Invite a helper"
                  />
                )}

                <CallControl
                  label={muted ? "Unmute" : "Mute"}
                  icon={muted ? "mic-off" : "mic"}
                  onPress={toggleMute}
                  backgroundColor={muted ? colors.danger + "25" : colors.background}
                  iconColor={muted ? colors.danger : colors.text}
                  textColor={colors.text}
                  accessibilityLabel={muted ? "Unmute microphone" : "Mute microphone"}
                />

                <CallControl
                  label="Switch"
                  icon="camera-reverse-outline"
                  onPress={switchCamera}
                  backgroundColor={colors.background}
                  iconColor={colors.text}
                  textColor={colors.text}
                  accessibilityLabel="Switch camera"
                />

                <CallControl
                  label="End"
                  icon="call"
                  onPress={() => void handleEndCall()}
                  backgroundColor={colors.danger}
                  iconColor="#FFFFFF"
                  textColor={colors.danger}
                  accessibilityLabel="End assistance call"
                  rotateIcon
                />
              </View>
            </>
          )}
        </View>

        {(callState === "ended" || callState === "error") && (
          <Pressable
            style={[styles.restartButton, { backgroundColor: colors.accent }]}
            onPress={() => void startAssistanceCall()}
            accessibilityRole="button"
            accessibilityLabel="Start a new assistance call"
          >
            <Ionicons name="call-outline" size={22} color={colors.accentText} />
            <Text style={[styles.restartButtonText, { color: colors.accentText }]}>Start Assistance Again</Text>
          </Pressable>
        )}
      </ScrollView>
    </View>
  );
}

type CallControlProps = {
  label: string;
  icon: React.ComponentProps<typeof Ionicons>["name"];
  onPress: () => void;
  backgroundColor: string;
  iconColor: string;
  textColor: string;
  accessibilityLabel: string;
  rotateIcon?: boolean;
};

function CallControl({
  label,
  icon,
  onPress,
  backgroundColor,
  iconColor,
  textColor,
  accessibilityLabel,
  rotateIcon = false,
}: CallControlProps) {
  return (
    <Pressable
      style={styles.control}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
    >
      <View style={[styles.controlCircle, { backgroundColor }]}>
        <Ionicons
          name={icon}
          size={27}
          color={iconColor}
          style={rotateIcon ? { transform: [{ rotate: "135deg" }] } : undefined}
        />
      </View>
      <Text style={[styles.controlLabel, { color: textColor }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  scroll: { flex: 1 },
  content: { paddingBottom: Spacing.xxxl },

  statusCard: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: Spacing.lg,
    marginTop: Spacing.md,
    padding: Spacing.md,
    borderRadius: Radius.md,
  },
  statusDot: { width: 10, height: 10, borderRadius: 5, marginRight: Spacing.md },
  statusTextContainer: { flex: 1 },
  statusTitle: { fontSize: Typography.size.base, fontWeight: "600" },
  statusSubtitle: { marginTop: 2, fontSize: Typography.size.xs, lineHeight: 18 },

  videoCard: {
    marginHorizontal: Spacing.lg,
    marginTop: Spacing.lg,
    padding: Spacing.md,
    borderRadius: Radius.md,
  },
  cardHeader: { flexDirection: "row", alignItems: "center", gap: Spacing.sm, marginBottom: Spacing.md },
  cardTitle: { fontSize: Typography.size.lg, fontWeight: "700" },
  videoContainer: {
    width: "100%",
    aspectRatio: 4 / 3,
    borderRadius: Radius.md,
    overflow: "hidden",
    backgroundColor: "#101010",
  },
  remoteVideo: { width: "100%", height: "100%" },
  waitingVideo: { flex: 1, alignItems: "center", justifyContent: "center", padding: Spacing.lg },
  waitingVideoTitle: { marginTop: Spacing.sm, color: "#FFFFFF", fontSize: 20, fontWeight: "700", textAlign: "center" },
  waitingVideoText: { marginTop: Spacing.xs, color: "#A0A0A0", fontSize: 14, lineHeight: 20, textAlign: "center" },
  cameraStatus: { flexDirection: "row", justifyContent: "center", alignItems: "center", gap: 6, paddingTop: Spacing.sm },
  cameraStatusText: { fontSize: Typography.size.xs },

  inlineControls: {
    flexDirection: "row",
    justifyContent: "space-evenly",
    alignItems: "flex-start",
    flexWrap: "wrap",
    gap: Spacing.sm,
    paddingTop: Spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "rgba(128,128,128,0.25)",
    marginTop: Spacing.md,
  },
  control: { minWidth: 62, alignItems: "center", paddingVertical: 4 },
  controlCircle: { width: 54, height: 54, borderRadius: 27, alignItems: "center", justifyContent: "center" },
  controlLabel: { marginTop: 6, fontSize: 12, fontWeight: "600", textAlign: "center" },

  restartButton: {
    marginHorizontal: Spacing.lg,
    marginTop: Spacing.lg,
    minHeight: 54,
    borderRadius: Radius.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: Spacing.sm,
    paddingHorizontal: Spacing.lg,
  },
  restartButtonText: { fontSize: Typography.size.base, fontWeight: "700" },

  webMessageCard: { margin: Spacing.lg, padding: Spacing.xl, borderRadius: Radius.md, alignItems: "center" },
  webMessageTitle: { marginTop: Spacing.md, fontSize: Typography.size.lg, fontWeight: "700", textAlign: "center" },
  webMessageText: { marginTop: Spacing.sm, fontSize: Typography.size.base, lineHeight: 22, textAlign: "center" },
});