// app/search.tsx
import React, { useEffect, useMemo, useState } from "react";
import { useLocalSearchParams, useRouter } from "expo-router";
import {
  StyleSheet,
  Text,
  View,
  Pressable,
  ScrollView,
  TextInput,
  useWindowDimensions,
  Alert,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Icon from "react-native-vector-icons/FontAwesome";
import HomeHeader from "./HomeHeader";
import { getRecentPlaces, markUsed, type PlaceItem } from "./lib/placesStore";

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
  const resultFontSize = Math.max(26, Math.min(36, height * 0.045));

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

  const hasDestination = query.trim().length > 0;

  const [recentPlaces, setRecentPlaces] = useState<PlaceItem[]>([]);

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

  useEffect(() => {
    (async () => {
      try {
        const list = await getRecentPlaces(6);
        setRecentPlaces(list);
      } catch {
      }
    })();
  }, []);

  const selectRecentPlace = async (place: PlaceItem) => {
    await markUsed(place.id);
    const list = await getRecentPlaces(6);
    setRecentPlaces(list);

    const trimmed = place.title.trim();
    setQuery(trimmed);
    setDestinationType(place.kind);
  };

  function onPressInterior() {
    if (!hasDestination) return;

    if (destinationType === "E") {
      Alert.alert("Error!!", "This is an External destination");
      return;
    }

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
    const encoded = encodeURIComponent(destinationText);

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
      <View style={[styles.content, { width: contentWidth }]}>
        <HomeHeader
          appTitle="WalkBuddy"
          onPressProfile={() => router.push("/profile" as any)}
          showDivider
          showLocation
        />

        {/* Spacer below header (visual breathing room) */}
        <View style={{ height: 2 }} />
        <View style={{ height: 2 }} />

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

          {!hasDestination && recentPlaces.length > 0 && (
            <View style={styles.recentWrap}>
              <Text style={styles.recentTitle}>Recent destinations</Text>
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.recentRow}
              >
                {recentPlaces.map((place) => (
                  <Pressable
                    key={place.id}
                    onPress={() => selectRecentPlace(place)}
                    style={styles.recentPill}
                    accessibilityLabel={`Recent destination: ${place.title}`}
                  >
                    <Text style={styles.recentPillText} numberOfLines={1}>
                      {place.title}
                    </Text>
                  </Pressable>
                ))}
              </ScrollView>
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

          <View style={{ height: 1 }} />
          <View style={{ height: 1 }} />
        </View>
      </View>
    </SafeAreaView>
  );
}

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
    width: "100%",
    paddingTop: 2,
    paddingHorizontal: 14,
    gap: 18,
    flexGrow: 1,
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

  resultCard: {
    width: "100%",
    backgroundColor: tokens.tile,
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 18,
    paddingVertical: 26,
    paddingHorizontal: 16,
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    flexGrow: 1,
    minHeight: 200,
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

  recentWrap: {
    width: "100%",
    marginTop: 10,
  },
  recentTitle: {
    color: tokens.text,
    opacity: 0.85,
    fontSize: 14,
    fontWeight: "900",
    marginBottom: 8,
  },
  recentRow: {
    gap: 10,
    paddingBottom: 4,
  },
  recentPill: {
    borderWidth: 2,
    borderColor: tokens.gold,
    backgroundColor: tokens.tile,
    borderRadius: 999,
    paddingVertical: 10,
    paddingHorizontal: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  recentPillText: {
    color: tokens.text,
    fontWeight: "800",
    fontSize: 13,
    maxWidth: 200,
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
