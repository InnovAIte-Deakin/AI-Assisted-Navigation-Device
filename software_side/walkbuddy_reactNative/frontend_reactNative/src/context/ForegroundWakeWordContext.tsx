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
const WAKE_PHRASES = ["hey walkbuddy", "hey buddy"];
const WAKE_CLIP_MS = 5000;
const COMMAND_CLIP_MS = 4200;

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
  const lower = transcript.toLowerCase();
  let match: { phrase: string; index: number } | null = null;

  for (const phrase of WAKE_PHRASES) {
    const index = lower.indexOf(phrase);
    if (index >= 0 && (!match || index < match.index)) match = { phrase, index };
  }

  return match;
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
      if (awaitingCommandRef.current) {
        awaitingCommandRef.current = false;
        commandText = cleaned;
      } else {
        const wakeMatch = findWakePhrase(cleaned);
        if (!wakeMatch) return;
        commandText = cleaned
          .slice(wakeMatch.index + wakeMatch.phrase.length)
          .replace(/^[,\s-]+/, "")
          .trim();
      }

      processingRef.current = true;
      stopActiveListening();
      tts.stop();

      try {
        if (!commandText) {
          awaitingCommandRef.current = true;
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
            awaitingCommandRef.current
              ? "Listening for a command"
              : "Listening for Hey Buddy or Hey WalkBuddy",
          );
        }
        if (canListen()) scheduleCycle(700);
      }
    },
    [canListen, runForegroundCommand, scheduleCycle, stopActiveListening, tts],
  );

  useEffect(() => {
    handleTranscriptRef.current = handleTranscript;
  }, [handleTranscript]);

  const runListeningCycle = useCallback(async () => {
    if (!canListen() || cycleRunningRef.current) return;

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
          awaitingCommandRef.current
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
          awaitingCommandRef.current
            ? "Listening for a command"
            : "Listening for Hey Buddy or Hey WalkBuddy",
        );
      }

      await delay(awaitingCommandRef.current ? COMMAND_CLIP_MS : WAKE_CLIP_MS);

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
      else if (result.error && !result.error.toLowerCase().includes("no speech")) {
        if (mountedRef.current) setStatus(`Transcription unavailable: ${result.error}`);
      }
    } finally {
      cycleRunningRef.current = false;
      if (canListen()) scheduleCycle(500);
    }
  }, [canListen, scheduleCycle, stt]);

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
      stopActiveListening();
    };
  }, [available, scheduleCycle, stopActiveListening]);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (nextState) => {
      appActiveRef.current = nextState === "active";
      if (appActiveRef.current) {
        if (enabledRef.current) {
          setStatus("Listening for Hey Buddy or Hey WalkBuddy");
          scheduleCycle(500);
        }
      } else {
        stopActiveListening();
        if (mountedRef.current && enabledRef.current) {
          setStatus("Paused while WalkBuddy is in the background");
        }
      }
    });

    return () => subscription.remove();
  }, [scheduleCycle, stopActiveListening]);

  const setEnabled = useCallback(
    async (nextEnabled: boolean) => {
      if (nextEnabled && !available) {
        setStatus("Voice activation is unavailable on this device");
        return false;
      }

      enabledRef.current = nextEnabled;
      setEnabledState(nextEnabled);
      awaitingCommandRef.current = false;
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
    [available, scheduleCycle, stopActiveListening],
  );

  const pause = useCallback(
    (reason = "manual") => {
      const wasAlreadyPaused = pauseReasonsRef.current.size > 0;
      pauseReasonsRef.current.add(reason);
      // Only the first pause request should stop the wake-word recorder.
      // Repeated requests can arrive after the camera has started its own
      // recording, so cancelling again would stop camera push-to-talk.
      if (!wasAlreadyPaused) stopActiveListening();
      if (mountedRef.current && enabledRef.current) setStatus("Voice activation paused");
    },
    [stopActiveListening],
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
