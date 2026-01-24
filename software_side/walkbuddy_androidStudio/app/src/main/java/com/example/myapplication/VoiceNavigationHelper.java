package com.example.myapplication;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.media.AudioManager;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.widget.Toast;

import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import java.util.ArrayList;
import java.util.List;

/**
 * Helper class to manage voice navigation functionality
 * Integrates Speech Recognition → YOLO Detection → Gemini LLM → TTS pipeline
 *
 * COMPLETE PIPELINE:
 * 1. User taps microphone button
 * 2. Speech-to-Text captures question
 * 3. YOLO captures detected objects
 * 4. Gemini AI processes question + objects
 * 5. TTS speaks response at MAXIMUM volume
 *
 * Features:
 * - Automatic permission handling
 * - Maximum volume TTS output
 * - YOLO detection integration
 * - Error handling and user feedback
 * - Resource management
 *
 * Usage:
 * VoiceNavigationHelper helper = new VoiceNavigationHelper(activity);
 * helper.setDetectionProvider(() -> getYOLODetections());
 * helper.setTTSAnnouncer(ttsAnnouncer);
 * helper.initialize();
 * helper.startVoiceInteraction();
 */
public class VoiceNavigationHelper {

    private static final String TAG = "VoiceNavHelper";
    private static final int REQUEST_PERMISSIONS = 200;

    private final Activity activity;
    private final Handler mainHandler;

    // Services
    private SpeechRecognitionService speechService;
    private GeminiService geminiService;
    private TTSAnnouncer ttsAnnouncer;
    private AudioManager audioManager;

    // State
    private boolean isInitialized = false;
    private boolean isProcessing = false;
    private int originalVolume = 0;
    private String lastResponse = "";

    /**
     * Interface for providing YOLO detections
     */
    public interface DetectionProvider {
        /**
         * Get current YOLO detections
         * @return List of detected object class names (e.g., ["table", "chair"])
         */
        List<String> getCurrentDetections();
    }

    private DetectionProvider detectionProvider;

    /**
     * Constructor
     *
     * @param activity The activity using voice navigation
     */
    public VoiceNavigationHelper(Activity activity) {
        if (activity == null) {
            throw new IllegalArgumentException("Activity cannot be null");
        }

        this.activity = activity;
        this.mainHandler = new Handler(Looper.getMainLooper());
        this.audioManager = (AudioManager) activity.getSystemService(Activity.AUDIO_SERVICE);

        Log.d(TAG, "VoiceNavigationHelper created");
    }

    /**
     * Set the detection provider (for YOLO integration)
     *
     * @param provider Callback to get current YOLO detections
     *
     * Example:
     * helper.setDetectionProvider(() -> {
     *     return Arrays.asList("table", "chair", "monitor");
     * });
     */
    public void setDetectionProvider(DetectionProvider provider) {
        this.detectionProvider = provider;
        Log.d(TAG, "Detection provider set");
    }

    /**
     * Set TTS announcer (optional - reuse existing one)
     *
     * @param announcer Existing TTSAnnouncer instance
     */
    public void setTTSAnnouncer(TTSAnnouncer announcer) {
        this.ttsAnnouncer = announcer;
        Log.d(TAG, "TTS announcer set externally");
    }

    /**
     * Initialize all services
     * Call this after setting providers and before startVoiceInteraction()
     */
    public void initialize() {
        Log.d(TAG, "Initializing voice navigation services");

        // Check permissions first
        if (!checkPermissions()) {
            Log.w(TAG, "Permissions not granted, requesting...");
            requestPermissions();
            return;
        }

        initializeServices();
    }

    /**
     * Initialize services after permissions granted
     */
    private void initializeServices() {
        Log.d(TAG, "Initializing services with permissions granted");

        try {
            // Initialize TTS (create new if not provided)
            if (ttsAnnouncer == null) {
                ttsAnnouncer = new TTSAnnouncer(activity);
                Log.d(TAG, "TTS initialized (new instance)");
            } else {
                Log.d(TAG, "TTS initialized (existing instance)");
            }

            // Initialize Gemini Service
            geminiService = new GeminiService(activity);

            // Verify API key is set
            if (!geminiService.isReady()) {
                Log.e(TAG, "Gemini service not ready - API key: " + geminiService.getApiKeyPreview());
                showToast("Please set your Gemini API key in strings.xml");
                return;
            }

            Log.d(TAG, "Gemini service initialized - API key: " + geminiService.getApiKeyPreview());

            // Initialize Speech Recognition
            speechService = new SpeechRecognitionService(activity, speechCallback);
            speechService.initialize();
            Log.d(TAG, "Speech recognition initialized");

            isInitialized = true;
            Log.d(TAG, "All services initialized successfully");

            showToast("Voice navigation ready");

        } catch (Exception e) {
            Log.e(TAG, "Error initializing services", e);
            showToast("Error initializing voice navigation: " + e.getMessage());
            isInitialized = false;
        }
    }

