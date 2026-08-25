import { Pressable, StyleSheet, ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

import { Spacing } from '@/constants/theme';
import { useThemeColors } from '@/hooks/use-theme-colors';

type BackButtonProps = {
  /** Overrides the default navigate-back behavior (e.g. to run cleanup first). */
  onPress?: () => void;
  /** Renders in normal flex flow (e.g. next to a title in a row) instead of
   * floating absolutely over the top-left of a header/container. */
  inline?: boolean;
  style?: ViewStyle;
};

/**
 * Shared back-navigation control — a bare, solid (bold) arrow, no circular
 * background/border. Defaults to floating absolutely at the top-left of the
 * nearest `position: 'relative'` ancestor (matches
 * app/(tabs)/exterior.tsx's header); pass `inline` to lay it out normally
 * instead, e.g. alongside a title in PageHeader.
 */
export function BackButton({ onPress, inline, style }: BackButtonProps) {
  const colors = useThemeColors();
  const router = useRouter();

  const handlePress = () => {
    if (onPress) {
      onPress();
      return;
    }
    const canGoBack = (router as any)?.canGoBack?.() ?? false;
    if (canGoBack) router.back();
    else router.replace('/' as any);
  };

  return (
    <Pressable
      onPress={handlePress}
      hitSlop={12}
      style={[inline ? styles.backBtnInline : styles.backBtn, style]}
      accessibilityLabel="Go back"
    >
      <Ionicons name="arrow-back" size={26} color={colors.accent} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  backBtn: {
    position: 'absolute',
    top: Spacing.xs,
    left: Spacing.sm,
    padding: Spacing.xs,
    zIndex: 20,
  },
  backBtnInline: {
    padding: Spacing.xs,
    // The arrow glyph sits slightly high within its box, so a plain
    // alignItems:'center' next to a large bold title reads as "above" it —
    // nudge down a couple px to land on the title's optical center.
    marginTop: 3,
  },
});
