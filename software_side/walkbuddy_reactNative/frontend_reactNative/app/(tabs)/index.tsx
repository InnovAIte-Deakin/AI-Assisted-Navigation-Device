// app/(tabs)/index.tsx
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "expo-router";
import {
  Alert,
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
import { Ionicons } from "@expo/vector-icons";

import HomeHeader from "../HomeHeader";
import ModelWebView from "../../src/components/ModelWebView";
import { API_BASE } from "../../src/config";
import { useSession } from "../../src/context/SessionContext";
import { Radius, Spacing, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";
import { IconTile } from "@/components/ui/IconTile";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { HeroButton } from "@/components/ui/HeroButton";

type DestinationType = "I" | "E";

export default function HomePage() {
  const colors = useThemeColors();
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

  const goToCamera = () => router.push("/camera");
  const goToEmergency = () => router.push("/emergency" as any);

  const goToSavedPlaces = () => router.push("/places");
  const goToFavourites = () => router.push("/favourites" as any);
  const goToAskAFriend = () => router.push("/ask-a-friend-web" as any);
  const goToPredictivePath = () => router.push("/predictive-path" as any);

  const goToCameraVoice = () =>
    router.push({ pathname: "/camera", params: { mode: "voice" } } as any);

  const goToCameraOCR = () =>
    router.push({ pathname: "/camera", params: { mode: "ocr" } } as any);

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
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.background }]}>
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

          <PrimaryButton label="SEARCH" icon="search-outline" onPress={openSearch} />

          {/* ─── Primary actions ─── */}
          <View style={styles.heroStack}>
            <HeroButton
              tone="accent"
              icon="camera-outline"
              title="Open Camera"
              subtitle="Scan objects, read text, and ask questions"
              onPress={goToCamera}
            />
            <HeroButton
              tone="danger"
              icon="warning-outline"
              title="Emergency"
              subtitle="Get help immediately"
              onPress={goToEmergency}
            />
          </View>

          {/* ─── Quick actions ─── */}
          <Text style={[styles.sectionLabel, { color: colors.textMuted }]}>QUICK ACTIONS</Text>
          <View style={styles.grid}>
            <IconTile
              icon="document-text-outline"
              label="TEXT READER"
              onPress={goToCameraOCR}
            />
            <IconTile
              icon="mic-outline"
              label="VOICE ASSIST"
              onPress={goToCameraVoice}
            />
            <IconTile
              icon="location-outline"
              label="PLACES"
              onPress={goToSavedPlaces}
            />
            <IconTile
              icon="people-outline"
              label="ASK A FRIEND"
              onPress={goToAskAFriend}
            />
            <IconTile
              icon="trending-up-outline"
              label="PREDICTIVE PATH"
              onPress={goToPredictivePath}
            />
            <IconTile
              icon="star-outline"
              label="FAVOURITES"
              onPress={goToFavourites}
            />
          </View>

          {/* ─── Vision preview ─── */}
          <View
            style={[
              styles.visionWrapper,
              { backgroundColor: colors.surface },
              visionPreviewOn && { borderWidth: 1, borderColor: colors.accent },
            ]}
          >
            <View style={styles.visionRow}>
              <Text style={[styles.visionTitle, { color: colors.text }]}>VISION ASSIST PREVIEW</Text>

              <View style={styles.visionToggle}>
                <Text style={[styles.visionToggleText, { color: colors.textMuted }]}>
                  {visionEnabled ? "On" : "Off"}
                </Text>

                <Switch
                  value={visionEnabled}
                  onValueChange={setVisionEnabled}
                  trackColor={{ false: colors.border, true: colors.surfaceElevated }}
                  thumbColor={visionEnabled ? colors.accent : colors.textMuted}
                />
              </View>
            </View>

            <Pressable
              onPress={toggleVisionPreview}
              style={({ pressed }) => [
                styles.visionCard,
                { backgroundColor: colors.surfaceElevated, borderColor: colors.accent + "66" },
                pressed && styles.pressed,
              ]}
            >
              <View style={[styles.visionInner, { backgroundColor: colors.background }]}>
                {visionEnabled && visionPreviewOn ? (
                  <ModelWebView url={visionUrl} loading={loading} />
                ) : (
                  <View style={styles.previewPlaceholder}>
                    <Ionicons name="eye-outline" size={24} color={colors.textMuted} />
                    <Text style={[styles.previewText, { color: colors.text }]}>
                      {visionEnabled ? "Tap to start camera" : "Vision disabled"}
                    </Text>
                    <Text style={[styles.previewSubtext, { color: colors.textMuted }]}>
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
          <Pressable onPress={() => {}} style={[styles.modalCard, { backgroundColor: colors.surfaceElevated, borderColor: colors.accent + "66" }]}>

            {/* Header */}
            <View style={styles.modalHeader}>
              <Ionicons name="search-outline" size={18} color={colors.accent} />
              <Text style={[styles.modalTitle, { color: colors.text }]}>Where to?</Text>
              <Pressable onPress={closeSearch} hitSlop={12}>
                <Ionicons name="close-outline" size={20} color={colors.textMuted} />
              </Pressable>
            </View>

            <View style={[styles.modalDivider, { backgroundColor: colors.accent + "33" }]} />

            {/* Search input */}
            <View style={[styles.searchBar, { backgroundColor: colors.surface, borderColor: colors.accent + "59" }]}>
              <Ionicons name="search-outline" size={16} color={colors.textMuted} />
              <TextInput
                value={query}
                onChangeText={(text) => {
                  setQuery(text);
                  setDestinationType(null);
                }}
                placeholder="Enter a destination"
                placeholderTextColor={colors.textMuted}
                style={[styles.searchInput, { color: colors.text }]}
                autoCapitalize="words"
                autoCorrect={false}
                returnKeyType="search"
                autoFocus
              />
              {query.length > 0 && (
                <Pressable onPress={() => setQuery("")} hitSlop={10}>
                  <Ionicons name="close-circle-outline" size={16} color={colors.textMuted} />
                </Pressable>
              )}
            </View>

            {/* Result preview */}
            {hasDestination && (
              <View style={[styles.resultCard, { backgroundColor: colors.surface, borderColor: colors.accent + "40" }]}>
                <Ionicons name="location-outline" size={20} color={colors.accent} />
                <Text style={[styles.resultTitle, { color: colors.text }]} numberOfLines={2}>
                  {query}
                </Text>
                <Text style={[styles.resultSub, { color: colors.textMuted }]}>Tap a mode below to navigate</Text>
              </View>
            )}

            {!hasDestination && (
              <View style={styles.emptyState}>
                <Ionicons name="navigate-outline" size={28} color={colors.textMuted} />
                <Text style={[styles.emptyStateText, { color: colors.textMuted }]}>
                  Type a destination to get started
                </Text>
              </View>
            )}

            <View style={[styles.modalDivider, { backgroundColor: colors.accent + "33" }]} />

            {/* Mode buttons */}
            <View style={styles.buttonRow}>
              <Pressable
                style={[
                  styles.modeBtn,
                  { backgroundColor: colors.surface, borderColor: colors.accent + "59" },
                  !hasDestination && styles.modeBtnDisabled,
                ]}
                onPress={onPressInterior}
                disabled={!hasDestination}
              >
                <Ionicons name="business-outline" size={18} color={hasDestination ? colors.accent : colors.textMuted} />
                <Text style={[styles.modeBtnText, { color: colors.text }, !hasDestination && styles.modeBtnTextDisabled]}>
                  INTERIOR
                </Text>
              </Pressable>

              <Pressable
                style={[
                  styles.modeBtn,
                  { backgroundColor: colors.accent, borderColor: colors.accent },
                  !hasDestination && styles.modeBtnDisabled,
                ]}
                onPress={onPressMaps}
                disabled={!hasDestination}
              >
                <Ionicons name="map-outline" size={18} color={hasDestination ? colors.accentText : colors.textMuted} />
                <Text
                  style={[
                    styles.modeBtnText,
                    { color: hasDestination ? colors.accentText : colors.text },
                    !hasDestination && styles.modeBtnTextDisabled,
                  ]}
                >
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

/* STYLES — structural only; colors applied inline so they react to
   light/dark via useThemeColors(). */

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    alignItems: "center",
  },

  content: {
    flex: 1,
    paddingHorizontal: Spacing.md,
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
    gap: Spacing.lg,
    paddingBottom: 120,
  },

  heroStack: {
    gap: Spacing.md,
  },

  sectionLabel: {
    fontSize: Typography.size.xs,
    fontWeight: "800",
    letterSpacing: 1,
    marginTop: Spacing.sm,
  },

  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: Spacing.sm,
  },

  visionWrapper: {
    borderRadius: Radius.lg,
    padding: Spacing.md,
  },

  visionRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: Spacing.sm,
  },

  visionTitle: {
    fontSize: Typography.size.sm,
    fontWeight: "900",
    letterSpacing: 0.5,
  },

  visionToggle: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.xs,
  },

  visionToggleText: {
    fontSize: Typography.size.xs,
    fontWeight: "700",
  },

  visionCard: {
    width: "100%",
    minHeight: 180,
    borderWidth: 1.5,
    borderRadius: Radius.lg,
    padding: Spacing.sm,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 6,
    elevation: 4,
  },

  visionInner: {
    flex: 1,
    minHeight: 160,
    borderRadius: Radius.md,
    overflow: "hidden",
  },

  previewPlaceholder: {
    minHeight: 160,
    alignItems: "center",
    justifyContent: "center",
    gap: Spacing.sm,
    paddingHorizontal: Spacing.xl,
  },

  previewText: {
    fontWeight: "900",
    textAlign: "center",
  },

  previewSubtext: {
    fontSize: Typography.size.xs,
    textAlign: "center",
  },

  // ─── Modal ───
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.75)",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: Spacing.xl,
  },

  modalCard: {
    width: "100%",
    maxWidth: 420,
    borderRadius: Radius.xl + 6,
    borderWidth: 1.5,
    overflow: "hidden",
    shadowOpacity: 0.2,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 8 },
    elevation: 16,
    padding: Spacing.xl,
    gap: Spacing.lg,
  },

  modalHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
  },

  modalTitle: {
    fontSize: Typography.size.lg,
    fontWeight: "900",
    flex: 1,
  },

  modalDivider: {
    height: 1,
  },

  searchBar: {
    flexDirection: "row",
    alignItems: "center",
    borderWidth: 1.5,
    borderRadius: Radius.lg,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md + 1,
    gap: Spacing.md,
  },

  searchInput: {
    flex: 1,
    fontSize: Typography.size.sm,
    fontWeight: "600",
  },

  resultCard: {
    borderRadius: Radius.lg,
    borderWidth: 1,
    padding: Spacing.lg,
    alignItems: "center",
    gap: Spacing.sm,
  },

  resultTitle: {
    fontSize: Typography.size.md,
    fontWeight: "900",
    textAlign: "center",
  },

  resultSub: {
    fontSize: Typography.size.xs,
    fontWeight: "600",
    textAlign: "center",
  },

  emptyState: {
    alignItems: "center",
    paddingVertical: Spacing.xl,
    gap: Spacing.md,
  },

  emptyStateText: {
    fontSize: Typography.size.sm,
    fontWeight: "600",
    textAlign: "center",
  },

  buttonRow: {
    flexDirection: "row",
    gap: Spacing.md,
  },

  modeBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: Spacing.sm,
    borderWidth: 1.5,
    borderRadius: Radius.lg,
    paddingVertical: Spacing.lg,
  },

  modeBtnDisabled: {
    opacity: 0.4,
  },

  modeBtnText: {
    fontSize: Typography.size.sm,
    fontWeight: "900",
    letterSpacing: 0.6,
  },

  modeBtnTextDisabled: {
    opacity: 0.7,
  },
});
