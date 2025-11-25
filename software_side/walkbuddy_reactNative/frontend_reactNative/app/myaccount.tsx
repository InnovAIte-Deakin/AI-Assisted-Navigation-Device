// app/myaccount.tsx
import React from "react";
import {
  ActivityIndicator,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import { useAuth } from "../src/context/AuthContext";

const GOLD = "#FFA500";
const BG = "#1B263B";
const ROW_BG = "#333333";

export default function MyAccountScreen() {
  const router = useRouter();
  const { profile, user, loading } = useAuth();

  // While auth/profile is loading
  if (loading) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color={GOLD} />
          <Text style={styles.loadingText}>Loading account…</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Not logged in / no profile
  if (!user || !profile) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <ScrollView contentContainerStyle={styles.container}>
          <View style={styles.header}>
            <TouchableOpacity onPress={() => router.back()}>
              <Text style={styles.backArrow}>←</Text>
            </TouchableOpacity>
            <Text style={styles.headerTitle}>MY ACCOUNT</Text>
          </View>

          <View style={styles.center}>
            <Text style={styles.infoText}>
              You are not logged in. Please log in to view your account.
            </Text>
            <TouchableOpacity
              style={styles.loginButton}
              onPress={() => router.push("/login")}
            >
              <Text style={styles.loginButtonText}>Go to login</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </SafeAreaView>
    );
  }

  const initial =
    profile.firstName && profile.firstName.length > 0
      ? profile.firstName[0].toUpperCase()
      : "?";

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.container}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()}>
            <Text style={styles.backArrow}>←</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle}>MY ACCOUNT</Text>
        </View>

        {/* Profile Icon */}
        <View style={styles.profileContainer}>
          <View style={styles.profileIcon}>
            <Text style={styles.profileText}>{initial}</Text>
          </View>
          <Text style={styles.profileName}>{profile.firstName}</Text>
        </View>

        {/* Rows */}
        <View style={styles.row}>
          <Text style={styles.rowLabel}>NAME</Text>
          <Text style={styles.rowValue}>{profile.firstName}</Text>
        </View>

        <View style={styles.row}>
          <Text style={styles.rowLabel}>AGE</Text>
          <Text style={styles.rowValue}>{profile.age}</Text>
        </View>

        <View style={styles.row}>
          <Text style={styles.rowLabel}>ADDRESS</Text>
          <Text style={styles.rowValue}>Not set</Text>
        </View>

        <View style={styles.row}>
          <Text style={styles.rowLabel}>EMAIL</Text>
          <Text style={styles.rowValue}>{profile.email}</Text>
        </View>

        <View style={styles.row}>
          <Text style={styles.rowLabel}>LANGUAGE</Text>
          <Text style={styles.rowValue}>{profile.language}</Text>
        </View>

        <View style={styles.row}>
          <Text style={styles.rowLabel}>ROLE</Text>
          <Text style={styles.rowValue}>{profile.role}</Text>
        </View>

        {/* You can later wire VOICE SETTINGS / HELP to real screens */}
        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: BG,
  },
  container: {
    flexGrow: 1,
    paddingHorizontal: 20,
    paddingTop: 20,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 30,
    width: "100%",
  },
  backArrow: {
    color: GOLD,
    fontSize: 26,
    marginRight: 10,
  },
  headerTitle: {
    color: GOLD,
    fontSize: 22,
    fontWeight: "bold",
  },
  profileContainer: {
    alignItems: "center",
    marginBottom: 30,
  },
  profileIcon: {
    backgroundColor: GOLD,
    borderRadius: 50,
    width: 100,
    height: 100,
    justifyContent: "center",
    alignItems: "center",
  },
  profileText: {
    fontSize: 40,
    color: BG,
    fontWeight: "800",
  },
  profileName: {
    marginTop: 12,
    color: GOLD,
    fontSize: 20,
    fontWeight: "700",
  },
  row: {
    backgroundColor: ROW_BG,
    paddingVertical: 15,
    paddingHorizontal: 20,
    borderRadius: 10,
    marginVertical: 8,
    width: "100%",
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  rowLabel: {
    color: GOLD,
    fontSize: 16,
    fontWeight: "bold",
  },
  rowValue: {
    color: "#E0E1DD",
    fontSize: 16,
    fontWeight: "600",
  },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 20,
  },
  loadingText: {
    marginTop: 12,
    color: GOLD,
    fontSize: 16,
    fontWeight: "600",
  },
  infoText: {
    color: "#E0E1DD",
    fontSize: 16,
    textAlign: "center",
    marginBottom: 20,
  },
  loginButton: {
    backgroundColor: GOLD,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  loginButtonText: {
    color: BG,
    fontWeight: "700",
    fontSize: 16,
  },
});
