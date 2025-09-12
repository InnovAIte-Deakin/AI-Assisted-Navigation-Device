import React from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import { NativeStackScreenProps } from "@react-navigation/native-stack";

type RootStackParamList = {
  SavedPlaces: undefined;
};

type SavedPlacesProps = NativeStackScreenProps<
  RootStackParamList,
  "SavedPlaces"
>;

export default function SavedPlaces({ navigation }: SavedPlacesProps) {
  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Ionicons
          name="arrow-back"
          size={26}
          color="#FFA500"
          onPress={() => navigation.goBack()}
        />
        <Text style={styles.headerTitle}>SAVED PLACES</Text>
      </View>

      {/* Saved Places */}
      <ScrollView contentContainerStyle={styles.placesContainer}>
        {["Finance", "Science", "Quiet Study Room", "Toilets"].map(
          (place, index) => (
            <TouchableOpacity key={index} style={styles.placeButton}>
              <Text style={styles.placeText}>{place}</Text>
            </TouchableOpacity>
          )
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#000",
  },
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
    color: "#FFA500",
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
  navItem: {
    alignItems: "center",
    justifyContent: "center",
  },
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
