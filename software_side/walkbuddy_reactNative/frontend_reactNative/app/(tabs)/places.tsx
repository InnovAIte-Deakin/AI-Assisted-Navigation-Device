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
import Icon from "react-native-vector-icons/FontAwesome";
import { useFocusEffect, useRouter } from "expo-router";

import HomeHeader from "../HomeHeader";

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
    <Pressable style={styles.placeCard} onPress={() => selectPlace(placeItem)}>
      {/* Kind Badge */}
      <View style={styles.placeType}>
        <Text style={styles.placeLabelText}>{placeItem.kind}</Text>
      </View>

      <Text style={styles.placeTitle} numberOfLines={1}>
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
        <Icon
          name={placeItem.isFav ? "heart" : "heart-o"}
          size={18}
          color={placeItem.isFav ? tokens.gold : tokens.muted}
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
    <SafeAreaView style={styles.screen} edges={["top"]}>
      <Pressable
        onPress={handleBack}
        style={styles.backBtnFloating}
        accessibilityLabel="Go back"
      >
        <Icon name="arrow-left" size={20} color="#FCA311" />
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
            <Icon name="map-marker" size={14} color={tokens.gold} />
            <Text style={styles.sectionTitle}>SAVED PLACES</Text>
            <View style={styles.sectionBadge}>
              <Text style={styles.sectionBadgeText}>{savedPlacesList.length}</Text>
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
              <View style={styles.emptyIconWrapper}>
                <Icon name="map-marker" size={36} color={tokens.gold} />
              </View>
              <Text style={styles.emptyTitle}>No Saved Places</Text>
              <Text style={styles.emptyText}>
                Places you save will appear here for quick access.
              </Text>
            </View>
          }
        />
      </View>
    </SafeAreaView>
  );
}

const tokens = {
  bg: "#0D1B2A",
  card: "#0b1520",
  border: "#FCA311",
  gold: "#FCA311",
  text: "#e8eef6",
  muted: "#6b7f99",
};

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: tokens.bg,
    alignItems: "center",
    position: "relative",
  },

  content: {
    flex: 1,
    paddingHorizontal: 12,
    paddingTop: 14,
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
    borderColor: "#FCA311",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 20,
  },

  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 14,
    paddingTop: 18,
    paddingBottom: 10,
  },

  sectionTitle: {
    color: tokens.text,
    fontSize: 13,
    fontWeight: "900",
    letterSpacing: 0.8,
    flex: 1,
  },

  sectionBadge: {
    backgroundColor: tokens.gold,
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },

  sectionBadgeText: {
    color: tokens.bg,
    fontSize: 11,
    fontWeight: "900",
  },

  listContent: {
    paddingHorizontal: 14,
    paddingBottom: 120,
    gap: 12,
  },

  listContentEmpty: {
    flexGrow: 1,
    justifyContent: "center",
    alignItems: "center",
  },

  placeCard: {
    borderWidth: 2,
    borderColor: tokens.border,
    borderRadius: 18,
    backgroundColor: tokens.card,
    paddingVertical: 16,
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
    borderRadius: 999,
    borderWidth: 2,
    borderColor: tokens.gold,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
    backgroundColor: "rgba(252,163,17,0.12)",
  },

  placeLabelText: {
    color: tokens.gold,
    fontWeight: "900",
    fontSize: 12,
  },

  placeTitle: {
    flex: 1,
    color: tokens.text,
    fontSize: 15,
    fontWeight: "700",
  },

  favPlaceButton: {
    paddingLeft: 10,
    paddingVertical: 4,
  },

  emptyContainer: {
    alignItems: "center",
    paddingHorizontal: 32,
    gap: 12,
  },

  emptyIconWrapper: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: "rgba(252,163,17,0.1)",
    borderWidth: 2,
    borderColor: "rgba(252,163,17,0.3)",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 4,
  },

  emptyTitle: {
    color: tokens.text,
    fontSize: 17,
    fontWeight: "900",
    letterSpacing: 0.3,
  },

  emptyText: {
    color: tokens.muted,
    fontSize: 13,
    fontWeight: "600",
    textAlign: "center",
    lineHeight: 20,
  },
});