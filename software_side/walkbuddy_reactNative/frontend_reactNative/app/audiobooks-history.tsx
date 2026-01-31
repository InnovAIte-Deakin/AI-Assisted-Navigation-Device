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

export default function AudiobooksHistoryScreen() {
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
      style={styles.bookCard}
      onPress={() => handleBookPress(item)}
      accessibilityRole="button"
      accessibilityLabel={`Play ${item.title} by ${item.author}`}
    >
      {item.cover_url ? (
        <Image source={{ uri: item.cover_url }} style={styles.coverImage} />
      ) : (
        <View style={styles.coverPlaceholder}>
          <Ionicons name="book" size={40} color="#888" />
        </View>
      )}
      <View style={styles.bookInfo}>
        <Text style={styles.bookTitle} numberOfLines={2}>
          {item.title}
        </Text>
        <Text style={styles.bookAuthor} numberOfLines={1}>
          {item.author}
        </Text>
        <View style={styles.bookMeta}>
          <Text style={styles.bookDuration}>{item.duration_formatted}</Text>
          <Text style={styles.bookDate}>{formatDate(item.addedAt)}</Text>
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
          <Ionicons name="trash-outline" size={22} color="#888" />
        </Pressable>
        <Ionicons name="play-circle" size={32} color="#F9A826" />
      </View>
    </Pressable>
  );

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.headerRow}>
        <Pressable onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="arrow-back" size={24} color="#FFF" />
        </Pressable>
        <Text style={styles.headerText}>HISTORY</Text>
        {history.length > 0 && (
          <Pressable onPress={handleClearHistory} style={styles.iconBtn}>
            <Ionicons name="trash-outline" size={24} color="#FF6B6B" />
          </Pressable>
        )}
      </View>
      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#F9A826" />
        </View>
      ) : history.length === 0 ? (
        <View style={styles.emptyContainer}>
          <Ionicons name="time-outline" size={64} color="#666" />
          <Text style={styles.emptyText}>No listening history</Text>
          <Text style={styles.emptySubtext}>
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
            <Text style={styles.countText}>
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
    backgroundColor: "#1B263B",
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingTop: 6,
    paddingBottom: 10,
    borderBottomWidth: 1.25,
    borderBottomColor: "#F9A826",
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
    color: "#ffffffff",
    fontSize: 22,
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
    color: "#FFF",
    fontSize: 20,
    fontWeight: "600",
    marginTop: 16,
  },
  emptySubtext: {
    color: "#AAA",
    fontSize: 14,
    marginTop: 8,
    textAlign: "center",
  },
  countText: {
    color: "#AAA",
    fontSize: 14,
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
    backgroundColor: "#2A2A2A",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#3A3A3A",
  },
  coverImage: {
    width: 60,
    height: 60,
    borderRadius: 8,
    backgroundColor: "#1A1A1A",
  },
  coverPlaceholder: {
    width: 60,
    height: 60,
    borderRadius: 8,
    backgroundColor: "#1A1A1A",
    alignItems: "center",
    justifyContent: "center",
  },
  bookInfo: {
    flex: 1,
    marginLeft: 12,
    marginRight: 8,
  },
  bookTitle: {
    color: "#FFF",
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 4,
  },
  bookAuthor: {
    color: "#AAA",
    fontSize: 14,
    marginBottom: 4,
  },
  bookMeta: {
    flexDirection: "row",
    gap: 12,
  },
  bookDuration: {
    color: "#888",
    fontSize: 12,
  },
  bookDate: {
    color: "#888",
    fontSize: 12,
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
