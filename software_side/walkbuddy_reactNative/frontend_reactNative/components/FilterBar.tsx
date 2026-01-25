import React from "react";
import { View, Text, Pressable, StyleSheet, ScrollView } from "react-native";
import { Ionicons } from "@expo/vector-icons";

export interface FilterOptions {
  languages: string[];
  genres: string[];
  durationBuckets: string[];
  sortOptions: string[];
}

export interface ActiveFilters {
  language?: string;
  genre?: string;
  duration?: string; // e.g., "<1h", "1-3h", etc.
  sort?: string;
}

interface FilterBarProps {
  filterOptions: FilterOptions | null;
  activeFilters: ActiveFilters;
  onFilterPress: (filterType: "language" | "genre" | "duration" | "sort" | "more") => void;
  onClearFilters: () => void;
  onSearch?: () => void;
  loading?: boolean;
}

export default function FilterBar({
  filterOptions,
  activeFilters,
  onFilterPress,
  onClearFilters,
  onSearch,
  loading = false,
}: FilterBarProps) {
  const activeCount = Object.values(activeFilters).filter((v) => v !== undefined && v !== "").length;

  const getFilterLabel = (type: keyof ActiveFilters): string => {
    const value = activeFilters[type];
    if (!value) {
      switch (type) {
        case "language":
          return "Language";
        case "genre":
          return "Genre";
        case "duration":
          return "Duration";
        case "sort":
          return "Sort";
        default:
          return "";
      }
    }
    return value;
  };

  const getFilterIcon = (type: keyof ActiveFilters): string => {
    switch (type) {
      case "language":
        return "language-outline";
      case "genre":
        return "book-outline";
      case "duration":
        return "time-outline";
      case "sort":
        return "swap-vertical-outline";
      default:
        return "ellipse-outline";
    }
  };

  if (loading) {
    return (
      <View style={styles.container}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
          {[1, 2, 3, 4].map((i) => (
            <View key={i} style={[styles.chip, styles.chipLoading]} />
          ))}
        </ScrollView>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        <Pressable
          style={[styles.chip, activeFilters.language && styles.chipActive]}
          onPress={() => onFilterPress("language")}
          accessibilityRole="button"
          accessibilityLabel={`Filter by language${activeFilters.language ? `: ${activeFilters.language}` : ""}`}
        >
          <Ionicons name={getFilterIcon("language")} size={16} color={activeFilters.language ? "#F9A826" : "#888"} />
          <Text style={[styles.chipText, activeFilters.language && styles.chipTextActive]}>
            {getFilterLabel("language")}
          </Text>
          {activeFilters.language && <View style={styles.chipBadge} />}
        </Pressable>

        <Pressable
          style={[styles.chip, activeFilters.genre && styles.chipActive]}
          onPress={() => onFilterPress("genre")}
          accessibilityRole="button"
          accessibilityLabel={`Filter by genre${activeFilters.genre ? `: ${activeFilters.genre}` : ""}`}
        >
          <Ionicons name={getFilterIcon("genre")} size={16} color={activeFilters.genre ? "#F9A826" : "#888"} />
          <Text style={[styles.chipText, activeFilters.genre && styles.chipTextActive]}>
            {getFilterLabel("genre")}
          </Text>
          {activeFilters.genre && <View style={styles.chipBadge} />}
        </Pressable>

        <Pressable
          style={[styles.chip, activeFilters.duration && styles.chipActive]}
          onPress={() => onFilterPress("duration")}
          accessibilityRole="button"
          accessibilityLabel={`Filter by duration${activeFilters.duration ? `: ${activeFilters.duration}` : ""}`}
        >
          <Ionicons name={getFilterIcon("duration")} size={16} color={activeFilters.duration ? "#F9A826" : "#888"} />
          <Text style={[styles.chipText, activeFilters.duration && styles.chipTextActive]}>
            {getFilterLabel("duration")}
          </Text>
          {activeFilters.duration && <View style={styles.chipBadge} />}
        </Pressable>

        <Pressable
          style={[styles.chip, activeFilters.sort && styles.chipActive]}
          onPress={() => onFilterPress("sort")}
          accessibilityRole="button"
          accessibilityLabel={`Sort by${activeFilters.sort ? `: ${activeFilters.sort}` : ""}`}
        >
          <Ionicons name={getFilterIcon("sort")} size={16} color={activeFilters.sort ? "#F9A826" : "#888"} />
          <Text style={[styles.chipText, activeFilters.sort && styles.chipTextActive]}>
            {getFilterLabel("sort")}
          </Text>
          {activeFilters.sort && <View style={styles.chipBadge} />}
        </Pressable>

        {activeCount > 0 && (
          <>
            {onSearch && (
              <Pressable
                style={styles.searchButton}
                onPress={onSearch}
                accessibilityRole="button"
                accessibilityLabel="Search with filters"
              >
                <Ionicons name="search" size={18} color="#F9A826" />
                <Text style={styles.searchButtonText}>Search</Text>
              </Pressable>
            )}
            <Pressable
              style={styles.clearButton}
              onPress={onClearFilters}
              accessibilityRole="button"
              accessibilityLabel={`Clear ${activeCount} active filter${activeCount > 1 ? "s" : ""}`}
            >
              <Ionicons name="close-circle" size={16} color="#FF6B6B" />
              <Text style={styles.clearButtonText}>Clear ({activeCount})</Text>
            </Pressable>
          </>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#1B263B",
    borderBottomWidth: 1,
    borderBottomColor: "#2A2A2A",
    paddingVertical: 8,
  },
  scrollContent: {
    paddingHorizontal: 16,
    gap: 8,
    alignItems: "center",
  },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: "#2A2A2A",
    borderWidth: 1,
    borderColor: "#3A3A3A",
    gap: 6,
    minWidth: 80,
    justifyContent: "center",
    position: "relative",
  },
  chipActive: {
    backgroundColor: "#3A3A3A",
    borderColor: "#F9A826",
  },
  chipLoading: {
    width: 100,
    opacity: 0.5,
  },
  chipText: {
    color: "#AAA",
    fontSize: 13,
    fontWeight: "500",
  },
  chipTextActive: {
    color: "#F9A826",
    fontWeight: "600",
  },
  chipBadge: {
    position: "absolute",
    top: -2,
    right: -2,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#F9A826",
  },
  searchButton: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: "#3A2F1F",
    borderWidth: 1.5,
    borderColor: "#F9A826",
    gap: 6,
  },
  searchButtonText: {
    color: "#F9A826",
    fontSize: 13,
    fontWeight: "700",
  },
  clearButton: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: "#2A1F1F",
    borderWidth: 1,
    borderColor: "#3A2F2F",
    gap: 6,
  },
  clearButtonText: {
    color: "#FF6B6B",
    fontSize: 13,
    fontWeight: "600",
  },
});
