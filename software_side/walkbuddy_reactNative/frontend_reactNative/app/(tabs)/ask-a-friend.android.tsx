import React, { Suspense } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import Constants from "expo-constants";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import { Radius, Spacing, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";
import { PageHeader } from "@/components/ui/PageHeader";

const AskAFriendAgora = React.lazy(
  () => import("@/components/AskAFriendAgora.android"),
);

function ExpoGoNotice() {
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
          Assistance calling requires the WalkBuddy development build
        </Text>

        <Text style={[styles.message, { color: colors.textMuted }]}>
          This feature uses Agora for secure camera, microphone, and video
          access. It is unavailable in Expo Go, but the rest of WalkBuddy can
          still be used normally.
        </Text>
      </View>
    </View>
  );
}

export default function AskAFriendAndroidScreen() {
  const isExpoGo = Constants.executionEnvironment === "storeClient";

  if (isExpoGo) {
    return <ExpoGoNotice />;
  }

  return (
    <Suspense
      fallback={
        <View style={styles.loading}>
          <ActivityIndicator size="large" />
        </View>
      }
    >
      <AskAFriendAgora />
    </Suspense>
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
  loading: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
});