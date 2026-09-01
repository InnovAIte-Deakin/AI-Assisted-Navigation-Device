import React, { useEffect, useMemo, useRef, useState } from "react";
import { View, Pressable, StyleSheet, Animated, Easing } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSegments } from "expo-router";

import { Radius, Spacing } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";

// Darker than colors.accent (#0E7C86) — the camera tab uses this instead of
// the shared accent so it reads as a deliberately deeper turquoise, not
// theme-reactive since the app is light-mode-only for now (see theme.ts).
const DARK_TURQUOISE = "#0A575E";
// Camera icon color specifically while the camera tab is active.
const DARK_BLUE = "#1B3A66";

// Trimmed from 7 to 5 icons — the core "get guided somewhere" + "see/hear
// my surroundings" actions, plus Ask a Friend. Audiobooks, Places, and
// Favourites moved to the home screen's quick-actions grid instead of
// living in the tab bar.
const TABS: {
  icon: keyof typeof Ionicons.glyphMap;
  activeIcon: keyof typeof Ionicons.glyphMap;
  route: string;
  size?: number;
  color?: string;
  activeColor?: string;
}[] = [
  { icon: "home-outline", activeIcon: "home", route: "index" },
  { icon: "walk-outline", activeIcon: "walk", route: "exterior" },
  {
    // Solid regardless of active state — the other tabs switch between
    // outline/solid via activeIcon, this one is always the solid variant.
    icon: "camera",
    activeIcon: "camera",
    route: "camera",
    size: 38,
    color: DARK_TURQUOISE,
    activeColor: DARK_BLUE,
  },
  { icon: "business-outline", activeIcon: "business", route: "indoor" },
  { icon: "people-outline", activeIcon: "people", route: "ask-a-friend-web" },
];

// Shared on all 4 sides: bottomBar's own icon-row padding, the highlight's
// horizontal track inset, AND its vertical top/bottom inset. Using one
// constant for all of these keeps the highlight's track locked to the same
// coordinates as the actual icon row (so it stays centered on every icon,
// not just approximately near it) while also giving equal spacing from
// bottomBar's border on every side.
const BAR_SIDE_PADDING = 16;
const ICON_SIZE = 25;
// Vertical-only inset for the highlight, separate from BAR_SIDE_PADDING —
// lets the highlight's height be tuned without touching the pill's own
// size or the horizontal alignment/track math above.
const PILL_VERTICAL_INSET = 8;

export default function Footer({ navigation, insets }: any) {
  const colors = useThemeColors();
  const segments = useSegments();
  const [barWidth, setBarWidth] = useState(0);

  const usable = segments.filter((s) => !s.startsWith("(") && s.length > 0);
  const currentRoute =
    usable.length === 0 ? "index" : usable[usable.length - 1];

  // -1 when the current route isn't one of the footer tabs (e.g. Audiobooks,
  // opened from the home screen's quick actions) — the pill hides instead of
  // defaulting to Home.
  const activeIndex = useMemo(() => {
    return TABS.findIndex((tab) => tab.route === currentRoute);
  }, [currentRoute]);

  const translateX = useRef(new Animated.Value(0)).current;

  // The highlight's track uses the exact same inset as bottomBar's own
  // paddingHorizontal, so each slot lines up precisely with where that same
  // icon actually sits (both are BAR_SIDE_PADDING from the border).
  const trackWidth = useMemo(() => {
    if (!barWidth) return 0;
    return barWidth - BAR_SIDE_PADDING * 2;
  }, [barWidth]);

  const slotWidth = useMemo(() => {
    if (!trackWidth) return 0;
    return trackWidth / TABS.length;
  }, [trackWidth]);

  const pillWidth = slotWidth;

  const getIndicatorX = (index: number) => {
    if (!slotWidth) return 0;
    return BAR_SIDE_PADDING + index * slotWidth;
  };

  useEffect(() => {
    if (activeIndex === -1) return;
    const targetX = getIndicatorX(activeIndex);

    Animated.timing(translateX, {
      toValue: targetX,
      duration: 260,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [activeIndex, slotWidth, pillWidth, translateX]);

  const isActive = (routeName: string) => currentRoute === routeName;

  return (
    <View
      style={[styles.footWrap, { paddingBottom: insets?.bottom ?? 0 }]}
      pointerEvents="box-none"
    >
      <View
        style={[styles.bottomBar, { backgroundColor: colors.background, borderColor: colors.accent }]}
        onLayout={(e) => setBarWidth(e.nativeEvent.layout.width)}
      >
        {barWidth > 0 && (
          <Animated.View
            pointerEvents="none"
            style={[
              styles.activePill,
              {
                width: pillWidth,
                opacity: activeIndex === -1 ? 0 : 1,
                transform: [{ translateX }],
                backgroundColor: colors.accent + "2E",
                shadowColor: colors.accent,
              },
            ]}
          />
        )}

        {TABS.map((tab) => (
          <Pressable
            key={tab.route}
            style={({ pressed }) => [
              styles.bottomItem,
              pressed && styles.pressedItem,
            ]}
            onPress={() => navigation.navigate(tab.route)}
          >
            <Ionicons
              name={isActive(tab.route) ? tab.activeIcon : tab.icon}
              size={tab.size ?? ICON_SIZE}
              color={
                isActive(tab.route)
                  ? tab.activeColor ?? tab.color ?? colors.accent
                  : tab.color ?? colors.accent
              }
            />
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  footWrap: {
    position: "absolute",
    left: 10,
    right: 10,
    bottom: 0,
    paddingHorizontal: Spacing.lg,
  },

  bottomBar: {
    position: "relative",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-around",
    borderRadius: Radius.pill,
    borderWidth: 2,
    paddingVertical: Spacing.md,
    paddingHorizontal: BAR_SIDE_PADDING,
    marginTop: Spacing.xxl,
    marginBottom: Spacing.sm,
    overflow: "hidden",
  },

  bottomItem: {
    flex: 1,
    // Fixed height (not intrinsic) so a larger per-tab icon size (e.g. the
    // camera tab) can't grow bottomBar's overall height or shift the other
    // icons — it just renders bigger, centered, within this same box.
    height: ICON_SIZE + Spacing.sm * 2,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 2,
  },

  activePill: {
    position: "absolute",
    left: 0,
    top: PILL_VERTICAL_INSET,
    bottom: PILL_VERTICAL_INSET,
    borderRadius: Radius.pill,

    // soft glow — radius kept within PILL_VERTICAL_INSET so it fades before
    // bottomBar's overflow:hidden clips it (avoids a hard-edged cutoff)
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.65,
    shadowRadius: 6,
    elevation: 6,
  },

  pressedItem: {
    transform: [{ scale: 0.96 }],
  },
});
