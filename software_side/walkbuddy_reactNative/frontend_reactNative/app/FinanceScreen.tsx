


import { Entypo, FontAwesome, Ionicons, MaterialIcons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React from "react";
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Radius, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";

export default function FinanceScreen() {
  const router = useRouter();
  const colors = useThemeColors();

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={24} color={colors.accent} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, { color: colors.text }]}>FINANCE</Text>
        <View style={{ width: 24 }} />
      </View>

      {/* Section Title */}
      <View style={[styles.section, { borderColor: colors.accent }]}>
        <Text style={[styles.sectionTitle, { color: colors.text }]}>Finance section</Text>
        <Text style={[styles.sectionSub, { color: colors.text }]}>25 ft, 7 o’clock</Text>
      </View>

      {/* Buttons */}
      <ScrollView contentContainerStyle={styles.buttonContainer}>
        <TouchableOpacity
          style={[styles.button, { backgroundColor: colors.surface, borderColor: colors.accent }]}
          onPress={() => router.push("/navigate")}   // ✅ route to /home
        >
          <Ionicons name="navigate" size={20} color={colors.accent} />
          <Text style={[styles.buttonText, { color: colors.text }]}>Go there</Text>
        </TouchableOpacity>

        <TouchableOpacity style={[styles.button, { backgroundColor: colors.surface, borderColor: colors.accent }]}>
          <Ionicons name="add-circle-outline" size={20} color={colors.accent} />
          <Text style={[styles.buttonText, { color: colors.text }]}>Save Location</Text>
        </TouchableOpacity>

        <TouchableOpacity style={[styles.button, { backgroundColor: colors.surface, borderColor: colors.accent }]}>
          <Entypo name="share" size={20} color={colors.accent} />
          <Text style={[styles.buttonText, { color: colors.text }]}>Share Location</Text>
        </TouchableOpacity>

        <TouchableOpacity style={[styles.button, { backgroundColor: colors.surface, borderColor: colors.accent }]}>
          <MaterialIcons name="photo-camera" size={20} color={colors.accent} />
          <Text style={[styles.buttonText, { color: colors.text }]}>Switch to Camera</Text>
        </TouchableOpacity>

        <TouchableOpacity style={[styles.button, { backgroundColor: colors.surface, borderColor: colors.accent }]}>
          <FontAwesome name="star" size={20} color={colors.accent} />
          <Text style={[styles.buttonText, { color: colors.text }]}>Add to Fav</Text>
        </TouchableOpacity>
      </ScrollView>

      {/* Bottom Nav */}
      <View style={[styles.bottomNav, { borderColor: colors.accent, backgroundColor: colors.surface }]}>
        {/* Home */}
        <TouchableOpacity style={[styles.navItem, { borderColor: colors.accent }]}>
          <Ionicons name="home" size={28} color={colors.accent} />
        </TouchableOpacity>

        {/* Camera */}
        <TouchableOpacity style={[styles.navItem, { borderColor: colors.accent }]}>
          <MaterialIcons name="photo-camera" size={32} color={colors.accent} />
        </TouchableOpacity>

        {/* My Account */}
        <TouchableOpacity style={styles.navItem}>
          <View style={[styles.accountCircle, { backgroundColor: colors.accent }]}>
            <Ionicons name="person" size={24} color={colors.accentText} />
            <Text style={[styles.accountText, { color: colors.accentText }]}>My{"\n"}Account</Text>
          </View>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
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
    fontSize: 22,
    fontWeight: "bold",
  },
  section: {
    borderBottomWidth: 1,
    borderTopWidth: 1,
    padding: 15,
  },
  sectionTitle: {
    fontSize: Typography.size.lg,
    fontWeight: "bold",
  },
  sectionSub: {
    fontSize: Typography.size.base,
    marginTop: 5,
  },
  buttonContainer: {
    paddingHorizontal: 30,
    marginTop: 20,
  },
  button: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1,
    borderRadius: Radius.sm,
    padding: 12,
    marginBottom: 15,
  },
  buttonText: {
    fontSize: Typography.size.base,
    marginLeft: 15,
  },
  bottomNav: {
    flexDirection: "row",
    borderTopWidth: 2,
  },
  navItem: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    borderRightWidth: 1,
    paddingVertical: 10,
  },
  accountCircle: {
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
    marginTop: 2,
  },
});
