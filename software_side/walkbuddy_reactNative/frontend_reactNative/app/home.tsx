// app/home.tsx
import { useRouter } from "expo-router";
import React from "react";
import {
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import Icon from "react-native-vector-icons/FontAwesome";
import { useAuth } from "../src/context/AuthContext";

const GOLD = "#FCA311";

export const options = {
  headerShown: false,
};

export default function HomePage() {
  const router = useRouter();
  const { profile, logout } = useAuth();

  const handleLoginPress = () => {
    router.push("/login");
  };

  const handleLogoutPress = async () => {
    try {
      await logout();
      // After logout, stay on Home; header will update automatically
      // because profile becomes null.
    } catch (err) {
      console.log("Home.logout error:", err);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Top row with Explore button (left), Home title (center), user / login controls (right) */}
      <View style={styles.topRow}>
        <Pressable
          style={styles.exploreBtn}
          onPress={() => router.push("/explore")}
          accessibilityLabel="Go to Explore"
        >
          <Text style={styles.exploreText}>Go to Explore page</Text>
        </Pressable>

        <Text style={styles.toptext}>Home</Text>

        <View style={styles.rightControls}>
          {profile ? (
            <>
              <Text style={styles.userName}>{profile.firstName}</Text>
              <Pressable
                style={styles.loginBtn}
                onPress={handleLogoutPress}
                accessibilityLabel="Logout"
              >
                <Text style={styles.loginText}>Logout</Text>
              </Pressable>
            </>
          ) : (
            <Pressable
              style={styles.loginBtn}
              onPress={handleLoginPress}
              accessibilityLabel="Go to Login"
            >
              <Text style={styles.loginText}>Login</Text>
            </Pressable>
          )}
        </View>
      </View>

      <View style={styles.line} />

      <View style={styles.locationBlock}>
        {/* Row with text on left and star on right */}
        <View style={styles.row}>
          <Text style={styles.subtext}>My Current</Text>
          <Icon name="star" size={22} color={GOLD} />
        </View>

        {/* Address lines */}
        <Text style={styles.addressText}>Street Address</Text>
        <Text style={styles.addressText}>City</Text>

        {/* Row for Zip + Share */}
        <View style={styles.row}>
          <Text style={styles.addressText}>Zip</Text>
          <Icon name="share-alt" size={22} color={GOLD} />
        </View>

        <View style={{ height: 10 }} />
        <View style={styles.line} />
      </View>

      <View style={styles.iconGrid}>
        <View style={styles.iconBox}>
          <Pressable
            style={styles.iconPressable}
            onPress={() => router.push("/savedplaces")}
            accessibilityLabel="Open saved"
          >
            <Icon name="bookmark" size={28} color={GOLD} />
            <Text style={styles.iconLabel}>Saved</Text>
          </Pressable>
        </View>

        <View style={styles.iconBox}>
          <Pressable
            style={styles.iconPressable}
            onPress={() => router.push("/quick-nav")}
            accessibilityLabel="Open Navigation"
          >
            <Icon name="location-arrow" size={28} color={GOLD} />
            <Text style={styles.iconLabel}>Navigation</Text>
          </Pressable>
        </View>

        <View style={styles.iconBox}>
          <Icon name="search" size={28} color={GOLD} />
          <Text style={styles.iconLabel}>Search</Text>
        </View>

        <View style={styles.iconBox}>
          <Pressable
            style={styles.iconPressable}
            onPress={() => router.push("/favourites")}
            accessibilityLabel="Open fav"
          >
            <Icon name="star" size={28} color={GOLD} />
            <Text style={styles.iconLabel}>Favourites</Text>
          </Pressable>
        </View>
      </View>

      <View style={styles.bottomBar}>
        <View style={styles.bottomItem}>
          <Pressable
          style={styles.bottomItem}
          onPress={() => router.push("/home")}
          accessibilityLabel="Go to Home"
        >
          <Icon name="home" size={28} color="#FCA311" />
        </Pressable>
        </View>
        <View style={styles.divider} />
        

        <Pressable
          style={styles.bottomItem}
          onPress={() => router.push("/camera")}
          accessibilityLabel="Open Camera"
        >
          <Icon name="camera" size={28} color={GOLD} />
        </Pressable>

        <View style={styles.divider} />

        <Pressable
          style={styles.bottomItem}
          onPress={() => router.push("/myaccount")}
          accessibilityLabel="Open Account"
        >
          <Icon name="user" size={28} color={GOLD} />
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  iconPressable: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    width: "100%",
    paddingHorizontal: 16,
    marginBottom: 10,
  },
  exploreBtn: {
    borderWidth: 1,
    borderColor: GOLD,
    borderRadius: 8,
    paddingVertical: 4,
    paddingHorizontal: 10,
    marginRight: 12,
    backgroundColor: "#1B263B",
  },
  exploreText: {
    color: "#E0E1DD",
    fontSize: 16,
    fontWeight: "600",
  },
  topLeft: {
    flexDirection: "row",
    alignItems: "center",
  },
  rightControls: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  userName: {
    color: GOLD,
    fontSize: 16,
    fontWeight: "600",
    marginRight: 4,
  },
  loginBtn: {
    borderWidth: 1,
    borderColor: GOLD,
    borderRadius: 8,
    paddingVertical: 4,
    paddingHorizontal: 12,
    backgroundColor: "#0D1B2A",
  },
  loginText: {
    color: GOLD,
    fontSize: 16,
    fontWeight: "600",
  },
  container: {
    flex: 1,
    backgroundColor: "#0D1B2A",
    justifyContent: "flex-start",
    alignItems: "center",
    paddingTop: 10,
  },
  toptext: {
    fontSize: 24,
    color: "#E0E1DD",
    fontWeight: "700",
    marginBottom: 10,
  },
  line: {
    height: 2,
    backgroundColor: GOLD,
    width: "100%",
  },
  locationBlock: {
    width: "100%",
    paddingHorizontal: 20,
    marginTop: 20,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  subtext: {
    fontSize: 20,
    color: "#FFFFFF",
    fontWeight: "600",
  },
  addressText: {
    fontSize: 18,
    color: "#E0E1DD",
    marginTop: 5,
    marginLeft: 5,
  },
  iconGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    marginTop: 20,
    width: "32%",
    paddingHorizontal: 20,
  },
  iconBox: {
    width: "45%",
    aspectRatio: 1,
    borderWidth: 2,
    borderColor: GOLD,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 15,
    backgroundColor: "#111",
  },
  iconLabel: {
    color: "#E0E1DD",
    marginTop: 8,
    fontSize: 14,
    fontWeight: "500",
  },
  bottomBar: {
    flexDirection: "row",
    justifyContent: "space-around",
    alignItems: "center",
    borderTopWidth: 2,
    borderColor: GOLD,
    width: "100%",
    paddingVertical: 10,
    marginTop: "auto",
    backgroundColor: "#0D1B2A",
  },
  bottomItem: {
    flex: 1,
    alignItems: "center",
  },
  divider: {
    width: 2,
    height: "60%",
    backgroundColor: GOLD,
  },
});