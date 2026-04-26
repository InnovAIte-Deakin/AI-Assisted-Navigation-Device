// app/(tabs)/index.tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "expo-router";
import {
  Alert,
  Animated,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
  useWindowDimensions,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Icon from "react-native-vector-icons/FontAwesome";

import HomeHeader from "../HomeHeader";
import ModelWebView from "../../src/components/ModelWebView";
import { API_BASE } from "../../src/config";
import { useSession } from "../../src/context/SessionContext";

type DestinationType = "I" | "E";

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

  const greeting = `Hi ${displayName}`;

  const [visionEnabled, setVisionEnabled] = useState(true);
  const [visionPreviewOn, setVisionPreviewOn] = useState(false);
  const [loading, setLoading] = useState(false);
  const [rev, setRev] = useState(0);
  const [showSearch, setShowSearch] = useState(false);
  const [query, setQuery] = useState("");
  const [destinationType, setDestinationType] = useState<DestinationType | null>(null);

  const hasDestination = query.trim().length > 0;

  const contentWidth = useMemo(() => {
    const padding = 24;
    const max = 720;
    return Math.min(max, Math.max(320, width - padding * 2));
  }, [width]);

  const goToSavedPlaces = () => router.push("/places");
  const goToFavourites = () => router.push("/favourites" as any);
  const goToProfile = () => router.push("/profile");
  const goToEmergency = () => router.push("/emergency" as any);

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

  const openSearch = () => {
    setQuery("");
    setDestinationType(null);
    setShowSearch(true);
  };

  const closeSearch = () => {
    setShowSearch(false);
    setQuery("");
    setDestinationType(null);
  };

  const onPressInterior = () => {
    if (!hasDestination) return;
    if (destinationType === "E") {
      Alert.alert("Error!", "This is an External destination");
      return;
    }
    closeSearch();
    router.push({ pathname: "/indoor" } as any);
  };

  const onPressMaps = () => {
    if (!hasDestination) return;
    if (destinationType === "I") {
      Alert.alert("Error!", "This is an Internal destination");
      return;
    }
    const destinationText = query.trim();
    closeSearch();
    router.push({
      pathname: "exterior",
      params: { presetDestination: destinationText, presetType: "E" },
    } as any);
  };

  return (
    <SafeAreaView style={styles.screen}>
      <View style={[styles.content, { width: contentWidth }]}>
        <ScrollView
          style={styles.pageScroll}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <HomeHeader
            greeting={greeting}
            appTitle="WalkBuddy"
            showDivider
            showLocation
          />

          <View style={styles.mainArea}>
            <BounceButton label="SEARCH" onPress={openSearch} search />

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
                icon="microphone"
                label="VOICE ASSIST"
                onPress={goToCameraVoice}
              />
              <ActionTile
                icon="map-marker"
                label="PLACES"
                onPress={goToSavedPlaces}
              />
              <ActionTile
                icon="exclamation-triangle"
                label="EMERGENCY"
                onPress={goToEmergency}
              />
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
                    <Icon name="eye" size={28} color={tokens.muted} />
                    <Text style={styles.previewText}>
                      {visionEnabled ? "Tap to start camera" : "Vision disabled"}
                    </Text>
                    <Text style={styles.previewSubtext}>
                      Starting camera gives live surroundings
                    </Text>
                  </View>
                )}
              </View>
            </Pressable>
          </View>
        </ScrollView>
      </View>

      {/* ─── Search Modal ─── */}
      <Modal
        visible={showSearch}
        transparent
        animationType="fade"
        onRequestClose={closeSearch}
      >
        <Pressable style={styles.modalOverlay} onPress={closeSearch}>
          <Pressable onPress={() => {}} style={styles.modalCard}>

            {/* Header */}
            <View style={styles.modalHeader}>
              <Icon name="search" size={18} color={tokens.gold} />
              <Text style={styles.modalTitle}>Where to?</Text>
              <Pressable onPress={closeSearch} hitSlop={12}>
                <Icon name="times" size={20} color={tokens.muted} />
              </Pressable>
            </View>

            <View style={styles.modalDivider} />

            {/* Search input */}
            <View style={styles.searchBar}>
              <Icon name="search" size={16} color={tokens.muted} />
              <TextInput
                value={query}
                onChangeText={(text) => {
                  setQuery(text);
                  setDestinationType(null);
                }}
                placeholder="Enter a destination"
                placeholderTextColor={tokens.muted}
                style={styles.searchInput}
                autoCapitalize="words"
                autoCorrect={false}
                returnKeyType="search"
                autoFocus
              />
              {query.length > 0 && (
                <Pressable onPress={() => setQuery("")} hitSlop={10}>
                  <Icon name="times-circle" size={16} color={tokens.muted} />
                </Pressable>
              )}
            </View>

            {/* Result preview */}
            {hasDestination && (
              <View style={styles.resultCard}>
                <Icon name="map-marker" size={20} color={tokens.gold} />
                <Text style={styles.resultTitle} numberOfLines={2}>
                  {query}
                </Text>
                <Text style={styles.resultSub}>Tap a mode below to navigate</Text>
              </View>
            )}

            {!hasDestination && (
              <View style={styles.emptyState}>
                <Icon name="location-arrow" size={28} color={tokens.muted} />
                <Text style={styles.emptyStateText}>
                  Type a destination to get started
                </Text>
              </View>
            )}

            <View style={styles.modalDivider} />

            {/* Mode buttons */}
            <View style={styles.buttonRow}>
              <Pressable
                style={[styles.modeBtn, !hasDestination && styles.modeBtnDisabled]}
                onPress={onPressInterior}
                disabled={!hasDestination}
              >
                <Icon name="building" size={18} color={hasDestination ? tokens.gold : tokens.muted} />
                <Text style={[styles.modeBtnText, !hasDestination && styles.modeBtnTextDisabled]}>
                  INTERIOR
                </Text>
              </Pressable>

              <Pressable
                style={[styles.modeBtn, styles.modeBtnGold, !hasDestination && styles.modeBtnDisabled]}
                onPress={onPressMaps}
                disabled={!hasDestination}
              >
                <Icon name="map" size={18} color={hasDestination ? "#071a2a" : tokens.muted} />
                <Text style={[styles.modeBtnText, hasDestination && styles.modeBtnTextDark, !hasDestination && styles.modeBtnTextDisabled]}>
                  MAPS
                </Text>
              </Pressable>
            </View>
          </Pressable>
        </Pressable>
      </Modal>
    </SafeAreaView>
  );
}

