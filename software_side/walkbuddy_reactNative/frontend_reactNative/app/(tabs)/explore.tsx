import { Ionicons } from "@expo/vector-icons";
import { Href, router } from "expo-router";
import { useMemo, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
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
] as const;

// Individual explicit routes for each category (all -> /home for now)
const ROUTE_MAP = {
  ARTS: "/arts",
  FIN: "/FinanceScreen",
  SCI: "/science",
  SCIFI: "/SCI-FI",
  GEO: "/geography",
  KIDS: "/kids",
  IT: "/IT",
  WC: "/toilets",
  HELP: "/helpdesk",
} as const satisfies Record<(typeof CATEGORIES)[number]["id"], Href>;

export default function ExploreScreen() {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return CATEGORIES as readonly (typeof CATEGORIES)[number][];
    return CATEGORIES.filter(
      (c) => c.title.toLowerCase().includes(q) || c.id.toLowerCase().includes(q)
    );
  }, [query]);

  // Uses the explicit per-ID route (currently all /home)
  const goToCategory = (id: (typeof CATEGORIES)[number]["id"]) => {
    const href = ROUTE_MAP[id];     // each ID has its own entry
    router.push(href);              // later change any single value here
  };

  const goHomeIcon = () => router.push("/home" as const);

  const ListHeader = (
    <>
      <View style={styles.headerRow}>
        <Pressable
          onPress={goHomeIcon}
          accessibilityRole="button"
          accessibilityLabel="Go to Home"
          style={styles.iconBtn}
        >
          <Ionicons name="home-outline" size={22} color="#F9A826" />
        </Pressable>
        <Text accessibilityRole="header" style={styles.headerText}>EXPLORE</Text>
        <View style={{ width: 32 }} />
      </View>

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
            onPress={() => goToCategory(item.id)}  // each button has its own mapped route
          />
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#1B263B" },

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
    color: "#ffffffff",
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
