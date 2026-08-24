import { useRef } from 'react';
import { Animated, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { Radius, Spacing, Typography } from '@/constants/theme';
import { useThemeColors } from '@/hooks/use-theme-colors';

type HeroButtonProps = {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  subtitle: string;
  /** accent = the app's primary teal, danger = red (e.g. Emergency). */
  tone: 'accent' | 'danger';
  onPress: () => void;
};

/**
 * Large full-width call-to-action card: icon + title + subtitle on a
 * solid color fill. Used for the home screen's top-level actions (Camera,
 * Emergency) — the "big, high-contrast, hard-to-miss button" pattern the
 * team asked for after looking at other accessibility apps.
 */
export function HeroButton({ icon, title, subtitle, tone, onPress }: HeroButtonProps) {
  const colors = useThemeColors();
  const fill = tone === 'danger' ? colors.danger : colors.accent;
  const onFill = tone === 'danger' ? '#FFFFFF' : colors.accentText;

  const scale = useRef(new Animated.Value(1)).current;
  const overlay = useRef(new Animated.Value(0)).current;

  const pressIn = () => {
    Animated.parallel([
      Animated.spring(scale, { toValue: 0.97, useNativeDriver: true, speed: 28, bounciness: 6 }),
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
    <Pressable onPress={onPress} onPressIn={pressIn} onPressOut={pressOut} accessibilityRole="button" accessibilityLabel={title}>
      <Animated.View style={[styles.card, { backgroundColor: fill, shadowColor: fill, transform: [{ scale }] }]}>
        <Animated.View pointerEvents="none" style={[styles.overlay, { opacity: overlay }]} />
        <View style={[styles.iconWrap, { backgroundColor: 'rgba(255,255,255,0.22)' }]}>
          <Ionicons name={icon} size={30} color={onFill} />
        </View>
        <View style={styles.textWrap}>
          <Text style={[styles.title, { color: onFill }]}>{title}</Text>
          <Text style={[styles.subtitle, { color: onFill }]}>{subtitle}</Text>
        </View>
        <Ionicons name="chevron-forward" size={22} color={onFill} />
      </Animated.View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    borderRadius: Radius.xl,
    padding: Spacing.lg,
    overflow: 'hidden',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.35,
    shadowRadius: 14,
    elevation: 8,
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(255,255,255,0.12)',
  },
  iconWrap: {
    width: 52,
    height: 52,
    borderRadius: Radius.lg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  textWrap: {
    flex: 1,
    gap: 2,
  },
  title: {
    fontSize: Typography.size.lg,
    fontWeight: Typography.weight.bold,
  },
  subtitle: {
    fontSize: Typography.size.xs,
    fontWeight: Typography.weight.medium,
    opacity: 0.9,
  },
});
