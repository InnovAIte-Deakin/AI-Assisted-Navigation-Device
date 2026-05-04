<<<<<<< Updated upstream
// app/(tabs)/home.tsx
import { useEffect, useMemo, useRef, useState } from "react";
=======
// app/(tabs)/index.tsx

import { useEffect, useMemo, useState } from "react";
>>>>>>> Stashed changes
import { useRouter } from "expo-router";
import {
  StyleSheet,
  Text,
  View,
  Pressable,
  Switch,
  useWindowDimensions,
<<<<<<< Updated upstream
  Animated,
=======
  ScrollView,
>>>>>>> Stashed changes
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Icon from "react-native-vector-icons/FontAwesome";

import HomeHeader from "../HomeHeader";
import ModelWebView from "../../src/components/ModelWebView";
import { API_BASE } from "../../src/config";
import { useSession } from "../../src/context/SessionContext";

export default function HomePage() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const { auth } = useSession();

  const displayName = useMemo(() => {
    if (auth.status === "loggedInWithProfile" && auth.profile.displayName) {
      return auth.profile.displayName;
    }
    return "there";
  }, [auth]);

  const [visionEnabled, setVisionEnabled] = useState(true);
  const [visionPreviewOn, setVisionPreviewOn] = useState(false);
  const [loading, setLoading] = useState(false);
  const [rev, setRev] = useState(0);

  const contentWidth = useMemo(() => {
    const padding = 24;
    const max = 720;
    return Math.min(max, Math.max(320, width - padding * 2));
  }, [width]);

  const goToNavigate = () => router.push("/search" as any);
  const goToSavedPlaces = () => router.push("/places");
<<<<<<< Updated upstream
  const goToCameraVoice = () => router.push("/camera" as any);
  const goToCameraOCR = () => router.push("/camera" as any);
=======
  const goToFavourites = () => router.push("/favourites" as any);
  const goToProfile = () => router.push("/profile");

  const goToCameraVoice = () =>
    router.push({ pathname: "/camera", params: { mode: "voice" } } as any);

  const goToCameraOCR = () =>
    router.push({ pathname: "/camera", params: { mode: "ocr" } } as any);

  const goToScreenReader = () => {
    const title = "Coming soon";
    const msg = "Screen Reader is not implemented yet.";
    Platform.OS === "web"
      ? (globalThis as any).alert?.(`${title}\n\n${msg}`)
      : Alert.alert(title, msg);
  };
>>>>>>> Stashed changes

  useEffect(() => {
    if (!visionEnabled) {
      setVisionPreviewOn(false);
      setLoading(false);
    }
  }, [visionEnabled]);

  useEffect(() => {
    if (!visionPreviewOn) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setRev((x) => x + 1);

    const t = setTimeout(() => setLoading(false), 800);
    return () => clearTimeout(t);
  }, [visionPreviewOn]);

  const visionUrl = `${API_BASE}/vision/?v=${rev}`;

  const toggleVisionPreview = () => {
    if (!visionEnabled) return;
    setVisionPreviewOn((prev) => !prev);
  };

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView
        contentContainerStyle={[styles.content, { width: contentWidth }]}
        showsVerticalScrollIndicator={false}
      >
        <HomeHeader
<<<<<<< Updated upstream
          greeting={`Hi ${displayName}`}
=======
          greeting="Hi Pranav"
>>>>>>> Stashed changes
          appTitle="WalkBuddy"
          showDivider
          showLocation
        />

<<<<<<< Updated upstream
        <View style={styles.mainArea}>

            <View style={styles.statusCard}>
              <Text style={styles.statusTitle}>NAVIGATION STATUS</Text>

              <Text style={styles.statusText}>Status: Ready</Text>
              <Text style={styles.statusSub}>Next: Awaiting input</Text>

              <Pressable style={styles.startButton}>
                <Text style={styles.startButtonText}>Start Navigation</Text>
              </Pressable>
            </View>

            <BounceButton label="SEARCH" onPress={goToNavigate} search />

          <View style={styles.grid}>
            <ActionTile
=======
        {/* LOCATION */}
        <View style={styles.locationCard}>
          <Icon name="map-marker" size={16} color={tokens.muted} />
          <Text style={styles.locationText}>Finding location...</Text>
        </View>

        {/* PRIMARY ACTION */}
        <Pressable
          onPress={goToNavigate}
          android_ripple={{ color: "#f2a90022" }}
          style={({ pressed }) => [
            styles.primaryButton,
            pressed && styles.pressed,
          ]}
        >
          <Icon name="map-marker" size={18} color={tokens.bg} />
          <Text style={styles.primaryText}>START NAVIGATION</Text>
        </Pressable>

        {/* SAVED & FAVOURITES */}
        <View style={styles.grid}>
          <ActionTile
            icon="bookmark"
            label="SAVED PLACES"
            onPress={goToSavedPlaces}
          />
          <ActionTile
            icon="heart"
            label="FAVOURITES"
            onPress={goToFavourites}
          />
        </View>

        {/* ASSISTIVE */}
        <View style={styles.sectionCard}>
          <Text style={styles.sectionLabel}>ASSISTIVE TOOLS</Text>

          <View style={styles.grid}>
            <ActionTile
              icon="volume-up"
              label="SCREEN READER"
              onPress={goToScreenReader}
            />
            <ActionTile
              icon="file-text"
              label="TEXT READER"
              onPress={goToCameraOCR}
            />
            <ActionTile
>>>>>>> Stashed changes
              icon="microphone"
              label="VOICE ASSIST"
              onPress={goToCameraVoice}
            />
<<<<<<< Updated upstream
            <ActionTile
              icon="map-marker"
              label="PLACES"
              onPress={goToSavedPlaces}
            />

            <View style={styles.centerRow}>
              <ActionTile
                icon="file-text"
                label="TEXT READER"
                onPress={goToCameraOCR}
                centered
              />
            </View>
=======
>>>>>>> Stashed changes
          </View>
        </View>

        {/* VISION */}
        <View
          style={[
            styles.visionWrapper,
            visionPreviewOn && styles.visionActive,
          ]}
        >
          <View style={styles.visionRow}>
            <Text style={styles.visionTitle}>VISION ASSIST</Text>

            <View style={styles.visionStatus}>
              <View
                style={[
                  styles.statusDot,
                  visionPreviewOn ? styles.liveDot : styles.offDot,
                ]}
              />
              <Text style={styles.statusText}>
                {visionPreviewOn ? "LIVE" : "OFF"}
              </Text>
            </View>

            <Switch
              value={visionEnabled}
              onValueChange={setVisionEnabled}
              trackColor={{ false: "#23384d", true: "#2d4b66" }}
              thumbColor={visionEnabled ? tokens.gold : "#9aa8b6"}
            />
          </View>

          <Pressable
            onPress={toggleVisionPreview}
            style={({ pressed }) => [
              styles.visionCard,
              pressed && styles.pressed,
            ]}
          >
            <View style={styles.visionInner}>
              {visionEnabled && visionPreviewOn ? (
                <ModelWebView url={visionUrl} loading={loading} />
              ) : (
                <View style={styles.previewPlaceholder}>
                  <Icon
<<<<<<< Updated upstream
                    name={visionEnabled ? "eye" : "ban"}
                    size={30}
                    color={tokens.gold}
=======
                    name="eye"
                    size={28}
                    color={tokens.muted}
>>>>>>> Stashed changes
                  />
                  <Text style={styles.previewText}>
                    {visionEnabled
                      ? "Tap to start camera"
                      : "Vision disabled"}
                  </Text>
                  <Text style={styles.previewSubtext}>
                    Starting camera gives live surroundings
                  </Text>
                </View>
              )}
            </View>
          </Pressable>
        </View>
<<<<<<< Updated upstream
      </View>
=======
      </ScrollView>
>>>>>>> Stashed changes
    </SafeAreaView>
  );
}

