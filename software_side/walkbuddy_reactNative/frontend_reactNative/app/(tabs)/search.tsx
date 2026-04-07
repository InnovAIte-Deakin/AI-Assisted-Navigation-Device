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
import Icon from "react-native-vector-icons/FontAwesome";
import HomeHeader from "../HomeHeader";
import {
  dismissRecentPlace,
  getRecentPlaces,
  PlaceItem,
  upsertPlaceUsed,
} from "../../src/utils/placesStore";
/*
  NOTE:
  This screen was originally UI-first.
  Now it also includes basic mode handoff (Interior / Maps) once a destination is entered.

  Real destination resolution (geocoding / indoor lookup) is handled in Exterior / Interior screens,
  not here.
*/

const tokens = {
  bg: "#0D1B2A",
  tile: "#111",
  text: "#E0E1DD",
  muted: "#b8c6d4",
  gold: "#FCA311",
};

type DestinationType = "I" | "E";

export default function SearchPage() {
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
    <SafeAreaView style={styles.screen} edges={["top"]}>
      <Pressable
        onPress={handleBack}
        style={styles.backBtnFloating}
        accessibilityLabel="Go back"
      >
        <Icon name="arrow-left" size={20} color={tokens.gold} />
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
          <Text style={styles.sectionTitle}>Enter Your Search</Text>

          {/* Search input */}
          <View style={styles.searchBar}>
            <Icon name="search" size={18} color={tokens.muted} />
            <TextInput
              value={query}
              onChangeText={(text) => {
                setQuery(text);
                // Reset destination type when user edits the input manually
                setDestinationType(null);
              }}
              placeholder="Enter a destination"
              placeholderTextColor={tokens.muted}
              style={styles.searchInput}
              autoCapitalize="words"
              autoCorrect={false}
              returnKeyType="search"
            />
          </View>

          {!hasDestination && recents.length > 0 && (
            <View style={styles.recentsCard}>
              <Text style={styles.recentsTitle}>Recent destinations</Text>
              <View style={styles.recentsGrid}>
                {recents.map((p) => (
                  <Pressable
                    key={p.id}
                    style={styles.recentChip}
                    onPress={() => applyRecent(p)}
                    accessibilityLabel={`Recent destination ${p.title}`}
                  >
                    <Text style={styles.recentChipType}>{p.kind}</Text>
                    <Text style={styles.recentChipText} numberOfLines={1}>
                      {p.title}
                    </Text>
                    <Pressable
                      onPress={(e) => {
                        e.stopPropagation();
                        void removeRecent(p);
                      }}
                      hitSlop={10}
                      style={styles.recentRemoveBtn}
                      accessibilityLabel={`Remove ${p.title} from recents`}
                    >
                      <Text style={styles.recentRemoveText}>×</Text>
                    </Pressable>
                  </Pressable>
                ))}
              </View>
            </View>
          )}

          {/* Result display area */}
          <View style={styles.resultCard}>
            <Text
              style={[styles.resultTitle, { fontSize: resultFontSize }]}
              numberOfLines={3}
            >
              {hasDestination
                ? query
                : "Enter a destination in the search bar to continue..."}
            </Text>
            <Text style={styles.resultSub} numberOfLines={3}>
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
                  !hasDestination && styles.modeBtnTextDisabled,
                ]}
              >
                INTERIOR
              </Text>
            </Pressable>

            <Pressable
              style={[
                styles.modeBtn,
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

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: tokens.bg,
    alignItems: "center",
    position: "relative",
  },

  content: {
    paddingHorizontal: 12,
    paddingTop: 14,
    paddingBottom: 40,
  },

  backBtnFloating: {
    position: "absolute",
    top: 12,
    left: 12,
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: "rgba(27,38,59,0.65)",
    borderWidth: 1.5,
    borderColor: tokens.gold,
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
    color: tokens.text,
    fontSize: 16,
    fontWeight: "800",
    marginBottom: 6,
  },

  searchBar: {
    width: "100%",
    height: 56,
    backgroundColor: tokens.tile,
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 14,
    paddingHorizontal: 14,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },

  searchInput: {
    flex: 1,
    color: tokens.text,
    fontSize: 16,
    fontWeight: "700",
  },

  recentsCard: {
    width: "100%",
    backgroundColor: tokens.tile,
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 14,
    paddingVertical: 12,
    paddingHorizontal: 12,
    gap: 10,
  },

  recentsTitle: {
    color: tokens.text,
    fontSize: 14,
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
    gap: 8,
    backgroundColor: "#0b0f14",
    borderWidth: 1,
    borderColor: tokens.gold,
    borderRadius: 999,
    paddingVertical: 10,
    paddingHorizontal: 12,
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
    borderColor: tokens.text,
    color: tokens.text,
    fontSize: 11,
    fontWeight: "900",
  },

  recentChipText: {
    color: tokens.text,
    fontSize: 13,
    fontWeight: "800",
    maxWidth: 240,
  },

  recentRemoveBtn: {
    marginLeft: 2,
    width: 24,
    height: 24,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(252,163,17,0.12)",
    borderWidth: 1,
    borderColor: "rgba(252,163,17,0.45)",
  },

  recentRemoveText: {
    color: tokens.text,
    fontSize: 18,
    fontWeight: "900",
    lineHeight: 18,
    marginTop: -1,
  },

  resultCard: {
    width: "100%",
    backgroundColor: tokens.tile,
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 18,
    paddingVertical: 18,
    paddingHorizontal: 16,
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    height: 180,
  },

  resultTitle: {
    color: tokens.text,
    fontWeight: "900",
    textAlign: "center",
    letterSpacing: 0.6,
  },

  resultSub: {
    color: tokens.text,
    opacity: 0.75,
    fontSize: 14,
    fontWeight: "700",
    textAlign: "center",
    lineHeight: 20,
  },

  buttonRow: {
    width: "100%",
    flexDirection: "row",
    gap: 12,
  },

  modeBtn: {
    flex: 1,
    backgroundColor: tokens.tile,
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 14,
    paddingVertical: 18,
    alignItems: "center",
  },

  modeBtnDisabled: {
    opacity: 0.45,
  },

  modeBtnText: {
    color: tokens.text,
    fontSize: 14,
    fontWeight: "900",
    letterSpacing: 0.6,
  },

  modeBtnTextDisabled: {
    opacity: 0.85,
  },
});