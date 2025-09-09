import { View, Text, FlatList, StyleSheet, Pressable, TextInput } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useMemo, useState } from "react";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import CategoryButton from "../../components/CategoryButton"; 

const CATEGORIES = [
  { id: "ARTS", title: "Arts" },
  { id: "FIN", title: "Finance" },
  { id: "SCI", title: "Science" },
  { id: "SCIFI", title: "Sci-Fi" },
  { id: "GEO", title: "Geography" },
  { id: "KIDS", title: "Kids" },
  { id: "IT", title: "I.T." },
  { id: "WC", title: "Toilets" },
  { id: "HELP", title: "Helpdesk" },
];

export default function ExploreScreen() {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return CATEGORIES;
    return CATEGORIES.filter(c =>
      c.title.toLowerCase().includes(q) || c.id.toLowerCase().includes(q)
    );
  }, [query]);

  const goToCategory = (id: string, title: string) =>
    router.push({ pathname: "/category/[id]", params: { id, title } });

  const goHome = () => router.replace("/");

  const ListHeader = (
    <>
      {/* Header row with Home icon + title */}
      <View style={styles.headerRow}>
        <Pressable
          onPress={goHome}
          accessibilityRole="button"
          accessibilityLabel="Go to Home"
          style={styles.iconBtn}
        >
          <Ionicons name="home-outline" size={22} color="#F9A826" />
        </Pressable>
        <Text accessibilityRole="header" style={styles.headerText}>EXPLORE</Text>
        <View style={{ width: 32 }} />
      </View>

      {/* Search bar */}
      <View style={styles.searchWrap}>
        <Ionicons name="search" size={16} color="#888" style={{ marginRight: 8 }} />
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="Search categories…"
          placeholderTextColor="#888"
          accessibilityLabel="Search categories"
          style={styles.searchInput}
          returnKeyType="search"
        />
      </View>
    </>
  );

  return (
    <SafeAreaView style={styles.root} edges={['top']}>
      <FlatList
        data={filtered}
        keyExtractor={(i) => i.id}
        numColumns={2}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={ListHeader}
        contentContainerStyle={{ paddingBottom: 24 }}
        columnWrapperStyle={{ gap: 12, paddingHorizontal: 16 }}
        renderItem={({ item }) => (
          <CategoryButton
            label={item.title}
            onPress={() => goToCategory(item.id, item.title)}
          />
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#0B0B0B" },

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
    width: 32, height: 32,
    alignItems: "center", justifyContent: "center",
    marginRight: 8,
  },
  headerText: {
    flex: 1,
    color: "#F9A826",
    fontSize: 22,                
    fontWeight: "800",
    letterSpacing: 1.1,
    textAlign: "center",
  },

  searchWrap: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 12,
    marginBottom: 10,
    marginHorizontal: 16,
    paddingHorizontal: 12,
    height: 40,                   
    borderRadius: 12,
    borderWidth: 1.25,
    borderColor: "#2A2A2A",
    backgroundColor: "#141414",
  },
  searchInput: {
    flex: 1,
    color: "#EEE",
    fontSize: 15,
  },
});
