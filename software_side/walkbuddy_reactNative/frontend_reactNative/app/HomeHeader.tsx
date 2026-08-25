import React, { useMemo } from "react";
import { View, Text, Pressable, StyleSheet, Switch } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useCurrentLocation } from "../src/utils/locationSaver";
import { useSession } from "../src/context/SessionContext";
import { Radius, Spacing, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";
import { BackButton } from "@/components/ui/BackButton";

type Props = {
  appTitle?: string;
  onPressProfile?: () => void;
  showDivider?: boolean;
  showLocation?: boolean;
  locationValue?: string;
  /** Replaces the profile icon with a back button, aligned in the same row
   * (for pushed pages like Profile/Places/Favourites where navigating "to
   * profile" from within them doesn't make sense). */
  showBackButton?: boolean;
};

export default function HomeHeader({
  appTitle = "WalkBuddy",
  onPressProfile,
  showDivider = true,
  showLocation = true,
  locationValue = "",
  showBackButton = false,
}: Props) {
  const colors = useThemeColors();
  const router = useRouter();
  const { auth } = useSession();

  const {
    currentLocation,
    destination,
    preferDestinationView,
    setPreferDestinationView,
    latitude,
    longitude,
  } = useCurrentLocation();

  // Only shows the user's actual name when logged in with a profile;
  // otherwise falls back to "there" rather than showing nothing.
  const displayName = useMemo(() => {
    if (auth.status === "loggedInWithProfile" && auth.profile.displayName) {
      return auth.profile.displayName;
    }
    return "there";
  }, [auth]);

  const derived = useMemo(() => {
    const leftText = displayName;

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
    displayName,
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
        <View style={styles.brandGroup}>
          {showBackButton ? (
            <BackButton inline />
          ) : (
            <Pressable
              onPress={handleProfilePress}
              hitSlop={10}
              style={styles.profileBtn}
            >
              <Ionicons name="person-circle-outline" size={34} color={colors.accent} />
            </Pressable>
          )}
          <Text style={[styles.title, { color: colors.text }]} numberOfLines={1}>
            {appTitle}
          </Text>
        </View>
        <View style={styles.greetingStack}>
          <Text style={[styles.welcomeLabel, { color: colors.textMuted }]} numberOfLines={1}>
            Welcome
          </Text>
          <Text style={[styles.greeting, { color: colors.text }]} numberOfLines={1}>
            {derived.leftText}
          </Text>
        </View>
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
  },

  headerRow: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: Spacing.xl,
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.md,
    borderRadius: Radius.md,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 5,
  },

  brandGroup: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    flexShrink: 1,
  },

  greetingStack: {
    alignItems: "flex-end",
    flexShrink: 1,
    marginLeft: Spacing.sm,
  },

  welcomeLabel: {
    fontSize: Typography.size.md,
    fontWeight: "700",
    textAlign: "right",
  },

  greeting: {
    fontSize: Typography.size.md,
    fontWeight: "700",
    textAlign: "right",
  },

  title: {
    fontSize: Typography.size.xxl,
    fontWeight: "900",
    flexShrink: 1,
  },

  profileBtn: {
    paddingVertical: Spacing.xs,
  },

  topDivider: {
    borderBottomWidth: 1,
    marginBottom: Spacing.md,
  },

  locationWrap: {
    width: "100%",
    marginBottom: Spacing.xs,
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
