import React, { useEffect, useMemo, useRef, useState } from "react";
import { View, Pressable, StyleSheet, Animated, Easing } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useSegments } from "expo-router";

import { Radius, Spacing } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";

// Trimmed from 7 to 5 icons — the core "get guided somewhere" + "see/hear
// my surroundings" actions. Ask a Friend, Places, and Favourites moved to
// the home screen's quick-actions grid instead of living in the tab bar.
const TABS: { icon: keyof typeof Ionicons.glyphMap; route: string }[] = [
  { icon: "home-outline", route: "index" },
  { icon: "camera-outline", route: "camera" },
  { icon: "business-outline", route: "indoor" },
  { icon: "walk-outline", route: "exterior" },
  { icon: "book-outline", route: "audiobooks" },
];

const BAR_SIDE_PADDING = 8;

export default function Footer({ navigation }: any) {
  const colors = useThemeColors();
  const segments = useSegments();
  const [barWidth, setBarWidth] = useState(0);

  const usable = segments.filter((s) => !s.startsWith("(") && s.length > 0);
  const currentRoute =
    usable.length === 0 ? "index" : usable[usable.length - 1];

  const activeIndex = useMemo(() => {
    const idx = TABS.findIndex((tab) => tab.route === currentRoute);
    return idx === -1 ? 0 : idx;
  }, [currentRoute]);

  const translateX = useRef(new Animated.Value(0)).current;

  const innerWidth = useMemo(() => {
    if (!barWidth) return 0;
    return barWidth - BAR_SIDE_PADDING * 2;
  }, [barWidth]);

  const slotWidth = useMemo(() => {
    if (!innerWidth) return 0;
    return innerWidth / TABS.length;
  }, [innerWidth]);

  // wider pill so it feels more flush at the edges
  const pillWidth = useMemo(() => {
    if (!slotWidth) return 0;
    return slotWidth + 6;
  }, [slotWidth]);

  const getIndicatorX = (index: number) => {
    if (!slotWidth || !pillWidth) return 0;
    return BAR_SIDE_PADDING + index * slotWidth + (slotWidth - pillWidth) / 2;
  };

  useEffect(() => {
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
    <View style={[styles.footWrap, { backgroundColor: colors.background }]}>
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
                transform: [{ translateX }],
                backgroundColor: "rgba(45, 212, 191, 0.18)",
                borderColor: "rgba(45, 212, 191, 0.55)",
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
              name={tab.icon}
              size={26}
              color={isActive(tab.route) ? colors.text : colors.accent}
            />
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  footWrap: {
    width: "100%",
    paddingHorizontal: Spacing.lg,
  },

  bottomBar: {
    position: "relative",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-around",
    borderRadius: Radius.pill,
    borderWidth: 2,
    paddingVertical: Spacing.lg,
    paddingHorizontal: BAR_SIDE_PADDING,
    marginVertical: Spacing.xxl,
    overflow: "hidden",
  },

  bottomItem: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 2,
    paddingVertical: Spacing.md,
  },

  activePill: {
    position: "absolute",
    left: 0,
    top: 3,
    bottom: 3,
    borderRadius: Radius.pill,
    borderWidth: 1,

    // stronger soft glow
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.65,
    shadowRadius: 12,
    elevation: 10,
  },

  pressedItem: {
    transform: [{ scale: 0.96 }],
  },
});
