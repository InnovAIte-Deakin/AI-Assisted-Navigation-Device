package com.example.myapplication;

import android.content.Context;
import android.media.AudioAttributes;
import android.speech.tts.TextToSpeech;

import java.util.LinkedList;
import java.util.Locale;
import java.util.Queue;

public class TTSAnnouncer {
    private final Context appContext;
    private TextToSpeech tts;
    private boolean isReady = false;
    private final Queue<String> pendingUtterances = new LinkedList<>();

    public TTSAnnouncer(Context context) {
        this.appContext = context.getApplicationContext();
        this.tts = new TextToSpeech(appContext, status -> {
            isReady = status == TextToSpeech.SUCCESS && tts.setLanguage(Locale.getDefault()) >= 0;
            if (isReady) {
                tts.setAudioAttributes(new AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build());
                flushQueue();
            }
        });
    }

    public void speak(String text) {
        if (text == null || text.isEmpty()) return;
        if (!isReady) {
            pendingUtterances.add(text);
            return;
        }
        tts.stop();
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, Long.toString(System.currentTimeMillis()));
    }

    private void flushQueue() {
        while (!pendingUtterances.isEmpty() && isReady) {
            String next = pendingUtterances.poll();
            tts.speak(next, TextToSpeech.QUEUE_ADD, null, Long.toString(System.currentTimeMillis()));
        }
    }

    public void shutdown() {
        if (tts != null) {
            tts.shutdown();
            tts = null;
        }
    }
}


