import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useState, useEffect, useCallback } from "react";
import { useFocusEffect } from "@react-navigation/native";
import React from "react";
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
import { getHistory, removeFromHistory, clearHistory, AudiobookItem } from "@/src/utils/audiobookStorage";
import { Radius, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";
import { BackButton } from "@/components/ui/BackButton";

export default function AudiobooksHistoryScreen() {
  const colors = useThemeColors();
  const [history, setHistory] = useState<AudiobookItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadHistory = async () => {
    try {
      setLoading(true);
      const hist = await getHistory();
      setHistory(hist);
    } catch (error) {
      console.error("Failed to load history:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  // Refresh when screen comes into focus
  useFocusEffect(
    useCallback(() => {
      loadHistory();
    }, [])
  );

  const handleRemoveFromHistory = async (bookId: string) => {
    try {
      await removeFromHistory(bookId);
      await loadHistory();
    } catch (error) {
      console.error("Failed to remove from history:", error);
      Alert.alert("Error", "Failed to remove from history. Please try again.");
    }
  };

  const handleClearHistory = () => {
    Alert.alert(
      "Clear History",
      "Are you sure you want to clear all listening history?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Clear",
          style: "destructive",
          onPress: async () => {
            try {
              await clearHistory();
              await loadHistory();
            } catch (error) {
              console.error("Failed to clear history:", error);
              Alert.alert("Error", "Failed to clear history. Please try again.");
            }
          },
        },
      ]
    );
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

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return "Today";
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays} days ago`;
    return date.toLocaleDateString();
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
          <Text style={[styles.bookDate, { color: colors.textMuted }]}>{formatDate(item.addedAt)}</Text>
        </View>
      </View>
      <View style={styles.bookActions}>
        <Pressable
          onPress={(e) => {
            e.stopPropagation();
            handleRemoveFromHistory(item.id);
          }}
          style={styles.actionButton}
          hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        >
          <Ionicons name="trash-outline" size={22} color={colors.textMuted} />
        </Pressable>
        <Ionicons name="play-circle" size={32} color={colors.accent} />
      </View>
    </Pressable>
  );

  return (
    <SafeAreaView style={[styles.root, { backgroundColor: colors.background }]} edges={["top"]}>
      <View style={[styles.headerRow, { borderBottomColor: colors.accent }]}>
        <BackButton />
        <Text style={[styles.headerText, { color: colors.text }]}>HISTORY</Text>
        {history.length > 0 && (
          <Pressable onPress={handleClearHistory} style={styles.iconBtn}>
            <Ionicons name="trash-outline" size={24} color={colors.danger} />
          </Pressable>
        )}
      </View>
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : history.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Ionicons name="time-outline" size={64} color={colors.textMuted} />
          <Text style={[styles.emptyText, { color: colors.text }]}>No listening history</Text>
          <Text style={[styles.emptySubtext, { color: colors.textMuted }]}>
            Books you listen to will appear here
          </Text>
        </View>
      ) : (
        <FlatList
          data={history}
          keyExtractor={(item) => item.id}
          renderItem={renderBookItem}
          contentContainerStyle={{ paddingBottom: 24 }}
          ListHeaderComponent={
            <Text style={[styles.countText, { color: colors.textMuted }]}>
              {history.length} {history.length === 1 ? "book" : "books"} in history
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
    position: "relative",
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
    paddingLeft: 52,
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
  bookDate: {
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
