// app/section.tsx
import { FontAwesome5, MaterialIcons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  Animated,
  Easing,
  Pressable,
  Share,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { addFavourite } from "./lib/favourites";

const GOLD = "#f9b233";
const DARK = "#1B263B";
const CARD = "#242424";

export default function SectionScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{
    title?: string;
    distance?: string;
    clock?: string;
  }>();

  const title = (params.title ?? "Kids").toString();
  const distance = (params.distance ?? "50 ft").toString();
  const clock = (params.clock ?? "6 o'clock").toString();

  // Toast control
  const [toastKey, setToastKey] = useState(0);
  const [toastHeader, setToastHeader] = useState("Saved");
  const [toastMessage, setToastMessage] = useState("Location saved successfully");

  const showToast = useCallback((header: string, message: string) => {
    setToastHeader(header);
    setToastMessage(message);
    setToastKey((k) => k + 1);
  }, []);

  const onBack = () => router.back();

  const onGoThere = useCallback(() => {
    Alert.alert("Navigation", `Starting guidance to ${title} Section.`);
  }, [title]);

  const onSave = useCallback(() => {
    showToast("Saved", "Location saved successfully");
  }, [showToast]);

  const onShare = useCallback(async () => {
    try {
      await Share.share({
        message: `Meet me at the ${title} Section — ${distance}, ${clock}.`,
      });
    } catch {}
  }, [title, distance, clock]);

  const onCamera = () => router.push("/camera");

  const onFav = useCallback(async () => {
    await addFavourite({ title, distance, clock });
    showToast("Add to fav", "Location added to fav successfully");
  }, [title, distance, clock, showToast]);

  return (
    <View style={styles.wrap}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={onBack} hitSlop={12}>
          <MaterialIcons name="arrow-back" size={26} color={GOLD} />
        </Pressable>
        <Text style={styles.headerTitle}>{title.toUpperCase()}</Text>
      </View>

      {/* Hero */}
      <View style={styles.hero}>
        <Text style={styles.sectionTitle}>{title} Section</Text>
        <Text style={styles.distance}>
          {distance}, {clock}
        </Text>
      </View>

      {/* Actions list */}
      <View style={styles.list}>
        <Row
          icon={<FontAwesome5 name="location-arrow" size={20} color={GOLD} />}
          label="Go there"
          onPress={onGoThere}
        />
        <Row
          icon={<MaterialIcons name="add-circle-outline" size={24} color={GOLD} />}
          label="Save Location"
          onPress={onSave}
        />
        <Row
          icon={<MaterialIcons name="share" size={22} color={GOLD} />}
          label="Share Location"
          onPress={onShare}
        />
        <Row
          icon={<MaterialIcons name="photo-camera" size={22} color={GOLD} />}
          label="Switch to Camera"
          onPress={onCamera}
        />
        <Row
          icon={<MaterialIcons name="star-border" size={24} color={GOLD} />}
          label="Add to Fav"
          onPress={onFav}
        />
      </View>

      {/* Bottom bar */}
      <View style={styles.bottomBar}>
        <Pressable style={styles.bottomCell} onPress={() => router.push("/(tabs)")}>
          <MaterialIcons name="home-filled" size={28} color={GOLD} />
        </Pressable>
        <Pressable
          style={[styles.bottomCell, styles.bottomDivider]}
          onPress={onCamera}
        >
          <MaterialIcons name="photo-camera" size={28} color={GOLD} />
        </Pressable>
        <Pressable style={styles.bottomCell} onPress={() => router.push("/account")}>
          <MaterialIcons name="account-circle" size={28} color={GOLD} />
        </Pressable>
      </View>

      {/* Toast */}
      <InfoToast key={toastKey} header={toastHeader} message={toastMessage} />
    </View>
  );
}

/** Row with left icon and right button */
function Row({
  icon,
  label,
  onPress,
}: {
  icon: React.ReactNode;
  label: string;
  onPress: () => void;
}) {
  return (
    <View style={styles.row}>
      <View style={styles.rowIcon}>{icon}</View>
      <Pressable style={styles.rowBtn} onPress={onPress}>
        <Text style={styles.rowBtnText}>{label}</Text>
      </Pressable>
    </View>
  );
}

/** Toast */
function InfoToast({ header, message }: { header: string; message: string }) {
  const opacity = useRef(new Animated.Value(0)).current;
  const translate = useRef(new Animated.Value(10)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(opacity, {
        toValue: 1,
        duration: 220,
        useNativeDriver: true,
        easing: Easing.out(Easing.cubic),
      }),
      Animated.timing(translate, {
        toValue: 0,
        duration: 220,
        useNativeDriver: true,
        easing: Easing.out(Easing.cubic),
      }),
    ]).start();

    const id = setTimeout(() => {
      Animated.parallel([
        Animated.timing(opacity, {
          toValue: 0,
          duration: 220,
          useNativeDriver: true,
          easing: Easing.in(Easing.cubic),
        }),
        Animated.timing(translate, {
          toValue: 10,
          duration: 220,
          useNativeDriver: true,
          easing: Easing.in(Easing.cubic),
        }),
      ]).start();
    }, 1600);

    return () => clearTimeout(id);
  }, [opacity, translate]);

  return (
    <Animated.View
      pointerEvents="none"
      style={[styles.toastWrap, { opacity, transform: [{ translateY: translate }] }]}
    >
      <Text style={styles.toastTitle}>{header}</Text>

      <View style={styles.toastCard}>
        <MaterialIcons name="notifications-none" size={20} color={GOLD} />
        <View style={{ flex: 1 }} />
        <MaterialIcons name="check" size={20} color={GOLD} />

        <View style={{ position: "absolute", left: 14, bottom: 10 }}>
          <Text style={styles.toastText}>{message}</Text>
        </View>
      </View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: DARK },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 10,
    borderBottomWidth: 2,
    borderBottomColor: GOLD,
  },
  headerTitle: {
    color: GOLD,
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: 1,
  },
  hero: {
    paddingHorizontal: 16,
    paddingVertical: 16,
    borderBottomWidth: 2,
    borderBottomColor: GOLD,
  },
  sectionTitle: { color: GOLD, fontSize: 26, fontWeight: "900", marginBottom: 8 },
  distance: { color: GOLD, fontSize: 22, fontWeight: "800" },
  list: { padding: 16, gap: 14 },
  row: { flexDirection: "row", alignItems: "center", gap: 14 },
  rowIcon: { width: 42, alignItems: "center" },
  rowBtn: {
    flex: 1,
    backgroundColor: CARD,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#383838",
  },
  rowBtnText: { color: GOLD, fontWeight: "800", fontSize: 16 },
  bottomBar: {
    flexDirection: "row",
    borderTopWidth: 2,
    borderTopColor: GOLD,
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 24,
    justifyContent: "space-between",
  },
  bottomCell: { flex: 1, alignItems: "center" },
  bottomDivider: { borderLeftWidth: 2, borderRightWidth: 2, borderColor: GOLD },
  toastWrap: { position: "absolute", right: 16, bottom: 24 },
  toastTitle: { color: "#bdbdbd", fontSize: 12, marginLeft: 6, marginBottom: 6 },
  toastCard: {
    width: 210,
    minHeight: 110,
    backgroundColor: "#0a0a0a",
    borderWidth: 1,
    borderColor: GOLD,
    borderRadius: 6,
    padding: 12,
    flexDirection: "row",
    alignItems: "flex-start",
  },
  toastText: { color: GOLD, fontWeight: "700", lineHeight: 16 },
});
