import React, { useMemo } from "react";
import { View, Text, Pressable, StyleSheet, Switch } from "react-native";
import Icon from "react-native-vector-icons/FontAwesome";
import { useRouter, useSegments } from "expo-router";
import { useCurrentLocation } from "./lib/locationSaver";

type Props = {
  greeting?: string;
  appTitle?: string;
  onPressProfile?: () => void;
  showDivider?: boolean;
  showLocation?: boolean;
  locationValue?: string;
};

function titleCaseFromSegment(seg: string) {
  const cleaned = (seg ?? "").replace(/[-_]/g, " ").trim();
  if (!cleaned) return "";
  return cleaned
    .split(" ")
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function getRouteNameFromSegments(segments: string[]) {
  const usable = segments.filter((s) => !s.startsWith("(") && s.length > 0);
  if (usable.length === 0) return "";
  const last = usable[usable.length - 1];
  if (last.toLowerCase() === "index") return "Home";
  return titleCaseFromSegment(last);
}

function isHomeBySegments(segments: string[]) {
  const usable = segments.filter((s) => !s.startsWith("(") && s.length > 0);
  if (usable.length === 0) return true;
  const last = (usable[usable.length - 1] ?? "").toLowerCase();
  return last === "home" || last === "index";
}

export default function HomeHeader({
  greeting = "Hi!",
  appTitle = "WalkBuddy",
  onPressProfile,
  showDivider = true,
  showLocation = true,
  locationValue = "",
}: Props) {
  const router = useRouter();
  const segments = useSegments();

  const {
    currentLocation,
    destination,
    preferDestinationView,
    setPreferDestinationView,
    latitude,
    longitude,
  } = useCurrentLocation();

  const derived = useMemo(() => {
    const onHome = isHomeBySegments(segments);
    const routeName = getRouteNameFromSegments(segments);
    const leftText = onHome ? greeting : `${routeName || "Page"} Page`;

    const hasDestination = !!destination && destination.trim().length > 0;
    const showingDestination = hasDestination && preferDestinationView;

    const label = showingDestination ? "DESTINATION" : "LOCATION";
    const value =
      (showingDestination ? destination : currentLocation) || locationValue;

    return {
      leftText,
      hasDestination,
      label,
      value,
      switchValue: hasDestination ? preferDestinationView : false,
    };
  }, [
    segments,
    greeting,
    currentLocation,
    destination,
    preferDestinationView,
    locationValue,
  ]);

  const handleProfilePress = () => {
    if (onPressProfile) {
      onPressProfile();
      return;
    }
    router.push("/profile" as any);
  };

  const handleLocationPress = () => {
    const providerLat =
      typeof latitude === "number" && Number.isFinite(latitude)
        ? latitude
        : undefined;

    const providerLng =
      typeof longitude === "number" && Number.isFinite(longitude)
        ? longitude
        : undefined;

    let parsedLat: number | undefined;
    let parsedLng: number | undefined;

    const text = String(derived.value || "");
    const m = text.match(/(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)/);
    if (m) {
      const a = Number(m[1]);
      const b = Number(m[2]);
      if (Number.isFinite(a) && Number.isFinite(b)) {
        parsedLat = a;
        parsedLng = b;
      }
    }

    const lat = providerLat ?? parsedLat;
    const lng = providerLng ?? parsedLng;

    router.push({
      pathname: "/location-map" as any,
      params: {
        lat: lat !== undefined ? String(lat) : "",
        lng: lng !== undefined ? String(lng) : "",
        label: derived.label,
        value: derived.value || "",
      },
    });
  };

  return (
    <View style={styles.wrap}>
      <View style={styles.headerRow}>
        {/* left text */}
        <Text style={styles.greeting} numberOfLines={1}>
          {derived.leftText}
        </Text>

        {/* perfectly centered title */}
        <Text style={styles.title} numberOfLines={1}>
          {appTitle}
        </Text>

        {/* profile icon */}
        <Pressable
          onPress={handleProfilePress}
          hitSlop={10}
          style={styles.profileBtn}
        >
          <Icon name="user-circle" size={34} color={tokens.gold} />
        </Pressable>
      </View>

      {showDivider && <View style={styles.topDivider} />}

      {showLocation && (
        <View style={styles.locationWrap}>
          <Text style={styles.locationLabel}>{derived.label}</Text>

          <Pressable onPress={handleLocationPress}>
            <View style={styles.locationOuterCard}>
              <View style={styles.locationInnerRow}>
                <Text style={styles.locationValue} numberOfLines={1}>
                  {derived.value || "Current location"}
                </Text>

                <Switch
                  disabled={!derived.hasDestination}
                  value={derived.switchValue}
                  onValueChange={(v) => {
                    if (!derived.hasDestination) return;
                    setPreferDestinationView(v);
                  }}
                  trackColor={{ false: "#23384d", true: "#2d4b66" }}
                  thumbColor={derived.switchValue ? tokens.gold : "#9aa8b6"}
                />
              </View>
            </View>
          </Pressable>
        </View>
      )}
    </View>
  );
}

const tokens = {
  bg: "#071a2a",
  tile: "#0b0f14",
  text: "#e8eef6",
  muted: "#b8c6d4",
  gold: "#f2a900",
  divider: "#f2a900",
};

const styles = StyleSheet.create({
  wrap: {
    width: "100%",
    paddingTop: 12,
    paddingBottom: 6,
  },

  headerRow: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 18,
    paddingTop: 10,
    paddingBottom: 10,
    paddingHorizontal: 10,
    position: "relative",

    backgroundColor: "#11273a",
    borderRadius: 12,

    // iOS shadow
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 4,

    // Android shadow
    elevation: 5,
  },

  greeting: {
    color: tokens.text,
    fontSize: 18,
    fontWeight: "700",
    flexShrink: 1,
    zIndex: 1,
  },

  title: {
    color: tokens.text,
    fontSize: 30,
    fontWeight: "900",
    position: "absolute",
    left: 0,
    right: 0,
    textAlign: "center",
  },

  profileBtn: {
    marginLeft: "auto",
    paddingVertical: 4,
    zIndex: 1,
  },

  topDivider: {
    borderBottomWidth: 1,
    borderBottomColor: tokens.divider,
    marginBottom: 12,
  },

  locationWrap: {
    width: "100%",
    marginBottom: 16,
  },

  locationLabel: {
    color: tokens.muted,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0.6,
    marginBottom: 8,
  },

  locationOuterCard: {
    backgroundColor: tokens.tile,
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 16,
    padding: 12,
  },

  locationInnerRow: {
    backgroundColor: "#0a121a",
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: 14,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
  },

  locationValue: {
    color: tokens.text,
    fontSize: 14,
    fontWeight: "800",
    flexShrink: 1,
  },
});