import React, { useEffect, useRef, useState } from "react";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { WebView } from "react-native-webview";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import * as Location from "expo-location";
import { useCurrentLocation } from "../src/utils/locationSaver";
import { useThemeColors } from "@/hooks/use-theme-colors";

// This screen is web-safe.
// Web uses a Leaflet iframe (same concept as the working exterior map panel).
// Native uses a simple placeholder panel unless you want to wire react-native-maps later.

type Params = {
  lat?: string;
  lng?: string;
  label?: string;
  value?: string;
};

function toNumber(s?: string) {
  if (!s) return undefined;
  const n = Number(s);
  return Number.isFinite(n) ? n : undefined;
}

type MapColors = {
  accent: string;
  text: string;
  textMuted: string;
  surface: string;
};

// Note: this HTML is rendered inside a WebView/iframe (a separate document,
// not part of the React tree), so it can't use useThemeColors() reactively —
// the current palette is threaded in as plain strings at generation time.
function generateMapHTML(lat: number, lng: number, label: string, value: string, colors: MapColors) {
  const safeLabel = (label || "LOCATION").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const safeValue = (value || "").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  return `
<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    html, body { height: 100%; margin: 0; }
    #map { width: 100%; height: 100%; }
    .badge {
      position: absolute;
      left: 12px;
      bottom: 12px;
      z-index: 9999;
      background: ${colors.surface}EB;
      border: 2px solid ${colors.accent};
      border-radius: 12px;
      padding: 10px 12px;
      max-width: calc(100% - 24px);
      color: ${colors.text};
      font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      box-sizing: border-box;
    }
    .badge .label {
      font-size: 11px;
      letter-spacing: 0.6px;
      font-weight: 800;
      color: ${colors.textMuted};
      margin-bottom: 4px;
    }
    .badge .value {
      font-size: 13px;
      font-weight: 800;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  </style>
</head>
<body>
  <div id="map"></div>
  <div class="badge">
    <div class="label">${safeLabel}</div>
    <div class="value">${safeValue || (lat.toFixed(5) + ", " + lng.toFixed(5))}</div>
  </div>
  <script>
    const map = L.map('map').setView([${lat}, ${lng}], 16);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    const marker = L.marker([${lat}, ${lng}], {
      icon: L.divIcon({
        className: 'current-location-marker',
        html: '<div style="background-color:${colors.accent};width:18px;height:18px;border-radius:50%;border:3px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.35);"></div>',
        iconSize: [18, 18],
        iconAnchor: [9, 9]
      })
    }).addTo(map);

    marker.bindPopup('${safeLabel}');
  </script>
</body>
</html>
  `.trim();
}

export default function LocationMapScreen() {
  const colors = useThemeColors();
  const router = useRouter();
  const params = useLocalSearchParams<Params>();

  const { currentLocation, destination, preferDestinationView } = useCurrentLocation();

  const containerRef = useRef<HTMLDivElement | null>(null);
  const [webReady, setWebReady] = useState(false);
  const [liveCoords, setLiveCoords] = useState<{ lat: number; lng: number } | null>(null);

  const paramLat = toNumber(params.lat);
  const paramLng = toNumber(params.lng);

  const finalLat = paramLat ?? liveCoords?.lat;
  const finalLng = paramLng ?? liveCoords?.lng;

  // Fetch live coords as fallback when not passed as params
  useEffect(() => {
    if (paramLat !== undefined && paramLng !== undefined) return;
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== "granted") return;
      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      setLiveCoords({ lat: loc.coords.latitude, lng: loc.coords.longitude });
    })();
  }, [paramLat, paramLng]);

  const derivedLabel =
    params.label ||
    (preferDestinationView && destination ? "DESTINATION" : "LOCATION");

  const derivedValue =
    params.value ||
    (preferDestinationView && destination ? destination : currentLocation) ||
    "";

  useEffect(() => {
    console.log("[location-map] params:", params);
    console.log("[location-map] final coords:", finalLat, finalLng);
  }, [params, finalLat, finalLng]);

  useEffect(() => {
    if (Platform.OS !== "web") return;
    if (!containerRef.current) return;

    if (typeof finalLat !== "number" || typeof finalLng !== "number") {
      containerRef.current.innerHTML = "";
      setWebReady(false);
      return;
    }

    const html = generateMapHTML(finalLat, finalLng, derivedLabel, derivedValue, colors);

    containerRef.current.innerHTML = "";
    const iframe = document.createElement("iframe");
    iframe.setAttribute("srcDoc", html);
    iframe.style.width = "100%";
    iframe.style.height = "100%";
    iframe.style.border = "none";
    iframe.setAttribute("title", "Location Map");
    iframe.setAttribute("sandbox", "allow-scripts allow-same-origin");
    containerRef.current.appendChild(iframe);

    setWebReady(true);
  }, [finalLat, finalLng, derivedLabel, derivedValue, colors]);

  const handleClose = () => {
    router.back();
  };

  const coordsReady = typeof finalLat === "number" && typeof finalLng === "number";

  return (
    <View style={[styles.screen, { backgroundColor: colors.background }]}>
      <View style={[styles.mapWrap, { backgroundColor: colors.background }]}>
        {Platform.OS === "web" ? (
          <View style={[styles.webHost, { backgroundColor: colors.background }]}>
            <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
          </View>
        ) : coordsReady ? (
          <WebView
            style={{ flex: 1 }}
            source={{ html: generateMapHTML(finalLat!, finalLng!, derivedLabel, derivedValue, colors) }}
            originWhitelist={["*"]}
            javaScriptEnabled
          />
        ) : (
          <View style={[styles.nativePlaceholder, { backgroundColor: colors.background }]}>
            <Text style={[styles.nativeNote, { color: colors.text, marginBottom: 0 }]}>Getting your location…</Text>
          </View>
        )}

        <Pressable
          onPress={handleClose}
          style={[styles.closeBtn, { backgroundColor: colors.accent }]}
          accessibilityLabel="Close map"
        >
          <Ionicons name="close-outline" size={22} color={colors.accentText} />
        </Pressable>
      </View>

      {Platform.OS === "web" && coordsReady && !webReady && (
        <View style={[styles.bottomBanner, { backgroundColor: colors.surface + "EB", borderColor: colors.accent }]}>
          <Text style={[styles.bottomBannerText, { color: colors.text }]}>Loading map…</Text>
        </View>
      )}
    </View>
  );
}

/* STYLES — structural only; colors applied inline so they react to
   light/dark via useThemeColors(). */

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },

  mapWrap: {
    flex: 1,
  },

  webHost: {
    flex: 1,
  },

  nativePlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },

  nativeTriangle: {
    width: 0,
    height: 0,
    borderLeftWidth: 22,
    borderRightWidth: 22,
    borderBottomWidth: 40,
    borderLeftColor: "transparent",
    borderRightColor: "transparent",
    marginBottom: 10,
  },

  nativeNote: {
    fontSize: 12,
    opacity: 0.9,
  },

  closeBtn: {
    position: "absolute",
    top: 18,
    right: 18,
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    elevation: 5,
  },

  bottomBanner: {
    position: "absolute",
    left: 12,
    right: 12,
    bottom: 12,
    borderWidth: 2,
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 12,
  },

  bottomBannerText: {
    fontSize: 12,
    fontWeight: "700",
  },
});
