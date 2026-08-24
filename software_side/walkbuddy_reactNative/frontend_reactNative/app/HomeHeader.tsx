import React, { useMemo } from "react";
import { View, Text, Pressable, StyleSheet, Switch } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter, useSegments } from "expo-router";
import { useCurrentLocation } from "../src/utils/locationSaver";
import { Radius, Spacing, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";

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
  const colors = useThemeColors();
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
    const leftText = onHome ? greeting : routeName || "Page";

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
      <View style={[styles.headerRow, { backgroundColor: colors.surface }]}>
        <Text style={[styles.greeting, { color: colors.text }]} numberOfLines={1}>
          {derived.leftText}
        </Text>
        <Text style={[styles.title, { color: colors.text }]} numberOfLines={1}>
          {appTitle}
        </Text>
        <Pressable
          onPress={handleProfilePress}
          hitSlop={10}
          style={styles.profileBtn}
        >
          <Ionicons name="person-circle-outline" size={34} color={colors.accent} />
        </Pressable>
      </View>

      {showDivider && <View style={[styles.topDivider, { borderBottomColor: colors.accent }]} />}

      {showLocation && (
        <View style={styles.locationWrap}>
          <Text style={[styles.locationLabel, { color: colors.textMuted }]}>{derived.label}</Text>
          <Pressable onPress={handleLocationPress}>
            <View style={[styles.locationCard, { backgroundColor: colors.surfaceElevated, borderColor: colors.border }]}>
              <Ionicons name="location-outline" size={16} color={colors.accent} style={styles.locationIcon} />
              <Text style={[styles.locationValue, { color: colors.text }]} numberOfLines={1}>
                {derived.value || "Current location"}
              </Text>
              <Switch
                disabled={!derived.hasDestination}
                value={derived.switchValue}
                onValueChange={(v) => {
                  if (!derived.hasDestination) return;
                  setPreferDestinationView(v);
                }}
                trackColor={{ false: colors.border, true: colors.surfaceElevated }}
                thumbColor={derived.switchValue ? colors.accent : colors.textMuted}
              />
            </View>
          </Pressable>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    width: "100%",
    paddingTop: Spacing.md,
    paddingBottom: Spacing.xs,
  },

  headerRow: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    marginBottom: Spacing.xl,
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.md,
    position: "relative",
    borderRadius: Radius.md,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 5,
  },

  greeting: {
    fontSize: Typography.size.md,
    fontWeight: "700",
    flexShrink: 1,
    zIndex: 1,
  },

  title: {
    fontSize: Typography.size.xxl,
    fontWeight: "900",
    position: "absolute",
    left: 0,
    right: 0,
    textAlign: "center",
  },

  profileBtn: {
    marginLeft: "auto",
    paddingVertical: Spacing.xs,
    zIndex: 1,
  },

  topDivider: {
    borderBottomWidth: 1,
    marginBottom: Spacing.md,
  },

  locationWrap: {
    width: "100%",
    marginBottom: Spacing.lg,
  },

  locationLabel: {
    fontSize: Typography.size.xs,
    fontWeight: "800",
    letterSpacing: 0.6,
    marginBottom: Spacing.sm,
  },

  locationCard: {
    borderWidth: 1.5,
    borderRadius: Radius.lg,
    paddingVertical: Spacing.lg,
    paddingHorizontal: Spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
  },

  locationIcon: {
    marginRight: 2,
  },

  locationValue: {
    fontSize: Typography.size.sm,
    fontWeight: "700",
    flex: 1,
  },
});
