/**
 * Web Text-to-Speech utilities
 * Provides TTS functionality for web platform using browser speechSynthesis API
 */

let currentUtterance: SpeechSynthesisUtterance | null = null;

export interface SpeakOptions {
  rate?: number;
  pitch?: number;
  volume?: number;
  lang?: string;
}

/**
 * Speak text using browser speechSynthesis API (web only)
 */
export function speakWeb(text: string, options: SpeakOptions = {}): void {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    console.warn("[webTTS] speechSynthesis not available");
    return;
  }

  // Stop any current speech
  stopWebSpeech();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = options.rate ?? 1.0;
  utterance.pitch = options.pitch ?? 1.0;
  utterance.volume = options.volume ?? 1.0;
  utterance.lang = options.lang ?? "en-US";

  currentUtterance = utterance;

  utterance.onend = () => {
    currentUtterance = null;
  };

  utterance.onerror = (error) => {
    console.error("[webTTS] Error:", error);
    currentUtterance = null;
  };

  window.speechSynthesis.speak(utterance);
}

/**
 * Stop current speech
 */
export function stopWebSpeech(): void {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) {
    return;
  }

  window.speechSynthesis.cancel();
  currentUtterance = null;
}

/**
 * Check if web TTS is available
 */
export function isWebTTSAvailable(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}
