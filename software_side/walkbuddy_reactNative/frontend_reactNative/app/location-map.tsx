import React, { useEffect, useRef, useState } from "react";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { WebView } from "react-native-webview";
import Icon from "react-native-vector-icons/FontAwesome";
import { useLocalSearchParams, useRouter } from "expo-router";
import * as Location from "expo-location";
import { useCurrentLocation } from "../src/utils/locationSaver";

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

function generateMapHTML(lat: number, lng: number, label: string, value: string) {
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
      background: rgba(11, 15, 20, 0.92);
      border: 2px solid #f2a900;
      border-radius: 12px;
      padding: 10px 12px;
      max-width: calc(100% - 24px);
      color: #e8eef6;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      box-sizing: border-box;
    }
    .badge .label {
      font-size: 11px;
      letter-spacing: 0.6px;
      font-weight: 800;
      color: #b8c6d4;
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
        html: '<div style="background-color:#f2a900;width:18px;height:18px;border-radius:50%;border:3px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.35);"></div>',
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

    const html = generateMapHTML(finalLat, finalLng, derivedLabel, derivedValue);

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
  }, [finalLat, finalLng, derivedLabel, derivedValue]);

  const handleClose = () => {
    router.back();
  };

  const coordsReady = typeof finalLat === "number" && typeof finalLng === "number";

  return (
    <View style={styles.screen}>
      <View style={styles.mapWrap}>
        {Platform.OS === "web" ? (
          <View style={styles.webHost}>
            <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
          </View>
        ) : coordsReady ? (
          <WebView
            style={{ flex: 1 }}
            source={{ html: generateMapHTML(finalLat!, finalLng!, derivedLabel, derivedValue) }}
            originWhitelist={["*"]}
            javaScriptEnabled
          />
        ) : (
          <View style={styles.nativePlaceholder}>
            <Text style={[styles.nativeNote, { marginBottom: 0 }]}>Getting your location…</Text>
          </View>
        )}

        <Pressable
          onPress={handleClose}
          style={styles.closeBtn}
          accessibilityLabel="Close map"
        >
          <Icon name="times" size={22} color="#000" />
        </Pressable>
      </View>

      {Platform.OS === "web" && coordsReady && !webReady && (
        <View style={styles.bottomBanner}>
          <Text style={styles.bottomBannerText}>Loading map…</Text>
        </View>
      )}
    </View>
  );
}

const tokens = {
  bg: "#071a2a",
  gold: "#f2a900",
  tile: "#0b0f14",
  text: "#e8eef6",
};

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: tokens.bg,
  },

  mapWrap: {
    flex: 1,
    backgroundColor: tokens.bg,
  },

  webHost: {
    flex: 1,
    backgroundColor: tokens.bg,
  },

  nativePlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: tokens.bg,
  },

  nativeTriangle: {
    width: 0,
    height: 0,
    borderLeftWidth: 22,
    borderRightWidth: 22,
    borderBottomWidth: 40,
    borderLeftColor: "transparent",
    borderRightColor: "transparent",
    borderBottomColor: tokens.gold,
    marginBottom: 10,
  },

  nativeNote: {
    color: tokens.text,
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
    backgroundColor: tokens.gold,
    alignItems: "center",
    justifyContent: "center",
    elevation: 5,
  },

  bottomBanner: {
    position: "absolute",
    left: 12,
    right: 12,
    bottom: 12,
    backgroundColor: "rgba(11, 15, 20, 0.92)",
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 12,
  },

  bottomBannerText: {
    color: tokens.text,
    fontSize: 12,
    fontWeight: "700",
  },
});
