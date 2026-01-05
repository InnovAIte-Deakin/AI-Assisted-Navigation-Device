import React, { useCallback, useState } from "react";
import {SafeAreaView,StyleSheet,Text,View,Pressable,FlatList,} from "react-native";
import Icon from "react-native-vector-icons/FontAwesome";
import { useFocusEffect } from "expo-router";

import {getPlacesSorted,toggleFavourite,markUsed,PlaceItem,} from "./lib/placesStore";

export default function PlacesPage() {
  const [savedPlacesList, setSavedPlacesList] = useState<PlaceItem[]>([]);

  const refresh = useCallback(async () => {
    const list = await getPlacesSorted();
    setSavedPlacesList(list);
  }, []);

  useFocusEffect(
    useCallback(() => {
      refresh();
    }, [refresh])
  );

  const selectFavPlace = async (placeId: string) => {
    const next = await toggleFavourite(placeId);
    setSavedPlacesList(next);
  };

  const selectPlace = async (placeItem: PlaceItem) => {
    const next = await markUsed(placeItem.id);
    setSavedPlacesList(next);
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
        onPress={() => selectFavPlace(placeItem.id)}
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
    <SafeAreaView style={styles.container}>
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
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0D1B2A",
  },

  listContent: {
    paddingTop: 14,
    paddingHorizontal: 14,
    paddingBottom: 8,
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
