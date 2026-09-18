import { StyleSheet, View, ViewProps } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Spacing } from '@/constants/theme';
import { useThemeColors } from '@/hooks/use-theme-colors';

type ScreenProps = ViewProps & {
  /** Set false to render edge-to-edge (e.g. full-bleed camera preview). */
  padded?: boolean;
};

/**
 * Standard screen wrapper: themed background (follows system light/dark)
 * + safe-area handling. Replaces the `styles.screen` / `styles.content`
 * pattern that used to be copy-pasted at the top of every screen's
 * StyleSheet.
 */
export function Screen({ padded = true, style, children, ...rest }: ScreenProps) {
  const colors = useThemeColors();
  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: colors.background }]} {...rest}>
      <View style={[styles.content, padded && styles.padded, style]}>
        {children}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
  },
  content: {
    flex: 1,
  },
  padded: {
    paddingHorizontal: Spacing.lg,
  },
});
