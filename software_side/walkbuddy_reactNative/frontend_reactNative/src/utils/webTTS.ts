// src/utils/webTTS.ts
// Web-specific Text-to-Speech using browser speechSynthesis API

let isSpeaking = false;
let currentUtterance: SpeechSynthesisUtterance | null = null;

/**
 * Speak text using browser TTS (web only)
 */
export function speakWeb(text: string, options?: { rate?: number; pitch?: number; volume?: number; lang?: string }): void {
  if (typeof window === "undefined" || !window.speechSynthesis) {
    console.warn("[TTS] speechSynthesis not available");
    return;
  }

  // Stop any current speech
  stopWebSpeech();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = options?.rate || 0.9; // Slightly slower for clarity (default 0.9)
  utterance.pitch = options?.pitch || 1.0; // Normal pitch
  utterance.volume = options?.volume || 1.0; // Maximum volume
  utterance.lang = options?.lang || "en-US"; // English (US)

  // Try to use a high-quality voice if available
  const voices = window.speechSynthesis.getVoices();
  // Prefer voices that sound clear and natural
  const preferredVoices = voices.filter(v => 
    v.lang.startsWith("en") && 
    (v.name.includes("Google") || v.name.includes("Microsoft") || v.name.includes("Samantha") || v.name.includes("Alex"))
  );
  if (preferredVoices.length > 0) {
    utterance.voice = preferredVoices[0];
    console.log("[TTS] Using voice:", preferredVoices[0].name);
  } else if (voices.length > 0) {
    // Fallback to first English voice
    const englishVoices = voices.filter(v => v.lang.startsWith("en"));
    if (englishVoices.length > 0) {
      utterance.voice = englishVoices[0];
      console.log("[TTS] Using voice:", englishVoices[0].name);
    }
  }

  utterance.onstart = () => {
    isSpeaking = true;
    console.log("[TTS] ✅ Started speaking:", text.substring(0, 50) + (text.length > 50 ? "..." : ""));
  };

  utterance.onend = () => {
    isSpeaking = false;
    currentUtterance = null;
    console.log("[TTS] ✅ Finished speaking");
    // Trigger callback if needed
    if (typeof (window as any).onTTSFinished === "function") {
      (window as any).onTTSFinished();
    }
  };

  utterance.onerror = (error) => {
    console.error("[TTS] ❌ Error:", error);
    isSpeaking = false;
    currentUtterance = null;
  };

  currentUtterance = utterance;
  
  // Ensure voices are loaded before speaking
  if (voices.length === 0) {
    // Voices might not be loaded yet, wait for them
    window.speechSynthesis.onvoiceschanged = () => {
      const updatedVoices = window.speechSynthesis.getVoices();
      const preferredVoices = updatedVoices.filter(v => 
        v.lang.startsWith("en") && 
        (v.name.includes("Google") || v.name.includes("Microsoft") || v.name.includes("Samantha") || v.name.includes("Alex"))
      );
      if (preferredVoices.length > 0) {
        utterance.voice = preferredVoices[0];
      }
      window.speechSynthesis.speak(utterance);
    };
  } else {
    window.speechSynthesis.speak(utterance);
  }
}

/**
 * Stop current speech
 */
export function stopWebSpeech(): void {
  if (typeof window !== "undefined" && window.speechSynthesis) {
    window.speechSynthesis.cancel();
    isSpeaking = false;
    currentUtterance = null;
  }
}

/**
 * Check if TTS is available
 */
export function isWebTTSAvailable(): boolean {
  return typeof window !== "undefined" && !!window.speechSynthesis;
}

/**
 * Check if currently speaking
 */
export function isWebSpeaking(): boolean {
  return isSpeaking;
}
