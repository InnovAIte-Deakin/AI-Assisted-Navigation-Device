import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import { Radius, Spacing, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";
import { PageHeader } from "@/components/ui/PageHeader";

export default function AskAFriendIosScreen() {
  const colors = useThemeColors();

  return (
    <View style={[styles.screen, { backgroundColor: colors.background }]}>
      <PageHeader title="Ask a Friend" onBackPress={() => router.back()} />

      <View style={[styles.card, { backgroundColor: colors.surface }]}>
        <Ionicons
          name="phone-portrait-outline"
          size={48}
          color={colors.accent}
        />

        <Text style={[styles.title, { color: colors.text }]}>
          Assistance calling is not available on iPhone yet
        </Text>

        <Text style={[styles.message, { color: colors.textMuted }]}>
          WalkBuddy’s secure two-way assistance call is currently being tested
          on the Android development build. iPhone calling support will be
          added in a future update.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },
  card: {
    margin: Spacing.lg,
    padding: Spacing.xl,
    borderRadius: Radius.md,
    alignItems: "center",
  },
  title: {
    marginTop: Spacing.md,
    fontSize: Typography.size.lg,
    fontWeight: "700",
    textAlign: "center",
  },
  message: {
    marginTop: Spacing.sm,
    fontSize: Typography.size.base,
    lineHeight: 22,
    textAlign: "center",
  },
});