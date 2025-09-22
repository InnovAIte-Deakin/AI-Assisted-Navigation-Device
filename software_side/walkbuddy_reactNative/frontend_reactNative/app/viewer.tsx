import React, { useEffect, useMemo, useState } from "react";
import { View, Text, Pressable, StyleSheet, Platform, Linking } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import ModelWebView from "../src/components/ModelWebView";
import { GRADIO_URL } from "../src/config";
import { switchMode, stopAll } from "../src/utils/api";

export default function Viewer() {
  const router = useRouter();
  const { mode } = useLocalSearchParams<{ mode?: "gradio" | "ocr" }>();
  const [loading, setLoading] = useState(true);
  const [rev, setRev] = useState(0); // cache-buster
  const [title, setTitle] = useState("Launching…");

  useEffect(() => {
    const m = (mode === "ocr" ? "ocr" : "gradio");
    setTitle(m === "gradio" ? "Object Detection" : "OCR + TTS");

    // tell main.py to start the chosen UI on :7860
    switchMode(m)
      .catch(e => console.error("switchMode failed:", e))
      .finally(() => {
        // small warmup then show UI
        setTimeout(() => { setRev(x => x + 1); setLoading(false); }, 800);
      });

    return () => { stopAll().catch(() => {}); };
  }, [mode]);

  const url = useMemo(() => `${GRADIO_URL}?v=${rev}`, [rev]);

  const openNewTab = () => {
    if (Platform.OS === "web") window.open(GRADIO_URL, "_blank");
    else Linking.openURL(GRADIO_URL);
  };

  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <Text style={styles.back}>‹ Back</Text>
        </Pressable>
        <Text style={styles.title}>{title}</Text>
        <Pressable onPress={openNewTab} hitSlop={12}>
          <Text style={styles.link}>Open in Tab</Text>
        </Pressable>
      </View>

      <View style={{ flex: 1 }}>
        <ModelWebView url={url} loading={loading} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: "#000" },
  header: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 2, borderBottomColor: "#f9b233"
  },
  back: { color: "#f9b233", fontWeight: "800" },
  title: { color: "#f9b233", fontWeight: "900", fontSize: 16 },
  link: { color: "#f9b233", fontWeight: "800" },
});
