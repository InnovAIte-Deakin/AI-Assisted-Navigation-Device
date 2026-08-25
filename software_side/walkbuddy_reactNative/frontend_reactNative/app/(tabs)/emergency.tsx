/*
   NOTE:
   The isEmergency variable is currently used to simulate different states.

   This is a UI-only implementation, and proper functionality along with
   additional interactions and features will be added in future updates.
*/

import React from "react";
import { StyleSheet, Text, View, ScrollView } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { Radius, Spacing, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";

export default function EmergencyScreen() {
  const colors = useThemeColors();
  const isEmergency = false;

  // Safety screen: alert/danger state maps to colors.danger, the "all
  // clear" state maps to colors.success. Card/pill backgrounds are a low
  // alpha tint of the status color over the screen background so the two
  // states stay visually distinct while remaining theme-reactive.
  const statusColor = isEmergency ? colors.danger : colors.success;
  const alertCardBg = statusColor + "14";
  const topBarBg = statusColor + "26";

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.background }]}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View style={[styles.simpleHeader, { backgroundColor: colors.surface }]}>
          <Text style={[styles.headerGreeting, { color: colors.text }]}>Emergency</Text>
          <Text style={[styles.simpleHeaderTitle, { color: colors.text }]}>WalkBuddy</Text>
          <Ionicons name="person-circle-outline" size={34} color={colors.accent} />
        </View>

        <View style={[styles.topDivider, { borderBottomColor: colors.accent }]} />

        <View style={styles.mainArea}>
          <View style={styles.statusRow}>
            <View
              style={[
                styles.topBar,
                {
                  borderColor: statusColor,
                  backgroundColor: topBarBg,
                },
              ]}
            >
              <View style={[styles.liveDot, { backgroundColor: statusColor }]} />
              <Text style={[styles.topBarText, { color: statusColor }]}>
                {isEmergency ? "ALERT ACTIVE" : "NO ALERT"}
              </Text>
            </View>

            <Text style={[styles.lastCheckedText, { color: statusColor }]}>
              Last checked: Just now
            </Text>
          </View>

          <View
            style={[
              styles.alertContainer,
              {
                borderColor: statusColor,
                backgroundColor: alertCardBg,
              },
            ]}
          >
            <View
              style={[
                styles.iconCircle,
                {
                  borderColor: statusColor,
                  backgroundColor: topBarBg,
                },
              ]}
            >
              <Ionicons
                name={isEmergency ? "warning-outline" : "happy-outline"}
                size={46}
                color={statusColor}
              />
            </View>

            <Text style={[styles.title, { color: statusColor }]}>
              {isEmergency ? "Emergency Detected" : "No Emergency Detected"}
            </Text>

            <Text style={[styles.subtitle, { color: colors.text }]}>
              {isEmergency
                ? "Safety guidance is now active"
                : "Everything is fine. No danger detected."}
            </Text>
          </View>

          <View style={[styles.statusCard, { backgroundColor: colors.surface, borderColor: statusColor }]}>
            <Text style={[styles.cardLabel, { color: colors.accent }]}>
              {isEmergency ? "Detected Situation" : "Current Status"}
            </Text>

            <Text style={[styles.cardTitle, { color: colors.text }]}>
              {isEmergency ? "Possible hazard nearby" : "Everything is clear"}
            </Text>

            <Text style={[styles.cardText, { color: colors.textMuted }]}>
              {isEmergency
                ? "Stay calm and follow the safety instructions shown on screen."
                : "No threat has been detected. The user can continue moving safely."}
            </Text>
          </View>

          <View style={[styles.voiceCard, { backgroundColor: colors.surfaceElevated, borderColor: colors.accent }]}>
            <Ionicons name="volume-high-outline" size={22} color={colors.accent} />

            <View style={styles.voiceTextBlock}>
              <Text style={[styles.voiceTitle, { color: colors.text }]}>Voice assistant ready</Text>
              <Text style={[styles.voiceText, { color: colors.textMuted }]}>
                {isEmergency
                  ? "Emergency instructions will be read aloud for the user."
                  : "Voice guidance is available if the user needs assistance."}
              </Text>
            </View>
          </View>

          <View style={[styles.instructionCard, { backgroundColor: colors.surfaceElevated, borderColor: colors.border }]}>
            <Text style={[styles.cardLabel, { color: colors.accent }]}>
              {isEmergency ? "Next Step" : "Safe Message"}
            </Text>

            <Text style={[styles.instructionText, { color: colors.text }]}>
              {isEmergency
                ? "Move away from the detected danger and wait for safe navigation guidance."
                : "No action is needed right now. Keep following the normal navigation guidance."}
            </Text>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

