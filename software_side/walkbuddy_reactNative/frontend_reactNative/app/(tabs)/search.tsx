// app/search.tsx
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import {
  StyleSheet,
  Text,
  View,
  Pressable,
  TextInput,
  useWindowDimensions,
  Alert,
  ScrollView,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import HomeHeader from "../HomeHeader";
import {
  dismissRecentPlace,
  getRecentPlaces,
  PlaceItem,
  upsertPlaceUsed,
} from "../../src/utils/placesStore";
import { Radius, Spacing, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";
/*
  NOTE:
  This screen was originally UI-first.
  Now it also includes basic mode handoff (Interior / Maps) once a destination is entered.

  Real destination resolution (geocoding / indoor lookup) is handled in Exterior / Interior screens,
  not here.
*/

type DestinationType = "I" | "E";

export default function SearchPage() {
  const colors = useThemeColors();
  const router = useRouter();
  const { width, height } = useWindowDimensions();
  const resultFontSize = Math.max(20, Math.min(28, height * 0.035));

  const { presetDestination, presetType } = useLocalSearchParams<{
    presetDestination?: string;
    presetType?: DestinationType;
  }>();

  const contentWidth = useMemo(() => {
    const padding = 24;
    const max = 720;
    return Math.min(max, Math.max(320, width - padding * 2));
  }, [width]);

  const [query, setQuery] = useState("");
  const [destinationType, setDestinationType] =
    useState<DestinationType | null>(null);
  const [recents, setRecents] = useState<PlaceItem[]>([]);

  const hasDestination = query.trim().length > 0;

  // Prefill search field when coming from Places
  useEffect(() => {
    if (typeof presetDestination !== "string") return;

    const trimmed = presetDestination.trim();
    setQuery(trimmed);

    if (presetType === "I" || presetType === "E") {
      setDestinationType(presetType);
    } else {
      setDestinationType(null);
    }
  }, [presetDestination, presetType]);

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      getRecentPlaces(6).then((list) => {
        if (!alive) return;
        setRecents(list);
      });
      return () => {
        alive = false;
      };
    }, [])
  );

  const applyRecent = (p: PlaceItem) => {
    setQuery(p.title);
    setDestinationType(p.kind);
  };

  const removeRecent = async (p: PlaceItem) => {
    setRecents((prev) => prev.filter((x) => x.id !== p.id));
    await dismissRecentPlace(p.id);
    const next = await getRecentPlaces(6);
    setRecents(next);
  };

  const handleBack = () => {
    const canGoBack = (router as any)?.canGoBack?.() ?? false;
    if (canGoBack) router.back();
    else router.replace("/" as any);
  };

  function onPressInterior() {
    if (!hasDestination) return;

    if (destinationType === "E") {
      Alert.alert("Error!!", "This is an External destination");
      return;
    }

    const destinationText = query.trim();
    void upsertPlaceUsed(destinationText, "I");

    router.push({
      pathname: "/indoor",
    } as any);
  }

  function onPressMaps() {
    console.log("[Search] MAPS pressed", {
      hasDestination,
      destinationType,
      query,
    });

    if (!hasDestination) return;

    if (destinationType === "I") {
      Alert.alert("Error!!", "This is an Internal destination");
      return;
    }

    const destinationText = query.trim();

    void upsertPlaceUsed(destinationText, "E");

    // Web: open exterior in a new empty window/tab
    // if (Platform.OS === "web") {
    //   const url = `/exterior?presetDestination=${encoded}&presetType=E`;
    //   window.open(url, "_blank", "noopener,noreferrer");
    //   return;
    // }

    // Mobile: navigate normally
    router.push({
      pathname: "exterior",
      params: { presetDestination: destinationText, presetType: "E" },
    } as any);
  }

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.background }]} edges={["top"]}>
      <Pressable
        onPress={handleBack}
        style={[styles.backBtnFloating, { backgroundColor: "rgba(27,38,59,0.65)", borderColor: colors.accent }]}
        accessibilityLabel="Go back"
      >
        <Ionicons name="arrow-back-outline" size={20} color={colors.accent} />
      </Pressable>
      <ScrollView
        contentContainerStyle={[
          styles.content,
          { width: contentWidth },
        ]}
        showsVerticalScrollIndicator={false}
      >
        <HomeHeader
          appTitle="WalkBuddy"
          onPressProfile={() => router.push("/profile" as any)}
          showDivider
          showLocation
        />

        <View style={{ height: 4 }} />
        <View style={styles.mainArea}>
          <Text style={[styles.sectionTitle, { color: colors.text }]}>Enter Your Search</Text>

          {/* Search input */}
          <View style={[styles.searchBar, { backgroundColor: colors.surface, borderColor: colors.accent }]}>
            <Ionicons name="search-outline" size={18} color={colors.textMuted} />
            <TextInput
              value={query}
              onChangeText={(text) => {
                setQuery(text);
                // Reset destination type when user edits the input manually
                setDestinationType(null);
              }}
              placeholder="Enter a destination"
              placeholderTextColor={colors.textMuted}
              style={[styles.searchInput, { color: colors.text }]}
              autoCapitalize="words"
              autoCorrect={false}
              returnKeyType="search"
            />
          </View>

          {!hasDestination && recents.length > 0 && (
            <View style={[styles.recentsCard, { backgroundColor: colors.surface, borderColor: colors.accent }]}>
              <Text style={[styles.recentsTitle, { color: colors.text }]}>Recent destinations</Text>
              <View style={styles.recentsGrid}>
                {recents.map((p) => (
                  <Pressable
                    key={p.id}
                    style={[styles.recentChip, { backgroundColor: colors.background, borderColor: colors.accent }]}
                    onPress={() => applyRecent(p)}
                    accessibilityLabel={`Recent destination ${p.title}`}
                  >
                    <Text style={[styles.recentChipType, { borderColor: colors.text, color: colors.text }]}>{p.kind}</Text>
                    <Text style={[styles.recentChipText, { color: colors.text }]} numberOfLines={1}>
                      {p.title}
                    </Text>
                    <Pressable
                      onPress={(e) => {
                        e.stopPropagation();
                        void removeRecent(p);
                      }}
                      hitSlop={10}
                      style={[styles.recentRemoveBtn, { backgroundColor: colors.accent + "1F", borderColor: colors.accent + "73" }]}
                      accessibilityLabel={`Remove ${p.title} from recents`}
                    >
                      <Text style={[styles.recentRemoveText, { color: colors.text }]}>×</Text>
                    </Pressable>
                  </Pressable>
                ))}
              </View>
            </View>
          )}

          {/* Result display area */}
          <View style={[styles.resultCard, { backgroundColor: colors.surface, borderColor: colors.accent }]}>
            <Text
              style={[styles.resultTitle, { color: colors.text, fontSize: resultFontSize }]}
              numberOfLines={3}
            >
              {hasDestination
                ? query
                : "Enter a destination in the search bar to continue..."}
            </Text>
            <Text style={[styles.resultSub, { color: colors.text }]} numberOfLines={3}>
              {hasDestination
                ? "This is the destination you entered"
                : "The selected destination will appear here"}
            </Text>
          </View>

          {/* Navigation mode buttons */}
          <View style={styles.buttonRow}>
            <Pressable
              style={[
                styles.modeBtn,
                { backgroundColor: colors.surface, borderColor: colors.accent },
                !hasDestination && styles.modeBtnDisabled,
              ]}
              onPress={onPressInterior}
              disabled={!hasDestination}
              accessibilityLabel="Interior navigation"
              accessibilityHint="Opens interior navigation for the selected destination"
            >
              <Text
                style={[
                  styles.modeBtnText,
                  { color: colors.text },
                  !hasDestination && styles.modeBtnTextDisabled,
                ]}
              >
                INTERIOR
              </Text>
            </Pressable>

            <Pressable
              style={[
                styles.modeBtn,
                { backgroundColor: colors.surface, borderColor: colors.accent },
                !hasDestination && styles.modeBtnDisabled,
              ]}
              onPress={onPressMaps}
              disabled={!hasDestination}
              accessibilityLabel="Outdoor maps navigation"
              accessibilityHint="Opens outdoor maps navigation for the selected destination"
            >
              <Text
                style={[
                  styles.modeBtnText,
                  { color: colors.text },
                  !hasDestination && styles.modeBtnTextDisabled,
                ]}
              >
                MAPS
              </Text>
            </Pressable>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

