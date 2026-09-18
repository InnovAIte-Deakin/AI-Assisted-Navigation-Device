import AsyncStorage from "@react-native-async-storage/async-storage";
import { useRouter } from "expo-router";
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { AppState, Platform } from "react-native";

import { getSTTService } from "../services/STTService";
import { getTTSService, RiskLevel } from "../services/TTSService";
import { matchVoiceCommand, VOICE_COMMAND_HELP } from "../services/VoiceCommandService";

const STORAGE_KEY = "@walkbuddy/foreground-wake-enabled";
const WAKE_CLIP_MS = 5000;
const COMMAND_CLIP_MS = 4200;
const COMMAND_WINDOW_MS = 15000;
const WAKE_PHRASE_PATTERN = /\bhey(?:[\s,.;:!?-]+)(?:walk[\s-]*buddy|buddy)\b/i;

type WakeWordContextValue = {
  enabled: boolean;
  available: boolean;
  listening: boolean;
  status: string;
  setEnabled: (enabled: boolean) => Promise<boolean>;
  pause: (reason?: string) => void;
  resume: (reason?: string) => void;
};

const WakeWordContext = createContext<WakeWordContextValue | null>(null);

const delay = (milliseconds: number) =>
  new Promise<void>((resolve) => setTimeout(resolve, milliseconds));

function findWakePhrase(transcript: string) {
  const match = WAKE_PHRASE_PATTERN.exec(transcript);
  if (!match) return null;

  return {
    index: match.index,
    endIndex: match.index + match[0].length,
  };
}

