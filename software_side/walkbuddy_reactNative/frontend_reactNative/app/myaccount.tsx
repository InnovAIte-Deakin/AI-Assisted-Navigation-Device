import { useRouter } from "expo-router";
import React from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
 
export default function MyAccountScreen() {
  const router = useRouter();
 
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
            <Text style={styles.profileText}>👤</Text>
          </View>
        </View>
 
        {/* Buttons */}
        {["NAME", "AGE", "ADDRESS", "EMAIL", "VOICE SETTINGS", "HELP"].map(
          (item, index) => (
            <TouchableOpacity key={index} style={styles.button}>
              <Text style={styles.buttonText}>{item}</Text>
            </TouchableOpacity>
          )
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
 
const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#1B263B", // keeps the same background
  },
  container: {
    flexGrow: 1,
    paddingHorizontal: 20,
    paddingTop: 20, // small extra spacing inside safe area
    alignItems: "center",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 30,
    width: "100%",
  },
  backArrow: {
    color: "#FFA500",
    fontSize: 26,
    marginRight: 10,
  },
  headerTitle: {
    color: "#FFA500",
    fontSize: 22,
    fontWeight: "bold",
  },
  profileContainer: {
    alignItems: "center",
    marginBottom: 30,
  },
  profileIcon: {
    backgroundColor: "#FFA500",
    borderRadius: 50,
    width: 100,
    height: 100,
    justifyContent: "center",
    alignItems: "center",
  },
  profileText: {
    fontSize: 40,
    color: "#1B263B",
  },
  button: {
    backgroundColor: "#333",
    paddingVertical: 15,
    paddingHorizontal: 30,
    borderRadius: 10,
    marginVertical: 8,
    width: "100%",
    alignItems: "center",
  },
  buttonText: {
    color: "#FFA500",
    fontSize: 16,
    fontWeight: "bold",
  },
});