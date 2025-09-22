import { View, Text, StyleSheet, Pressable, Alert, ScrollView } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

const COLORS = {
  bg: "#0B0B0B",
  card: "#1A1A1A",
  text: "#F9A826",
  textDim: "#C9A356",
  border: "#F9A826",
  iconBg: "#111111",
};



type Action = {
  key: string;
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
};


export default function CategoryDetails() {
  const { id, title } = useLocalSearchParams<{ id?: string; title?: string }>();
  const name = (title ?? id ?? "CATEGORY").toString();

  const sectionTitle = `${name} section`;
  const distanceDirection = "25 ft, 7 o’clock";

  const actions: Action[] = [
    { key: "go", label: "Go there", icon: "navigate" },
    { key: "save", label: "Save Location", icon: "add-circle-outline" },
    { key: "share", label: "Share Location", icon: "share-social-outline" },
    { key: "camera", label: "Switch to Camera", icon: "camera-outline" },
    { key: "fav", label: "Add to Fav", icon: "star-outline" },
  ];

  const handleAction = (a: Action) => {
    switch (a.key) {
      case "go":
        Alert.alert("Navigate", `Starting guidance to ${name}…`);
        break;
      case "save":
        Alert.alert("Saved", `${name} saved to your locations.`);
        break;
      case "share":
        Alert.alert("Share", `Sharing ${name} location…`);
        break;
      case "camera":
        // TODO: router.push("/camera");
        Alert.alert("Camera", "Switching to camera (TODO).");
        break;
      case "fav":
        Alert.alert("Favorites", `${name} added to favorites.`);
        break;
    }
  };



  return (
    <SafeAreaView style={styles.root} edges={["top", "bottom"]}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.headerIconBtn} accessibilityLabel="Go back">
          <Ionicons name="arrow-back" size={22} color={COLORS.text} />
        </Pressable>
        <Text style={styles.headerTitle}>{name.toUpperCase()}</Text>
        <View style={{ width: 32 }} />
      </View>

      {/* Scrollable content (note: bottom padding so it never hides behind bar) */}
      <ScrollView contentContainerStyle={{ paddingBottom: 88 }}>
        <View style={styles.sectionHeaderWrap}>
          <Text style={styles.sectionTitle}>{sectionTitle}</Text>
          <Text style={styles.sectionSub}>{distanceDirection}</Text>
        </View>

        <View style={styles.actionsWrap}>
          {actions.map((a) => (
            <View key={a.key} style={styles.actionRow}>
              <View style={styles.leftIconCell}>
                <Ionicons name={a.icon} size={22} color={COLORS.text} />
              </View>

              <Pressable
                onPress={() => handleAction(a)}
                style={({ pressed }) => [styles.actionBtn, pressed && { opacity: 0.9, transform: [{ scale: 0.99 }] }]}
                accessibilityRole="button"
                accessibilityLabel={a.label}
              >
                <Text style={styles.actionLabel}>{a.label}</Text>
              </Pressable>
            </View>
          ))}
        </View>
      </ScrollView>

      {/* Fixed bottom action bar */}
      <View style={styles.bottomBar}>
        <BottomItem
          label="Home"
          icon="home-outline"
          onPress={() => router.replace("/")} // to your Home tab
        />
        <BottomItem
          label="Camera"
          icon="camera-outline"
          onPress={() => {
            // TODO: create /camera screen and navigate there
            // router.push("/camera");
            Alert.alert("Camera", "Open camera (TODO).");
          }}
        />
        <BottomItem
          label="My Account"
          icon="person-circle-outline"
          onPress={() => {
            // TODO: create /account screen
            // router.push("/account");
            Alert.alert("Account", "Open account (TODO).");
          }}
        />
      </View>
    </SafeAreaView>
  );
}

/* --- tiny subcomponent for the bar --- */
function BottomItem({
  label,
  icon,
  onPress,
}: {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={styles.bottomItem} accessibilityRole="button" accessibilityLabel={label}>
      <Ionicons name={icon} size={22} color={COLORS.text} />
      <Text style={styles.bottomLabel} numberOfLines={1}>
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.bg },

  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 14,
    paddingTop: 6,
    paddingBottom: 10,
    borderBottomWidth: 1.2,
    borderBottomColor: COLORS.border,
  },
  headerIconBtn: {
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 8,
  },
  headerTitle: {
    flex: 1,
    textAlign: "center",
    color: COLORS.text,
    fontSize: 20,
    fontWeight: "800",
    letterSpacing: 1,
  },

  sectionHeaderWrap: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  sectionTitle: {
    color: COLORS.text,
    fontSize: 20,
    fontWeight: "800",
    marginBottom: 6,
  },
  sectionSub: {
    color: COLORS.textDim,
    fontSize: 16,
    fontWeight: "600",
  },

  actionsWrap: {
    paddingHorizontal: 16,
    paddingTop: 16,
    gap: 12,
  },
  actionRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  leftIconCell: {
    width: 48,
    height: 48,
    borderRadius: 10,
    backgroundColor: COLORS.iconBg,
    borderWidth: 1.2,
    borderColor: COLORS.border,
    alignItems: "center",
    justifyContent: "center",
  },
  actionBtn: {
    flex: 1,
    height: 48,
    borderRadius: 10,
    backgroundColor: COLORS.card,
    borderWidth: 1.6,
    borderColor: COLORS.border,
    alignItems: "center",
    justifyContent: "center",
  },
  actionLabel: {
    color: COLORS.text,
    fontWeight: "700",
    fontSize: 15.5,
  },

  bottomBar: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: "row",
    backgroundColor: COLORS.bg,
    borderTopWidth: 1.2,
    borderTopColor: COLORS.border,
    paddingHorizontal: 16,
    paddingBottom: 12, // SafeArea bottom handled by SafeAreaView
    paddingTop: 8,
    justifyContent: "space-between",
  },
  bottomItem: {
    flex: 1,
    alignItems: "center",
    gap: 4,
  },
  bottomLabel: {
    color: COLORS.text,
    fontSize: 12.5,
    fontWeight: "600",
  },
});