<<<<<<< Updated upstream
function BounceButton({
  label,
  onPress,
  search = false,
}: {
  label: string;
  onPress: () => void;
  search?: boolean;
}) {
  const scale = useRef(new Animated.Value(1)).current;
  const overlayOpacity = useRef(new Animated.Value(0)).current;

  const handlePressIn = () => {
    Animated.parallel([
      Animated.spring(scale, {
        toValue: 0.965,
        useNativeDriver: true,
        speed: 28,
        bounciness: 6,
      }),
      Animated.timing(overlayOpacity, {
        toValue: 1,
        duration: 80,
        useNativeDriver: true,
      }),
    ]).start();
  };

  const handlePressOut = () => {
    Animated.parallel([
      Animated.spring(scale, {
        toValue: 1,
        useNativeDriver: true,
        speed: 22,
        bounciness: 10,
      }),
      Animated.timing(overlayOpacity, {
        toValue: 0,
        duration: 120,
        useNativeDriver: true,
      }),
    ]).start();
  };

  return (
    <Pressable
      onPress={onPress}
      onPressIn={handlePressIn}
      onPressOut={handlePressOut}
    >
      <Animated.View
        style={[
          search ? styles.searchButton : styles.tileInner,
          { transform: [{ scale }] },
        ]}
      >
        <Animated.View
          pointerEvents="none"
          style={[
            search ? styles.searchPressOverlay : styles.tilePressOverlay,
            { opacity: overlayOpacity },
          ]}
        />
        <Text style={search ? styles.searchText : styles.tileText}>{label}</Text>
      </Animated.View>
    </Pressable>
  );
}

