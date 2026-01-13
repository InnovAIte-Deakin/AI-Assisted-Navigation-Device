/**
 * Speech-to-Text Service for React Native
 * 
 * Provides cross-platform STT functionality:
 * - Web: Uses Web Speech API
 * - Native: Uses expo-av for recording, sends to backend for transcription
 * 
 * Author: ML Engineering Team
 * Purpose: Add STT for voice navigation commands
 */

import { Platform, Alert } from 'react-native';
import { Audio } from 'expo-av';
import * as FileSystem from 'expo-file-system/legacy';
import { API_BASE } from '../config';

export interface STTResult {
  text: string;
  confidence?: number;
  error?: string;
}

export interface STTConfig {
  language?: string;
  continuous?: boolean;
  interimResults?: boolean;
}

class STTService {
  private recognitionRef: any = null;
  private recordingRef: Audio.Recording | null = null;
  private isRecording = false;
  private recordingStartTime: number = 0;
  private config: STTConfig;

  constructor(config: STTConfig = {}) {
    this.config = {
      language: config.language ?? 'en-US',
      continuous: config.continuous ?? false,
      interimResults: config.interimResults ?? true,
    };
  }

  /**
   * Check if STT is available on the current platform
   */
  isAvailable(): boolean {
    if (Platform.OS === 'web') {
      const W = globalThis as any;
      return !!(W.SpeechRecognition || W.webkitSpeechRecognition);
    }
    // Native: expo-av is always available
    return true;
  }