    /**
     * Start voice interaction pipeline
     * This is called when user taps the microphone button
     */
    public void startVoiceInteraction() {
        Log.d(TAG, "startVoiceInteraction() called");

        // Check if already processing
        if (isProcessing) {
            Log.w(TAG, "Already processing a request");
            showToast("Please wait, processing previous request");
            return;
        }

        // Check if initialized
        if (!isInitialized) {
            Log.w(TAG, "Services not initialized");
            showToast("Initializing voice navigation...");
            initialize();

            // Try again after a short delay
            mainHandler.postDelayed(this::startVoiceInteraction, 2000);
            return;
        }

        // Check permissions
        if (!checkPermissions()) {
            Log.w(TAG, "Permissions not granted");
            requestPermissions();
            return;
        }

        // Announce that we're listening
        if (ttsAnnouncer != null) {
            ttsAnnouncer.speak("Listening. What's your question?");
        }

        // Start speech recognition after short delay (let TTS finish)
        mainHandler.postDelayed(() -> {
            if (speechService != null) {
                Log.d(TAG, "Starting speech recognition");
                isProcessing = true;
                speechService.startListening();
            } else {
                Log.e(TAG, "Speech service is null");
                showToast("Speech recognition not available");
                isProcessing = false;
            }
        }, 1500);
    }

    /**
     * Stop current interaction
     */
    public void stopInteraction() {
        Log.d(TAG, "Stopping interaction");

        if (speechService != null) {
            speechService.stopListening();
        }

        isProcessing = false;
        restoreVolume();
    }

    /**
     * Repeat last response
     */
    public void repeatLastResponse() {
        if (lastResponse != null && !lastResponse.isEmpty()) {
            Log.d(TAG, "Repeating last response: " + lastResponse);
            speakLoudly(lastResponse);
        } else {
            Log.d(TAG, "No previous response to repeat");
            showToast("No previous response");
        }
    }

    /**
     * Check required permissions
     */
    private boolean checkPermissions() {
        String[] requiredPermissions = {
                Manifest.permission.RECORD_AUDIO,
                Manifest.permission.MODIFY_AUDIO_SETTINGS
        };

        for (String permission : requiredPermissions) {
            if (ContextCompat.checkSelfPermission(activity, permission)
                    != PackageManager.PERMISSION_GRANTED) {
                Log.d(TAG, "Permission not granted: " + permission);
                return false;
            }
        }

        return true;
    }

    /**
     * Request required permissions
     */
    private void requestPermissions() {
        String[] permissions = {
                Manifest.permission.RECORD_AUDIO,
                Manifest.permission.MODIFY_AUDIO_SETTINGS
        };

        ActivityCompat.requestPermissions(activity, permissions, REQUEST_PERMISSIONS);
        Log.d(TAG, "Requested permissions");
    }

    /**
     * Handle permission result
     * Call this from your Activity's onRequestPermissionsResult
     *
     * @param requestCode Request code from onRequestPermissionsResult
     * @param grantResults Grant results array
     */
    public void onPermissionResult(int requestCode, int[] grantResults) {
        if (requestCode == REQUEST_PERMISSIONS) {
            boolean allGranted = true;
            for (int result : grantResults) {
                if (result != PackageManager.PERMISSION_GRANTED) {
                    allGranted = false;
                    break;
                }
            }

            if (allGranted) {
                Log.d(TAG, "Permissions granted");
                initializeServices();
            } else {
                Log.w(TAG, "Permissions denied");
                showToast("Microphone permission required for voice navigation");
            }
        }
    }

    /**
     * Speech recognition callbacks
     */
    private final SpeechRecognitionService.SpeechRecognitionCallback speechCallback =
            new SpeechRecognitionService.SpeechRecognitionCallback() {

                @Override
                public void onSpeechReady() {
                    Log.d(TAG, "Speech ready - user can speak now");
                    mainHandler.post(() -> {
                        showToast("Listening...");
                    });
                }

                @Override
                public void onSpeechStart() {
                    Log.d(TAG, "User started speaking");
                }

                @Override
                public void onSpeechResult(String text) {
                    Log.d(TAG, "Speech recognized: " + text);

                    mainHandler.post(() -> {
                        showToast("You said: " + text);
                    });

                    // STEP 3: Get current YOLO detections
                    List<String> detectedObjects = getCurrentYOLODetections();

                    Log.d(TAG, "Detected objects: " + detectedObjects);

                    // STEP 4: Send to Gemini LLM
                    processWithGemini(text, detectedObjects);
                }

                @Override
                public void onSpeechError(String error) {
                    Log.e(TAG, "Speech error: " + error);
                    isProcessing = false;

                    mainHandler.post(() -> {
                        showToast(error);
                    });
                }

                @Override
                public void onSpeechEnd() {
                    Log.d(TAG, "Speech ended");
                }
            };

