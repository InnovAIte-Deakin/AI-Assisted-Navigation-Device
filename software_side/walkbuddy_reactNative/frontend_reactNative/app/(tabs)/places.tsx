import React, { useCallback, useMemo, useState } from "react";
import {
  StyleSheet,
  Text,
  View,
  Pressable,
  FlatList,
  useWindowDimensions,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";

import HomeHeader from "../HomeHeader";
import { Radius, Spacing, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";

import {
  getPlacesSorted,
  toggleFavourite,
  markUsed,
  PlaceItem,
} from "../../src/utils/placesStore"

async function seedPlacesOnce() {
  const list = await getPlacesSorted();
  if (list.length > 0) return;

  const now = Date.now();
  const dummy: PlaceItem[] = [
    { id: `${now}-home`, kind: "I", title: "My Apartment", isFav: true, createdAt: now, lastUsed: 0 },
    { id: `${now}-office`, kind: "I", title: "Office Reception", isFav: false, createdAt: now - 1, lastUsed: 0 },
    { id: `${now}-shops`, kind: "E", title: "Westfield Geelong", isFav: false, createdAt: now - 2, lastUsed: 0 },
    { id: `${now}-station`, kind: "E", title: "Geelong Railway Station", isFav: false, createdAt: now - 3, lastUsed: 0 },
    { id: `${now}-library`, kind: "E", title: "Geelong Library & Heritage Centre", isFav: false, createdAt: now - 4, lastUsed: 0 },
  ];

  const AsyncStorage = (await import("@react-native-async-storage/async-storage")).default;
  await AsyncStorage.setItem("wb:places_v2", JSON.stringify(dummy));
}

export default function PlacesPage() {
  const colors = useThemeColors();
  const router = useRouter();
  const { width } = useWindowDimensions();

  const [savedPlacesList, setSavedPlacesList] = useState<PlaceItem[]>([]);

  const contentWidth = useMemo(() => {
    const padding = 24;
    const max = 720;
    return Math.min(max, Math.max(320, width - padding * 2));
  }, [width]);

  const refresh = useCallback(async () => {
    const list = await getPlacesSorted();
    setSavedPlacesList(list);
  }, []);

  useFocusEffect(
    useCallback(() => {
      seedPlacesOnce().then(refresh);
    }, [refresh]),
  );

  const selectFavPlace = async (placeId: string) => {
    const next = await toggleFavourite(placeId);
    setSavedPlacesList(next);
  };

  const selectPlace = async (placeItem: PlaceItem) => {
    const next = await markUsed(placeItem.id);
    setSavedPlacesList(next);
    router.push({
      pathname: "/search",
      params: { presetDestination: placeItem.title, presetType: placeItem.kind },
    } as any);
  };

  const renderPlaceItem = ({ item: placeItem }: { item: PlaceItem }) => (
    <Pressable style={[styles.placeCard, { backgroundColor: colors.surface, borderColor: colors.accent }]} onPress={() => selectPlace(placeItem)}>
      {/* Kind Badge */}
      <View style={[styles.placeType, { borderColor: colors.accent, backgroundColor: colors.accent + "1F" }]}>
        <Text style={[styles.placeLabelText, { color: colors.accent }]}>{placeItem.kind}</Text>
      </View>

      <Text style={[styles.placeTitle, { color: colors.text }]} numberOfLines={1}>
        {placeItem.title}
      </Text>

      <Pressable
        onPress={(e) => {
          e.stopPropagation();
          selectFavPlace(placeItem.id);
        }}
        hitSlop={12}
        style={styles.favPlaceButton}
        accessibilityLabel={placeItem.isFav ? "Unfavourite place" : "Favourite place"}
      >
        <Ionicons
          name={placeItem.isFav ? "heart" : "heart-outline"}
          size={18}
          color={placeItem.isFav ? colors.accent : colors.textMuted}
        />
      </Pressable>
    </Pressable>
  );

  const handleBack = () => {
    const canGoBack = (router as any)?.canGoBack?.() ?? false;
    if (canGoBack) router.back();
    else router.replace("/" as any);
  };

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.background }]} edges={["top"]}>
      <Pressable
        onPress={handleBack}
        style={[styles.backBtnFloating, { backgroundColor: "rgba(27,38,59,0.65)", borderColor: colors.accent }]}
        accessibilityLabel="Go back"
      >
        <Ionicons name="arrow-back-outline" size={20} color={colors.accent} />
      </Pressable>
      <View style={[styles.content, { width: contentWidth }]}>
        <HomeHeader
          greeting="Places"
          appTitle="WalkBuddy"
          onPressProfile={() => router.push("/profile" as any)}
          showDivider
          showLocation
        />

        {/* Section Title */}
        {savedPlacesList.length > 0 && (
          <View style={styles.sectionHeader}>
            <Ionicons name="location-outline" size={14} color={colors.accent} />
            <Text style={[styles.sectionTitle, { color: colors.text }]}>SAVED PLACES</Text>
            <View style={[styles.sectionBadge, { backgroundColor: colors.accent }]}>
              <Text style={[styles.sectionBadgeText, { color: colors.background }]}>{savedPlacesList.length}</Text>
            </View>
          </View>
        )}

        <FlatList
          data={savedPlacesList}
          keyExtractor={(placeItem) => placeItem.id}
          renderItem={renderPlaceItem}
          contentContainerStyle={[
            styles.listContent,
            savedPlacesList.length === 0 && styles.listContentEmpty,
          ]}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <View style={[styles.emptyIconWrapper, { backgroundColor: colors.accent + "1A", borderColor: colors.accent + "4D" }]}>
                <Ionicons name="location-outline" size={36} color={colors.accent} />
              </View>
              <Text style={[styles.emptyTitle, { color: colors.text }]}>No Saved Places</Text>
              <Text style={[styles.emptyText, { color: colors.textMuted }]}>
                Places you save will appear here for quick access.
              </Text>
            </View>
          }
        />
      </View>
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
    flex: 1,
    paddingHorizontal: Spacing.md,
    paddingTop: 14,
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

  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    paddingHorizontal: 14,
    paddingTop: 18,
    paddingBottom: 10,
  },

  sectionTitle: {
    fontSize: Typography.size.sm,
    fontWeight: "900",
    letterSpacing: 0.8,
    flex: 1,
  },

  sectionBadge: {
    borderRadius: Radius.pill,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
  },

  sectionBadgeText: {
    fontSize: 11,
    fontWeight: "900",
  },

  listContent: {
    paddingHorizontal: 14,
    paddingBottom: 120,
    gap: Spacing.md,
  },

  listContentEmpty: {
    flexGrow: 1,
    justifyContent: "center",
    alignItems: "center",
  },

  placeCard: {
    borderWidth: 2,
    borderRadius: 18,
    paddingVertical: Spacing.lg,
    paddingHorizontal: 14,
    flexDirection: "row",
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.2,
    shadowRadius: 6,
    elevation: 4,
  },

  placeType: {
    width: 30,
    height: 30,
    borderRadius: Radius.pill,
    borderWidth: 2,
    alignItems: "center",
    justifyContent: "center",
    marginRight: Spacing.md,
  },

  placeLabelText: {
    fontWeight: "900",
    fontSize: 12,
  },

  placeTitle: {
    flex: 1,
    fontSize: Typography.size.sm,
    fontWeight: "700",
  },

  favPlaceButton: {
    paddingLeft: 10,
    paddingVertical: 4,
  },

  emptyContainer: {
    alignItems: "center",
    paddingHorizontal: 32,
    gap: Spacing.md,
  },

  emptyIconWrapper: {
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: 2,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 4,
  },

  emptyTitle: {
    fontSize: 17,
    fontWeight: "900",
    letterSpacing: 0.3,
  },

  emptyText: {
    fontSize: Typography.size.sm,
    fontWeight: "600",
    textAlign: "center",
    lineHeight: 20,
  },
});
