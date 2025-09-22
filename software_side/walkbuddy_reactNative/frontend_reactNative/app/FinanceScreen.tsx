


import { Entypo, FontAwesome, Ionicons, MaterialIcons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React from "react";
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";

export default function FinanceScreen() {
  const router = useRouter();

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={24} color="#FFA500" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>FINANCE</Text>
        <View style={{ width: 24 }} />
      </View>

      {/* Section Title */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Finance section</Text>
        <Text style={styles.sectionSub}>25 ft, 7 o’clock</Text>
      </View>

      {/* Buttons */}
      <ScrollView contentContainerStyle={styles.buttonContainer}>
        <TouchableOpacity
          style={styles.button}
          onPress={() => router.push("/navigate")}   // ✅ route to /home
        >
          <Ionicons name="navigate" size={20} color="#FFA500" />
          <Text style={styles.buttonText}>Go there</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.button}>
          <Ionicons name="add-circle-outline" size={20} color="#FFA500" />
          <Text style={styles.buttonText}>Save Location</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.button}>
          <Entypo name="share" size={20} color="#FFA500" />
          <Text style={styles.buttonText}>Share Location</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.button}>
          <MaterialIcons name="photo-camera" size={20} color="#FFA500" />
          <Text style={styles.buttonText}>Switch to Camera</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.button}>
          <FontAwesome name="star" size={20} color="#FFA500" />
          <Text style={styles.buttonText}>Add to Fav</Text>
        </TouchableOpacity>
      </ScrollView>

      {/* Bottom Nav */}
      <View style={styles.bottomNav}>
        {/* Home */}
        <TouchableOpacity style={styles.navItem}>
          <Ionicons name="home" size={28} color="#FFA500" />
        </TouchableOpacity>

        {/* Camera */}
        <TouchableOpacity style={styles.navItem}>
          <MaterialIcons name="photo-camera" size={32} color="#FFA500" />
        </TouchableOpacity>

        {/* My Account */}
        <TouchableOpacity style={styles.navItem}>
          <View style={styles.accountCircle}>
            <Ionicons name="person" size={24} color="black" />
            <Text style={styles.accountText}>My{"\n"}Account</Text>
          </View>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#1B263B",
    paddingTop: 50,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    marginBottom: 10,
  },
  headerTitle: {
    color: "#ffffffff",
    fontSize: 22,
    fontWeight: "bold",
  },
  section: {
    borderBottomWidth: 1,
    borderTopWidth: 1,
    borderColor: "#FFA500",
    padding: 15,
  },
  sectionTitle: {
    color: "#ffffffff",
    fontSize: 20,
    fontWeight: "bold",
  },
  sectionSub: {
    color: "#ffffffff",
    fontSize: 16,
    marginTop: 5,
  },
  buttonContainer: {
    paddingHorizontal: 30,
    marginTop: 20,
  },
  button: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#1a1a1a",
    borderWidth: 1,
    borderColor: "#FFA500",
    borderRadius: 8,
    padding: 12,
    marginBottom: 15,
  },
  buttonText: {
    color: "#ffffffff",
    fontSize: 16,
    marginLeft: 15,
  },
  bottomNav: {
    flexDirection: "row",
    borderTopWidth: 2,
    borderColor: "#FFA500",
    backgroundColor: "black",
  },
  navItem: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    borderRightWidth: 1,
    borderColor: "#FFA500",
    paddingVertical: 10,
  },
  accountCircle: {
    backgroundColor: "#FFA500",
    borderRadius: 50,
    width: 70,
    height: 70,
    alignItems: "center",
    justifyContent: "center",
    padding: 5,
  },
  accountText: {
    fontSize: 10,
    fontWeight: "bold",
    textAlign: "center",
    color: "black",
    marginTop: 2,
  },
});
