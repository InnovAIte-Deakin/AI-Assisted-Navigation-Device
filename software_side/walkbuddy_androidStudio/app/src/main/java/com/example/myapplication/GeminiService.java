package com.example.myapplication;

import android.content.Context;
import android.util.Log;

import com.google.ai.client.generativeai.GenerativeModel;
import com.google.ai.client.generativeai.java.GenerativeModelFutures;
import com.google.ai.client.generativeai.type.Content;
import com.google.ai.client.generativeai.type.GenerateContentResponse;
import com.google.common.util.concurrent.FutureCallback;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;

import java.util.List;
import java.util.concurrent.Executor;
import java.util.concurrent.Executors;

/**
 * Service for interacting with Google Gemini FREE LLM
 * Handles navigation guidance generation for visually impaired users
 *
 * Features:
 * - FREE Google Gemini API (1,500 requests/day)
 * - Navigation guidance based on detected objects
 * - Path clearance checking
 * - Environment description
 *
 * Usage:
 * GeminiService service = new GeminiService(context);
 * service.getNavigationGuidance(objects, question, callback);
 */
public class GeminiService {

    private static final String TAG = "GeminiService";

    private final Context context;
    private final String geminiApiKey;
    private final GenerativeModelFutures model;
    private final Executor executor;

    /**
     * Callback interface for async Gemini responses
     */
    public interface GeminiCallback {
        /**
         * Called when Gemini successfully generates a response
         * @param response The generated navigation guidance text
         */
        void onSuccess(String response);

        /**
         * Called when an error occurs
         * @param error Error message describing what went wrong
         */
        void onError(String error);
    }

    /**
     * Constructor - Initializes Gemini service with FREE API
     *
     * @param context Application context
     */
    public GeminiService(Context context) {
        this.context = context.getApplicationContext();

        // Load API key from strings.xml (secure method)
        this.geminiApiKey = context.getString(R.string.gemini_api_key);

        // Initialize executor for async operations
        this.executor = Executors.newSingleThreadExecutor();

        // Initialize Gemini model (FREE tier - gemini-1.5-flash)
        GenerativeModel gm = new GenerativeModel("gemini-1.5-flash", geminiApiKey);
        this.model = GenerativeModelFutures.from(gm);

        Log.d(TAG, "GeminiService initialized with FREE Gemini 1.5 Flash model");
    }

    /**
     * Generate navigation guidance based on detected objects and user question
     *
     * This is the main method for voice navigation queries.
     *
     * @param detectedObjects List of objects detected by YOLO (e.g., ["table", "chair"])
     * @param userQuestion Question asked by user via voice (e.g., "Is the path clear?")
     * @param callback Callback to receive response or error
     *
     * Example:
     * service.getNavigationGuidance(
     *     Arrays.asList("table", "chair"),
     *     "Is the path clear?",
     *     new GeminiCallback() {
     *         void onSuccess(String response) {
     *             // Handle response: "Yes, path clear. Table on right."
     *         }
     *     }
     * );
     */
    public void getNavigationGuidance(List<String> detectedObjects,
                                      String userQuestion,
                                      GeminiCallback callback) {

        if (callback == null) {
            Log.e(TAG, "Callback cannot be null");
            return;
        }

        if (userQuestion == null || userQuestion.trim().isEmpty()) {
            callback.onError("Question cannot be empty");
            return;
        }

        // Build optimized prompt for navigation
        String prompt = buildNavigationPrompt(detectedObjects, userQuestion);

        Log.d(TAG, "Sending to Gemini - Question: " + userQuestion +
                ", Objects: " + (detectedObjects != null ? detectedObjects.size() : 0));

        // Create content for Gemini
        Content content = new Content.Builder()
                .addText(prompt)
                .build();

        // Make async API call to Gemini
        ListenableFuture<GenerateContentResponse> response = model.generateContent(content);

        // Handle response asynchronously
        Futures.addCallback(response, new FutureCallback<GenerateContentResponse>() {
            @Override
            public void onSuccess(GenerateContentResponse result) {
                try {
                    String text = result.getText();
                    if (text != null && !text.isEmpty()) {
                        Log.d(TAG, "Gemini response received: " + text);
                        callback.onSuccess(text.trim());
                    } else {
                        Log.w(TAG, "Empty response from Gemini");
                        callback.onError("No response generated. Please try again.");
                    }
                } catch (Exception e) {
                    Log.e(TAG, "Error processing Gemini response", e);
                    callback.onError("Error processing response: " + e.getMessage());
                }
            }

            @Override
            public void onFailure(Throwable t) {
                Log.e(TAG, "Gemini API call failed", t);

                // Provide user-friendly error message
                String errorMsg;
                if (t.getMessage() != null && t.getMessage().contains("API key")) {
                    errorMsg = "API key error. Please check your configuration.";
                } else if (t.getMessage() != null && t.getMessage().contains("network")) {
                    errorMsg = "Network error. Please check your internet connection.";
                } else {
                    errorMsg = "Navigation guidance failed. Please try again.";
                }

                callback.onError(errorMsg);
            }
        }, executor);
    }