/* COMPONENTS */

function BounceButton({ label, onPress, search }: { label: string; onPress: () => void; search?: boolean }) {
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
    <Pressable
      onPress={onPress}
      onPressIn={handlePressIn}
      onPressOut={handlePressOut}
    >
      <Animated.View
        style={[styles.searchButton, { transform: [{ scale }] }]}
      >
        <Animated.View
          pointerEvents="none"
          style={[styles.searchPressOverlay, { opacity: overlayOpacity }]}
        />
        <Icon
          name="search"
          size={16}
          color={tokens.text}
          style={styles.searchIcon}
        />
        <Text style={styles.searchText}>SEARCH</Text>
      </Animated.View>
    </Pressable>
  );
}

function ActionTile({
  icon,
  label,
  onPress,
}: {
  icon: string;
  label: string;
  onPress: () => void;
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
    <View style={styles.tile}>
      <Pressable
        onPress={onPress}
        onPressIn={handlePressIn}
        onPressOut={handlePressOut}
        android_ripple={{ color: "#f2a90022" }}
      >
        <Animated.View
          style={[styles.tileOuter, { transform: [{ scale }] }]}
        >
          <View style={styles.tileInner}>
            <Animated.View
              pointerEvents="none"
              style={[styles.tilePressOverlay, { opacity: overlayOpacity }]}
            />

            <Icon
              name={icon}
              size={24}
              color="#071a2a"
              style={styles.tileIcon}
            />

            <Text style={styles.tileText}>{label}</Text>
          </View>
        </Animated.View>
      </Pressable>
    </View>
  );
}

/* TOKENS */

