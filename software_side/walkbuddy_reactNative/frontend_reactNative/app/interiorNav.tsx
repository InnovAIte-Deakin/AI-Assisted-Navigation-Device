//  Note: this page currently contains only the basic UI layout.
//  Navigation and camera functionality will be added later. 

import React, { useState } from "react";
import {SafeAreaView,StyleSheet,Text,View,Pressable,ScrollView,Switch,} from "react-native";
import { useLocalSearchParams } from "expo-router";
import HomeHeader from "./HomeHeader";
import { Radius, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";

export default function InteriorMapPage() {
  const colors = useThemeColors();
  const [cameraViewEnabled, setCameraViewEnabled] = useState(false);
  const { targetedDestination } = useLocalSearchParams<{ targetedDestination?: string }>();

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: colors.background }]}>
      <ScrollView
        style={[styles.scroll, { backgroundColor: colors.background }]}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.centerColumn}>
          <HomeHeader/>

          <View style={styles.main}>
            <View style={styles.directionArrowContainer}>
              <Text style={[styles.directionArrow, { color: colors.accent }]}>↑</Text>
            </View>

            <Text style={[styles.navigationInstructions, { color: colors.text }]}>
              HAPTICS & VOICE{"\n"}INSTRUCTIONS
            </Text>

            {/* CAMERA CARD */}
            <View style={[styles.cameraCard, { backgroundColor: colors.surface, borderColor: colors.accent }]}>
              <View style={styles.cameraHeader}>
                <Text style={[styles.cameraTitle, { color: colors.textMuted }]}>CAMERA VIEW</Text>

                <View style={styles.cameraToggleContainer}>
                  <Text style={[styles.toggleText, { color: colors.textMuted }]}>
                    {cameraViewEnabled ? "On" : "Off"}
                  </Text>
                  <Switch
                    value={cameraViewEnabled}
                    onValueChange={setCameraViewEnabled}
                    thumbColor={cameraViewEnabled ? colors.accent : colors.textMuted}
                    trackColor={{ false: colors.border, true: colors.surfaceElevated }}
                  />
                </View>
              </View>

              {/* Camera View Area */}
              {cameraViewEnabled ? (
                <View style={[styles.cameraViewBox, { borderColor: colors.accent + "66", backgroundColor: colors.surfaceElevated }]}/>
              ) : (
                <Pressable
                  style={[styles.enableCameraViewButton, { borderColor: colors.accent + "66", backgroundColor: colors.surfaceElevated }]}
                  onPress={() => setCameraViewEnabled(true)}
                >
                  <Text style={[styles.enableCameraViewButtonTitle, { color: colors.text }]}>
                    TURN CAMERA VIEW{"\n"}ON
                  </Text>
                </Pressable>
              )}
            </View>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

/* STYLES — structural only; colors applied inline so they react to
   light/dark via useThemeColors(). */

const styles = StyleSheet.create({
  safe:{
    flex: 1,
  },

  scroll:
  { flex: 1,
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
    fontWeight: "900",
    lineHeight: 125,
  },

  navigationInstructions:{
    marginTop: 10,
    textAlign: "center",
    fontSize: Typography.size.sm,
    fontWeight: "800",
    letterSpacing: 0.6,
  },

  cameraCard:{
    marginTop: 22,
    width: "100%",
    borderWidth: 2,
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
    fontSize: Typography.size.xs,
    fontWeight: "800",
    letterSpacing: 1,
  },

  cameraToggleContainer:{
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },

  toggleText:{
    fontSize: Typography.size.xs,
    fontWeight: "800",
  },

  cameraViewBox:{
    height: 260,
    borderRadius: 14,
    borderWidth: 2,
  },

  enableCameraViewButton:{
    height: 260,
    borderRadius: 14,
    borderWidth: 2,
    alignItems: "center",
    justifyContent: "center",
  },

  enableCameraViewButtonTitle:{
    fontSize: Typography.size.sm,
    fontWeight: "800",
    textAlign: "center",
    letterSpacing: 0.8,
  },
});
