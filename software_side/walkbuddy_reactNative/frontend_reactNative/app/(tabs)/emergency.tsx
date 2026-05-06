/*
   NOTE:
   The isEmergency variable is currently used to simulate different states.

   This is a UI-only implementation, and proper functionality along with
   additional interactions and features will be added in future updates.
*/

import React from "react";
import { StyleSheet, Text, View, ScrollView } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Icon from "react-native-vector-icons/FontAwesome";

export default function EmergencyScreen() {
  const isEmergency = false;
  const statusColor = isEmergency ? tokens.red : tokens.green;

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.simpleHeader}>
          <Text style={styles.headerGreeting}>Emergency</Text>
          <Text style={styles.simpleHeaderTitle}>WalkBuddy</Text>
          <Icon name="user-circle" size={34} color={tokens.gold} />
        </View>

        <View style={styles.topDivider} />

        <View style={styles.mainArea}>
          <View style={[styles.topBar, { borderColor: statusColor }]}>
            <View style={[styles.liveDot, { backgroundColor: statusColor }]} />
            <Text style={[styles.topBarText, { color: statusColor }]}>
              {isEmergency ? "ALERT ACTIVE" : "NO ALERT"}
            </Text>
          </View>

          <View style={styles.alertHeader}>
            <View style={[styles.iconCircle, { borderColor: statusColor }]}>
              <Icon
                name={isEmergency ? "exclamation-triangle" : "smile-o"}
                size={46}
                color={statusColor}
              />
            </View>

            <Text style={[styles.title, { color: statusColor }]}>
              {isEmergency ? "Emergency Detected" : "No Emergency Detected"}
            </Text>

            <Text style={styles.subtitle}>
              {isEmergency
                ? "Safety guidance is now active"
                : "Everything is fine. No danger detected."}
            </Text>
          </View>

          <View style={[styles.statusCard, { borderColor: statusColor }]}>
            <Text style={styles.cardLabel}>
              {isEmergency ? "Detected Situation" : "Current Status"}
            </Text>

            <Text style={styles.cardTitle}>
              {isEmergency ? "Possible hazard nearby" : "Everything is clear"}
            </Text>

            <Text style={styles.cardText}>
              {isEmergency
                ? "Stay calm and follow the safety instructions shown on screen."
                : "No threat has been detected. The user can continue moving safely."}
            </Text>
          </View>

          <View style={styles.voiceCard}>
            <Icon name="volume-up" size={22} color={tokens.gold} />

            <View style={styles.voiceTextBlock}>
              <Text style={styles.voiceTitle}>Voice assistant ready</Text>
              <Text style={styles.voiceText}>
                {isEmergency
                  ? "Emergency instructions will be read aloud for the user."
                  : "Voice guidance is available if the user needs assistance."}
              </Text>
            </View>
          </View>

          <View style={styles.instructionCard}>
            <Text style={styles.cardLabel}>
              {isEmergency ? "Next Step" : "Safe Message"}
            </Text>

            <Text style={styles.instructionText}>
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

const tokens = {
  bg: "#071a2a",
  card: "#08131f",
  cardDark: "#0b0f14",
  text: "#e8eef6",
  muted: "#b8c6d4",
  gold: "#f2a900",
  red: "#ff3b30",
  green: "#34c759",
};

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: tokens.bg,
  },

  scroll: {
    flex: 1,
  },

  content: {
    paddingHorizontal: 12,
    paddingTop: 8,
    paddingBottom: 120,
  },

  simpleHeader: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#11273a",
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 14,
    marginBottom: 12,
    elevation: 5,
  },

  headerGreeting: {
    color: tokens.text,
    fontSize: 18,
    fontWeight: "700",
    flex: 1,
    zIndex: 1,
  },

  simpleHeaderTitle: {
    color: tokens.text,
    fontSize: 30,
    fontWeight: "900",
    position: "absolute",
    left: 0,
    right: 0,
    textAlign: "center",
  },

  topDivider: {
    borderBottomWidth: 1,
    borderBottomColor: tokens.gold,
    marginBottom: 12,
  },

  mainArea: {
    width: "100%",
    paddingHorizontal: 12,
    paddingTop: 20,
  },

  topBar: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#151116",
    borderWidth: 1.5,
    borderRadius: 999,
    paddingVertical: 9,
    paddingHorizontal: 14,
    marginBottom: 34,
  },

  liveDot: {
    width: 9,
    height: 9,
    borderRadius: 5,
    marginRight: 8,
  },

  topBarText: {
    fontSize: 12,
    fontWeight: "900",
    letterSpacing: 0.8,
  },

  alertHeader: {
    alignItems: "center",
    marginBottom: 26,
  },

  iconCircle: {
    width: 104,
    height: 104,
    borderRadius: 52,
    borderWidth: 2.5,
    backgroundColor: "#130b0b",
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
    color: tokens.text,
    fontSize: 16,
    fontWeight: "700",
    textAlign: "center",
    marginTop: 8,
  },

  statusCard: {
    width: "100%",
    backgroundColor: tokens.card,
    borderWidth: 1.5,
    borderRadius: 22,
    padding: 20,
    marginBottom: 16,
  },

  cardLabel: {
    color: tokens.gold,
    fontSize: 12,
    fontWeight: "900",
    letterSpacing: 0.8,
    textTransform: "uppercase",
    marginBottom: 8,
  },

  cardTitle: {
    color: tokens.text,
    fontSize: 20,
    fontWeight: "900",
    marginBottom: 8,
  },

  cardText: {
    color: tokens.muted,
    fontSize: 15,
    fontWeight: "700",
    lineHeight: 22,
  },

  voiceCard: {
    width: "100%",
    backgroundColor: tokens.cardDark,
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 20,
    padding: 18,
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 16,
  },

  voiceTextBlock: {
    flex: 1,
    marginLeft: 14,
  },

  voiceTitle: {
    color: tokens.text,
    fontSize: 16,
    fontWeight: "900",
    marginBottom: 4,
  },

  voiceText: {
    color: tokens.muted,
    fontSize: 13,
    fontWeight: "700",
    lineHeight: 19,
  },

  instructionCard: {
    width: "100%",
    backgroundColor: "#0a121a",
    borderWidth: 1.5,
    borderColor: "#29445f",
    borderRadius: 20,
    padding: 18,
  },

  instructionText: {
    color: tokens.text,
    fontSize: 16,
    fontWeight: "800",
    lineHeight: 23,
  },
});