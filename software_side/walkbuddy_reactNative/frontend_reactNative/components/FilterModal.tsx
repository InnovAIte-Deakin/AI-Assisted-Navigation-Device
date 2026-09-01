import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  Pressable,
  StyleSheet,
  Modal,
  TextInput,
  FlatList,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { SafeAreaView } from "react-native-safe-area-context";
import { FilterOptions, ActiveFilters } from "./FilterBar";
import { Radius, Spacing, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";

interface FilterModalProps {
  visible: boolean;
  filterType: "language" | "genre" | "duration" | "sort" | null;
  filterOptions: FilterOptions | null;
  activeFilters: ActiveFilters;
  onSelect: (filterType: string, value: string | undefined) => void;
  onClose: () => void;
}

export default function FilterModal({
  visible,
  filterType,
  filterOptions,
  activeFilters,
  onSelect,
  onClose,
}: FilterModalProps) {
  const colors = useThemeColors();
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    if (!visible) {
      setSearchQuery("");
    }
  }, [visible]);

  // Debug logging
  useEffect(() => {
    if (visible) {
      console.log(`[FilterModal] Modal visible: ${visible}, filterType: ${filterType}, filterOptions:`, filterOptions);
    }
  }, [visible, filterType, filterOptions]);

  if (!filterType) {
    return null;
  }

  // If filterOptions is null, show a loading state or default options
  if (!filterOptions) {
    return (
      <Modal
        visible={visible}
        animationType="slide"
        transparent={true}
        onRequestClose={onClose}
        accessibilityViewIsModal={true}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : "height"}
          style={styles.modalContainer}
        >
          <Pressable style={styles.backdrop} onPress={onClose} />
          <View style={[styles.modalContent, { backgroundColor: colors.surface }]}>
            <SafeAreaView edges={["bottom"]} style={styles.safeArea}>
              <View style={[styles.header, { borderBottomColor: colors.border }]}>
                <Text style={[styles.headerTitle, { color: colors.text }]}>Loading filters...</Text>
                <Pressable
                  onPress={onClose}
                  style={styles.closeButton}
                  accessibilityRole="button"
                  accessibilityLabel="Close filter"
                >
                  <Ionicons name="close" size={24} color={colors.text} />
                </Pressable>
              </View>
              <View style={styles.emptyContainer}>
                <Text style={[styles.emptyText, { color: colors.textMuted }]}>Please wait while filters are loading...</Text>
              </View>
            </SafeAreaView>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    );
  }

  const getOptions = (): string[] => {
    switch (filterType) {
      case "language":
        return filterOptions.languages;
      case "genre":
        return filterOptions.genres;
      case "duration":
        return filterOptions.durationBuckets;
      case "sort":
        return filterOptions.sortOptions;
      default:
        return [];
    }
  };

  const getTitle = (): string => {
    switch (filterType) {
      case "language":
        return "Select Language";
      case "genre":
        return "Select Genre";
      case "duration":
        return "Select Duration";
      case "sort":
        return "Sort By";
      default:
        return "Filter";
    }
  };

  const getCurrentValue = (): string | undefined => {
    return activeFilters[filterType];
  };

  const options = getOptions();
  const filteredOptions = searchQuery
    ? options.filter((opt) => opt.toLowerCase().includes(searchQuery.toLowerCase()))
    : options;

  const handleSelect = (value: string) => {
    const currentValue = getCurrentValue();
    // Toggle: if same value selected, deselect it
    const newValue = currentValue === value ? undefined : value;
    onSelect(filterType, newValue);
    onClose();
  };

  const getSortLabel = (sortValue: string): string => {
    const labels: Record<string, string> = {
      relevance: "Relevance",
      popular: "Most Popular",
      newest: "Newest First",
      longest: "Longest First",
      title_az: "Title (A-Z)",
      author_az: "Author (A-Z)",
    };
    return labels[sortValue] || sortValue;
  };

  const getDurationLabel = (durationValue: string): string => {
    const labels: Record<string, string> = {
      "<1h": "Less than 1 hour",
      "1-3h": "1 to 3 hours",
      "3-10h": "3 to 10 hours",
      "10h+": "More than 10 hours",
    };
    return labels[durationValue] || durationValue;
  };

  const renderOption = ({ item }: { item: string }) => {
    const currentValue = getCurrentValue();
    const isSelected = currentValue === item;

    let displayLabel = item;
    if (filterType === "sort") {
      displayLabel = getSortLabel(item);
    } else if (filterType === "duration") {
      displayLabel = getDurationLabel(item);
    }

    return (
      <Pressable
        style={[styles.option, { borderBottomColor: colors.border }, isSelected && { backgroundColor: colors.surfaceElevated }]}
        onPress={() => handleSelect(item)}
        accessibilityRole="button"
        accessibilityLabel={`${displayLabel}${isSelected ? ", selected" : ""}`}
        accessibilityState={{ selected: isSelected }}
      >
        <Text style={[styles.optionText, { color: colors.text }, isSelected && { color: colors.accent, fontWeight: "600" }]}>
          {displayLabel}
        </Text>
        {isSelected && <Ionicons name="checkmark-circle" size={20} color={colors.accent} />}
      </Pressable>
    );
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={true}
      onRequestClose={onClose}
      accessibilityViewIsModal={true}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={styles.modalContainer}
      >
        <Pressable style={styles.backdrop} onPress={onClose} />
        <View style={[styles.modalContent, { backgroundColor: colors.surface }]}>
          <SafeAreaView edges={["bottom"]} style={styles.safeArea}>
            <View style={[styles.header, { borderBottomColor: colors.border }]}>
              <View style={styles.headerTitleContainer}>
                <Text style={[styles.headerTitle, { color: colors.text }]}>{getTitle()}</Text>
                {filteredOptions.length > 0 && (
                  <Text style={[styles.headerSubtitle, { color: colors.textMuted }]}>
                    {filteredOptions.length} {filterType === "language" ? "languages" : filterType === "genre" ? "genres" : "options"} available
                  </Text>
                )}
              </View>
              <Pressable
                onPress={onClose}
                style={styles.closeButton}
                accessibilityRole="button"
                accessibilityLabel="Close filter"
              >
                <Ionicons name="close" size={24} color={colors.text} />
              </Pressable>
            </View>

            {/* Search bar - shown for all filter types */}
            <View style={[styles.searchContainer, { backgroundColor: colors.surfaceElevated, borderColor: colors.accent, shadowColor: colors.accent }]}>
              <Ionicons name="search" size={18} color={colors.accent} style={styles.searchIcon} />
              <TextInput
                style={[styles.searchInput, { color: colors.text }]}
                placeholder={
                  filterType === "language"
                    ? "Search languages..."
                    : filterType === "genre"
                    ? "Search genres..."
                    : filterType === "duration"
                    ? "Search duration options..."
                    : "Search sort options..."
                }
                placeholderTextColor={colors.textMuted}
                value={searchQuery}
                onChangeText={setSearchQuery}
                accessibilityLabel={`Search ${filterType}`}
                autoFocus={true}
                returnKeyType="search"
              />
              {searchQuery.length > 0 && (
                <Pressable
                  onPress={() => setSearchQuery("")}
                  style={styles.clearSearchButton}
                  accessibilityRole="button"
                  accessibilityLabel="Clear search"
                >
                  <Ionicons name="close-circle" size={20} color={colors.textMuted} />
                </Pressable>
              )}
            </View>

            <FlatList
              data={filteredOptions}
              renderItem={renderOption}
              keyExtractor={(item) => item}
              style={styles.optionsList}
              contentContainerStyle={styles.optionsListContent}
              keyboardShouldPersistTaps="handled"
              initialNumToRender={20}
              maxToRenderPerBatch={20}
              windowSize={10}
              removeClippedSubviews={true}
              ListEmptyComponent={
                <View style={styles.emptyContainer}>
                  <Ionicons name="search-outline" size={48} color={colors.textMuted} />
                  <Text style={[styles.emptyText, { color: colors.textMuted }]}>No {filterType} found matching "{searchQuery}"</Text>
                </View>
              }
            />
          </SafeAreaView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  modalContainer: {
    flex: 1,
    justifyContent: "flex-end",
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0, 0, 0, 0.5)",
  },
  modalContent: {
    borderTopLeftRadius: Radius.xl - 2,
    borderTopRightRadius: Radius.xl - 2,
    maxHeight: "80%",
    minHeight: "40%",
  },
  safeArea: {
    flex: 1,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.lg,
    borderBottomWidth: 1,
  },
  headerTitleContainer: {
    flex: 1,
    marginRight: Spacing.lg,
  },
  headerTitle: {
    fontSize: Typography.size.md,
    fontWeight: "700",
  },
  headerSubtitle: {
    fontSize: Typography.size.xs,
    marginTop: 2,
  },
  closeButton: {
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
  },
  searchContainer: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: Spacing.lg,
    marginTop: Spacing.md,
    marginBottom: Spacing.sm,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm + 2,
    borderRadius: Radius.md - 2,
    borderWidth: 1.5,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 3,
  },
  searchIcon: {
    marginRight: Spacing.sm + 2,
  },
  searchInput: {
    flex: 1,
    fontSize: 15,
    fontWeight: "500",
  },
  clearSearchButton: {
    marginLeft: Spacing.sm,
  },
  optionsList: {
    flex: 1,
  },
  optionsListContent: {
    paddingBottom: Spacing.lg,
  },
  option: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md + 2,
    borderBottomWidth: 1,
  },
  optionText: {
    fontSize: 15,
  },
  emptyContainer: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: Spacing.xxl * 2,
    paddingHorizontal: Spacing.xxl,
  },
  emptyText: {
    fontSize: Typography.size.sm,
    textAlign: "center",
    marginTop: Spacing.lg,
  },
});