function ActionTile({
  icon,
  label,
  onPress,
  centered = false,
}: {
  icon: string;
  label: string;
  onPress: () => void;
  centered?: boolean;
}) {
  const scale = useRef(new Animated.Value(1)).current;
  const overlayOpacity = useRef(new Animated.Value(0)).current;

  const handlePressIn = () => {
    Animated.parallel([
      Animated.spring(scale, {
        toValue: 0.96,
        useNativeDriver: true,
        speed: 28,
        bounciness: 6,
      }),
      Animated.timing(overlayOpacity, {
        toValue: 1,
        duration: 80,
        useNativeDriver: true,
      }),
    ]).start();
  };

  const handlePressOut = () => {
    Animated.parallel([
      Animated.spring(scale, {
        toValue: 1,
        useNativeDriver: true,
        speed: 22,
        bounciness: 10,
      }),
      Animated.timing(overlayOpacity, {
        toValue: 0,
        duration: 120,
        useNativeDriver: true,
      }),
    ]).start();
  };

  return (
    <View style={[styles.tile, centered && styles.tileCentered]}>
      <View style={styles.tileOuter}>
        <Pressable
          onPress={onPress}
          onPressIn={handlePressIn}
          onPressOut={handlePressOut}
        >
          <Animated.View
            style={[
              styles.tileInner,
              { transform: [{ scale }] },
            ]}
          >
            <Animated.View
              pointerEvents="none"
              style={[styles.tilePressOverlay, { opacity: overlayOpacity }]}
            />
            <Icon
              name={icon}
              size={24}
              color={tokens.gold}
              style={styles.tileIcon}
            />
            <Text style={styles.tileText}>{label}</Text>
          </Animated.View>
        </Pressable>
      </View>
=======
/* COMPONENT */

function ActionTile({ icon, label, onPress }: any) {
  return (
    <View style={styles.tile}>
      <Pressable
        onPress={onPress}
        android_ripple={{ color: "#f2a90022" }}
        style={({ pressed }) => [
          styles.tileInner,
          pressed && styles.pressed,
        ]}
      >
        <Icon name={icon} size={22} color={tokens.text} />
        <Text style={styles.tileText}>{label}</Text>
      </Pressable>
>>>>>>> Stashed changes
    </View>
  );
}

/* TOKENS */

const tokens = {
  bg: "#071a2a",
  tile: "#0b0f14",
<<<<<<< Updated upstream
  tileInner: "#08131f",
=======
  card: "#0d141c",
>>>>>>> Stashed changes
  text: "#e8eef6",
  muted: "#b8c6d4",
  gold: "#f2a900",
  green: "#2ecc71",
};

/* STYLES */

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: tokens.bg,
    alignItems: "center",
  },

  content: {
    paddingHorizontal: 12,
    gap: 18,
    paddingBottom: 40,
  },

<<<<<<< Updated upstream
  mainArea: {
    flex: 1,
    width: "100%",
    paddingTop: 10,
  },

  searchButton: {
    width: "100%",
    backgroundColor: "#12314a",
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 20,
    paddingVertical: 20,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 20,
    overflow: "hidden",

    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.18,
    shadowRadius: 6,
    elevation: 4,
  },

  searchPressOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(255,255,255,0.10)",
  },

  searchText: {
    color: tokens.text,
    fontSize: 18,
    fontWeight: "900",
    letterSpacing: 0.8,
=======
  pressed: {
    opacity: 0.85,
    transform: [{ scale: 0.98 }],
  },

  locationCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: tokens.tile,
    borderRadius: 12,
    padding: 14,
  },

  locationText: {
    color: tokens.muted,
    fontWeight: "600",
  },

  primaryButton: {
    flexDirection: "row",
    gap: 10,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: tokens.gold,
    borderRadius: 14,
    paddingVertical: 16,
  },

  primaryText: {
    color: tokens.bg,
    fontSize: 15,
    fontWeight: "900",
  },

  sectionCard: {
    backgroundColor: tokens.card,
    borderRadius: 16,
    padding: 12,
  },

  sectionLabel: {
    color: tokens.muted,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1,
    marginBottom: 6,
>>>>>>> Stashed changes
  },

  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
