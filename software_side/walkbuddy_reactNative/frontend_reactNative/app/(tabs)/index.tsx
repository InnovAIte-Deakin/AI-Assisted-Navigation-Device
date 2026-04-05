// app/(tabs)/home.tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "expo-router";
import {
  StyleSheet,
  Text,
  View,
  Pressable,
  Switch,
  useWindowDimensions,
  Animated,
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

  const goToAccount = () => router.push("/profile");
  const goToNavigate = () => router.push("/search" as any);
  const goToSavedPlaces = () => router.push("/places");
  const goToCameraVoice = () => router.push("/camera" as any);
  const goToCameraOCR = () => router.push("/camera" as any);

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

  const visionUrl = useMemo(() => {
    return `${API_BASE}/vision/?v=${rev}`;
  }, [rev]);

  const toggleVisionPreview = () => {
    if (!visionEnabled) return;
    setVisionPreviewOn((prev) => !prev);
  };

  const visionHintText = useMemo(() => {
    if (!visionEnabled) return "Vision disabled";
    return visionPreviewOn
      ? "Tap to turn preview off"
      : "Tap to turn preview on";
  }, [visionEnabled, visionPreviewOn]);

  return (
    <SafeAreaView style={styles.screen}>
      <View style={[styles.content, { width: contentWidth }]}>
        <HomeHeader
          greeting={`Hi ${displayName}`}
          appTitle="WalkBuddy"
          onPressProfile={goToAccount}
          showDivider
          showLocation
        />

        <View style={styles.mainArea}>
          <BounceButton label="SEARCH" onPress={goToNavigate} search />

          <View style={styles.grid}>
            <ActionTile
              icon="microphone"
              label="VOICE ASSIST"
              onPress={goToCameraVoice}
            />
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
          </View>

          <View style={styles.visionRow}>
            <Text style={styles.visionTitle}>VISION ASSIST</Text>

            <View style={styles.visionToggle}>
              <Text style={styles.visionToggleText}>
                {visionEnabled ? "On" : "Off"}
              </Text>
              <Switch
                value={visionEnabled}
                onValueChange={setVisionEnabled}
                trackColor={{ false: "#23384d", true: "#2d4b66" }}
                thumbColor={visionEnabled ? tokens.gold : "#9aa8b6"}
              />
            </View>
          </View>

          <Pressable
            style={[
              styles.visionCard,
              !visionEnabled && styles.visionCardDisabled,
            ]}
            onPress={toggleVisionPreview}
          >
            <View style={styles.visionInner}>
              {visionEnabled && visionPreviewOn ? (
                <ModelWebView url={visionUrl} loading={loading} />
              ) : (
                <View style={styles.previewPlaceholder}>
                  <Icon
                    name={visionEnabled ? "eye" : "ban"}
                    size={30}
                    color={tokens.gold}
                  />
                  <Text style={styles.previewText}>VISION PREVIEW</Text>
                  <Text style={styles.previewSubtext}>{visionHintText}</Text>
                </View>
              )}
            </View>
          </Pressable>
        </View>
      </View>
    </SafeAreaView>
  );
}

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
    </View>
  );
}

const tokens = {
  bg: "#071a2a",
  tile: "#0b0f14",
  tileInner: "#08131f",
  text: "#e8eef6",
  muted: "#b8c6d4",
  gold: "#f2a900",
};

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: tokens.bg,
    alignItems: "center",
  },

  content: {
    flex: 1,
    paddingHorizontal: 12,
    paddingTop: 8,
  },

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
  },

  grid: {
    width: "100%",
    flexDirection: "row",
    flexWrap: "wrap",
    marginBottom: 22,
  },

  tile: {
    width: "50%",
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
  },

  tileText: {
    color: tokens.text,
    fontSize: 15,
    fontWeight: "800",
    textAlign: "center",
    letterSpacing: 0.3,
  },

  visionRow: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 10,
  },

  visionTitle: {
    color: tokens.text,
    fontSize: 15,
    fontWeight: "900",
    letterSpacing: 0.5,
  },

  visionToggle: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },

  visionToggleText: {
    color: tokens.muted,
    fontSize: 12,
    fontWeight: "800",
  },

  visionCard: {
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
  },

  visionInner: {
    flex: 1,
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 16,
    overflow: "hidden",
    backgroundColor: "#0a121a",
  },

  previewPlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingHorizontal: 16,
  },

  previewText: {
    color: tokens.text,
    fontSize: 15,
    fontWeight: "900",
    textAlign: "center",
    letterSpacing: 0.6,
  },

  previewSubtext: {
    color: tokens.muted,
    fontSize: 12,
    fontWeight: "700",
    textAlign: "center",
    marginTop: 4,
  },
});