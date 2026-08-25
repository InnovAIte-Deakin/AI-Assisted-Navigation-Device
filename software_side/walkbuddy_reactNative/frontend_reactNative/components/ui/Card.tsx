import { StyleSheet, View, ViewProps } from 'react-native';

import { Radius, Spacing } from '@/constants/theme';
import { useThemeColors } from '@/hooks/use-theme-colors';

type CardProps = ViewProps & {
  /** Adds an accent-colored border, e.g. to show an "active" state. */
  highlighted?: boolean;
  elevated?: boolean;
};

/**
 * Themed surface container, reactive to light/dark. Replaces the
 * `sectionCard` / `visionWrapper` / `modalCard`-style ad hoc containers
 * that used to be redefined per screen.
 */
export function Card({ highlighted, elevated, style, children, ...rest }: CardProps) {
  const colors = useThemeColors();
  return (
    <View
      style={[
        styles.card,
        { backgroundColor: colors.surface },
        elevated && { backgroundColor: colors.surfaceElevated, ...styles.elevated },
        highlighted && { borderWidth: 1, borderColor: colors.accent },
        style,
      ]}
      {...rest}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: Radius.lg,
    padding: Spacing.md,
  },
  elevated: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 6,
    elevation: 4,
  },
});
