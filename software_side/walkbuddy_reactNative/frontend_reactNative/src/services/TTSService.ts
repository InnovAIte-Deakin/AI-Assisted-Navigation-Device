/**
 * Text-to-Speech Service for React Native
 *
 * - Native: expo-speech
 * - Web: Web Speech API (speechSynthesis)
 *
 * Includes anti-spam logic (cooldown, dedupe, risk escalation)
 */

import { Platform } from "react-native";
import * as Speech from "expo-speech";

export enum RiskLevel {
  CLEAR = 0,
  LOW = 1,
  MEDIUM = 2,
  HIGH = 3,
  CRITICAL = 4,
}

interface MessageContext {
  message: string;
  riskLevel: RiskLevel;
  timestamp: number;
  messageId: string;
}

interface TTSConfig {
  cooldownSeconds: number;
  language?: string;
  pitch?: number;
  rate?: number;
  volume?: number;
}

class TTSService {
  private cooldownSeconds: number;
  private lastSpokenTime: number = 0;
  private lastMessage: string | null = null;
  private lastRiskLevel: RiskLevel = RiskLevel.CLEAR;
  private messageHistory: MessageContext[] = [];
  private maxHistory: number = 10;
  private config: TTSConfig;

  constructor(config: Partial<TTSConfig> = {}) {
    this.cooldownSeconds = config.cooldownSeconds ?? 3.0;
    this.config = {
      cooldownSeconds: this.cooldownSeconds,
      // Use a BCP-47-ish value that works on both expo-speech + browser
      language: config.language ?? "en-US",
      pitch: config.pitch ?? 1.0,
      rate: config.rate ?? 0.9,
      volume: config.volume ?? 1.0,
    };
  }

  // ---------------- Web impl ----------------
  private async speakWeb(message: string): Promise<void> {
    const w = globalThis as any;
    const synth: SpeechSynthesis | undefined = w?.speechSynthesis;

    if (!synth) throw new Error("SpeechSynthesis not available");

    // Only cancel if something is speaking/pending to avoid constant "canceled" errors.
    if (synth.speaking || synth.pending) synth.cancel();

    // Voices can be empty until voiceschanged fires
    const ensureVoices = () =>
      new Promise<void>((resolve) => {
        const voices = synth.getVoices?.() ?? [];
        if (voices.length) return resolve();

        const onVoicesChanged = () => {
          synth.removeEventListener?.("voiceschanged", onVoicesChanged);
          resolve();
        };
        synth.addEventListener?.("voiceschanged", onVoicesChanged);
        setTimeout(resolve, 250); // fallback
      });

    await ensureVoices();

    await new Promise<void>((resolve, reject) => {
      const u = new SpeechSynthesisUtterance(message);

      u.lang = this.config.language || "en-US";
      u.rate = this.config.rate ?? 1.0;
      u.pitch = this.config.pitch ?? 1.0;
      u.volume = this.config.volume ?? 1.0;

      u.onend = () => resolve();
      u.onerror = (e) => {
        // Chrome often reports "canceled" / "interrupted" when you call cancel()
        const err = String((e as any)?.error || "");
        if (err === "canceled" || err === "interrupted") return resolve();
        reject(new Error(err || "speech error"));
      };

      synth.speak(u);
    });
  }

  // ---------------- Anti-spam helpers ----------------
  private generateMessageId(message: string): string {
    const normalized = message.toLowerCase().trim();
    let hash = 0;
    for (let i = 0; i < normalized.length; i++) {
      const char = normalized.charCodeAt(i);
      hash = (hash << 5) - hash + char;
      hash = hash & hash; // 32-bit
    }
    return hash.toString();
  }

  private shouldSpeak(
    message: string,
    riskLevel: RiskLevel,
    force: boolean = false,
  ): boolean {
    if (force) return true;

    const currentTime = Date.now() / 1000;
    const messageId = this.generateMessageId(message);

    const timeSinceLast = currentTime - this.lastSpokenTime;
    if (timeSinceLast < this.cooldownSeconds) {
      if (riskLevel <= this.lastRiskLevel) return false;
    }

    if (messageId === this.generateMessageId(this.lastMessage || "")) {
      if (riskLevel <= this.lastRiskLevel) return false;
    }

    if (riskLevel > this.lastRiskLevel) return true;

    return true;
  }

  // ---------------- Public API ----------------
  async speak(
    message: string,
    riskLevel: RiskLevel = RiskLevel.LOW,
    force: boolean = false,
  ): Promise<boolean> {
    if (!message || !message.trim()) return false;
    if (!this.shouldSpeak(message, riskLevel, force)) return false;

    try {
      if (Platform.OS === "web") {
        await this.speakWeb(message);
      } else {
        Speech.stop();
        await new Promise<void>((resolve, reject) => {
          Speech.speak(message, {
            language: this.config.language,
            pitch: this.config.pitch,
            rate: this.config.rate,
            volume: this.config.volume,
            onDone: () => resolve(),
            onStopped: () => resolve(),
            onError: (error) => reject(error),
          });
        });
      }

      const currentTime = Date.now() / 1000;
      this.lastSpokenTime = currentTime;
      this.lastMessage = message;
      this.lastRiskLevel = riskLevel;

      const context: MessageContext = {
        message,
        riskLevel,
        timestamp: currentTime,
        messageId: this.generateMessageId(message),
      };
      this.messageHistory.push(context);
      if (this.messageHistory.length > this.maxHistory)
        this.messageHistory.shift();

      console.log(
        `[TTS Service] Spoke: '${message}' (risk: ${RiskLevel[riskLevel]})`,
      );
      return true;
    } catch (error) {
      console.error(`[TTS Service] Failed to speak: '${message}'`, error);
      return false;
    }
  }

  speakAsync(
    message: string,
    riskLevel: RiskLevel = RiskLevel.LOW,
    force: boolean = false,
  ): void {
    this.speak(message, riskLevel, force).catch((error) => {
      console.error("[TTS Service] Async speak error:", error);
    });
  }

  stop(): void {
    if (Platform.OS === "web") {
      const w = globalThis as any;
      w?.speechSynthesis?.cancel?.();
      return;
    }
    Speech.stop();
  }

  getStatus() {
    const currentTime = Date.now() / 1000;
    const timeSinceLast = currentTime - this.lastSpokenTime;

    return {
      cooldownSeconds: this.cooldownSeconds,
      timeSinceLastMessage: timeSinceLast,
      cooldownActive: timeSinceLast < this.cooldownSeconds,
      lastMessage: this.lastMessage,
      lastRiskLevel: RiskLevel[this.lastRiskLevel],
      messageHistoryCount: this.messageHistory.length,
      config: this.config,
    };
  }

  reset(): void {
    this.lastSpokenTime = 0;
    this.lastMessage = null;
    this.lastRiskLevel = RiskLevel.CLEAR;
    this.messageHistory = [];
    this.stop();
  }

  updateConfig(config: Partial<TTSConfig>): void {
    this.config = { ...this.config, ...config };
    if (config.cooldownSeconds !== undefined) {
      this.cooldownSeconds = config.cooldownSeconds;
    }
  }
}

// Singleton
let globalTTSService: TTSService | null = null;

export function getTTSService(config?: Partial<TTSConfig>): TTSService {
  if (globalTTSService === null) {
    globalTTSService = new TTSService(config);
  }
  return globalTTSService;
}

export default TTSService;
