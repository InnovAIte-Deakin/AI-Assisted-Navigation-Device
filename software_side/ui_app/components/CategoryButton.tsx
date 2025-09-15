import { Pressable, Text, StyleSheet } from "react-native";

export default function CategoryButton({
  label,
  onPress,
}: { label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.btn, pressed && { opacity: 0.9 }]}>
      <Text style={styles.text} numberOfLines={1} ellipsizeMode="tail">
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    flex: 1,
    minHeight: 82,               // was tall; this feels balanced on iPhone
    borderRadius: 12,
    backgroundColor: "#242424",
    borderWidth: 1,
    borderColor: "#F9A826",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 10,
    // margin is handled by FlatList's columnWrapper gap; add only vertical:
    marginVertical: 6,
  },
  text: {
    color: "#F9A826",
    fontWeight: "700",
    fontSize: 16,                // readable but compact
    letterSpacing: 0.3,
  },
});
