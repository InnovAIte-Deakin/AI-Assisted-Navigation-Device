import { useRef } from 'react';
import { Animated, Easing, Pressable, StyleSheet, Text, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { Radius, Spacing, Typography } from '@/constants/theme';
import { useThemeColors } from '@/hooks/use-theme-colors';

type PrimaryButtonProps = {
  label: string;
  onPress: () => void;
  icon?: keyof typeof Ionicons.glyphMap;
  disabled?: boolean;
  style?: ViewStyle;
};

/**
 * Full-width call-to-action button with the press-scale + flash animation
 * that used to be hand-rolled per screen (see the old `BounceButton` in
 * app/(tabs)/index.tsx). Outlined accent style, reactive to light/dark.
 */
export function PrimaryButton({ label, onPress, icon, disabled, style }: PrimaryButtonProps) {
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
      Animated.timing(overlay, { toValue: 0, duration: 120, easing: Easing.out(Easing.cubic), useNativeDriver: true }),
    ]).start();
  };

  return (
    <Pressable onPress={onPress} onPressIn={pressIn} onPressOut={pressOut} disabled={disabled}>
      <Animated.View
        style={[
          styles.button,
          { backgroundColor: colors.surfaceElevated, borderColor: colors.accent },
          disabled && styles.disabled,
          { transform: [{ scale }] },
          style,
        ]}
      >
        <Animated.View pointerEvents="none" style={[styles.overlay, { opacity: overlay }]} />
        {icon && <Ionicons name={icon} size={18} color={colors.text} />}
        <Text style={[styles.label, { color: colors.text }]}>{label}</Text>
      </Animated.View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    width: '100%',
    borderWidth: 2,
    borderRadius: Radius.pill,
    paddingVertical: Spacing.xl,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.18,
    shadowRadius: 6,
    elevation: 4,
  },
  disabled: {
    opacity: 0.4,
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(255,255,255,0.10)',
  },
  label: {
    fontSize: Typography.size.md,
    fontWeight: Typography.weight.bold,
  },
});
