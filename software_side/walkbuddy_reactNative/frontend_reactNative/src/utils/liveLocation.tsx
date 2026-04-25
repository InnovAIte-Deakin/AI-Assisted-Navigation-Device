// app/lib/liveLocation.tsx
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import * as Location from "expo-location";

type Coords = { latitude: number; longitude: number };

type LiveLocationContextType = {
  // Header display values
  currentLocation: string;
  destination: string | null;

  // Destination toggle (header switch)
  preferDestinationView: boolean;
  setPreferDestinationView: (value: boolean) => void;

  // Destination setters (Search/Places can feed this)
  setDestination: (value: string | null) => void;
  clearDestination: () => void;

  // Live GPS watcher control
  liveEnabled: boolean;
  setLiveEnabled: (value: boolean) => void;

  // Debug/diagnostics (optional use)
  lastCoords: Coords | null;
  lastUpdatedAt: number | null;
  lastError: string | null;
};

const LiveLocationContext = createContext<LiveLocationContextType | null>(null);

function safeJoin(parts: Array<string | undefined | null>, sep = " ") {
  return parts
    .map((p) => (p ?? "").trim())
    .filter((p) => p.length > 0)
    .join(sep)
    .trim();
}

function formatAddressLine(a: Location.LocationGeocodedAddress) {
  // Aim: "1 Smith St, Collingwood" (no postcode)
  const street = safeJoin([a.streetNumber, a.street], " ");
  const suburb = a.city || a.subregion || a.region || "";
  const line = safeJoin([street, suburb], ", ");
  return line || "Current location";
}

async function reverseGeocodeToLine(coords: Coords) {
  try {
    const results = await Location.reverseGeocodeAsync({
      latitude: coords.latitude,
      longitude: coords.longitude,
    });

    if (!results || results.length === 0) return "Current location";
    return formatAddressLine(results[0]);
  } catch {
    return "Current location";
  }
}

export function LiveLocationProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [currentLocation, setCurrentLocation] = useState("Current location");
  const [destination, setDestinationState] = useState<string | null>(null);

  const [preferDestinationView, setPreferDestinationView] = useState(false);

  const [liveEnabled, setLiveEnabled] = useState(false);
  const [lastCoords, setLastCoords] = useState<Coords | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  const subscriptionRef = useRef<Location.LocationSubscription | null>(null);
  const geocodeInFlightRef = useRef(false);
  const lastGeocodeAtRef = useRef(0);

  const clearDestination = useCallback(() => {
    setDestinationState(null);
    setPreferDestinationView(false);
  }, []);

  const setDestination = useCallback((value: string | null) => {
    const cleaned = typeof value === "string" ? value.trim() : "";
    setDestinationState(cleaned.length > 0 ? cleaned : null);

    // If a destination is set, keep the switch meaningful
    if (cleaned.length > 0) {
      setPreferDestinationView(true);
    } else {
      setPreferDestinationView(false);
    }
  }, []);

  const stopWatcher = useCallback(() => {
    if (subscriptionRef.current) {
      try {
        subscriptionRef.current.remove();
      } catch {}
      subscriptionRef.current = null;
    }
  }, []);

  const startWatcher = useCallback(async () => {
    stopWatcher();
    setLastError(null);

    const perm = await Location.requestForegroundPermissionsAsync();
    if (perm.status !== "granted") {
      setLastError("Location permission not granted.");
      return;
    }

    subscriptionRef.current = await Location.watchPositionAsync(
      {
        accuracy: Location.Accuracy.BestForNavigation,
        timeInterval: 2000,
        distanceInterval: 5,
      },
      async (loc) => {
        const coords: Coords = {
          latitude: loc.coords.latitude,
          longitude: loc.coords.longitude,
        };

        setLastCoords(coords);

        const now = Date.now();
        setLastUpdatedAt(now);

        // Throttle reverse geocode to avoid hammering OS services
        const throttleMs = 6000;
        if (geocodeInFlightRef.current) return;
        if (now - lastGeocodeAtRef.current < throttleMs) return;

        geocodeInFlightRef.current = true;
        lastGeocodeAtRef.current = now;

        const line = await reverseGeocodeToLine(coords);
        geocodeInFlightRef.current = false;

        // Only update the base location string; header decides what to show
        setCurrentLocation(line);
      }
    );
  }, [stopWatcher]);

  // Manage watcher lifecycle
  useEffect(() => {
    if (!liveEnabled) {
      stopWatcher();
      return;
    }

    startWatcher();

    return () => {
      stopWatcher();
    };
  }, [liveEnabled, startWatcher, stopWatcher]);

  // Optional: if user switches to destination view and destination exists, keep it stable
  useEffect(() => {
    const hasDestination = !!destination && destination.trim().length > 0;
    if (!hasDestination && preferDestinationView) {
      setPreferDestinationView(false);
    }
  }, [destination, preferDestinationView]);

  const value = useMemo<LiveLocationContextType>(() => {
    return {
      currentLocation,
      destination,

      preferDestinationView,
      setPreferDestinationView,

      setDestination,
      clearDestination,

      liveEnabled,
      setLiveEnabled,

      lastCoords,
      lastUpdatedAt,
      lastError,
    };
  }, [
    currentLocation,
    destination,
    preferDestinationView,
    setPreferDestinationView,
    setDestination,
    clearDestination,
    liveEnabled,
    setLiveEnabled,
    lastCoords,
    lastUpdatedAt,
    lastError,
  ]);

  return (
    <LiveLocationContext.Provider value={value}>
      {children}
    </LiveLocationContext.Provider>
  );
}

export function useLiveLocation() {
  const ctx = useContext(LiveLocationContext);
  if (!ctx) {
    throw new Error("useLiveLocation must be used within LiveLocationProvider");
  }
  return ctx;
}
