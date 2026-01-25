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

import HomeHeader from "./HomeHeader";
import Footer from "./Footer";

import {
  getPlacesSorted,
  toggleFavourite,
  markUsed,
  PlaceItem,
} from "./lib/placesStore";

/*
  TEMPORARY TESTING ONLY
  This seeds AsyncStorage with 5 dummy places if none exist.
  This must be REMOVED once real location data is wired in.
*/
async function seedPlacesOnce() {
  const list = await getPlacesSorted();
  if (list.length > 0) return;

  const now = Date.now();
  const dummy: PlaceItem[] = [
    {
      id: `${now}-home`,
      kind: "I",
      title: "My Apartment",
      isFav: true,
      createdAt: now,
      lastUsed: 0,
    },
    {
      id: `${now}-office`,
      kind: "I",
      title: "Office Reception",
      isFav: false,
      createdAt: now - 1,
      lastUsed: 0,
    },
    {
      id: `${now}-shops`,
      kind: "E",
      title: "Westfield Geelong",
      isFav: false,
      createdAt: now - 2,
      lastUsed: 0,
    },
    {
      id: `${now}-station`,
      kind: "E",
      title: "Geelong Railway Station",
      isFav: false,
      createdAt: now - 3,
      lastUsed: 0,
    },
    {
      id: `${now}-library`,
      kind: "E",
      title: "Geelong Library & Heritage Centre",
      isFav: false,
      createdAt: now - 4,
      lastUsed: 0,
    },
  ];

  const AsyncStorage =
    (await import("@react-native-async-storage/async-storage")).default;
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
    }, [refresh])
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
      params: { presetDestination: placeItem.title,
      presetType: placeItem.kind,},
    } as any);
  };

  const renderPlaceItem = ({ item: placeItem }: { item: PlaceItem }) => (
    <Pressable style={styles.placeCard} onPress={() => selectPlace(placeItem)}>
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
        accessibilityLabel={
          placeItem.isFav ? "Unfavourite place" : "Favourite place"
        }
      >
        <Icon
          name={placeItem.isFav ? "heart" : "heart-o"}
          size={18}
          color="#FCA311"
        />
      </Pressable>
    </Pressable>
  );

  return (
    <SafeAreaView style={styles.screen} edges={["top"]}>
      <View style={[styles.content, { width: contentWidth }]}>
        <HomeHeader
          appTitle="WalkBuddy"
          onPressProfile={() => router.push("/profile" as any)}
          showDivider
          showLocation
        />

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
              <Text style={styles.emptyText}>No places stored</Text>
            </View>
          }
        />
        <Footer/>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#0D1B2A",
    alignItems: "center",
  },

  content: {
    flex: 1,
    paddingHorizontal: 12,
    paddingTop: 8,
  },

  listContent: {
    paddingTop: 14,
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
    borderColor: "#FCA311",
    borderRadius: 14,
    backgroundColor: "#111",
    paddingVertical: 14,
    paddingHorizontal: 12,
    flexDirection: "row",
    alignItems: "center",
  },
  
  placeType: {
    width: 26,
    height: 26,
    borderRadius: 999,
    borderWidth: 2,
    borderColor: "#E0E1DD",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 10,
  },

  placeLabelText: {
    color: "#E0E1DD",
    fontWeight: "800",
    fontSize: 12,
  },

  placeTitle: {
    flex: 1,
    color: "#E0E1DD",
    fontSize: 14,
    fontWeight: "700",
  },

  favPlaceButton: {
    paddingLeft: 10,
    paddingVertical: 4,
  },

  emptyContainer: {
    alignItems: "center",
    paddingHorizontal: 14,
  },

  emptyText: {
    color: "#E0E1DD",
    opacity: 0.75,
    fontSize: 14,
  },
});
