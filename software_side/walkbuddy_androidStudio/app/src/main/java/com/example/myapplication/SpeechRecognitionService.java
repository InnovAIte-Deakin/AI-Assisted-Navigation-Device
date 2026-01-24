package com.example.myapplication;

import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.util.Log;

import java.util.ArrayList;
import java.util.Locale;

/**
 * Service for handling Speech-to-Text (STT)
 * Converts user voice to text using Android's built-in speech recognition
 *
 * Features:
 * - Real-time speech recognition
 * - Error handling with user-friendly messages
 * - Partial results support
 * - Multiple language support
 *
 * Usage:
 * SpeechRecognitionService service = new SpeechRecognitionService(context, callback);
 * service.initialize();
 * service.startListening();
 */
public class SpeechRecognitionService {

    private static final String TAG = "SpeechRecognition";

    private final Context context;
    private final SpeechRecognitionCallback callback;
    private SpeechRecognizer speechRecognizer;
    private boolean isListening = false;

    /**
     * Callback interface for speech recognition events
     */
    public interface SpeechRecognitionCallback {
        /**
         * Called when speech recognizer is ready to listen
         */
        void onSpeechReady();

        /**
         * Called when user starts speaking
         */
        void onSpeechStart();

        /**
         * Called when speech is successfully recognized
         * @param text The recognized text
         */
        void onSpeechResult(String text);

        /**
         * Called when an error occurs
         * @param error User-friendly error message
         */
        void onSpeechError(String error);

        /**
         * Called when user stops speaking
         */
        void onSpeechEnd();
    }

    /**
     * Constructor
     *
     * @param context Application context
     * @param callback Callback to receive speech recognition events
     */
    public SpeechRecognitionService(Context context, SpeechRecognitionCallback callback) {
        this.context = context.getApplicationContext();
        this.callback = callback;
    }

    /**
     * Initialize speech recognizer
     * Call this before startListening()
     */
    public void initialize() {
        // Check if speech recognition is available on device
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            Log.e(TAG, "Speech recognition not available on this device");
            if (callback != null) {
                callback.onSpeechError("Speech recognition not available on this device");
            }
            return;
        }

