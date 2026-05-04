// app/(tabs)/favourites.tsx

import React, { useCallback, useMemo, useState } from "react";
import {
  StyleSheet,
  Text,
  View,
  Pressable,
  TextInput,
  FlatList,
  useWindowDimensions,
  Alert,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Icon from "react-native-vector-icons/FontAwesome";
import { useFocusEffect, useRouter } from "expo-router";

import HomeHeader from "../HomeHeader";
import {
  getPlacesSorted,
  toggleFavourite,
  markUsed,
  saveCurrentLocation,
  PlaceItem,
  PlaceKind,
} from "../lib/placesStore";

/* ─── TOKENS (same as index.tsx) ──────────────────────────── */

const tokens = {
  bg: "#071a2a",
  tile: "#0b0f14",
  card: "#0d141c",
  text: "#e8eef6",
  muted: "#b8c6d4",
  gold: "#f2a900",
  green: "#2ecc71",
  red: "#e74c3c",
};

/* ─── MAIN COMPONENT ─────────────────────────────────────── */

export default function FavouritesPage() {
  const router = useRouter();
  const { width } = useWindowDimensions();

  const [favourites, setFavourites] = useState<PlaceItem[]>([]);
  const [newName, setNewName] = useState("");
  const [newKind, setNewKind] = useState<PlaceKind>("E");
  const [showAddForm, setShowAddForm] = useState(false);

  const contentWidth = useMemo(() => {
    const padding = 24;
    const max = 720;
    return Math.min(max, Math.max(320, width - padding * 2));
  }, [width]);

  /* Refresh list — only favourited items */
  const refresh = useCallback(async () => {
    const all = await getPlacesSorted();
    setFavourites(all.filter((p) => p.isFav));
  }, []);

  useFocusEffect(
    useCallback(() => {
      refresh();
    }, [refresh])
  );

  /* ── Actions ───────────────────────────────────────────── */

  const handleRemoveFavourite = async (id: string) => {
    await toggleFavourite(id); // toggles isFav off
    refresh();
  };

  const handleNavigate = async (place: PlaceItem) => {
    await markUsed(place.id);
    router.push({
      pathname: "/search",
      params: {
        presetDestination: place.title,
        presetType: place.kind,
      },
    } as any);
  };

  const handleViewOnMap = (place: PlaceItem) => {
    router.push({
      pathname: "/location-map",
      params: {
        label: "FAVOURITE",
        value: place.title,
      },
    } as any);
  };

  const handleAddFavourite = async () => {
    const trimmed = newName.trim();
    if (!trimmed) {
      const msg = "Please enter a location name.";
      Platform.OS === "web"
        ? (globalThis as any).alert?.(msg)
        : Alert.alert("Missing Name", msg);
      return;
    }

    const result = await saveCurrentLocation(trimmed, newKind);

    // Now toggle it to favourite if it isn't already
    if (!result.item.isFav) {
      await toggleFavourite(result.item.id);
    }

    setNewName("");
    setShowAddForm(false);
    refresh();
  };

  /* ── Render item ───────────────────────────────────────── */

  const renderFavItem = ({ item }: { item: PlaceItem }) => (
    <View style={styles.favCard}>
      {/* Kind badge */}
      <View style={styles.kindBadge}>
        <Text style={styles.kindText}>{item.kind}</Text>
      </View>

      {/* Title — tappable to navigate */}
      <Pressable
        onPress={() => handleNavigate(item)}
        style={styles.titleArea}
        accessibilityLabel={`Navigate to ${item.title}`}
      >
        <Text style={styles.favTitle} numberOfLines={1}>
          {item.title}
        </Text>
        <Text style={styles.favSub}>
          {item.kind === "I" ? "Interior" : "Exterior"} · Tap to navigate
        </Text>
      </Pressable>

      {/* Map button */}
      <Pressable
        onPress={() => handleViewOnMap(item)}
        hitSlop={10}
        style={styles.iconBtn}
        accessibilityLabel={`View ${item.title} on map`}
      >
        <Icon name="map" size={16} color={tokens.gold} />
      </Pressable>

      {/* Remove favourite */}
      <Pressable
        onPress={() => handleRemoveFavourite(item.id)}
        hitSlop={10}
        style={styles.iconBtn}
        accessibilityLabel={`Remove ${item.title} from favourites`}
      >
        <Icon name="heart" size={18} color={tokens.red} />
      </Pressable>
    </View>
  );

  /* ── UI ─────────────────────────────────────────────────── */

  return (
    <SafeAreaView style={styles.screen}>
      <View style={[styles.outerContent, { width: contentWidth }]}>
        <HomeHeader
          greeting="Favourites"
          appTitle="WalkBuddy"
          showDivider
          showLocation
        />

        {/* Add‑favourite toggle button */}
        <Pressable
          onPress={() => setShowAddForm((v) => !v)}
          android_ripple={{ color: "#f2a90022" }}
          style={({ pressed }) => [
            styles.addToggleBtn,
            pressed && styles.pressed,
          ]}
        >
          <Icon
            name={showAddForm ? "minus" : "plus"}
            size={16}
            color={tokens.bg}
          />
          <Text style={styles.addToggleText}>
            {showAddForm ? "CANCEL" : "ADD FAVOURITE LOCATION"}
          </Text>
        </Pressable>

        {/* Inline add form */}
        {showAddForm && (
          <View style={styles.addFormCard}>
            <Text style={styles.formLabel}>NEW FAVOURITE</Text>

            <View style={styles.inputRow}>
              <Icon name="map-marker" size={16} color={tokens.muted} />
              <TextInput
                value={newName}
                onChangeText={setNewName}
                placeholder="Location name"
                placeholderTextColor={tokens.muted}
                style={styles.textInput}
                autoCapitalize="words"
                autoCorrect={false}
                returnKeyType="done"
                onSubmitEditing={handleAddFavourite}
              />
            </View>

            {/* Interior / Exterior picker */}
            <View style={styles.kindRow}>
              <Pressable
                onPress={() => setNewKind("I")}
                style={[
                  styles.kindOption,
                  newKind === "I" && styles.kindOptionActive,
                ]}
              >
                <Icon
                  name="building"
                  size={14}
                  color={newKind === "I" ? tokens.bg : tokens.muted}
                />
                <Text
                  style={[
                    styles.kindOptionText,
                    newKind === "I" && styles.kindOptionTextActive,
                  ]}
                >
                  INTERIOR
                </Text>
              </Pressable>

              <Pressable
                onPress={() => setNewKind("E")}
                style={[
                  styles.kindOption,
                  newKind === "E" && styles.kindOptionActive,
                ]}
              >
                <Icon
                  name="globe"
                  size={14}
                  color={newKind === "E" ? tokens.bg : tokens.muted}
                />
                <Text
                  style={[
                    styles.kindOptionText,
                    newKind === "E" && styles.kindOptionTextActive,
                  ]}
                >
                  EXTERIOR
                </Text>
              </Pressable>
            </View>

            <Pressable
              onPress={handleAddFavourite}
              style={({ pressed }) => [
                styles.saveBtn,
                pressed && styles.pressed,
              ]}
            >
              <Icon name="heart" size={14} color={tokens.bg} />
              <Text style={styles.saveBtnText}>SAVE TO FAVOURITES</Text>
            </Pressable>
          </View>
        )}

        {/* Favourites list */}
        <FlatList
          data={favourites}
          keyExtractor={(item) => item.id}
          renderItem={renderFavItem}
          contentContainerStyle={[
            styles.listContent,
            favourites.length === 0 && styles.listContentEmpty,
          ]}
          showsVerticalScrollIndicator={false}
          ListEmptyComponent={
            <View style={styles.emptyWrap}>
              <Icon name="heart-o" size={40} color={tokens.muted} />
              <Text style={styles.emptyTitle}>No Favourites Yet</Text>
              <Text style={styles.emptySub}>
                Tap the button above to add your favourite locations for quick
                access.
              </Text>
            </View>
          }
        />
      </View>
    </SafeAreaView>
  );
}

/* ─── STYLES ──────────────────────────────────────────────── */

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: tokens.bg,
    alignItems: "center",
  },

  outerContent: {
    flex: 1,
    paddingHorizontal: 12,
    paddingTop: 0,
  },

  pressed: {
    opacity: 0.85,
    transform: [{ scale: 0.98 }],
  },

  /* ── Add toggle button ─────────────────────────── */

  addToggleBtn: {
    flexDirection: "row",
    gap: 10,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: tokens.gold,
    borderRadius: 14,
    paddingVertical: 14,
    marginBottom: 14,
  },

  addToggleText: {
    color: tokens.bg,
    fontSize: 14,
    fontWeight: "900",
  },

  /* ── Add form card ─────────────────────────────── */

  addFormCard: {
    backgroundColor: tokens.card,
    borderRadius: 16,
    padding: 16,
    gap: 14,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: tokens.gold,
  },

  formLabel: {
    color: tokens.muted,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1,
  },

  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: tokens.tile,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },

  textInput: {
    flex: 1,
    color: tokens.text,
    fontSize: 15,
    fontWeight: "700",
  },

  kindRow: {
    flexDirection: "row",
    gap: 10,
  },

  kindOption: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    backgroundColor: tokens.tile,
    borderRadius: 12,
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: "transparent",
  },

  kindOptionActive: {
    backgroundColor: tokens.gold,
    borderColor: tokens.gold,
  },

  kindOptionText: {
    color: tokens.muted,
    fontSize: 12,
    fontWeight: "800",
  },

  kindOptionTextActive: {
    color: tokens.bg,
  },

  saveBtn: {
    flexDirection: "row",
    gap: 8,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: tokens.green,
    borderRadius: 12,
    paddingVertical: 14,
  },

  saveBtnText: {
    color: tokens.bg,
    fontSize: 13,
    fontWeight: "900",
  },

  /* ── Favourites list ───────────────────────────── */

  listContent: {
    paddingTop: 4,
    paddingBottom: 120,
    gap: 10,
  },

  listContentEmpty: {
    flexGrow: 1,
    justifyContent: "center",
    alignItems: "center",
  },

  favCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: tokens.tile,
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: 14,
    gap: 10,
    borderWidth: 1,
    borderColor: "#1a2a3a",
  },

  kindBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: tokens.gold,
    alignItems: "center",
    justifyContent: "center",
  },

  kindText: {
    color: tokens.gold,
    fontWeight: "900",
    fontSize: 12,
  },

  titleArea: {
    flex: 1,
    gap: 2,
  },

  favTitle: {
    color: tokens.text,
    fontSize: 14,
    fontWeight: "800",
  },

  favSub: {
    color: tokens.muted,
    fontSize: 11,
    fontWeight: "600",
  },

  iconBtn: {
    paddingHorizontal: 6,
    paddingVertical: 4,
  },

  /* ── Empty state ───────────────────────────────── */

  emptyWrap: {
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 30,
    paddingTop: 60,
  },

  emptyTitle: {
    color: tokens.text,
    fontSize: 18,
    fontWeight: "900",
  },

  emptySub: {
    color: tokens.muted,
    fontSize: 13,
    fontWeight: "600",
    textAlign: "center",
    lineHeight: 20,
  },
});
