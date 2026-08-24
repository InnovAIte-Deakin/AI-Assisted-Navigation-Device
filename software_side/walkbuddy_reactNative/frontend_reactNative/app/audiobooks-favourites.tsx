import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useState, useEffect, useCallback } from "react";
import { useFocusEffect } from "@react-navigation/native";
import {
  ActivityIndicator,
  FlatList,
  Image,
  Pressable,
  StyleSheet,
  Text,
  View,
  Alert,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { getFavorites, removeFavorite, AudiobookItem } from "@/src/utils/audiobookStorage";
import { Radius, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";

export default function AudiobooksFavouritesScreen() {
  const colors = useThemeColors();
  const [favorites, setFavorites] = useState<AudiobookItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadFavorites = async () => {
    try {
      setLoading(true);
      const favs = await getFavorites();
      setFavorites(favs);
    } catch (error) {
      console.error("Failed to load favorites:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFavorites();
  }, []);

  // Refresh when screen comes into focus
  useFocusEffect(
    useCallback(() => {
      loadFavorites();
    }, [])
  );

  const handleRemoveFavorite = async (bookId: string) => {
    try {
      await removeFavorite(bookId);
      await loadFavorites();
    } catch (error) {
      console.error("Failed to remove favorite:", error);
      Alert.alert("Error", "Failed to remove favorite. Please try again.");
    }
  };

  const handleBookPress = (book: AudiobookItem) => {
    router.push({
      pathname: "/audiobooks-player",
      params: {
        bookId: book.id,
        title: book.title,
        author: book.author,
        coverUrl: book.cover_url || "",
      },
    });
  };

  const renderBookItem = ({ item }: { item: AudiobookItem }) => (
    <Pressable
      style={[styles.bookCard, { backgroundColor: colors.surface, borderColor: colors.border }]}
      onPress={() => handleBookPress(item)}
      accessibilityRole="button"
      accessibilityLabel={`Play ${item.title} by ${item.author}`}
    >
      {item.cover_url ? (
        <Image source={{ uri: item.cover_url }} style={[styles.coverImage, { backgroundColor: colors.background }]} />
      ) : (
        <View style={[styles.coverPlaceholder, { backgroundColor: colors.background }]}>
          <Ionicons name="book" size={40} color={colors.textMuted} />
        </View>
      )}
      <View style={styles.bookInfo}>
        <Text style={[styles.bookTitle, { color: colors.text }]} numberOfLines={2}>
          {item.title}
        </Text>
        <Text style={[styles.bookAuthor, { color: colors.textMuted }]} numberOfLines={1}>
          {item.author}
        </Text>
        <View style={styles.bookMeta}>
          <Text style={[styles.bookDuration, { color: colors.textMuted }]}>{item.duration_formatted}</Text>
          <Text style={[styles.bookLanguage, { color: colors.textMuted }]}>{item.language}</Text>
        </View>
      </View>
      <View style={styles.bookActions}>
        <Pressable
          onPress={(e) => {
            e.stopPropagation();
            handleRemoveFavorite(item.id);
          }}
          style={styles.actionButton}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        >
          <Ionicons name="heart" size={24} color={colors.danger} />
        </Pressable>
        <Ionicons name="play-circle" size={32} color={colors.accent} />
      </View>
    </Pressable>
  );

  return (
    <SafeAreaView style={[styles.root, { backgroundColor: colors.background }]} edges={["top"]}>
      <View style={[styles.headerRow, { borderBottomColor: colors.accent }]}>
        <Pressable onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="arrow-back" size={24} color={colors.text} />
        </Pressable>
        <Text style={[styles.headerText, { color: colors.text }]}>FAVOURITES</Text>
        <View style={styles.iconBtn} />
      </View>
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : favorites.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Ionicons name="heart-outline" size={64} color={colors.textMuted} />
          <Text style={[styles.emptyText, { color: colors.text }]}>No favorites yet</Text>
          <Text style={[styles.emptySubtext, { color: colors.textMuted }]}>
            Tap the heart icon on any book to add it to favorites
          </Text>
        </View>
      ) : (
        <FlatList
          data={favorites}
          keyExtractor={(item) => item.id}
          renderItem={renderBookItem}
          contentContainerStyle={{ paddingBottom: 24 }}
          ListHeaderComponent={
            <Text style={[styles.countText, { color: colors.textMuted }]}>
              {favorites.length} {favorites.length === 1 ? "favorite" : "favorites"}
            </Text>
          }
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingTop: 6,
    paddingBottom: 10,
    borderBottomWidth: 1.25,
  },
  iconBtn: {
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 8,
  },
  headerText: {
    flex: 1,
    fontSize: Typography.size.xl,
    fontWeight: "800",
    letterSpacing: 1.1,
    textAlign: "center",
  },
  loadingContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  emptyContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 32,
  },
  emptyText: {
    fontSize: Typography.size.lg,
    fontWeight: "600",
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: Typography.size.sm,
    marginTop: 8,
    textAlign: "center",
  },
  countText: {
    fontSize: Typography.size.sm,
    marginHorizontal: 16,
    marginTop: 12,
    marginBottom: 8,
  },
  bookCard: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: 16,
    marginTop: 12,
    padding: 12,
    borderRadius: Radius.md,
    borderWidth: 1,
  },
  coverImage: {
    width: 60,
    height: 60,
    borderRadius: Radius.sm,
  },
  coverPlaceholder: {
    width: 60,
    height: 60,
    borderRadius: Radius.sm,
    alignItems: "center",
    justifyContent: "center",
  },
  bookInfo: {
    flex: 1,
    marginLeft: 12,
    marginRight: 8,
  },
  bookTitle: {
    fontSize: Typography.size.base,
    fontWeight: "600",
    marginBottom: 4,
  },
  bookAuthor: {
    fontSize: Typography.size.sm,
    marginBottom: 4,
  },
  bookMeta: {
    flexDirection: "row",
    gap: 12,
  },
  bookDuration: {
    fontSize: Typography.size.xs,
  },
  bookLanguage: {
    fontSize: Typography.size.xs,
  },
  bookActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  actionButton: {
    padding: 4,
  },
});