        // Create speech recognizer
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context);

        if (speechRecognizer == null) {
            Log.e(TAG, "Failed to create speech recognizer");
            if (callback != null) {
                callback.onSpeechError("Failed to initialize speech recognition");
            }
            return;
        }

        // Set recognition listener
        speechRecognizer.setRecognitionListener(recognitionListener);

        Log.d(TAG, "Speech recognizer initialized successfully");
    }

    /**
     * Start listening for user speech
     *
     * User will see/hear a beep indicating they can speak
     */
    public void startListening() {
        if (isListening) {
            Log.w(TAG, "Already listening, ignoring request");
            return;
        }

        if (speechRecognizer == null) {
            Log.e(TAG, "Speech recognizer not initialized");
            if (callback != null) {
                callback.onSpeechError("Speech recognition not initialized. Please restart.");
            }
            return;
        }

        // Create recognition intent
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);

        // Use free-form language model (best for natural speech)
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);

        // Use device's default language
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault());

        // Enable partial results (real-time transcription)
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);

        // Request only the best match
        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);

        // Set prompt text (shows in Google's speech dialog)
        intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "Ask your navigation question...");

        // Prefer offline recognition if available
        intent.putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true);

        Log.d(TAG, "Starting speech recognition");

        try {
            speechRecognizer.startListening(intent);
        } catch (Exception e) {
            Log.e(TAG, "Error starting speech recognition", e);
            if (callback != null) {
                callback.onSpeechError("Failed to start listening: " + e.getMessage());
            }
        }
    }

    /**
     * Stop listening
     * Call this to stop recognition before user finishes speaking
     */
    public void stopListening() {
        if (speechRecognizer != null) {
            Log.d(TAG, "Stopping speech recognition");
            speechRecognizer.stopListening();
        }
        isListening = false;
    }

    /**
     * Cancel recognition
     * More abrupt than stopListening() - use for errors
     */
    public void cancel() {
        if (speechRecognizer != null) {
            Log.d(TAG, "Cancelling speech recognition");
            speechRecognizer.cancel();
        }
        isListening = false;
    }

    /**
     * Release resources
     * Call this in your Activity's onDestroy()
     */
    public void destroy() {
        if (speechRecognizer != null) {
            Log.d(TAG, "Destroying speech recognizer");
            speechRecognizer.destroy();
            speechRecognizer = null;
        }
        isListening = false;
    }

    /**
     * Check if currently listening
     *
     * @return true if speech recognizer is active
     */
    public boolean isListening() {
        return isListening;
    }

    /**
     * Recognition listener implementation
     * Handles all speech recognition events
     */
    private final RecognitionListener recognitionListener = new RecognitionListener() {

        @Override
        public void onReadyForSpeech(Bundle params) {
            isListening = true;
            Log.d(TAG, "Ready for speech - user can speak now");

            if (callback != null) {
                callback.onSpeechReady();
            }
        }

        @Override
        public void onBeginningOfSpeech() {
            Log.d(TAG, "User started speaking");

            if (callback != null) {
                callback.onSpeechStart();
            }
        }

        @Override
        public void onRmsChanged(float rmsdB) {
            // Audio level changed - can be used for visual feedback
            // rmsdB is the sound level in decibels
            // You can use this to show a volume meter
        }

        @Override
        public void onBufferReceived(byte[] buffer) {
            // Audio buffer received - not commonly used
        }

        @Override
        public void onEndOfSpeech() {
            isListening = false;
            Log.d(TAG, "User stopped speaking");

            if (callback != null) {
                callback.onSpeechEnd();
            }
        }

        @Override
        public void onError(int error) {
            isListening = false;

            // Convert error code to user-friendly message
            String errorMessage = getErrorMessage(error);
            Log.e(TAG, "Speech recognition error: " + errorMessage + " (code: " + error + ")");

            if (callback != null) {
                callback.onSpeechError(errorMessage);
            }
        }

        @Override
        public void onResults(Bundle results) {
            isListening = false;

            // Get recognition results
            ArrayList<String> matches = results.getStringArrayList(
                    SpeechRecognizer.RESULTS_RECOGNITION);

            if (matches != null && !matches.isEmpty()) {
                // Take the best match (first result)
                String recognizedText = matches.get(0);

                Log.d(TAG, "Speech recognized: \"" + recognizedText + "\"");
                Log.d(TAG, "All matches: " + matches);

                if (callback != null) {
                    callback.onSpeechResult(recognizedText);
                }
            } else {
                Log.w(TAG, "No speech recognized");

                if (callback != null) {
                    callback.onSpeechError("No speech recognized. Please try again.");
                }
            }
        }

        @Override
        public void onPartialResults(Bundle partialResults) {
            // Partial recognition results (real-time transcription)
            // Can be used to show what's being recognized in real-time

            ArrayList<String> partialMatches = partialResults.getStringArrayList(
                    SpeechRecognizer.RESULTS_RECOGNITION);

            if (partialMatches != null && !partialMatches.isEmpty()) {
                String partialText = partialMatches.get(0);
                Log.d(TAG, "Partial result: " + partialText);

                // You could add a callback here for real-time transcription
                // callback.onPartialResult(partialText);
            }
        }

        @Override
        public void onEvent(int eventType, Bundle params) {
            // Reserved for future events
            Log.d(TAG, "Speech event: " + eventType);
        }
    };

    /**
     * Convert error code to human-readable message
     *
     * @param error Error code from SpeechRecognizer
     * @return User-friendly error message
     */
    private String getErrorMessage(int error) {
        switch (error) {
            case SpeechRecognizer.ERROR_AUDIO:
                return "Audio recording error. Please check your microphone.";

            case SpeechRecognizer.ERROR_CLIENT:
                return "Client error. Please try again.";

            case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS:
                return "Microphone permission required. Please grant permission in settings.";

            case SpeechRecognizer.ERROR_NETWORK:
                return "Network error. Please check your internet connection.";

            case SpeechRecognizer.ERROR_NETWORK_TIMEOUT:
                return "Network timeout. Please try again.";

            case SpeechRecognizer.ERROR_NO_MATCH:
                return "No speech detected. Please speak clearly and try again.";

            case SpeechRecognizer.ERROR_RECOGNIZER_BUSY:
                return "Speech recognition is busy. Please wait and try again.";

            case SpeechRecognizer.ERROR_SERVER:
                return "Server error. Please try again later.";

            case SpeechRecognizer.ERROR_SPEECH_TIMEOUT:
                return "No speech detected. Please speak immediately after the beep.";

            case SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED:
                return "Language not supported. Please change your device language.";

            case SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE:
                return "Language data unavailable. Please check your device settings.";

            default:
                return "Unknown error occurred. Please try again.";
        }
    }

    /**
     * Get detailed error information for debugging
     *
     * @param error Error code
     * @return Detailed error description
     */
    public static String getDetailedError(int error) {
        switch (error) {
            case SpeechRecognizer.ERROR_AUDIO:
                return "ERROR_AUDIO (" + error + "): Audio recording error";
            case SpeechRecognizer.ERROR_CLIENT:
                return "ERROR_CLIENT (" + error + "): Client side error";
            case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS:
                return "ERROR_INSUFFICIENT_PERMISSIONS (" + error + "): Insufficient permissions";
            case SpeechRecognizer.ERROR_NETWORK:
                return "ERROR_NETWORK (" + error + "): Network error";
            case SpeechRecognizer.ERROR_NETWORK_TIMEOUT:
                return "ERROR_NETWORK_TIMEOUT (" + error + "): Network timeout";
            case SpeechRecognizer.ERROR_NO_MATCH:
                return "ERROR_NO_MATCH (" + error + "): No recognition result matched";
            case SpeechRecognizer.ERROR_RECOGNIZER_BUSY:
                return "ERROR_RECOGNIZER_BUSY (" + error + "): RecognitionService busy";
            case SpeechRecognizer.ERROR_SERVER:
                return "ERROR_SERVER (" + error + "): Server error";
            case SpeechRecognizer.ERROR_SPEECH_TIMEOUT:
                return "ERROR_SPEECH_TIMEOUT (" + error + "): No speech input";
            default:
                return "UNKNOWN_ERROR (" + error + ")";
        }
    }
}