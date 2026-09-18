import React from "react";
import { View, Text, Pressable, StyleSheet, ScrollView } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { Radius, Spacing, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";

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
  const colors = useThemeColors();
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
      <View style={[styles.container, { backgroundColor: colors.surface, borderBottomColor: colors.border }]}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
          {[1, 2, 3, 4].map((i) => (
            <View key={i} style={[styles.chip, { backgroundColor: colors.surfaceElevated, borderColor: colors.border }, styles.chipLoading]} />
          ))}
        </ScrollView>
      </View>
    );
  }

  return (
    <View style={[styles.container, { backgroundColor: colors.surface, borderBottomColor: colors.border }]}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        <Pressable
          style={[
            styles.chip,
            { backgroundColor: colors.surfaceElevated, borderColor: colors.border },
            activeFilters.language && { backgroundColor: colors.surfaceElevated, borderColor: colors.accent },
          ]}
          onPress={() => onFilterPress("language")}
          accessibilityRole="button"
          accessibilityLabel={`Filter by language${activeFilters.language ? `: ${activeFilters.language}` : ""}`}
        >
          <Ionicons name={getFilterIcon("language") as any} size={16} color={activeFilters.language ? colors.accent : colors.textMuted} />
          <Text style={[styles.chipText, { color: colors.textMuted }, activeFilters.language && { color: colors.accent, fontWeight: "600" }]}>
            {getFilterLabel("language")}
          </Text>
          {activeFilters.language && <View style={[styles.chipBadge, { backgroundColor: colors.accent }]} />}
        </Pressable>

        <Pressable
          style={[
            styles.chip,
            { backgroundColor: colors.surfaceElevated, borderColor: colors.border },
            activeFilters.genre && { backgroundColor: colors.surfaceElevated, borderColor: colors.accent },
          ]}
          onPress={() => onFilterPress("genre")}
          accessibilityRole="button"
          accessibilityLabel={`Filter by genre${activeFilters.genre ? `: ${activeFilters.genre}` : ""}`}
        >
          <Ionicons name={getFilterIcon("genre") as any} size={16} color={activeFilters.genre ? colors.accent : colors.textMuted} />
          <Text style={[styles.chipText, { color: colors.textMuted }, activeFilters.genre && { color: colors.accent, fontWeight: "600" }]}>
            {getFilterLabel("genre")}
          </Text>
          {activeFilters.genre && <View style={[styles.chipBadge, { backgroundColor: colors.accent }]} />}
        </Pressable>

        <Pressable
          style={[
            styles.chip,
            { backgroundColor: colors.surfaceElevated, borderColor: colors.border },
            activeFilters.duration && { backgroundColor: colors.surfaceElevated, borderColor: colors.accent },
          ]}
          onPress={() => onFilterPress("duration")}
          accessibilityRole="button"
          accessibilityLabel={`Filter by duration${activeFilters.duration ? `: ${activeFilters.duration}` : ""}`}
        >
          <Ionicons name={getFilterIcon("duration") as any} size={16} color={activeFilters.duration ? colors.accent : colors.textMuted} />
          <Text style={[styles.chipText, { color: colors.textMuted }, activeFilters.duration && { color: colors.accent, fontWeight: "600" }]}>
            {getFilterLabel("duration")}
          </Text>
          {activeFilters.duration && <View style={[styles.chipBadge, { backgroundColor: colors.accent }]} />}
        </Pressable>

        <Pressable
          style={[
            styles.chip,
            { backgroundColor: colors.surfaceElevated, borderColor: colors.border },
            activeFilters.sort && { backgroundColor: colors.surfaceElevated, borderColor: colors.accent },
          ]}
          onPress={() => onFilterPress("sort")}
          accessibilityRole="button"
          accessibilityLabel={`Sort by${activeFilters.sort ? `: ${activeFilters.sort}` : ""}`}
        >
          <Ionicons name={getFilterIcon("sort") as any} size={16} color={activeFilters.sort ? colors.accent : colors.textMuted} />
          <Text style={[styles.chipText, { color: colors.textMuted }, activeFilters.sort && { color: colors.accent, fontWeight: "600" }]}>
            {getFilterLabel("sort")}
          </Text>
          {activeFilters.sort && <View style={[styles.chipBadge, { backgroundColor: colors.accent }]} />}
        </Pressable>

        {activeCount > 0 && (
          <>
            {onSearch && (
              <Pressable
                style={[styles.searchButton, { backgroundColor: colors.accent + "26", borderColor: colors.accent }]}
                onPress={onSearch}
                accessibilityRole="button"
                accessibilityLabel="Search with filters"
              >
                <Ionicons name="search" size={18} color={colors.accent} />
                <Text style={[styles.searchButtonText, { color: colors.accent }]}>Search</Text>
              </Pressable>
            )}
            <Pressable
              style={[styles.clearButton, { backgroundColor: colors.danger + "1F", borderColor: colors.danger + "40" }]}
              onPress={onClearFilters}
              accessibilityRole="button"
              accessibilityLabel={`Clear ${activeCount} active filter${activeCount > 1 ? "s" : ""}`}
            >
              <Ionicons name="close-circle" size={16} color={colors.danger} />
              <Text style={[styles.clearButtonText, { color: colors.danger }]}>Clear ({activeCount})</Text>
            </Pressable>
          </>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderBottomWidth: 1,
    paddingVertical: Spacing.sm,
  },
  scrollContent: {
    paddingHorizontal: Spacing.lg,
    gap: Spacing.sm,
    alignItems: "center",
  },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: Spacing.md,
    paddingVertical: 6,
    borderRadius: Radius.md + 4,
    borderWidth: 1,
    gap: 6,
    minWidth: 80,
    justifyContent: "center",
    position: "relative",
  },
  chipLoading: {
    width: 100,
    opacity: 0.5,
  },
  chipText: {
    fontSize: Typography.size.sm,
    fontWeight: "500",
  },
  chipBadge: {
    position: "absolute",
    top: -2,
    right: -2,
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  searchButton: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: Radius.md + 4,
    borderWidth: 1.5,
    gap: 6,
  },
  searchButtonText: {
    fontSize: Typography.size.sm,
    fontWeight: "700",
  },
  clearButton: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: Spacing.md,
    paddingVertical: 6,
    borderRadius: Radius.md + 4,
    borderWidth: 1,
    gap: 6,
  },
  clearButtonText: {
    fontSize: Typography.size.sm,
    fontWeight: "600",
  },
});