  /**
   * Start listening for speech (Web Speech API)
   */
  startListeningWeb(
    onResult: (text: string, isFinal: boolean) => void,
    onError?: (error: string) => void
  ): boolean {
    if (Platform.OS !== 'web') {
      return false;
    }

    const W = globalThis as any;
    const SR = W.SpeechRecognition || W.webkitSpeechRecognition;
    
    if (!SR) {
      onError?.('Speech recognition not available in this browser');
      return false;
    }

    try {
      const rec = new SR();
      this.recognitionRef = rec;
      rec.lang = this.config.language;
      rec.continuous = this.config.continuous;
      rec.interimResults = this.config.interimResults;

      rec.onresult = (e: any) => {
        let text = '';
        let isFinal = false;
        
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const result = e.results[i];
          text += result[0].transcript;
          if (result.isFinal) {
            isFinal = true;
          }
        }
        
        onResult(text.trim(), isFinal);
      };

      rec.onend = () => {
        this.recognitionRef = null;
      };

      rec.onerror = (e: any) => {
        const errorMsg = e.error || 'Speech recognition error';
        onError?.(errorMsg);
        this.recognitionRef = null;
      };

      rec.start();
      return true;
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Failed to start speech recognition';
      onError?.(errorMsg);
      return false;
    }
  }

  /**
   * Stop listening (Web Speech API)
   */
  stopListeningWeb(): void {
    if (this.recognitionRef) {
      try {
        this.recognitionRef.stop();
      } catch (error) {
        console.log('[STT] Error stopping web recognition:', error);
      }
      this.recognitionRef = null;
    }
  }

  /**
   * Start recording audio (Native - expo-av)
   */
  async startRecordingNative(): Promise<boolean> {
    if (Platform.OS === 'web') {
      return false;
    }

    if (this.isRecording) {
      return false;
    }

    try {
      // Request permissions
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert(
          'Permission Required',
          'Microphone permission is required for voice commands.'
        );
        return false;
      }

      // Configure audio mode
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      // Create and start recording
      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );

      this.recordingRef = recording;
      this.isRecording = true;
      this.recordingStartTime = Date.now();
      console.log('[STT] Recording started at:', this.recordingStartTime);
      return true;
    } catch (error) {
      console.error('[STT] Error starting recording:', error);
      Alert.alert('Recording Error', 'Failed to start audio recording');
      return false;
    }
  }

  /**
   * Stop recording and transcribe (Native)
   */
  async stopRecordingNative(): Promise<STTResult> {
    if (!this.recordingRef || !this.isRecording) {
      return { text: '', error: 'No active recording' };
    }

    try {
      // Calculate recording duration
      const durationMs = Date.now() - this.recordingStartTime;
      console.log('[STT] Recording duration:', durationMs, 'ms');

      // Validate recording duration
      if (durationMs < 1500) {
        const errorMsg = 'Recording too short. Speak for 2–3 seconds.';
        console.log('[STT]', errorMsg);
        // Clean up recording
        try {
          await this.recordingRef.stopAndUnloadAsync();
          const uri = this.recordingRef.getURI();
          if (uri) {
            await FileSystem.deleteAsync(uri, { idempotent: true });
          }
        } catch (e) {
          // Ignore cleanup errors
        }
        this.recordingRef = null;
        this.isRecording = false;
        return { text: '', error: errorMsg };
      }

      // Stop recording
      await this.recordingRef.stopAndUnloadAsync();
      const uri = this.recordingRef.getURI();
      this.recordingRef = null;
      this.isRecording = false;

      if (!uri) {
        return { text: '', error: 'No audio file recorded' };
      }

      // Validate file size before uploading
      const info = await FileSystem.getInfoAsync(uri);
      console.log('[STT] Audio URI:', uri);
      console.log('[STT] File info:', JSON.stringify(info, null, 2));

      if (!info.exists) {
        return { text: '', error: 'No audio captured. Check Microphone permission and try again.' };
      }

      if (info.size !== undefined && info.size < 10000) {
        console.log('[STT] File too small:', info.size, 'bytes');
        // Clean up small file
        try {
          await FileSystem.deleteAsync(uri, { idempotent: true });
        } catch (e) {
          // Ignore cleanup errors
        }
        return { text: '', error: 'No audio captured. Check Microphone permission and try again.' };
      }

      console.log('[STT] Audio file size:', info.size, 'bytes');

      // Send to backend for transcription
      const result = await this.transcribeAudio(uri, durationMs);
      
      // Clean up audio file using expo-file-system
      try {
        await FileSystem.deleteAsync(uri, { idempotent: true });
      } catch (e) {
        // Ignore cleanup errors
        console.log('[STT] Error deleting recording file:', e);
      }

      return result;
    } catch (error) {
      this.isRecording = false;
      const errorMsg = error instanceof Error ? error.message : 'Recording error';
      console.error('[STT] Error stopping recording:', error);
      return { text: '', error: errorMsg };
    }
  }

  /**
   * Send audio file to backend for transcription
   * FIX: Added timeout to prevent voice "Processing..." from getting stuck
   * Voice got stuck because /stt/transcribe could hang indefinitely without a timeout
   */
  private async transcribeAudio(uri: string, durationMs: number): Promise<STTResult> {
    const STT_TIMEOUT_MS = 25000; // 25 second timeout (same as vision endpoint)
    const requestUrl = `${API_BASE}/stt/transcribe`;
    
    console.log('[STT] Request URL:', requestUrl);
    console.log('[STT] Recording duration:', durationMs, 'ms');

    try {
      const formData = new FormData();
      formData.append('file', {
        uri,
        type: 'audio/m4a',
        name: 'recording.m4a',
      } as any);

      // Add timeout to prevent voice processing from hanging
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        controller.abort();
        console.log(`[STT] Request timed out after ${STT_TIMEOUT_MS}ms`);
      }, STT_TIMEOUT_MS);

      let response: Response;
      let responseBodyText: string = '';
      try {
        response = await fetch(requestUrl, {
          method: 'POST',
          body: formData,
          signal: controller.signal,
        });
        clearTimeout(timeoutId);
        
        console.log('[STT] Response status:', response.status);
      } catch (fetchError: any) {
        clearTimeout(timeoutId);
        if (fetchError.name === 'AbortError') {
          console.log('[STT] Request aborted (timeout)');
          return { text: '', error: 'Transcription request timed out. Please check your network connection.' };
        }
        const errorMsg = fetchError instanceof Error ? fetchError.message : 'Network error';
        console.log('[STT] Fetch error:', errorMsg);
        return { text: '', error: errorMsg };
      }

      // Read response body text for logging
      try {
        responseBodyText = await response.text();
        console.log('[STT] Response body:', responseBodyText);
      } catch (e) {
        console.log('[STT] Could not read response body:', e);
      }

      if (!response.ok) {
        return { text: '', error: `Server error: ${response.status} - ${responseBodyText}` };
      }

      // Parse JSON response
      let data: any;
      try {
        data = JSON.parse(responseBodyText);
      } catch (e) {
        console.log('[STT] Failed to parse JSON response:', e);
        return { text: '', error: 'Invalid response from server' };
      }

      // Handle "No speech detected" gracefully
      if (data.error && typeof data.error === 'string') {
        const errorLower = data.error.toLowerCase();
        if (errorLower.includes('no speech detected') || errorLower.includes('no speech')) {
          const helpfulMsg = 'No speech detected. Speak louder, closer to the mic, and record 2–3 seconds.';
          console.log('[STT]', helpfulMsg);
          return { text: '', error: helpfulMsg };
        }
        // Return other errors as-is
        return { text: '', error: data.error };
      }

      // Check if text is empty or contains "No speech detected"
      const transcribedText = data.text || '';
      if (!transcribedText.trim()) {
        const helpfulMsg = 'No speech detected. Speak louder, closer to the mic, and record 2–3 seconds.';
        console.log('[STT] Empty transcription:', helpfulMsg);
        return { text: '', error: helpfulMsg };
      }

      if (transcribedText.toLowerCase().includes('no speech detected')) {
        const helpfulMsg = 'No speech detected. Speak louder, closer to the mic, and record 2–3 seconds.';
        console.log('[STT]', helpfulMsg);
        return { text: '', error: helpfulMsg };
      }

      console.log('[STT] Transcription successful:', transcribedText);
      return {
        text: transcribedText,
        confidence: data.confidence,
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Network error';
      console.error('[STT] Transcription error:', errorMsg);
      return { text: '', error: errorMsg };
    }
  }

  /**
   * Start listening (platform-agnostic)
   */
  startListening(
    onResult: (text: string, isFinal: boolean) => void,
    onError?: (error: string) => void
  ): boolean {
    if (Platform.OS === 'web') {
      return this.startListeningWeb(onResult, onError);
    } else {
      // For native, we'll use recording (caller should handle start/stop)
      return true;
    }
  }

  /**
   * Stop listening (platform-agnostic)
   */
  stopListening(): void {
    if (Platform.OS === 'web') {
      this.stopListeningWeb();
    } else {
      // Native recording is stopped via stopRecordingNative
    }
  }

  /**
   * Check if currently listening/recording
   */
  isListening(): boolean {
    if (Platform.OS === 'web') {
      return this.recognitionRef !== null;
    } else {
      return this.isRecording;
    }
  }
}

// Export singleton instance
let globalSTTService: STTService | null = null;

/**
 * Get or create global STT service instance
 */
export function getSTTService(config?: STTConfig): STTService {
  if (globalSTTService === null) {
    globalSTTService = new STTService(config);
  }
  return globalSTTService;
}

export default STTService;

