// app/lib/locationSaver.tsx

/**
 * Location State Provider (production-ready)
 *
 * Goals:
 * - Single, app-wide "current location" source driven by a real Expo Location watcher.
 * - Human-readable location string (no postcode) for the header and anywhere else that needs it.
 * - Destination is event-driven (set when user chooses a destination), not re-rolled or faked.
 * - Header toggle is enabled only when a destination exists.
 *
 * Notes:
 * - This provider does NOT calculate routes. Exterior/Internal navigation screens own that.
 * - This provider is safe to keep long-term (not a throwaway mock).
 *
 * Display style target:
 * - "Corner of Smith St & Johnston St"
 * - "Recognisable place name, Street" (no postcode)
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Platform } from "react-native";
import { useSegments } from "expo-router";
import * as Location from "expo-location";

type LocationContextType = {
  currentLocation: string;
  destination: string | null;

  setCurrentLocation: (value: string) => void;
  setDestination: (value: string | null) => void;

  // Header switch (view preference only)
  preferDestinationView: boolean;
  setPreferDestinationView: (value: boolean) => void;

  // Utility
  clearDestination: () => void;

  // Route info (kept for future use / debugging)
  currentRouteKey: string;
  previousRouteKey: string;
};

const CurrentLocationContext = createContext<LocationContextType | null>(null);

const UPDATE_THROTTLE_MS = 2500;

// Turn this on temporarily when debugging location on web
const DEBUG_LOCATION = true;

function isValidString(v: unknown): v is string {
  return typeof v === "string" && v.trim().length > 0;
}

function cleanAddressPart(v: unknown) {
  if (!isValidString(v)) return "";
  return v.trim();
}

function stripPostcodeAndCountry(input: string) {
  // Remove trailing "VIC 3000" style and any trailing ", Australia"
  // Keep it conservative so we don't accidentally butcher place names.
  let s = input.trim();

  s = s.replace(/\s+\b(?:VIC|NSW|QLD|SA|WA|TAS|NT|ACT)\b\s*\d{4}\b/gi, (m) =>
    m.replace(/\s*\d{4}\b/g, "")
  );

  s = s.replace(/\s*\b\d{4}\b/g, "");
  s = s.replace(/\s*,?\s*Australia\s*$/i, "");
  return s.trim().replace(/\s{2,}/g, " ");
}

function titleCaseStreetName(s: string) {
  // Keep it simple: "smith st" => "Smith St"
  // Avoid heavy rules; reverse geocode often already returns decent casing.
  const cleaned = s.trim();
  if (!cleaned) return "";
  if (/[A-Z]/.test(cleaned)) return cleaned;

  return cleaned
    .split(" ")
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function buildCornerString(street: string, street2: string) {
  const a = titleCaseStreetName(street);
  const b = titleCaseStreetName(street2);
  if (!a || !b) return "";
  return `Corner of ${a} & ${b}`;
}

function buildStreetString(street: string, number?: string) {
  const s = titleCaseStreetName(street);
  if (!s) return "";
  const n = cleanAddressPart(number);
  if (!n) return stripPostcodeAndCountry(s);
  return stripPostcodeAndCountry(`${n} ${s}`);
}

function buildFallbackAreaString(suburb?: string, city?: string) {
  const a = cleanAddressPart(suburb);
  const b = cleanAddressPart(city);
  const joined = [a, b].filter(Boolean).join(", ");
  return stripPostcodeAndCountry(joined);
}

function formatAddressFromGeocode(results: Location.LocationGeocodedAddress[]) {
  const first = results?.[0];
  if (!first) return "";

  const street = cleanAddressPart(first.street);
  const name = cleanAddressPart(first.name);
  const streetNumber = cleanAddressPart(first.streetNumber);

  const city = cleanAddressPart(first.city);
  const district = cleanAddressPart(first.district);
  const subregion = cleanAddressPart(first.subregion);
  const region = cleanAddressPart(first.region);

  // Best case: intersection / corner is not directly available from Expo’s Address.
  // We approximate:
  // - If "name" looks like an intersection (contains '&' or ' and '), display as a corner string.
  // - Else: use "streetNumber street" or "street" or "name" then area fallback.
  const nameLower = name.toLowerCase();
  if (name && (name.includes("&") || nameLower.includes(" and "))) {
    const parts = name
      .replace(/\s+and\s+/gi, " & ")
      .split("&")
      .map((p) => p.trim())
      .filter(Boolean);

    if (parts.length >= 2) {
      const corner = buildCornerString(parts[0], parts[1]);
      if (corner) return corner;
    }
  }

  const streetLine = buildStreetString(street, streetNumber);
  if (streetLine) return streetLine;

  if (name) return stripPostcodeAndCountry(titleCaseStreetName(name));

  const area = buildFallbackAreaString(district || subregion, city || region);
  if (area) return area;

  return "";
}

function coordsFallback(lat: number, lng: number) {
  // This is mainly for web where reverse geocode can be flaky.
  // It proves the watcher is running and permissions are correct.
  return `Near ${lat.toFixed(4)}, ${lng.toFixed(4)}`;
}

export function CurrentLocationProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const segments = useSegments();

  const [currentLocation, setCurrentLocation] = useState<string>("Locating…");
  const [destination, setDestination] = useState<string | null>(null);

  const [preferDestinationView, setPreferDestinationView] = useState(false);

  const [currentRouteKey, setCurrentRouteKey] = useState("");
  const [previousRouteKey, setPreviousRouteKey] = useState("");

  const lastRouteKeyRef = useRef<string>("");
  const watchSubRef = useRef<Location.LocationSubscription | null>(null);
  const lastUpdateAtRef = useRef<number>(0);
  const lastEmittedValueRef = useRef<string>("");

  const clearDestination = useCallback(() => {
    setDestination(null);
    setPreferDestinationView(false);
  }, []);

  const stopWatcher = useCallback(() => {
    if (watchSubRef.current) {
      try {
        watchSubRef.current.remove();
      } catch {
        // Ignore cleanup errors
      }
      watchSubRef.current = null;
    }
  }, []);

  const startWatcher = useCallback(async () => {
    setCurrentLocation("Locating…");

    const { status } = await Location.requestForegroundPermissionsAsync();

    if (DEBUG_LOCATION) {
      console.log("[locationSaver] permission status:", status, "platform:", Platform.OS);
    }

    if (status !== "granted") {
      setCurrentLocation("Location permission required");
      return;
    }

    // Prime with an immediate read (helps Home first load)
    try {
      const loc = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });

      const lat = loc.coords.latitude;
      const lng = loc.coords.longitude;

      if (DEBUG_LOCATION) {
        console.log("[locationSaver] initial coords:", lat, lng);
      }

      try {
        const results = await Location.reverseGeocodeAsync({
          latitude: lat,
          longitude: lng,
        });

        const formatted = formatAddressFromGeocode(results);

        if (DEBUG_LOCATION) {
          console.log("[locationSaver] reverseGeocode results:", results);
          console.log("[locationSaver] formatted:", formatted || "(empty)");
        }

        const safe = formatted || coordsFallback(lat, lng);

        setCurrentLocation(safe);
        lastEmittedValueRef.current = safe;
        lastUpdateAtRef.current = Date.now();
      } catch (err) {
        if (DEBUG_LOCATION) {
          console.warn("[locationSaver] reverseGeocode failed (initial):", err);
        }
        setCurrentLocation(coordsFallback(lat, lng));
      }
    } catch (err) {
      if (DEBUG_LOCATION) {
        console.warn("[locationSaver] getCurrentPosition failed:", err);
      }
      setCurrentLocation("Current location");
    }

    stopWatcher();

    // Watcher: low/medium frequency. Exterior navigation owns high-frequency tracking.
    const sub = await Location.watchPositionAsync(
      {
        accuracy:
          Platform.OS === "ios" || Platform.OS === "android"
            ? Location.Accuracy.Balanced
            : Location.Accuracy.Low,
        timeInterval: 5000,
        distanceInterval: 10,
      },
      async (pos) => {
        const now = Date.now();
        if (now - lastUpdateAtRef.current < UPDATE_THROTTLE_MS) return;

        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;

        try {
          const results = await Location.reverseGeocodeAsync({
            latitude: lat,
            longitude: lng,
          });

          const formatted = formatAddressFromGeocode(results);
          const safe = formatted || coordsFallback(lat, lng);

          if (safe === lastEmittedValueRef.current) {
            lastUpdateAtRef.current = now;
            return;
          }

          setCurrentLocation(safe);
          lastEmittedValueRef.current = safe;
          lastUpdateAtRef.current = now;

          if (DEBUG_LOCATION) {
            console.log("[locationSaver] watch update:", safe);
          }
        } catch (err) {
          if (DEBUG_LOCATION) {
            console.warn("[locationSaver] reverseGeocode failed (watch):", err);
          }

          // Don’t overwrite a good value with an error.
          // But if we only ever had the placeholder, show coords so you can see it's alive.
          if (!lastEmittedValueRef.current || lastEmittedValueRef.current === "Locating…") {
            const safe = coordsFallback(lat, lng);
            setCurrentLocation(safe);
            lastEmittedValueRef.current = safe;
          }

          lastUpdateAtRef.current = now;
        }
      }
    );

    watchSubRef.current = sub;
  }, [stopWatcher]);

  // Start watcher once for the app lifetime
  useEffect(() => {
    startWatcher();
    return () => stopWatcher();
  }, [startWatcher, stopWatcher]);

  // Route tracking (kept, but no longer rerolls data)
  useEffect(() => {
    const routeKey = segments.join("/");

    if (lastRouteKeyRef.current === "") {
      lastRouteKeyRef.current = routeKey;
      setCurrentRouteKey(routeKey);
      return;
    }

    if (routeKey !== lastRouteKeyRef.current) {
      const prev = lastRouteKeyRef.current;
      lastRouteKeyRef.current = routeKey;

      setPreviousRouteKey(prev);
      setCurrentRouteKey(routeKey);
    }
  }, [segments]);

  // Auto-switch header view to destination when a destination is set the first time.
  useEffect(() => {
    if (destination && destination.trim().length > 0) {
      setPreferDestinationView(true);
    } else {
      setPreferDestinationView(false);
    }
  }, [destination]);

  const value = useMemo<LocationContextType>(() => {
    return {
      currentLocation,
      destination,

      setCurrentLocation,
      setDestination,

      preferDestinationView,
      setPreferDestinationView,

      clearDestination,

      currentRouteKey,
      previousRouteKey,
    };
  }, [
    currentLocation,
    destination,
    preferDestinationView,
    clearDestination,
    currentRouteKey,
    previousRouteKey,
  ]);

  return (
    <CurrentLocationContext.Provider value={value}>
      {children}
    </CurrentLocationContext.Provider>
  );
}

export function useCurrentLocation() {
  const context = useContext(CurrentLocationContext);

  if (!context) {
    throw new Error(
      "useCurrentLocation must be used inside CurrentLocationProvider"
    );
  }

  return context;
}
