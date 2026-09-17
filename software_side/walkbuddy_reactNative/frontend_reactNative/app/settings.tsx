// app/settings.tsx
import React, { useMemo } from "react";
import { StyleSheet, Switch, Text, View, useWindowDimensions } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import HomeHeader from "./HomeHeader";
import Footer from "./Footer";
import { Spacing, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";
import { useWakeWord } from "@/src/context/ForegroundWakeWordContext";

export default function SettingsPage() {
  const colors = useThemeColors();
  const { width } = useWindowDimensions();
  const { enabled, available, listening, status, setEnabled } = useWakeWord();

  const contentWidth = useMemo(() => {
    const padding = 24;
    const max = 720;
    return Math.min(max, Math.max(320, width - padding * 2));
  }, [width]);

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.background }]} edges={["top"]}>
      <View style={[styles.content, { width: contentWidth }]}>
        <HomeHeader
          showDivider
          showLocation={true}
        />

        <View style={[styles.card, { borderColor: colors.accent, backgroundColor: colors.surface }]}>
          <Text style={[styles.title, { color: colors.text }]}>Settings</Text>
          <View style={styles.settingRow}>
            <View style={styles.settingCopy}>
              <Text style={[styles.subtitle, { color: colors.text }]}>Hey Buddy / Hey WalkBuddy</Text>
              <Text style={[styles.note, { color: colors.textMuted }]}>
                Records short clips for transcription only while WalkBuddy is open.
              </Text>
            </View>
            <Switch
              value={enabled}
              disabled={!available}
              onValueChange={(nextValue) => void setEnabled(nextValue)}
              trackColor={{ false: colors.border, true: colors.accent }}
              thumbColor={enabled ? colors.accentText : colors.textMuted}
              accessibilityLabel="Hey Buddy foreground voice activation"
              accessibilityHint="Turns foreground wake phrase listening on or off"
            />
          </View>
          <Text style={[styles.note, { color: colors.textMuted }]}>
            {available
              ? `${listening ? "Active" : "Status"}: ${status}`
              : "Voice activation is unavailable on this device or browser."}
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
  },

  note: {
    fontSize: Typography.size.xs,
    lineHeight: 16,
  },

  settingRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: Spacing.md,
    marginBottom: Spacing.md,
  },

  settingCopy: {
    flex: 1,
    gap: Spacing.xs,
  },
});
