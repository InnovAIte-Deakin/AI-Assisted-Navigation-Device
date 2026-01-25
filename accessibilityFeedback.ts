 // --- Reusable accessibility feedback (haptics + voice) ---
// Throttle to avoid spamming feedback
const lastAlertAtRef = useRef(0);
const lastLabelRef = useRef<string>("");
const lastLabelAtRef = useRef(0);

type FeedbackOptions = {
  enableHaptics?: boolean;
  enableSpeech?: boolean;
  minIntervalMs?: number;   // throttle between ANY alerts
  dedupeLabelMs?: number;   // avoid repeating same label too often

  confidence?: number;      // optional confidence from WebView
  minConfidence?: number;   // optional threshold
};


const triggerAccessibilityFeedback = useCallback(
  async (label: string, opts: FeedbackOptions = {}) => {
    const {
      enableHaptics = true,
      enableSpeech = true,
      minIntervalMs = 800,
      dedupeLabelMs = 1500,
    } = opts;

    const now = Date.now();

    // global throttle
    if (now - lastAlertAtRef.current < minIntervalMs) return;

    // dedupe same label
    if (
      label === lastLabelRef.current &&
      now - lastLabelAtRef.current < dedupeLabelMs
    ) {
      return;
    }

    // update refs
    lastAlertAtRef.current = now;
    lastLabelRef.current = label;
    lastLabelAtRef.current = now;

    // haptics
    if (enableHaptics) {
      try {
        await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
      } catch {}
    }

    // speech (uses your existing speak() throttle)
    if (enableSpeech) {
      speak(label);
    }
  },
  [speak]
);

  // return JSX
  return (
    <View style={styles.previewBox}>
      {(mode === "vision" || mode === "ocr") && (
        <ModelWebView
          url={url}
          loading={loading}
          onObjectDetected={(label: string, confidence?: number) => {
            triggerAccessibilityFeedback(label, { confidence });
          }}
        />
      )}

      {/* rest of your UI */}
    </View>
  );
}

