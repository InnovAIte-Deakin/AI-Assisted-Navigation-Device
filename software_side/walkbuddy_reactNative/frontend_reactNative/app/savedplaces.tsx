import { Href, router } from "expo-router";
import React from "react";
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

// Stable list of places (ids used for routing map)
const PLACES = [
  { id: "FIN", label: "Finance" },
  { id: "SCI", label: "Science" },
  { id: "QSR", label: "Quiet Study Room" },
  { id: "WC",  label: "Toilets" },
] as const;

// Explicit per-button routes (all -> /home for now)
// Later, change any single value (e.g., FIN: "/category/finance")
const ROUTE_MAP = {
  FIN: "/FinanceScreen",
  SCI: "/science",
  QSR: "/quietstudyroom",
  WC:  "/toilets",
} as const satisfies Record<typeof PLACES[number]["id"], Href>;

export default function SavedPlaces() {
  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        {/* Uncomment if you want a back button */}
        {/* <Ionicons name="arrow-back" size={26} color="#FFA500" onPress={() => router.back()} /> */}
        <Text style={styles.headerTitle}>SAVED PLACES</Text>
      </View>

      {/* Saved Places */}
      <ScrollView contentContainerStyle={styles.placesContainer}>
        {PLACES.map((p) => (
          <TouchableOpacity
            key={p.id}
            style={styles.placeButton}
            onPress={() => router.push(ROUTE_MAP[p.id])} // each has its own explicit entry
            accessibilityRole="button"
            accessibilityLabel={`Open ${p.label}`}
          >
            <Text style={styles.placeText}>{p.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#1B263B" },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 20,
    marginTop: 10,
  },
  headerTitle: {
    color: "#FFA500",
    fontSize: 20,
    fontWeight: "bold",
    marginLeft: 10,
  },
  placesContainer: {
    paddingTop: 30,
    paddingHorizontal: 20,
    alignItems: "center",
  },
  placeButton: {
    backgroundColor: "#333",
    paddingVertical: 15,
    borderRadius: 10,
    marginVertical: 8,
    width: "90%",
    alignItems: "center",
  },
  placeText: {
    color: "#ffffffff",
    fontSize: 16,
    fontWeight: "bold",
  },
  bottomNav: {
    flexDirection: "row",
    justifyContent: "space-around",
    borderTopWidth: 2,
    borderTopColor: "#FFA500",
    paddingVertical: 10,
    backgroundColor: "#000",
  },
  navItem: { alignItems: "center", justifyContent: "center" },
  accountIcon: {
    backgroundColor: "#FFA500",
    borderRadius: 50,
    padding: 12,
    alignItems: "center",
  },
  accountText: {
    color: "#000",
    fontSize: 10,
    fontWeight: "bold",
    marginTop: 2,
    textAlign: "center",
  },
});
