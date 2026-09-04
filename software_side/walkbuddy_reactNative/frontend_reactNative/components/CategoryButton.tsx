import { Pressable, Text, StyleSheet } from "react-native";
import { Radius, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";

export default function CategoryButton({
  label,
  onPress,
}: { label: string; onPress: () => void }) {
  const colors = useThemeColors();
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.btn,
        { backgroundColor: colors.surface, borderColor: colors.accent },
        pressed && { opacity: 0.9 },
      ]}
    >
      <Text style={[styles.text, { color: colors.accent }]} numberOfLines={1} ellipsizeMode="tail">
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    flex: 1,
    minHeight: 82,               // was tall; this feels balanced on iPhone
    borderRadius: Radius.md,
    borderWidth: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 10,
    // margin is handled by FlatList's columnWrapper gap; add only vertical:
    marginVertical: 6,
  },
  text: {
    fontWeight: "700",
    fontSize: Typography.size.base,                // readable but compact
    letterSpacing: 0.3,
  },
});
