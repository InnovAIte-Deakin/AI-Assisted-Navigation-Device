// src/utils/webTTS.ts
// Web-specific Text-to-Speech using browser speechSynthesis API

let isSpeaking = false;
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

  stopWebSpeech();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = options.rate ?? 0.9;
  utterance.pitch = options.pitch ?? 1.0;
  utterance.volume = options.volume ?? 1.0;
  utterance.lang = options.lang ?? "en-US";

  const pickVoice = (voices: SpeechSynthesisVoice[]) => {
    // Prefer clear/natural english voices when available
    const preferred = voices.filter(
      (v) =>
        v.lang.startsWith("en") &&
        (v.name.includes("Google") ||
          v.name.includes("Microsoft") ||
          v.name.includes("Samantha") ||
          v.name.includes("Alex")),
    );
    if (preferred.length > 0) return preferred[0];

    const english = voices.filter((v) => v.lang.startsWith("en"));
    if (english.length > 0) return english[0];

    return voices[0];
  };

  const applyBestVoice = () => {
    const voices = window.speechSynthesis.getVoices();
    if (voices.length > 0) {
      const v = pickVoice(voices);
      if (v) utterance.voice = v;
    }
  };

  utterance.onstart = () => {
    isSpeaking = true;
    currentUtterance = utterance;
  };

  utterance.onend = () => {
    isSpeaking = false;
    currentUtterance = null;
    if (typeof (window as any).onTTSFinished === "function") {
      (window as any).onTTSFinished();
    }
  };

  utterance.onerror = (error) => {
    console.error("[webTTS] Error:", error);
    isSpeaking = false;
    currentUtterance = null;
  };

  // Voices may load async on first use
  applyBestVoice();
  if (window.speechSynthesis.getVoices().length === 0) {
    const prev = window.speechSynthesis.onvoiceschanged;
    window.speechSynthesis.onvoiceschanged = () => {
      applyBestVoice();
      window.speechSynthesis.speak(utterance);
      // avoid permanently overriding if something else sets this
      window.speechSynthesis.onvoiceschanged = prev ?? null;
    };
  } else {
    window.speechSynthesis.speak(utterance);
  }
}

/**
 * Stop current speech
 */
export function stopWebSpeech(): void {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  isSpeaking = false;
  currentUtterance = null;
}

/**
 * Check if web TTS is available
 */
export function isWebTTSAvailable(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

/**
 * Optional: only keep if something imports it
 */
export function isWebSpeaking(): boolean {
  return isSpeaking;
}