/* STYLES — structural only; colors applied inline so they react to
   light/dark via useThemeColors(). */

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    alignItems: "center",
    position: "relative",
  },

  content: {
    paddingHorizontal: Spacing.md,
    paddingTop: 14,
    paddingBottom: 40,
  },

  backBtnFloating: {
    position: "absolute",
    top: Spacing.md,
    left: Spacing.md,
    width: 44,
    height: 44,
    borderRadius: Radius.xl,
    borderWidth: 1.5,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 20,
  },

  mainArea: {
    width: "100%",
    paddingTop: 2,
    paddingHorizontal: 14,
    gap: 18,
  },

  sectionTitle: {
    fontSize: Typography.size.base,
    fontWeight: "800",
    marginBottom: 6,
  },

  searchBar: {
    width: "100%",
    height: 56,
    borderWidth: 2,
    borderRadius: 14,
    paddingHorizontal: 14,
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
  },

  searchInput: {
    flex: 1,
    fontSize: Typography.size.base,
    fontWeight: "700",
  },

  recentsCard: {
    width: "100%",
    borderWidth: 2,
    borderRadius: 14,
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.md,
    gap: 10,
  },

  recentsTitle: {
    fontSize: Typography.size.sm,
    fontWeight: "900",
    letterSpacing: 0.3,
  },

  recentsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },

  recentChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    borderWidth: 1,
    borderRadius: Radius.pill,
    paddingVertical: 10,
    paddingHorizontal: Spacing.md,
    maxWidth: "100%",
  },

  recentChipType: {
    width: 18,
    height: 18,
    textAlign: "center",
    textAlignVertical: "center",
    borderRadius: 9,
    overflow: "hidden",
    borderWidth: 1,
    fontSize: 11,
    fontWeight: "900",
  },

  recentChipText: {
    fontSize: 13,
    fontWeight: "800",
    maxWidth: 240,
  },

  recentRemoveBtn: {
    marginLeft: 2,
    width: 24,
    height: 24,
    borderRadius: Radius.md,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
  },

  recentRemoveText: {
    fontSize: Typography.size.md,
    fontWeight: "900",
    lineHeight: 18,
    marginTop: -1,
  },

  resultCard: {
    width: "100%",
    borderWidth: 2,
    borderRadius: 18,
    paddingVertical: 18,
    paddingHorizontal: Spacing.lg,
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    height: 180,
  },

  resultTitle: {
    fontWeight: "900",
    textAlign: "center",
    letterSpacing: 0.6,
  },

  resultSub: {
    opacity: 0.75,
    fontSize: Typography.size.sm,
    fontWeight: "700",
    textAlign: "center",
    lineHeight: 20,
  },

  buttonRow: {
    width: "100%",
    flexDirection: "row",
    gap: Spacing.md,
  },

  modeBtn: {
    flex: 1,
    borderWidth: 2,
    borderRadius: 14,
    paddingVertical: 18,
    alignItems: "center",
  },

  modeBtnDisabled: {
    opacity: 0.45,
  },

  modeBtnText: {
    fontSize: Typography.size.sm,
    fontWeight: "900",
    letterSpacing: 0.6,
  },

  modeBtnTextDisabled: {
    opacity: 0.85,
  },
});
