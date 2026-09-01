import { useRef } from 'react';
import { Animated, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { Radius, Spacing, Typography } from '@/constants/theme';
import { useThemeColors } from '@/hooks/use-theme-colors';

type IconTileProps = {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  onPress: () => void;
};

/**
 * Accent-filled grid tile used for the home screen's secondary "quick
 * actions" (replaces the old per-screen `ActionTile` / `CategoryButton`
 * implementations). Fixed at ~48% width so two fit per row in a
 * `flexWrap: 'wrap'` grid with a small gap. Reactive to light/dark.
 */
export function IconTile({ icon, label, onPress }: IconTileProps) {
  const colors = useThemeColors();
  const scale = useRef(new Animated.Value(1)).current;
  const overlay = useRef(new Animated.Value(0)).current;

  const pressIn = () => {
    Animated.parallel([
      Animated.spring(scale, { toValue: 0.96, useNativeDriver: true, speed: 28, bounciness: 6 }),
      Animated.timing(overlay, { toValue: 1, duration: 80, useNativeDriver: true }),
    ]).start();
  };

  const pressOut = () => {
    Animated.parallel([
      Animated.spring(scale, { toValue: 1, useNativeDriver: true, speed: 22, bounciness: 10 }),
      Animated.timing(overlay, { toValue: 0, duration: 120, useNativeDriver: true }),
    ]).start();
  };

  return (
    <View style={styles.wrap}>
      <Pressable onPress={onPress} onPressIn={pressIn} onPressOut={pressOut} android_ripple={{ color: 'rgba(4,33,28,0.15)' }}>
        <Animated.View style={[styles.outer, { borderColor: colors.accent, shadowColor: colors.accent }, { transform: [{ scale }] }]}>
          <View style={[styles.inner, { backgroundColor: colors.accent }]}>
            <Animated.View pointerEvents="none" style={[styles.overlay, { opacity: overlay }]} />
            <Ionicons name={icon} size={22} color={colors.accentText} />
            <Text style={[styles.label, { color: colors.accentText }]}>{label}</Text>
          </View>
        </Animated.View>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    width: '48%',
  },
  outer: {
    borderWidth: 2,
    borderRadius: Radius.xl,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.5,
    shadowRadius: 14,
    elevation: 6,
  },
  inner: {
    width: '100%',
    borderRadius: Radius.xl - 2,
    minHeight: 92,
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.sm,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.xs,
    overflow: 'hidden',
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(255,255,255,0.15)',
  },
  label: {
    fontSize: Typography.size.xs,
    fontWeight: Typography.weight.bold,
    textAlign: 'center',
    letterSpacing: 0.3,
  },
});
