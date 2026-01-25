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
          <View style={styles.modalContent}>
            <SafeAreaView edges={["bottom"]} style={styles.safeArea}>
              <View style={styles.header}>
                <Text style={styles.headerTitle}>Loading filters...</Text>
                <Pressable
                  onPress={onClose}
                  style={styles.closeButton}
                  accessibilityRole="button"
                  accessibilityLabel="Close filter"
                >
                  <Ionicons name="close" size={24} color="#FFF" />
                </Pressable>
              </View>
              <View style={styles.emptyContainer}>
                <Text style={styles.emptyText}>Please wait while filters are loading...</Text>
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
        style={[styles.option, isSelected && styles.optionSelected]}
        onPress={() => handleSelect(item)}
        accessibilityRole="button"
        accessibilityLabel={`${displayLabel}${isSelected ? ", selected" : ""}`}
        accessibilityState={{ selected: isSelected }}
      >
        <Text style={[styles.optionText, isSelected && styles.optionTextSelected]}>
          {displayLabel}
        </Text>
        {isSelected && <Ionicons name="checkmark-circle" size={20} color="#F9A826" />}
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
        <View style={styles.modalContent}>
          <SafeAreaView edges={["bottom"]} style={styles.safeArea}>
            <View style={styles.header}>
              <View style={styles.headerTitleContainer}>
                <Text style={styles.headerTitle}>{getTitle()}</Text>
                {filteredOptions.length > 0 && (
                  <Text style={styles.headerSubtitle}>
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
                <Ionicons name="close" size={24} color="#FFF" />
              </Pressable>
            </View>

            {/* Search bar - shown for all filter types */}
            <View style={styles.searchContainer}>
              <Ionicons name="search" size={18} color="#F9A826" style={styles.searchIcon} />
              <TextInput
                style={styles.searchInput}
                placeholder={
                  filterType === "language" 
                    ? "Search languages..." 
                    : filterType === "genre"
                    ? "Search genres..."
                    : filterType === "duration"
                    ? "Search duration options..."
                    : "Search sort options..."
                }
                placeholderTextColor="#888"
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
                  <Ionicons name="close-circle" size={20} color="#888" />
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
                  <Ionicons name="search-outline" size={48} color="#666" />
                  <Text style={styles.emptyText}>No {filterType} found matching "{searchQuery}"</Text>
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
    backgroundColor: "#1B263B",
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
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
    paddingHorizontal: 16,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#2A2A2A",
  },
  headerTitleContainer: {
    flex: 1,
    marginRight: 16,
  },
  headerTitle: {
    color: "#FFF",
    fontSize: 18,
    fontWeight: "700",
  },
  headerSubtitle: {
    color: "#888",
    fontSize: 12,
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
    marginHorizontal: 16,
    marginTop: 12,
    marginBottom: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: "#2A2A2A",
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: "#F9A826",
    shadowColor: "#F9A826",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 3,
  },
  searchIcon: {
    marginRight: 10,
  },
  searchInput: {
    flex: 1,
    color: "#FFF",
    fontSize: 15,
    fontWeight: "500",
  },
  clearSearchButton: {
    marginLeft: 8,
  },
  optionsList: {
    flex: 1,
  },
  optionsListContent: {
    paddingBottom: 16,
  },
  option: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: "#2A2A2A",
  },
  optionSelected: {
    backgroundColor: "#2A2A2A",
  },
  optionText: {
    color: "#FFF",
    fontSize: 15,
  },
  optionTextSelected: {
    color: "#F9A826",
    fontWeight: "600",
  },
  emptyContainer: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 48,
    paddingHorizontal: 24,
  },
  emptyText: {
    color: "#888",
    fontSize: 14,
    textAlign: "center",
    marginTop: 16,
  },
});
