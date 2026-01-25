//  Note: this page currently contains only the basic UI layout.
//  Navigation and camera functionality will be added later. 

import React, { useState } from "react";
import {SafeAreaView,StyleSheet,Text,View,Pressable,ScrollView,Switch,} from "react-native";
import { useLocalSearchParams } from "expo-router";
import HomeHeader from "./HomeHeader";
import Footer from "./Footer";

export default function InteriorMapPage() {
  const [cameraViewEnabled, setCameraViewEnabled] = useState(false);
  const { targetedDestination } = useLocalSearchParams<{ targetedDestination?: string }>();

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.centerColumn}>
          <HomeHeader/>

          <View style={styles.main}>
            <View style={styles.directionArrowContainer}>
              <Text style={styles.directionArrow}>↑</Text>
            </View>

            <Text style={styles.navigationInstructions}>
              HAPTICS & VOICE{"\n"}INSTRUCTIONS
            </Text>

            {/* CAMERA CARD */}
            <View style={styles.cameraCard}>
              <View style={styles.cameraHeader}>
                <Text style={styles.cameraTitle}>CAMERA VIEW</Text>

                <View style={styles.cameraToggleContainer}>
                  <Text style={styles.toggleText}>
                    {cameraViewEnabled ? "On" : "Off"}
                  </Text>
                  <Switch
                    value={cameraViewEnabled}
                    onValueChange={setCameraViewEnabled}
                    thumbColor={cameraViewEnabled ? GOLD : "#9aa3ad"}
                    trackColor={{ false: "#233044", true: "#7a5600" }}
                  />
                </View>
              </View>

              {/* Camera View Area */}
              {cameraViewEnabled ? (
                <View style={styles.cameraViewBox}/>
              ) : (
                <Pressable
                  style={styles.enableCameraViewButton}
                  onPress={() => setCameraViewEnabled(true)}
                >
                  <Text style={styles.enableCameraViewButtonTitle}>
                    TURN CAMERA VIEW{"\n"}ON
                  </Text>
                </Pressable>
              )}
            </View>
          </View>
          <Footer/>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const BG = "#0D1B2A";
const GOLD = "#FCA311";
const CARD = "#0B1522";
const TEXT = "#FFFFFF";
const MUTED = "#BFC7D5";

const styles = StyleSheet.create({
  safe:{
    flex: 1,
    backgroundColor: BG
  },

  scroll:
  { flex: 1,
    backgroundColor: BG
  },

  scrollContent:{ 
    paddingVertical: 10, 
    alignItems: "center" 
  },

  centerColumn:{
    width: "100%",
    maxWidth: 780,
    paddingHorizontal: 18,
  },

  main:{
    paddingTop: 10,
    paddingBottom: 18,
    alignItems: "center",
  },

  directionArrowContainer:{ 
    marginTop: 25, 
    alignItems: "center" 
  },

  directionArrow:{
    fontSize: 120,
    color: GOLD,
    fontWeight: "900",
    lineHeight: 125,
  },

  navigationInstructions:{
    marginTop: 10,
    textAlign: "center",
    color: TEXT,
    fontSize: 14,
    fontWeight: "800",
    letterSpacing: 0.6,
  },

  cameraCard:{
    marginTop: 22,
    width: "100%",
    backgroundColor: CARD,
    borderWidth: 2,
    borderColor: GOLD,
    borderRadius: 18,
    padding: 14,
  },

  cameraHeader:{
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 10,
  },

  cameraTitle:{
    color: MUTED,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 1,
  },

  cameraToggleContainer:{
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },

  toggleText:{
    color: MUTED,
    fontSize: 12,
    fontWeight: "800",
  },

  cameraViewBox:{
    height: 260,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: "rgba(252,163,17,0.4)",
    backgroundColor: "#070B12",
  },

  enableCameraViewButton:{
    height: 260,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: "rgba(252,163,17,0.4)",
    backgroundColor: "#070B12",
    alignItems: "center",
    justifyContent: "center",
  },

  enableCameraViewButtonTitle:{
    color: TEXT,
    fontSize: 14,
    fontWeight: "800",
    textAlign: "center",
    letterSpacing: 0.8,
  },
});
