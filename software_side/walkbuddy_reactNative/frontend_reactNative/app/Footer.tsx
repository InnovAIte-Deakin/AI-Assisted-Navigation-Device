import React, { useEffect, useMemo, useRef, useState } from "react";
import { View, Pressable, StyleSheet, Animated, Easing } from "react-native";
import Icon from "react-native-vector-icons/FontAwesome";
import { useSegments } from "expo-router";

const TABS = [
  { icon: "home", route: "index" },
  { icon: "camera", route: "camera" },
  { icon: "building", route: "indoor" },
  { icon: "road", route: "exterior" },
  { icon: "book", route: "audiobooks" },
  { icon: "question-circle", route: "ask-a-friend-web" },
  { icon: "map", route: "places" },
];

const BAR_SIDE_PADDING = 8;

export default function Footer({ navigation }: any) {
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
    <View style={styles.footWrap}>
      <View
        style={styles.bottomBar}
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
            <Icon
              name={tab.icon}
              size={26}
              color={isActive(tab.route) ? "#FFFFFF" : "#FCA311"}
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
    paddingHorizontal: 14,
    backgroundColor: "#0D1B2A",
  },

  bottomBar: {
    position: "relative",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-around",
    backgroundColor: "#0D1B2A",
    borderColor: "#FCA311",
    borderRadius: 999,
    borderWidth: 2,
    paddingVertical: 14,
    paddingHorizontal: BAR_SIDE_PADDING,
    marginVertical: 20,
    overflow: "hidden",
  },

  bottomItem: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 2,
    paddingVertical: 12,
  },

  activePill: {
    position: "absolute",
    left: 0,
    top: 3,
    bottom: 3,
    borderRadius: 999,
    backgroundColor: "rgba(252, 163, 17, 0.18)",
    borderWidth: 1,
    borderColor: "rgba(252, 163, 17, 0.55)",

    // stronger soft glow
    shadowColor: "#FCA311",
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.65,
    shadowRadius: 12,
    elevation: 10,
  },

  pressedItem: {
    transform: [{ scale: 0.96 }],
  },
});