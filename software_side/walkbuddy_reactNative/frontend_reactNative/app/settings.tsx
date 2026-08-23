// app/settings.tsx
import React, { useMemo } from "react";
import { StyleSheet, Text, View, useWindowDimensions } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import HomeHeader from "./HomeHeader";
import Footer from "./Footer";
import { Spacing, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";

export default function SettingsPage() {
  const colors = useThemeColors();
  const { width } = useWindowDimensions();

  const contentWidth = useMemo(() => {
    const padding = 24;
    const max = 720;
    return Math.min(max, Math.max(320, width - padding * 2));
  }, [width]);

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.background }]} edges={["top"]}>
      <View style={[styles.content, { width: contentWidth }]}>
        <HomeHeader
          title="Settings"
          showDivider
          showLocation={true}
        />

        <View style={[styles.card, { borderColor: colors.accent, backgroundColor: colors.surface }]}>
          <Text style={[styles.title, { color: colors.text }]}>Settings</Text>
          <Text style={[styles.subtitle, { color: colors.text }]}>
            This screen is intentionally minimal.
          </Text>
          <Text style={[styles.note, { color: colors.textMuted }]}>
            It exists to keep navigation stable while the real settings
            functionality is implemented.
          </Text>
        </View>

        <Footer />
      </View>
    </SafeAreaView>
  );
}

/* STYLES — structural only; colors applied inline so they react to
   light/dark via useThemeColors(). */

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    alignItems: "center",
  },

  content: {
    flex: 1,
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.sm,
  },

  card: {
    marginTop: Spacing.md,
    borderWidth: 2,
    borderRadius: 14,
    paddingVertical: Spacing.xl,
    paddingHorizontal: Spacing.lg,
  },

  title: {
    fontSize: Typography.size.md,
    fontWeight: "900",
    marginBottom: 6,
  },

  subtitle: {
    fontSize: Typography.size.sm,
    fontWeight: "700",
    marginBottom: Spacing.sm,
  },

  note: {
    fontSize: Typography.size.xs,
    lineHeight: 16,
  },
});