const tokens = {
  bg: "#071a2a",
  tile: "#0b0f14",
  card: "#0d141c",
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
    flex: 1,
    paddingHorizontal: 12,
  },

  pressed: {
    opacity: 0.85,
    transform: [{ scale: 0.98 }],
  },

  pageScroll: {
    flex: 1,
    width: "100%",
  },

  scrollContent: {
    gap: 18,
    paddingBottom: 120,
  },

  mainArea: {
    gap: 0,
    width: "100%",
    paddingTop: 10,
  },

  searchButton: {
    width: "100%",
    backgroundColor: "#12314a",
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 50,
    paddingVertical: 20,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    marginBottom: 20,
    overflow: "hidden",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.18,
    shadowRadius: 6,
    elevation: 4,
  },

  searchIcon: {
    marginRight: 2,
  },

  searchPressOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(255,255,255,0.10)",
  },

  searchText: {
    color: tokens.text,
    fontSize: 18,
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
  },

  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginBottom: 22,
    gap: 10,
  },

  tile: {
    width: "48%",
  },

  tileOuter: {
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 22,
    shadowColor: tokens.gold,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.6,
    shadowRadius: 16,
    elevation: 6,
  },

  tileInner: {
    width: "100%",
    backgroundColor: tokens.gold,
    borderRadius: 20,
    minHeight: 108,
    paddingVertical: 18,
    paddingHorizontal: 8,
    alignItems: "center",
    gap: 8,
    overflow: "hidden",
  },

  tilePressOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(255,255,255,0.15)",
  },

  tileIcon: {},

  tileText: {
    color: "#071a2a",
    fontSize: 12,
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
    fontSize: 15,
    fontWeight: "900",
    letterSpacing: 0.5,
  },

  visionToggle: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },

  visionToggleText: {
    color: tokens.muted,
    fontSize: 12,
    fontWeight: "700",
  },

  visionCard: {
    width: "100%",
    minHeight: 220,
    flex: 1,
    backgroundColor: "#0d1f32",
    borderWidth: 1.5,
    borderColor: "rgba(242,169,0,0.4)",
    borderRadius: 18,
    padding: 10,
    marginBottom: 6,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 6,
    elevation: 4,
  },

  visionInner: {
    flex: 1,
    borderRadius: 14,
    overflow: "hidden",
    backgroundColor: "#0a121a",
  },

  previewPlaceholder: {
    minHeight: 190,
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingHorizontal: 20,
  },

  previewText: {
    color: tokens.text,
    fontWeight: "900",
    textAlign: "center",
  },

  previewSubtext: {
    color: tokens.muted,
    fontSize: 12,
    textAlign: "center",
  },

  // ─── Modal ───
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.75)",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 20,
  },

  modalCard: {
    width: "100%",
    maxWidth: 420,
    backgroundColor: "#0f1e2e",
    borderRadius: 28,
    borderWidth: 1.5,
    borderColor: "rgba(242,169,0,0.4)",
    overflow: "hidden",
    shadowColor: tokens.gold,
    shadowOpacity: 0.2,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 8 },
    elevation: 16,
    padding: 20,
    gap: 16,
  },

  modalHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },

  modalTitle: {
    color: tokens.text,
    fontSize: 20,
    fontWeight: "900",
    flex: 1,
  },

  modalDivider: {
    height: 1,
    backgroundColor: "rgba(242,169,0,0.2)",
  },

  searchBar: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#162233",
    borderWidth: 1.5,
    borderColor: "rgba(242,169,0,0.35)",
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 13,
    gap: 10,
  },

  searchInput: {
    flex: 1,
    color: tokens.text,
    fontSize: 15,
    fontWeight: "600",
  },

  resultCard: {
    backgroundColor: "#162233",
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "rgba(242,169,0,0.25)",
    padding: 16,
    alignItems: "center",
    gap: 8,
  },

  resultTitle: {
    color: tokens.text,
    fontSize: 18,
    fontWeight: "900",
    textAlign: "center",
  },

  resultSub: {
    color: tokens.muted,
    fontSize: 12,
    fontWeight: "600",
    textAlign: "center",
  },

  emptyState: {
    alignItems: "center",
    paddingVertical: 20,
    gap: 10,
  },

  emptyStateText: {
    color: tokens.muted,
    fontSize: 14,
    fontWeight: "600",
    textAlign: "center",
  },

  buttonRow: {
    flexDirection: "row",
    gap: 12,
  },

  modeBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    backgroundColor: "#162233",
    borderWidth: 1.5,
    borderColor: "rgba(242,169,0,0.35)",
    borderRadius: 14,
    paddingVertical: 14,
  },

  modeBtnGold: {
    backgroundColor: tokens.gold,
    borderColor: tokens.gold,
  },

  modeBtnDisabled: {
    opacity: 0.4,
  },

  modeBtnText: {
    color: tokens.text,
    fontSize: 14,
    fontWeight: "900",
    letterSpacing: 0.6,
  },

  modeBtnTextDark: {
    color: "#071a2a",
  },

  modeBtnTextDisabled: {
    opacity: 0.7,
  },
});
