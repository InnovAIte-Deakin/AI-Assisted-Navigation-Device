// src/components/ModelWebView.tsx
import React, { memo, useState } from "react";
import {
  ActivityIndicator,
  Platform,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { WebView } from "react-native-webview";

type Props = {
  url: string;
  loading?: boolean;
};

function ModelWebView({ url, loading }: Props) {
  const [err, setErr] = useState<string | null>(null);

  if (!url) {
    return (
      <View style={styles.container}>
        <View style={styles.loader}>
          <ActivityIndicator />
        </View>
      </View>
    );
  }

  // ---------- WEB (browser) ----------
  if (Platform.OS === "web") {
    return (
      <div style={{ position: "relative", width: "100%", height: "100%" }}>
        {loading && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "grid",
              placeItems: "center",
              background: "rgba(0,0,0,0.25)",
              zIndex: 1,
            }}
          >
            <span style={{ color: "#fff" }}>launching…</span>
          </div>
        )}
        {err && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "grid",
              placeItems: "center",
              background: "rgba(255,0,0,0.12)",
              zIndex: 2,
              padding: 12,
            }}
          >
            <pre style={{ color: "#fff", whiteSpace: "pre-wrap" }}>{err}</pre>
          </div>
        )}
        <iframe
          key={url} 
          src={url}
          style={{
            border: 0,
            width: "100%",
            height: "100%",
            background: "transparent",
          }}
          allow="camera; microphone; clipboard-read; clipboard-write; autoplay; fullscreen *; geolocation *"
          referrerPolicy="no-referrer"
          onError={() =>
            setErr(
              "iframe failed to load. Is the backend URL reachable from this page?"
            )
          }
        />
      </div>
    );
  }

  // ---------- NATIVE (Expo Go / iOS / Android) ----------
  return (
    <View style={styles.container}>
      {(loading || !url) && (
        <View style={styles.loader}>
          <ActivityIndicator />
        </View>
      )}
      {err && (
        <View style={styles.error}>
          <Text style={{ color: "#fff" }}>{err}</Text>
        </View>
      )}
      <WebView
        originWhitelist={["*"]}
        source={{ uri: url }}
        javaScriptEnabled
        domStorageEnabled
        allowsInlineMediaPlayback
        mediaPlaybackRequiresUserAction={false}
        mixedContentMode="always"
        style={{ backgroundColor: "transparent" }}
        mediaCapturePermissionGrantType="grant"
        onHttpError={(e) =>
          setErr(`HTTP ${e.nativeEvent.statusCode} loading ${url}`)
        }
        onError={(e) =>
          setErr(`WebView error: ${e.nativeEvent.description ?? "unknown"}`)
        }
      />
    </View>
  );
}

export default memo(ModelWebView);

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#000" },
  loader: {
    position: "absolute",
    inset: 0,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1,
  },
  error: {
    position: "absolute",
    inset: 0,
    alignItems: "center",
    justifyContent: "center",
    padding: 12,
    backgroundColor: "#000C",
    zIndex: 2,
  },
});
