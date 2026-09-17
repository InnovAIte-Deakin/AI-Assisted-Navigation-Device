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
import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";

import HomeHeader from "../HomeHeader";
import {
  getPlacesSorted,
  toggleFavourite,
  markUsed,
  saveCurrentLocation,
  PlaceItem,
  PlaceKind,
} from "../../src/utils/placesStore";
import { Radius, Spacing, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";

/* ─── MAIN COMPONENT ─────────────────────────────────────── */

export default function FavouritesPage() {
  const colors = useThemeColors();
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
    <View style={[styles.favCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
      {/* Kind badge */}
      <View style={[styles.kindBadge, { borderColor: colors.accent }]}>
        <Text style={[styles.kindText, { color: colors.accent }]}>{item.kind}</Text>
      </View>

      {/* Title — tappable to navigate */}
      <Pressable
        onPress={() => handleNavigate(item)}
        style={styles.titleArea}
        accessibilityLabel={`Navigate to ${item.title}`}
      >
        <Text style={[styles.favTitle, { color: colors.text }]} numberOfLines={1}>
          {item.title}
        </Text>
        <Text style={[styles.favSub, { color: colors.textMuted }]}>
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
        <Ionicons name="map-outline" size={16} color={colors.accent} />
      </Pressable>

      {/* Remove favourite */}
      <Pressable
        onPress={() => handleRemoveFavourite(item.id)}
        hitSlop={10}
        style={styles.iconBtn}
        accessibilityLabel={`Remove ${item.title} from favourites`}
      >
        <Ionicons name="heart" size={18} color={colors.danger} />
      </Pressable>
    </View>
  );

  /* ── UI ─────────────────────────────────────────────────── */

  return (
    <View style={[styles.screen, { backgroundColor: colors.background }]}>
      <View style={[styles.outerContent, { width: contentWidth }]}>
        <HomeHeader
          appTitle="WalkBuddy"
          showDivider
          showLocation
          showBackButton
        />

        {/* Add‑favourite toggle button */}
        <Pressable
          onPress={() => setShowAddForm((v) => !v)}
          android_ripple={{ color: colors.accent + "22" }}
          style={({ pressed }) => [
            styles.addToggleBtn,
            { backgroundColor: colors.accent },
            pressed && styles.pressed,
          ]}
        >
          <Ionicons
            name={showAddForm ? "remove-outline" : "add-outline"}
            size={16}
            color={colors.background}
          />
          <Text style={[styles.addToggleText, { color: colors.background }]}>
            {showAddForm ? "CANCEL" : "ADD FAVOURITE LOCATION"}
          </Text>
        </Pressable>

        {/* Inline add form */}
        {showAddForm && (
          <View style={[styles.addFormCard, { backgroundColor: colors.surfaceElevated, borderColor: colors.accent }]}>
            <Text style={[styles.formLabel, { color: colors.textMuted }]}>NEW FAVOURITE</Text>

            <View style={[styles.inputRow, { backgroundColor: colors.surface }]}>
              <Ionicons name="location-outline" size={16} color={colors.textMuted} />
              <TextInput
                value={newName}
                onChangeText={setNewName}
                placeholder="Location name"
                placeholderTextColor={colors.textMuted}
                style={[styles.textInput, { color: colors.text }]}
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
                  { backgroundColor: colors.surface, borderColor: "transparent" },
                  newKind === "I" && { backgroundColor: colors.accent, borderColor: colors.accent },
                ]}
              >
                <Ionicons
                  name="business-outline"
                  size={14}
                  color={newKind === "I" ? colors.background : colors.textMuted}
                />
                <Text
                  style={[
                    styles.kindOptionText,
                    { color: colors.textMuted },
                    newKind === "I" && { color: colors.background },
                  ]}
                >
                  INTERIOR
                </Text>
              </Pressable>

              <Pressable
                onPress={() => setNewKind("E")}
                style={[
                  styles.kindOption,
                  { backgroundColor: colors.surface, borderColor: "transparent" },
                  newKind === "E" && { backgroundColor: colors.accent, borderColor: colors.accent },
                ]}
              >
                <Ionicons
                  name="globe-outline"
                  size={14}
                  color={newKind === "E" ? colors.background : colors.textMuted}
                />
                <Text
                  style={[
                    styles.kindOptionText,
                    { color: colors.textMuted },
                    newKind === "E" && { color: colors.background },
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
                { backgroundColor: colors.success },
                pressed && styles.pressed,
              ]}
            >
              <Ionicons name="heart" size={14} color={colors.background} />
              <Text style={[styles.saveBtnText, { color: colors.background }]}>SAVE TO FAVOURITES</Text>
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
              <Ionicons name="heart-outline" size={40} color={colors.textMuted} />
              <Text style={[styles.emptyTitle, { color: colors.text }]}>No Favourites Yet</Text>
              <Text style={[styles.emptySub, { color: colors.textMuted }]}>
                Tap the button above to add your favourite locations for quick
                access.
              </Text>
            </View>
          }
        />
      </View>
    </View>
  );
}

/* ─── STYLES — structural only; colors applied inline so they react to
   light/dark via useThemeColors(). ──────────────────────────────── */

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    alignItems: "center",
  },

  outerContent: {
    flex: 1,
    paddingHorizontal: Spacing.md,
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
    borderRadius: 14,
    paddingVertical: Spacing.md + 2,
    marginBottom: Spacing.md + 2,
  },

  addToggleText: {
    fontSize: Typography.size.sm,
    fontWeight: "900",
  },

  /* ── Add form card ─────────────────────────────── */

  addFormCard: {
    borderRadius: Radius.lg,
    padding: Spacing.md + 4,
    gap: Spacing.md + 2,
    marginBottom: Spacing.md + 2,
    borderWidth: 1,
  },

  formLabel: {
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1,
  },

  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    borderRadius: Radius.md,
    paddingHorizontal: Spacing.md + 2,
    paddingVertical: Spacing.md,
  },

  textInput: {
    flex: 1,
    fontSize: Typography.size.sm,
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
    gap: Spacing.sm,
    borderRadius: Radius.md,
    paddingVertical: Spacing.md,
    borderWidth: 1,
  },

  kindOptionText: {
    fontSize: 12,
    fontWeight: "800",
  },

  saveBtn: {
    flexDirection: "row",
    gap: Spacing.sm,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: Radius.md,
    paddingVertical: Spacing.md + 2,
  },

  saveBtnText: {
    fontSize: 13,
    fontWeight: "900",
  },

  /* ── Favourites list ───────────────────────────── */

  listContent: {
    paddingTop: 4,
    paddingBottom: 120,
    gap: Spacing.sm + 2,
  },

  listContentEmpty: {
    flexGrow: 1,
    justifyContent: "center",
    alignItems: "center",
  },

  favCard: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: Radius.lg,
    paddingVertical: Spacing.md + 2,
    paddingHorizontal: Spacing.md + 2,
    gap: 10,
    borderWidth: 1,
  },

  kindBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 2,
    alignItems: "center",
    justifyContent: "center",
  },

  kindText: {
    fontWeight: "900",
    fontSize: 12,
  },

  titleArea: {
    flex: 1,
    gap: 2,
  },

  favTitle: {
    fontSize: Typography.size.sm,
    fontWeight: "800",
  },

  favSub: {
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
    gap: Spacing.md,
    paddingHorizontal: 30,
    paddingTop: 60,
  },

  emptyTitle: {
    fontSize: Typography.size.md,
    fontWeight: "900",
  },

  emptySub: {
    fontSize: Typography.size.sm,
    fontWeight: "600",
    textAlign: "center",
    lineHeight: 20,
  },
});
