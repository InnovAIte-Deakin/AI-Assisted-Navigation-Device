import { Entypo, Ionicons, MaterialIcons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import React from "react";
import {
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

const GOLD = "#FFA500";
const BG = "#1B263B";
const CARD = "#1a1a1a";

type BtnProps = { label: string; icon: React.ReactNode; onPress: () => void };

function RowButton({ label, icon, onPress }: BtnProps) {
  return (
    <TouchableOpacity style={styles.button} onPress={onPress} activeOpacity={0.85}>
      {icon}
      <Text style={styles.buttonText}>{label}</Text>
    </TouchableOpacity>
  );
}

export default function FavouritesScreen() {
  const router = useRouter();
  const goTo = (dest: string) => console.log("Favourites ->", dest);

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor={BG} />

      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={24} color={GOLD} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>FAVOURITES</Text>
        <View style={{ width: 24 }} />
      </View>

      {/* Section (subtitle) */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Access your favourite locations.</Text>
        <Text style={styles.sectionSub}>Quick actions</Text>
      </View>

      {/* Buttons */}
      <ScrollView contentContainerStyle={styles.buttonContainer}>
        <RowButton
          label="ARTS"
          onPress={() => goTo("Arts")}
          icon={<Ionicons name="color-palette-outline" size={20} color={GOLD} />}
        />
        <RowButton
          label="HELPDESK"
          onPress={() => goTo("Helpdesk")}
          icon={<Entypo name="help" size={20} color={GOLD} />}
        />
        <RowButton
          label="Finance"
          onPress={() => goTo("Finance")}
          icon={<MaterialIcons name="account-balance-wallet" size={20} color={GOLD} />}
        />
      </ScrollView>

      {/* Bottom Nav with separated slots */}
      <View style={styles.bottomNav}>
        <TouchableOpacity style={[styles.navItem, styles.navLeft]} onPress={() => goTo("Home")}>
          <Ionicons name="home" size={24} color={GOLD} />
        </TouchableOpacity>

        <TouchableOpacity style={[styles.navItem, styles.navMiddle]} onPress={() => goTo("Camera")}>
          <MaterialIcons name="photo-camera" size={24} color={GOLD} />
        </TouchableOpacity>

        <TouchableOpacity style={[styles.navItem, styles.navRight]} onPress={() => goTo("Account")}>
          <View style={styles.accountBtn}>
            <Ionicons name="person" size={20} color="black" />
            <Text style={styles.accountText}>My{"\n"}Account</Text>
          </View>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: BG,
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
    color: GOLD,
    fontSize: 22,
    fontWeight: "bold",
  },
  section: {
    borderBottomWidth: 1,
    borderTopWidth: 1,
    borderColor: GOLD,
    padding: 15,
  },
  sectionTitle: {
    color: GOLD,
    fontSize: 20,
    fontWeight: "bold",
  },
  sectionSub: {
    color: GOLD,
    fontSize: 16,
    marginTop: 5,
  },
  buttonContainer: {
    paddingHorizontal: 30,
    marginTop: 20,
    paddingBottom: 90,
  },
  button: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: CARD,
    borderWidth: 1,
    borderColor: GOLD,
    borderRadius: 8,
    padding: 12,
    marginBottom: 15,
  },
  buttonText: {
    color: GOLD,
    fontSize: 16,
    marginLeft: 15,
  },
  bottomNav: {
    flexDirection: "row",
    borderTopWidth: 1,
    borderColor: GOLD,
    backgroundColor: BG,
  },
  navItem: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 10,
  },
  navLeft: {
    borderRightWidth: 1,
    borderColor: GOLD,
  },
  navMiddle: {
    borderRightWidth: 1,
    borderColor: GOLD,
  },
  navRight: {
    // rightmost, no border needed
  },
  accountBtn: {
    backgroundColor: GOLD,
    borderRadius: 50,
    padding: 10,
    alignItems: "center",
    borderWidth: 1,
    borderColor: GOLD,
  },
  accountText: {
    fontSize: 10,
    fontWeight: "bold",
    textAlign: "center",
    color: "black",
    marginTop: 2,
    lineHeight: 12,
  },
});