    /**
     * Get current YOLO detections
     */
    private List<String> getCurrentYOLODetections() {
        if (detectionProvider != null) {
            try {
                List<String> detections = detectionProvider.getCurrentDetections();
                return detections != null ? detections : new ArrayList<>();
            } catch (Exception e) {
                Log.e(TAG, "Error getting detections from provider", e);
                return new ArrayList<>();
            }
        }

        // Fallback: return empty list
        Log.w(TAG, "No detection provider set, returning empty list");
        return new ArrayList<>();
    }

    /**
     * STEP 4: Process with Gemini LLM
     */
    private void processWithGemini(String userQuestion, List<String> detectedObjects) {
        Log.d(TAG, "Processing with Gemini - Question: " + userQuestion +
                ", Objects: " + detectedObjects);

        mainHandler.post(() -> {
            showToast("Processing...");
        });

        if (geminiService == null) {
            Log.e(TAG, "Gemini service is null");
            speakLoudly("Service error. Please restart the app.");
            isProcessing = false;
            return;
        }

        geminiService.getNavigationGuidance(
                detectedObjects,
                userQuestion,
                new GeminiService.GeminiCallback() {
                    @Override
                    public void onSuccess(String response) {
                        Log.d(TAG, "Gemini response: " + response);

                        // Store for repeat functionality
                        lastResponse = response;

                        // STEP 5-6: Speak response at MAXIMUM volume
                        speakLoudly(response);

                        isProcessing = false;
                    }

                    @Override
                    public void onError(String error) {
                        Log.e(TAG, "Gemini error: " + error);

                        mainHandler.post(() -> {
                            showToast("Error: " + error);
                        });

                        speakLoudly("Sorry, I couldn't process that request. Please try again.");

                        isProcessing = false;
                    }
                }
        );
    }

    /**
     * STEP 6: Speak at MAXIMUM volume
     */
    private void speakLoudly(String text) {
        if (ttsAnnouncer == null) {
            Log.e(TAG, "TTS not available");
            showToast("Text-to-speech not available");
            return;
        }

        Log.d(TAG, "Speaking at maximum volume: " + text);

        // Save current volume
        originalVolume = audioManager.getStreamVolume(AudioManager.STREAM_MUSIC);

        // Set to MAXIMUM volume
        int maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
        audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, maxVolume, 0);

        Log.d(TAG, "Volume set to maximum: " + maxVolume + " (was " + originalVolume + ")");

        // Speak the text
        ttsAnnouncer.speak(text);

        // Restore volume after 5 seconds
        mainHandler.postDelayed(this::restoreVolume, 5000);

        // Also show in UI
        mainHandler.post(() -> {
            showToast(text);
        });
    }

    /**
     * Restore original volume
     */
    private void restoreVolume() {
        if (audioManager != null && originalVolume > 0) {
            audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, originalVolume, 0);
            Log.d(TAG, "Volume restored to: " + originalVolume);
            originalVolume = 0;
        }
    }

    /**
     * Show toast on main thread
     */
    private void showToast(String message) {
        mainHandler.post(() -> {
            Toast.makeText(activity, message, Toast.LENGTH_SHORT).show();
        });
    }

    /**
     * Check if voice navigation is ready
     */
    public boolean isReady() {
        return isInitialized &&
                geminiService != null &&
                geminiService.isReady() &&
                speechService != null &&
                ttsAnnouncer != null;
    }

    /**
     * Check if currently processing a request
     */
    public boolean isProcessing() {
        return isProcessing;
    }

    /**
     * Get last response (for debugging or repeat functionality)
     */
    public String getLastResponse() {
        return lastResponse;
    }

    /**
     * Release resources
     * Call this in your Activity's onDestroy()
     */
    public void release() {
        Log.d(TAG, "Releasing resources");

        if (speechService != null) {
            speechService.destroy();
            speechService = null;
        }

        restoreVolume();

        // Don't shutdown TTS if it was provided externally
        // The activity will handle that
        if (ttsAnnouncer != null) {
            // Only shutdown if we created it
            // ttsAnnouncer.shutdown();
        }

        geminiService = null;
        isInitialized = false;
        isProcessing = false;

        Log.d(TAG, "Resources released");
    }
}