    /**
     * Quick path clearance check (optimized for speed)
     *
     * Faster than full navigation guidance - use for simple "is path clear?" queries
     *
     * @param detectedObjects List of detected obstacles
     * @param callback Callback to receive response
     */
    public void checkPathClearance(List<String> detectedObjects, GeminiCallback callback) {

        if (callback == null) {
            Log.e(TAG, "Callback cannot be null");
            return;
        }

        // If no objects detected, path is clear!
        if (detectedObjects == null || detectedObjects.isEmpty()) {
            Log.d(TAG, "No objects detected - path is clear");
            callback.onSuccess("Path is clear ahead. You may proceed safely.");
            return;
        }

        // Build optimized prompt for quick path check
        String prompt = "You are a safety assistant for visually impaired navigation.\n" +
                "Detected objects: " + String.join(", ", detectedObjects) + "\n\n" +
                "Respond in ONE sentence:\n" +
                "- Is the path safe to walk?\n" +
                "- Which side are obstacles (left/right/center)?\n\n" +
                "Keep response under 15 words.";

        Log.d(TAG, "Quick path check - Objects: " + detectedObjects.size());

        Content content = new Content.Builder().addText(prompt).build();
        ListenableFuture<GenerateContentResponse> response = model.generateContent(content);

        Futures.addCallback(response, new FutureCallback<GenerateContentResponse>() {
            @Override
            public void onSuccess(GenerateContentResponse result) {
                try {
                    String text = result.getText();
                    String safetyText = (text != null && !text.isEmpty())
                            ? text.trim()
                            : "Unable to assess path safety.";

                    Log.d(TAG, "Path check response: " + safetyText);
                    callback.onSuccess(safetyText);
                } catch (Exception e) {
                    Log.e(TAG, "Error processing path check", e);
                    callback.onError("Path check failed: " + e.getMessage());
                }
            }

            @Override
            public void onFailure(Throwable t) {
                Log.e(TAG, "Path check failed", t);
                callback.onError("Path check failed. Please try again.");
            }
        }, executor);
    }

    /**
     * Generate description of current environment
     *
     * Use for "what's around me?" or "describe my surroundings" queries
     *
     * @param detectedObjects List of detected objects
     * @param callback Callback to receive response
     */
    public void describeEnvironment(List<String> detectedObjects, GeminiCallback callback) {

        if (callback == null) {
            Log.e(TAG, "Callback cannot be null");
            return;
        }

        // Handle empty environment
        if (detectedObjects == null || detectedObjects.isEmpty()) {
            Log.d(TAG, "No objects to describe");
            callback.onSuccess("I don't detect any objects in your immediate surroundings.");
            return;
        }

        // Build prompt for environment description
        String prompt = "Describe this environment for a visually impaired person.\n" +
                "Objects present: " + String.join(", ", detectedObjects) + "\n\n" +
                "Provide a brief, helpful description in ONE sentence.\n" +
                "Focus on what's most relevant for safe navigation.";

        Log.d(TAG, "Environment description - Objects: " + detectedObjects.size());

        Content content = new Content.Builder().addText(prompt).build();
        ListenableFuture<GenerateContentResponse> response = model.generateContent(content);

        Futures.addCallback(response, new FutureCallback<GenerateContentResponse>() {
            @Override
            public void onSuccess(GenerateContentResponse result) {
                try {
                    String text = result.getText();
                    String description = (text != null && !text.isEmpty())
                            ? text.trim()
                            : "Multiple objects detected around you.";

                    Log.d(TAG, "Environment description: " + description);
                    callback.onSuccess(description);
                } catch (Exception e) {
                    Log.e(TAG, "Error processing environment description", e);
                    callback.onError("Description failed: " + e.getMessage());
                }
            }

            @Override
            public void onFailure(Throwable t) {
                Log.e(TAG, "Environment description failed", t);
                callback.onError("Environment description failed. Please try again.");
            }
        }, executor);
    }

    /**
     * Build optimized prompt for navigation guidance
     *
     * This creates a carefully crafted prompt that gets the best responses from Gemini
     *
     * @param detectedObjects List of detected objects (can be null/empty)
     * @param userQuestion User's question
     * @return Formatted prompt string
     */
    private String buildNavigationPrompt(List<String> detectedObjects, String userQuestion) {

        // Format objects list
        String objectsList;
        if (detectedObjects == null || detectedObjects.isEmpty()) {
            objectsList = "No obstacles detected in immediate vicinity";
        } else {
            objectsList = String.join(", ", detectedObjects);
        }

        // Build comprehensive prompt with clear instructions
        return "You are an AI navigation assistant for visually impaired users.\n" +
                "Speak naturally and concisely. Use simple, clear language.\n\n" +

                "CURRENT ENVIRONMENT:\n" +
                "Objects detected: " + objectsList + "\n\n" +

                "USER QUESTION:\n" +
                "\"" + userQuestion + "\"\n\n" +

                "INSTRUCTIONS:\n" +
                "- Respond in 1-2 SHORT sentences (maximum 20 words)\n" +
                "- Use directional terms: left, right, ahead, behind, center\n" +
                "- Prioritize safety information first\n" +
                "- Be specific about object positions\n" +
                "- Use natural, conversational tone\n" +
                "- Do NOT mention that you are an AI\n" +
                "- Do NOT ask follow-up questions\n\n" +

                "RESPONSE:";
    }

    /**
     * Check if service is properly initialized
     *
     * @return true if API key is set and model is ready
     */
    public boolean isReady() {
        return geminiApiKey != null &&
                !geminiApiKey.isEmpty() &&
                !geminiApiKey.equals("YOUR_API_KEY_HERE") &&
                model != null;
    }

    /**
     * Get the current API key (for debugging - don't log in production!)
     *
     * @return First 10 characters of API key (masked)
     */
    public String getApiKeyPreview() {
        if (geminiApiKey == null || geminiApiKey.length() < 10) {
            return "NOT_SET";
        }
        return geminiApiKey.substring(0, 10) + "...";
    }
}