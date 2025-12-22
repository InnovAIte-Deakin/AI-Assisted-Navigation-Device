import React from "react";
import { Alert, Pressable, StyleSheet, View, Platform } from "react-native";
import Icon from "react-native-vector-icons/FontAwesome";
import { useRouter, usePathname } from "expo-router";

import { useCurrentLocation } from "./lib/locationSaver";
import { saveCurrentLocation } from "./lib/placesStore";

export default function Footer() {
  const router = useRouter();
  const pathname = usePathname();
  const { currentLocation } = useCurrentLocation();

  const navPage = (targetedRoute: string) => {
    if (pathname !== targetedRoute) {
      router.push(targetedRoute as any);
    }
  };

  const showAlertMessage = (alertTitle: string, alertMessage: string) => {
    if (Platform.OS === "web") {
      (globalThis as any).alert?.(`${alertTitle}\n\n${alertMessage}`);
    } else {
      Alert.alert(alertTitle, alertMessage);
    }
  };

  const saveCurrentTapLocation = async () => {
    if (!currentLocation || !currentLocation.trim()) {
      showAlertMessage(
        "Can't save location",
        "Location is not available yet."
      );
      return;
    }

    const result = await saveCurrentLocation(currentLocation, "E");

    if (result.status === "exists") {
      showAlertMessage(
        "Already saved",
        "This location is already saved."
      );
    } else {
      showAlertMessage(
        "Saved successfully",
        "Location saved successfully."
      );
    }
  };

  return (
    <View style={styles.footWrap}>
      <View style={styles.bottomBar}>
        <Pressable style={styles.bottomItem} onPress={() => navPage("/home")}>
          <Icon name="home" size={30} color="#FCA311" />
        </Pressable>

        <View style={styles.divider} />

        <Pressable style={styles.bottomItem} onPress={() => navPage("/camera")}>
          <Icon name="camera" size={30} color="#FCA311" />
        </Pressable>

        <View style={styles.divider} />

        <Pressable style={styles.bottomItem} onPress={() => navPage("/voice")}>
          <Icon name="microphone" size={30} color="#FCA311" />
        </Pressable>

        <View style={styles.divider} />

        <Pressable style={styles.bottomItem} onPress={() => navPage("/places")}>
          <Icon name="map-marker" size={30} color="#FCA311" />
        </Pressable>

        <View style={styles.divider} />

        <Pressable style={styles.bottomItem} onPress={saveCurrentTapLocation}>
          <Icon name="heart" size={30} color="#FCA311" />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  footWrap: {
    width: "100%",
    paddingHorizontal: 14,
    paddingBottom: 0,
    marginTop: 0,
    backgroundColor: "transparent",
  },
  bottomBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-around",
    backgroundColor: "#0D1B2A",
    borderColor: "#FCA311",
    borderWidth: 2,
    borderRadius: 999,
    paddingVertical: 22,
    paddingHorizontal: 14,
    overflow: "hidden",
  },
  bottomItem: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 7,
  },
  divider: {
    width: 2,
    height: "60%",
    backgroundColor: "#FCA311",
    opacity: 0.8,
  },
});