<<<<<<< Updated upstream
    marginBottom: 22,
=======
>>>>>>> Stashed changes
  },

  tile: {
    width: "50%",
<<<<<<< Updated upstream
    padding: 10,
  },

  tileCentered: {
    width: "50%",
  },

  centerRow: {
    width: "100%",
    alignItems: "center",
  },

  tileOuter: {
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 22,

    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.18,
    shadowRadius: 6,
    elevation: 4,
  },

  tileInner: {
    width: "100%",
    backgroundColor: tokens.tileInner,
    borderRadius: 20,
    minHeight: 108,
    paddingVertical: 18,
    paddingHorizontal: 16,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },

  tilePressOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(255,255,255,0.08)",
  },

  tileIcon: {
    marginBottom: 10,
=======
    padding: 8,
  },

  tileInner: {
    backgroundColor: tokens.tile,
    borderRadius: 14,
    paddingVertical: 20,
    alignItems: "center",
    gap: 8,
>>>>>>> Stashed changes
  },

  tileText: {
    color: tokens.text,
    fontSize: 15,
    fontWeight: "800",
    textAlign: "center",
    letterSpacing: 0.3,
  },

  visionWrapper: {
    backgroundColor: tokens.card,
    borderRadius: 16,
    padding: 12,
  },

  visionActive: {
    borderWidth: 1,
    borderColor: tokens.gold,
  },

  visionRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 8,
  },

  visionTitle: {
    color: tokens.text,
<<<<<<< Updated upstream
    fontSize: 15,
    fontWeight: "900",
    letterSpacing: 0.5,
=======
    fontWeight: "900",
>>>>>>> Stashed changes
  },

  visionStatus: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },

  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },

  liveDot: {
    backgroundColor: tokens.green,
  },

  offDot: {
    backgroundColor: tokens.muted,
  },

  statusText: {
    color: tokens.muted,
    fontSize: 11,
    fontWeight: "700",
  },

  visionCard: {
<<<<<<< Updated upstream
    width: "100%",
    flex: 1,
    backgroundColor: tokens.tile,
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 18,
    padding: 14,
    marginBottom: 6,

    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 6,
    elevation: 4,
  },

  visionCardDisabled: {
    opacity: 0.5,
=======
    height: 260,
    borderRadius: 14,
    overflow: "hidden",
    backgroundColor: tokens.tile,
>>>>>>> Stashed changes
  },

  visionInner: {
    flex: 1,
<<<<<<< Updated upstream
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 16,
    overflow: "hidden",
    backgroundColor: "#0a121a",
=======
>>>>>>> Stashed changes
  },

  previewPlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingHorizontal: 20,
  },

  previewText: {
    color: tokens.text,
<<<<<<< Updated upstream
    fontSize: 15,
=======
>>>>>>> Stashed changes
    fontWeight: "900",
    textAlign: "center",
  },

  previewSubtext: {
    color: tokens.muted,
    fontSize: 12,
    textAlign: "center",
  },
<<<<<<< Updated upstream

  statusCard: {
    width: "100%",
    backgroundColor: "#0b1a26",
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 16,
    padding: 16,
    marginBottom: 20,
  },

  statusTitle: {
    color: tokens.text,
    fontSize: 14,
    fontWeight: "900",
    marginBottom: 8,
  },

  statusText: {
    color: tokens.text,
    fontSize: 13,
    fontWeight: "700",
  },

  statusSub: {
    color: tokens.muted,
    fontSize: 12,
    marginBottom: 12,
  },

  startButton: {
    backgroundColor: "#12314a",
    paddingVertical: 10,
    borderRadius: 10,
    alignItems: "center",
  },

  startButtonText: {
    color: tokens.text,
    fontWeight: "800",
  },

=======
>>>>>>> Stashed changes
});