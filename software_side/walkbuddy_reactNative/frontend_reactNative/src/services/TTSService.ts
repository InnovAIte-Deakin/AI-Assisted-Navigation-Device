/**
 * Text-to-Speech Service for React Native
 * 
 * This service provides offline-friendly TTS with anti-spam logic:
 * - Cooldown between repeated messages
 * - Only speaks when message changes or risk level increases
 * - Prevents audio spam for accessibility
 * 
 * Uses expo-speech for device-based TTS (offline, no cloud required)
 * 
 * Author: ML Engineering Team
 * Purpose: Sprint 2 - TTS Implementation
 */

import * as Speech from 'expo-speech';

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

/**
 * Text-to-Speech Service with anti-spam logic
 */
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
      language: config.language ?? 'en',
      pitch: config.pitch ?? 1.0,
      rate: config.rate ?? 0.9, // Slightly slower for clarity
      volume: config.volume ?? 1.0,
    };
  }

  /**
   * Generate a unique ID for a message (normalized)
   */
  private generateMessageId(message: string): string {
    const normalized = message.toLowerCase().trim();
    // Simple hash-like ID
    let hash = 0;
    for (let i = 0; i < normalized.length; i++) {
      const char = normalized.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return hash.toString();
  }

  /**
   * Determine if a message should be spoken based on anti-spam rules
   */
  private shouldSpeak(
    message: string,
    riskLevel: RiskLevel,
    force: boolean = false
  ): boolean {
    if (force) {
      return true;
    }

    const currentTime = Date.now() / 1000; // Convert to seconds
    const messageId = this.generateMessageId(message);

    // Check cooldown
    const timeSinceLast = currentTime - this.lastSpokenTime;
    if (timeSinceLast < this.cooldownSeconds) {
      // BUT: Allow if risk level increased (important safety override)
      if (riskLevel <= this.lastRiskLevel) {
        return false;
      }
    }

    // Check if message changed
    if (messageId === this.generateMessageId(this.lastMessage || '')) {
      // Same message, but allow if risk increased
      if (riskLevel <= this.lastRiskLevel) {
        return false;
      }
    }

    // Risk escalation: always speak if risk increased
    if (riskLevel > this.lastRiskLevel) {
      return true;
    }

    // All checks passed
    return true;
  }

  /**
   * Speak a message with anti-spam protection
   * 
   * @param message The text message to speak (should be short and clear)
   * @param riskLevel Risk level of the message (affects priority)
   * @param force Force speaking even if cooldown active (use sparingly)
   * @returns Promise that resolves to true if message was spoken, false if suppressed
   * 
   * @example
   * ```typescript
   * const tts = new TTSService();
   * await tts.speak("Chair on your left, nearby", RiskLevel.MEDIUM);
   * await tts.speak("Path ahead is clear", RiskLevel.CLEAR);
   * ```
   */
  async speak(
    message: string,
    riskLevel: RiskLevel = RiskLevel.LOW,
    force: boolean = false
  ): Promise<boolean> {
    if (!message || !message.trim()) {
      return false;
    }

    // Check if we should speak
    if (!this.shouldSpeak(message, riskLevel, force)) {
      return false;
    }

    try {
      // Stop any current speech
      Speech.stop();

      // Speak the message
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

      // Update state
      const currentTime = Date.now() / 1000;
      this.lastSpokenTime = currentTime;
      this.lastMessage = message;
      this.lastRiskLevel = riskLevel;

      // Add to history
      const context: MessageContext = {
        message,
        riskLevel,
        timestamp: currentTime,
        messageId: this.generateMessageId(message),
      };
      this.messageHistory.push(context);
      if (this.messageHistory.length > this.maxHistory) {
        this.messageHistory.shift();
      }

      console.log(`[TTS Service] Spoke: '${message}' (risk: ${RiskLevel[riskLevel]})`);
      return true;
    } catch (error) {
      console.error(`[TTS Service] Failed to speak: '${message}'`, error);
      return false;
    }
  }

  /**
   * Speak a message asynchronously (non-blocking)
   * 
   * This is useful for real-time systems where blocking on TTS
   * would slow down the main processing loop.
   */
  speakAsync(
    message: string,
    riskLevel: RiskLevel = RiskLevel.LOW,
    force: boolean = false
  ): void {
    this.speak(message, riskLevel, force).catch((error) => {
      console.error('[TTS Service] Async speak error:', error);
    });
  }

  /**
   * Stop current speech
   */
  stop(): void {
    Speech.stop();
  }

  /**
   * Get current status of the TTS service
   */
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

  /**
   * Reset TTS service state (useful for testing or restart)
   */
  reset(): void {
    this.lastSpokenTime = 0;
    this.lastMessage = null;
    this.lastRiskLevel = RiskLevel.CLEAR;
    this.messageHistory = [];
    Speech.stop();
  }

  /**
   * Update TTS configuration
   */
  updateConfig(config: Partial<TTSConfig>): void {
    this.config = { ...this.config, ...config };
    if (config.cooldownSeconds !== undefined) {
      this.cooldownSeconds = config.cooldownSeconds;
    }
  }
}

// Export singleton instance (for convenience)
let globalTTSService: TTSService | null = null;

/**
 * Get or create global TTS service instance
 * 
 * This is a convenience function for getting a shared TTS service
 * across the application.
 */
export function getTTSService(config?: Partial<TTSConfig>): TTSService {
  if (globalTTSService === null) {
    globalTTSService = new TTSService(config);
  }
  return globalTTSService;
}

export default TTSService;



