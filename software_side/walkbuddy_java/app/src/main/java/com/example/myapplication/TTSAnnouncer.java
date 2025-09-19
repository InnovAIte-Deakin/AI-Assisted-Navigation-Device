package com.example.myapplication;

import android.content.Context;
import android.media.AudioAttributes;
import android.speech.tts.TextToSpeech;
import android.util.Log;

import java.util.LinkedList;
import java.util.Locale;
import java.util.Queue;

public class TTSAnnouncer {
    private static final String TAG = "TTSAnnouncer";
    private final Context appContext;
    private TextToSpeech tts;
    private boolean isReady = false;
    private final Queue<String> pendingUtterances = new LinkedList<>();

    public TTSAnnouncer(Context context) {
        this.appContext = context.getApplicationContext();
        Log.d(TAG, "Initializing TTS...");
        this.tts = new TextToSpeech(appContext, status -> {
            Log.d(TAG, "TTS initialization status: " + status);
            if (status == TextToSpeech.SUCCESS) {
                int langResult = tts.setLanguage(Locale.getDefault());
                Log.d(TAG, "Language set result: " + langResult);
                isReady = langResult >= 0;
                if (isReady) {
                    Log.d(TAG, "TTS is ready!");
                    tts.setAudioAttributes(new AudioAttributes.Builder()
                            .setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
                            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                            .build());
                    flushQueue();
                } else {
                    Log.e(TAG, "TTS language not supported");
                }
            } else {
                Log.e(TAG, "TTS initialization failed with status: " + status);
                isReady = false;
            }
        });
    }

    public void speak(String text) {
        if (text == null || text.isEmpty()) return;
        Log.d(TAG, "speak() called with: " + text);
        Log.d(TAG, "TTS isReady: " + isReady);
        if (!isReady) {
            Log.d(TAG, "TTS not ready, adding to queue");
            pendingUtterances.add(text);
            return;
        }
        Log.d(TAG, "Speaking: " + text);
        tts.stop();
        int result = tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, Long.toString(System.currentTimeMillis()));
        Log.d(TAG, "TTS speak result: " + result);
    }

    private void flushQueue() {
        Log.d(TAG, "Flushing queue, items: " + pendingUtterances.size());
        while (!pendingUtterances.isEmpty() && isReady) {
            String next = pendingUtterances.poll();
            Log.d(TAG, "Speaking queued: " + next);
            int result = tts.speak(next, TextToSpeech.QUEUE_ADD, null, Long.toString(System.currentTimeMillis()));
            Log.d(TAG, "Queued speak result: " + result);
        }
    }

    public void shutdown() {
        if (tts != null) {
            tts.shutdown();
            tts = null;
        }
    }
}