/* STYLES — structural only; colors applied inline so they react to
   light/dark via useThemeColors(). */

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },

  scroll: {
    flex: 1,
  },

  content: {
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.sm,
    paddingBottom: 120,
  },

  simpleHeader: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    borderRadius: Radius.md,
    paddingVertical: 14,
    paddingHorizontal: 14,
    marginBottom: Spacing.md,
    elevation: 5,
  },

  headerGreeting: {
    fontSize: Typography.size.md,
    fontWeight: "700",
    flex: 1,
    zIndex: 1,
  },

  simpleHeaderTitle: {
    fontSize: Typography.size.xxl,
    fontWeight: "900",
    position: "absolute",
    left: 0,
    right: 0,
    textAlign: "center",
  },

  topDivider: {
    borderBottomWidth: 1,
    marginBottom: Spacing.md,
  },

  mainArea: {
    width: "100%",
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.xl,
  },

  statusRow: {
    marginBottom: 18,
    alignItems: "center",
  },

  topBar: {
    alignSelf: "center",
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1.5,
    borderRadius: Radius.pill,
    paddingVertical: 9,
    paddingHorizontal: 14,
    marginBottom: Spacing.sm,
  },

  liveDot: {
    width: 9,
    height: 9,
    borderRadius: 5,
    marginRight: Spacing.sm,
  },

  topBarText: {
    fontSize: Typography.size.xs,
    fontWeight: "900",
    letterSpacing: 0.8,
  },

  lastCheckedText: {
    fontSize: Typography.size.xs,
    fontWeight: "700",
    marginTop: 2,
  },

  alertContainer: {
    width: "100%",
    alignItems: "center",
    borderWidth: 1.5,
    borderRadius: Radius.xl,
    paddingVertical: 28,
    paddingHorizontal: Spacing.lg,
    marginBottom: Spacing.lg,
  },

  iconCircle: {
    width: 104,
    height: 104,
    borderRadius: 52,
    borderWidth: 2.5,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 18,
  },

  title: {
    fontSize: 31,
    fontWeight: "900",
    textAlign: "center",
    letterSpacing: 0.4,
  },

  subtitle: {
    fontSize: Typography.size.base,
    fontWeight: "700",
    textAlign: "center",
    marginTop: Spacing.sm,
  },

  statusCard: {
    width: "100%",
    borderWidth: 1.5,
    borderRadius: Radius.xl,
    padding: Spacing.xl,
    marginBottom: Spacing.lg,
  },

  cardLabel: {
    fontSize: Typography.size.xs,
    fontWeight: "900",
    letterSpacing: 0.8,
    textTransform: "uppercase",
    marginBottom: Spacing.sm,
  },

  cardTitle: {
    fontSize: Typography.size.lg,
    fontWeight: "900",
    marginBottom: Spacing.sm,
  },

  cardText: {
    fontSize: 15,
    fontWeight: "700",
    lineHeight: 22,
  },

  voiceCard: {
    width: "100%",
    borderWidth: 2,
    borderRadius: 20,
    padding: 18,
    flexDirection: "row",
    alignItems: "center",
    marginBottom: Spacing.lg,
  },

  voiceTextBlock: {
    flex: 1,
    marginLeft: 14,
  },

  voiceTitle: {
    fontSize: Typography.size.base,
    fontWeight: "900",
    marginBottom: Spacing.xs,
  },

  voiceText: {
    fontSize: 13,
    fontWeight: "700",
    lineHeight: 19,
  },

  instructionCard: {
    width: "100%",
    borderWidth: 1.5,
    borderRadius: 20,
    padding: 18,
  },

  instructionText: {
    fontSize: Typography.size.base,
    fontWeight: "800",
    lineHeight: 23,
  },
});
