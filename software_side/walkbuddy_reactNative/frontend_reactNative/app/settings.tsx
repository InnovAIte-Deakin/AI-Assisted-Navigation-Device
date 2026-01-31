// app/settings.tsx
import React, { useMemo } from "react";
import { StyleSheet, Text, View, useWindowDimensions } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import HomeHeader from "./HomeHeader";
import Footer from "./Footer";

const tokens = {
  bg: "#0D1B2A",
  tile: "#111",
  text: "#E0E1DD",
  muted: "#b8c6d4",
  gold: "#FCA311",
};

export default function SettingsPage() {
  const { width } = useWindowDimensions();

  const contentWidth = useMemo(() => {
    const padding = 24;
    const max = 720;
    return Math.min(max, Math.max(320, width - padding * 2));
  }, [width]);

  return (
    <SafeAreaView style={styles.screen} edges={["top"]}>
      <View style={[styles.content, { width: contentWidth }]}>
        <HomeHeader
          title="Settings"
          showDivider
          showLocation={true}
        />

        <View style={styles.card}>
          <Text style={styles.title}>Settings</Text>
          <Text style={styles.subtitle}>
            This screen is intentionally minimal.
          </Text>
          <Text style={styles.note}>
            It exists to keep navigation stable while the real settings
            functionality is implemented.
          </Text>
        </View>

        <Footer />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: tokens.bg,
    alignItems: "center",
  },

  content: {
    flex: 1,
    paddingHorizontal: 12,
    paddingTop: 8,
  },

  card: {
    marginTop: 12,
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 14,
    backgroundColor: tokens.tile,
    paddingVertical: 20,
    paddingHorizontal: 16,
  },

  title: {
    color: tokens.text,
    fontSize: 18,
    fontWeight: "900",
    marginBottom: 6,
  },

  subtitle: {
    color: tokens.text,
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 8,
  },

  note: {
    color: tokens.muted,
    fontSize: 12,
    lineHeight: 16,
  },
});
