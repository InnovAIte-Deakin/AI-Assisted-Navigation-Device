// MapPanel component for native platforms (iOS/Android)
import React from 'react';
import { StyleSheet, View } from 'react-native';
import { WebView } from 'react-native-webview';
import { Location, RouteStep } from '../types/navigation';

interface MapPanelProps {
  currentLocation?: Location;
  routeSteps?: RouteStep[];
  routeGeometry?: number[][]; // Full route polyline [[lat, lng], ...]
  destination?: { lat: number; lng: number; name?: string };
  showMap: boolean;
}

export default function MapPanel({
  currentLocation,
  routeSteps,
  routeGeometry,
  destination,
  showMap,
}: MapPanelProps) {
  if (!showMap) {
    return <MinimalVisualPanel />;
  }

  // For native platforms, use WebView
  return (
    <WebView
      source={{ html: generateMapHTML(currentLocation, routeGeometry, destination) }}
      style={styles.webview}
      javaScriptEnabled
      domStorageEnabled
      originWhitelist={['*']}
    />
  );
}

function MinimalVisualPanel() {
  return (
    <View style={styles.minimalPanel}>
      <View style={styles.arrowContainer}>
        <View style={styles.arrow} />
      </View>
    </View>
  );
}

function generateMapHTML(
  currentLocation?: Location,
  routeGeometry?: number[][],
  destination?: { lat: number; lng: number; name?: string }
): string {
  const lat = currentLocation?.latitude ?? (destination?.lat ?? 0);
  const lng = currentLocation?.longitude ?? (destination?.lng ?? 0);

  // Use route geometry if available, otherwise fall back to destination
  const hasRoute = routeGeometry && routeGeometry.length > 0;
  const boundsCoords = hasRoute ? routeGeometry : (destination ? [[destination.lat, destination.lng]] : []);

  return `
<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    body { margin: 0; padding: 0; overflow: hidden; }
    #map { width: 100%; height: 100vh; }
  </style>
</head>
<body>
  <div id="map"></div>
  <script>
    const map = L.map('map').setView([${lat}, ${lng}], ${hasRoute ? 13 : 15});
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    ${currentLocation ? `
    const currentMarker = L.marker([${currentLocation.latitude}, ${currentLocation.longitude}], {
      icon: L.divIcon({
        className: 'current-location-marker',
        html: '<div style="background-color: #4285F4; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>',
        iconSize: [16, 16],
        iconAnchor: [8, 8]
      })
    }).addTo(map);
    currentMarker.bindPopup('Your Location');
    ` : ''}

    ${destination ? `
    const destMarker = L.marker([${destination.lat}, ${destination.lng}], {
      icon: L.divIcon({
        className: 'destination-marker',
        html: '<div style="background-color: #f9b233; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>',
        iconSize: [20, 20],
        iconAnchor: [10, 10]
      })
    }).addTo(map);
    destMarker.bindPopup('${destination.name || 'Destination'}');
    ` : ''}

    ${hasRoute ? `
    const routeCoords = ${JSON.stringify(routeGeometry)};
    const polyline = L.polyline(routeCoords, { 
      color: '#f9b233', 
      weight: 5,
      opacity: 0.8,
      lineJoin: 'round',
      lineCap: 'round'
    }).addTo(map);
    
    // Fit map to show entire route with padding
    const bounds = polyline.getBounds();
    map.fitBounds(bounds, { padding: [50, 50] });
    ` : ''}
  </script>
</body>
</html>
  `.trim();
}

const styles = StyleSheet.create({
  webview: {
    flex: 1,
    backgroundColor: '#1B263B',
  },
  minimalPanel: {
    flex: 1,
    backgroundColor: '#1B263B',
    alignItems: 'center',
    justifyContent: 'center',
  },
  arrowContainer: {
    width: 120,
    height: 120,
    alignItems: 'center',
    justifyContent: 'center',
  },
  arrow: {
    width: 0,
    height: 0,
    borderLeftWidth: 30,
    borderRightWidth: 30,
    borderBottomWidth: 60,
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    borderBottomColor: '#f9b233',
  },
});