export function WakeWordProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const tts = useMemo(() => getTTSService({ cooldownSeconds: 1.2 }), []);
  const stt = useMemo(
    () => getSTTService({ language: "en-AU", continuous: true, interimResults: false }),
    [],
  );

  const mountedRef = useRef(true);
  const enabledRef = useRef(false);
  const appActiveRef = useRef(AppState.currentState === "active");
  const processingRef = useRef(false);
  const awaitingCommandRef = useRef(false);
  const awaitingCommandUntilRef = useRef(0);
  const cycleRunningRef = useRef(false);
  const generationRef = useRef(0);
  const pauseReasonsRef = useRef(new Set<string>());
  const cycleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const runCycleRef = useRef<() => Promise<void>>(async () => {});
  const handleTranscriptRef = useRef<(text: string) => Promise<void>>(async () => {});

  const [enabled, setEnabledState] = useState(false);
  const [available] = useState(() => stt.isAvailable());
  const [listening, setListening] = useState(false);
  const [status, setStatus] = useState("Voice activation is off");

  const clearAwaitingCommand = useCallback(() => {
    awaitingCommandRef.current = false;
    awaitingCommandUntilRef.current = 0;
  }, []);

  const hasActiveCommandWindow = useCallback(() => {
    if (!awaitingCommandRef.current) return false;
    if (Date.now() <= awaitingCommandUntilRef.current) return true;

    clearAwaitingCommand();
    if (mountedRef.current && enabledRef.current) {
      setStatus("Listening for Hey Buddy or Hey WalkBuddy");
    }
    return false;
  }, [clearAwaitingCommand]);

  const canListen = useCallback(
    () =>
      enabledRef.current &&
      appActiveRef.current &&
      pauseReasonsRef.current.size === 0 &&
      !processingRef.current,
    [],
  );

  const scheduleCycle = useCallback((delayMs = 400) => {
    if (cycleTimerRef.current) clearTimeout(cycleTimerRef.current);
    cycleTimerRef.current = setTimeout(() => {
      cycleTimerRef.current = null;
      void runCycleRef.current();
    }, delayMs);
  }, []);

  const stopActiveListening = useCallback(() => {
    if (cycleTimerRef.current) {
      clearTimeout(cycleTimerRef.current);
      cycleTimerRef.current = null;
    }

    generationRef.current += 1;
    if (Platform.OS === "web") stt.stopListening();
    else void stt.cancelRecordingNative();

    if (mountedRef.current) setListening(false);
  }, [stt]);

  const speakAndNavigate = useCallback(
    async (message: string, pathname: string, replace = false) => {
      await tts.speak(message, RiskLevel.LOW, true);
      if (replace) router.replace(pathname as any);
      else router.push(pathname as any);
    },
    [router, tts],
  );

  const runForegroundCommand = useCallback(
    async (commandText: string) => {
      const command = matchVoiceCommand(commandText);

      switch (command) {
        case "help":
          await tts.speak(VOICE_COMMAND_HELP, RiskLevel.LOW, true);
          return;
        case "repeat-guidance": {
          const previous = tts.getStatus().lastMessage;
          await tts.speak(
            previous || "There is no previous guidance to repeat.",
            RiskLevel.LOW,
            true,
          );
          return;
        }
        case "stop-speaking":
          tts.stop();
          return;
        case "go-home":
          await speakAndNavigate("Going home.", "/", true);
          return;
        case "go-back":
          await tts.speak("Going back.", RiskLevel.LOW, true);
          router.back();
          return;
        case "read-text":
          await tts.speak("Opening the text reader.", RiskLevel.LOW, true);
          router.push({ pathname: "/camera", params: { mode: "ocr" } } as any);
          return;
        case "describe-surroundings":
          await speakAndNavigate("Opening Vision Assist.", "/camera");
          return;
        case "open-camera":
          await speakAndNavigate("Opening the camera.", "/camera");
          return;
        case "open-search":
          await speakAndNavigate("Opening search.", "/search");
          return;
        case "open-places":
          await speakAndNavigate("Opening places.", "/places");
          return;
        case "open-audiobooks":
          await speakAndNavigate("Opening audiobooks.", "/audiobooks");
          return;
        case "open-favourites":
          await speakAndNavigate("Opening favourites.", "/favourites");
          return;
        case "open-audiobook-favourites":
          await speakAndNavigate("Opening audiobook favourites.", "/audiobooks-favourites");
          return;
        case "open-audiobook-history":
          await speakAndNavigate("Opening audiobook history.", "/audiobooks-history");
          return;
        case "open-listen-later":
          await speakAndNavigate("Opening Listen Later.", "/audiobooks-listen-later");
          return;
        case "open-indoor-navigation":
          await speakAndNavigate("Opening indoor navigation.", "/indoor");
          return;
        case "open-outdoor-navigation":
          await speakAndNavigate("Opening outdoor navigation.", "/exterior");
          return;
        case "open-predictive-path":
          await speakAndNavigate("Opening predictive path.", "/predictive-path");
          return;
        case "open-ask-a-friend":
          await speakAndNavigate("Opening Ask a Friend.", "/ask-a-friend-web");
          return;
        case "open-emergency":
          await tts.speak("Opening the emergency screen.", RiskLevel.HIGH, true);
          router.push("/emergency" as any);
          return;
        case "open-profile":
          await speakAndNavigate("Opening your profile.", "/profile");
          return;
        case "open-settings":
          await speakAndNavigate("Opening settings.", "/settings");
          return;
        case "open-location-map":
          await speakAndNavigate("Opening your location map.", "/location-map");
          return;
        case "open-helper":
          await speakAndNavigate("Opening the helper interface.", "/helper-web");
          return;
        default:
          await tts.speak(
            "I did not recognize that command. Say Hey Buddy, help, to hear the command list.",
            RiskLevel.LOW,
            true,
          );
      }
    },
    [router, speakAndNavigate, tts],
  );

  const handleTranscript = useCallback(
    async (transcript: string) => {
      const cleaned = transcript.trim();
      if (!cleaned || !canListen()) return;

      let commandText = "";
      if (hasActiveCommandWindow()) {
        clearAwaitingCommand();
        commandText = cleaned;
      } else {
        const wakeMatch = findWakePhrase(cleaned);
        if (!wakeMatch) return;
        commandText = cleaned
          .slice(wakeMatch.endIndex)
          .replace(/^[\s,.;:!?\u2013\u2014-]+/, "")
          .trim();
      }

      processingRef.current = true;
      stopActiveListening();
      tts.stop();

      try {
        if (!commandText) {
          awaitingCommandRef.current = true;
          awaitingCommandUntilRef.current = Date.now() + COMMAND_WINDOW_MS;
          if (mountedRef.current) setStatus("Listening for a command");
          await tts.speak("I'm listening.", RiskLevel.LOW, true);
          return;
        }

        if (mountedRef.current) setStatus(`Command: ${commandText}`);
        await runForegroundCommand(commandText);
      } finally {
        processingRef.current = false;
        if (mountedRef.current) {
          setStatus(
            hasActiveCommandWindow()
              ? "Listening for a command"
              : "Listening for Hey Buddy or Hey WalkBuddy",
          );
        }
        if (canListen()) scheduleCycle(700);
      }
    },
    [
      canListen,
      clearAwaitingCommand,
      hasActiveCommandWindow,
      runForegroundCommand,
      scheduleCycle,
      stopActiveListening,
      tts,
    ],
  );

  useEffect(() => {
    handleTranscriptRef.current = handleTranscript;
  }, [handleTranscript]);

  const runListeningCycle = useCallback(async () => {
    if (!canListen() || cycleRunningRef.current) return;
    const awaitingCommand = hasActiveCommandWindow();

    if (Platform.OS === "web") {
      if (stt.isListening()) {
        if (mountedRef.current) setListening(true);
        scheduleCycle(1000);
        return;
      }

      const started = stt.startListening(
        (text, isFinal) => {
          if (isFinal) void handleTranscriptRef.current(text);
        },
        (error) => {
          if (mountedRef.current) {
            setListening(false);
            setStatus(`Voice activation error: ${error}`);
          }
          if (canListen()) scheduleCycle(1200);
        },
      );

      if (!started) {
        if (mountedRef.current) setStatus("Voice recognition is unavailable in this browser");
        return;
      }

      if (mountedRef.current) {
        setListening(true);
        setStatus(
          awaitingCommand
            ? "Listening for a command"
            : "Listening for Hey Buddy or Hey WalkBuddy",
        );
      }
      scheduleCycle(1000);
      return;
    }

    cycleRunningRef.current = true;
    const generation = generationRef.current;

    try {
      const started = await stt.startRecordingNative();
      if (!started) {
        enabledRef.current = false;
        setEnabledState(false);
        await AsyncStorage.setItem(STORAGE_KEY, "false");
        if (mountedRef.current) setStatus("Microphone permission is required");
        return;
      }

      if (generation !== generationRef.current || !canListen()) {
        // stopActiveListening already cancelled this wake-word recording.
        // Cancelling again here can stop a newer camera push-to-talk recording
        // because both features intentionally share the same STT service.
        return;
      }

      if (mountedRef.current) {
        setListening(true);
        setStatus(
          awaitingCommand
            ? "Listening for a command"
            : "Listening for Hey Buddy or Hey WalkBuddy",
        );
      }

      await delay(awaitingCommand ? COMMAND_CLIP_MS : WAKE_CLIP_MS);

      if (generation !== generationRef.current || !canListen()) {
        // The pause/disable path owns cancellation. Do not cancel again after
        // this stale timer, or it may cancel a recording started by the camera.
        return;
      }

      if (mountedRef.current) {
        setListening(false);
        setStatus("Checking for Hey Buddy");
      }
      const result = await stt.stopRecordingNative();

      if (generation !== generationRef.current || !canListen()) return;
      if (result.text?.trim()) await handleTranscriptRef.current(result.text);
      else {
        // A wake phrase only arms one follow-up clip. Empty audio must not leave
        // a bare command able to run later without a fresh wake phrase.
        if (awaitingCommand) clearAwaitingCommand();
        if (result.error && !result.error.toLowerCase().includes("no speech")) {
          if (mountedRef.current) setStatus(`Transcription unavailable: ${result.error}`);
        }
      }
    } finally {
      cycleRunningRef.current = false;
      if (canListen()) scheduleCycle(500);
    }
  }, [canListen, clearAwaitingCommand, hasActiveCommandWindow, scheduleCycle, stt]);

  useEffect(() => {
    runCycleRef.current = runListeningCycle;
  }, [runListeningCycle]);

  useEffect(() => {
    mountedRef.current = true;
    let cancelled = false;

    void (async () => {
      const saved = await AsyncStorage.getItem(STORAGE_KEY);
      if (cancelled || saved !== "true" || !available) return;
      enabledRef.current = true;
      setEnabledState(true);
      setStatus("Starting foreground voice activation");
      scheduleCycle(300);
    })();

    return () => {
      cancelled = true;
      mountedRef.current = false;
      clearAwaitingCommand();
      stopActiveListening();
    };
  }, [available, clearAwaitingCommand, scheduleCycle, stopActiveListening]);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (nextState) => {
      appActiveRef.current = nextState === "active";
      if (appActiveRef.current) {
        if (enabledRef.current) {
          setStatus("Listening for Hey Buddy or Hey WalkBuddy");
          scheduleCycle(500);
        }
      } else {
        clearAwaitingCommand();
        stopActiveListening();
        if (mountedRef.current && enabledRef.current) {
          setStatus("Paused while WalkBuddy is in the background");
        }
      }
    });

    return () => subscription.remove();
  }, [clearAwaitingCommand, scheduleCycle, stopActiveListening]);

  const setEnabled = useCallback(
    async (nextEnabled: boolean) => {
      if (nextEnabled && !available) {
        setStatus("Voice activation is unavailable on this device");
        return false;
      }

      enabledRef.current = nextEnabled;
      setEnabledState(nextEnabled);
      clearAwaitingCommand();
      await AsyncStorage.setItem(STORAGE_KEY, String(nextEnabled));

      if (nextEnabled) {
        setStatus("Starting foreground voice activation");
        scheduleCycle(200);
      } else {
        stopActiveListening();
        setStatus("Voice activation is off");
      }
      return true;
    },
    [available, clearAwaitingCommand, scheduleCycle, stopActiveListening],
  );

  const pause = useCallback(
    (reason = "manual") => {
      const wasAlreadyPaused = pauseReasonsRef.current.size > 0;
      pauseReasonsRef.current.add(reason);
      clearAwaitingCommand();
      // Only the first pause request should stop the wake-word recorder.
      // Repeated requests can arrive after the camera has started its own
      // recording, so cancelling again would stop camera push-to-talk.
      if (!wasAlreadyPaused) stopActiveListening();
      if (mountedRef.current && enabledRef.current) setStatus("Voice activation paused");
    },
    [clearAwaitingCommand, stopActiveListening],
  );

  const resume = useCallback(
    (reason = "manual") => {
      pauseReasonsRef.current.delete(reason);
      if (pauseReasonsRef.current.size === 0 && enabledRef.current) {
        setStatus("Listening for Hey Buddy or Hey WalkBuddy");
        scheduleCycle(400);
      }
    },
    [scheduleCycle],
  );

  const value = useMemo(
    () => ({ enabled, available, listening, status, setEnabled, pause, resume }),
    [available, enabled, listening, pause, resume, setEnabled, status],
  );

  return <WakeWordContext.Provider value={value}>{children}</WakeWordContext.Provider>;
}

export function useWakeWord() {
  const context = useContext(WakeWordContext);
  if (!context) throw new Error("useWakeWord must be used inside WakeWordProvider");
  return context;
}
