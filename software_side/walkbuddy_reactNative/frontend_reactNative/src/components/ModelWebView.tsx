//-- the starting one which works--

// // src/components/ModelWebView.tsx
// import React, { memo } from "react";
// import { Platform, View, ActivityIndicator, StyleSheet } from "react-native";
// import { WebView } from "react-native-webview";

// type Props = { url: string; loading?: boolean };

// function ModelWebView({ url, loading }: Props) {
//   if (Platform.OS === "web") {
//     return (
//       <div style={{ position: "relative", width: "100%", height: "100%" }}>
//         {loading && (
//           <div style={{
//             position: "absolute", inset: 0, display: "grid", placeItems: "center",
//             background: "rgba(0,0,0,0.25)", zIndex: 1
//           }}>
//             <span style={{ color: "#fff" }}>loading…</span>
//           </div>
//         )}
//         <iframe
//           key={url}
//           src={url}
//           style={{
//             border: 0,
//             width: "100%",
//             height: "100%",
//             backgroundColor: "transparent",   // 👈 allow transparency
//           }}
//           allow="camera; microphone; clipboard-read; clipboard-write; autoplay; fullscreen *"
//           allowFullScreen
//           referrerPolicy="no-referrer"
//           sandbox="allow-scripts allow-same-origin allow-forms allow-downloads allow-popups"
//         />
//       </div>
//     );
//   }

//   return (
//     <View style={styles.container}>
//       {loading && (
//         <View style={styles.loader}><ActivityIndicator /></View>
//       )}
//       <WebView
//         source={{ uri: url }}
//         javaScriptEnabled
//         domStorageEnabled
//         allowsInlineMediaPlayback
//         mediaPlaybackRequiresUserAction={false}
//         startInLoadingState
//         style={{ backgroundColor: "transparent" }}   // 👈 important
//         // @ts-ignore
//         mediaCapturePermissionGrantType="grant"
//       />
//     </View>
//   );
// }

// export default memo(ModelWebView);

// const styles = StyleSheet.create({
//   container: { flex: 1, backgroundColor: "transparent" },   // 👈 transparent background
//   loader: { position: "absolute", inset: 0, alignItems: "center", justifyContent: "center", zIndex: 1 }
// });

//-----------------------------------
// --- the second one with is correct but not workinh

// src/components/ModelWebView.tsx --no uncomment

// import React, { memo, useState } from "react";
// import { Platform, View, ActivityIndicator, StyleSheet, Text } from "react-native";
// import { WebView } from "react-native-webview";

// type Props = { url: string; loading?: boolean };

// function ModelWebView({ url, loading }: Props) {
//   const [err, setErr] = useState<string | null>(null);

//   if (Platform.OS === "web") {
//     // IMPORTANT: broader sandbox + allow
//     return (
//       <div style={{ position: "relative", width: "100%", height: "100%" }}>
//         {loading && (
//           <div style={{
//             position: "absolute", inset: 0, display: "grid", placeItems: "center",
//             background: "rgba(0,0,0,0.25)", zIndex: 1
//           }}>
//             <span style={{ color: "#fff" }}>launching…</span>
//           </div>
//         )}
//         {err && (
//           <div style={{
//             position: "absolute", inset: 0, display: "grid", placeItems: "center",
//             background: "rgba(255,0,0,0.12)", zIndex: 2
//           }}>
//             <pre style={{ color: "#fff", padding: 12, whiteSpace: "pre-wrap" }}>{err}</pre>
//           </div>
//         )}
//         <iframe
//           key={url}                                  // force reload when url changes
//           src={url}
//           style={{ border: 0, width: "100%", height: "100%" }}
//           allow="camera; microphone; clipboard-read; clipboard-write; autoplay; fullscreen *"
//           // Slightly looser sandbox so Gradio can run WS/fetch in iframe
//           sandbox="allow-scripts allow-same-origin allow-forms allow-downloads allow-popups allow-modals"
//           referrerPolicy="no-referrer"
//           onError={() => setErr("iframe failed to load. Check GRADIO_URL host/port reachability.")}
//         />
//       </div>
//     );
//   }

//   return (
//     <View style={styles.container}>
//       {(loading || !url) && (
//         <View style={styles.loader}><ActivityIndicator /></View>
//       )}
//       {err && (
//         <View style={styles.error}>
//           <Text style={{ color: "#fff" }}>{err}</Text>
//         </View>
//       )}
//       <WebView
//         // allow any http(s) origin
//         originWhitelist={["*"]}
//         source={{ uri: url }}
//         javaScriptEnabled
//         domStorageEnabled
//         allowsInlineMediaPlayback
//         mediaPlaybackRequiresUserAction={false}
//         // Android: allow http + ws to 7860
//         mixedContentMode="always"
//         // iOS: transparent background not required, but harmless
//         style={{ backgroundColor: "transparent" }}
//         // Helps camera/mic perms for newer RN WebView
//         // @ts-ignore
//         mediaCapturePermissionGrantType="grant"
//         onHttpError={(e) => setErr(`HTTP ${e.nativeEvent.statusCode} loading ${url}`)}
//         onError={(e) => setErr(`WebView error: ${e.nativeEvent.description}`)}
//       />
//     </View>
//   );
// }

// export default memo(ModelWebView);

// const styles = StyleSheet.create({
//   container: { flex: 1, backgroundColor: "#000" },
//   loader: { position: "absolute", inset: 0, alignItems: "center", justifyContent: "center", zIndex: 1 },
//   error: { position: "absolute", inset: 0, alignItems: "center", justifyContent: "center", padding: 12, backgroundColor: "#000C" }
// });

// -------------------

// src/components/ModelWebView.tsx
import React, { memo, useState } from "react";
import { Platform, View, ActivityIndicator, StyleSheet, Text } from "react-native";
import { WebView } from "react-native-webview";

type Props = { url: string; loading?: boolean };

function ModelWebView({ url, loading }: Props) {
  const [err, setErr] = useState<string | null>(null);

  if (Platform.OS === "web") {
    // IMPORTANT:
    // - No sandbox attribute (can restrict internals like WS/fetch in some setups)
    // - Same "allow" as your working viewer
    // - Height is 100% of parent; make sure parent sets an explicit height
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
          key={url} // force reload when url changes (?v= cache-buster)
          src={url}
          style={{
            border: 0,
            width: "100%",
            height: "100%",
            background: "transparent",
          }}
          // allow everything Gradio typically needs
          allow="camera; microphone; clipboard-read; clipboard-write; autoplay; fullscreen *; geolocation *"
          referrerPolicy="no-referrer"
          onError={() => setErr("iframe failed to load. Is GRADIO_URL reachable from this page?")}
        />
      </div>
    );
  }

  // Native
  return (
    <View style={styles.container}>
      {(loading || !url) && <View style={styles.loader}><ActivityIndicator /></View>}
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
        // @ts-ignore
        mediaCapturePermissionGrantType="grant"
        onHttpError={(e) => setErr(`HTTP ${e.nativeEvent.statusCode} loading ${url}`)}
        onError={(e) => setErr(`WebView error: ${e.nativeEvent.description}`)}
      />
    </View>
  );
}

export default memo(ModelWebView);

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#000" },
  loader: { position: "absolute", inset: 0, alignItems: "center", justifyContent: "center", zIndex: 1 },
  error: { position: "absolute", inset: 0, alignItems: "center", justifyContent: "center", padding: 12, backgroundColor: "#000C" },
});
