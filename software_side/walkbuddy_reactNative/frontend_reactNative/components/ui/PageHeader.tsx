import { ReactNode } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Radius, Spacing, Typography } from '@/constants/theme';
import { useThemeColors } from '@/hooks/use-theme-colors';
import { BackButton } from './BackButton';

type PageHeaderProps = {
  title: string;
  /** Overrides the default navigate-back behavior (e.g. to run cleanup first). */
  onBackPress?: () => void;
  /** Optional trailing action (e.g. exterior.tsx's edit-destination button). */
  right?: ReactNode;
};

/**
 * Same card-row styling as HomeHeader's header (rounded surface, shadow),
 * but for non-tab pages: back button in place of the profile icon, the
 * page's own title in place of "WalkBuddy", and no Welcome/name greeting or
 * location bar underneath.
 *
 * Screens render this directly in a plain View (no SafeAreaView) — it
 * handles its own top clearance via useSafeAreaInsets so it can't render
 * under the status bar/notch, without the double-reserved gap a
 * SafeAreaView + this component's own padding would otherwise stack up.
 */
export function PageHeader({ title, onBackPress, right }: PageHeaderProps) {
  const colors = useThemeColors();
  const insets = useSafeAreaInsets();

  return (
    <View style={[styles.wrap, { paddingTop: insets.top + Spacing.xs }]}>
      <View style={[styles.headerRow, { backgroundColor: colors.surface }]}>
        <BackButton inline onPress={onBackPress} />
        <Text style={[styles.title, { color: colors.text }]} numberOfLines={1}>
          {title}
        </Text>
        {right}
      </View>
      <View style={[styles.divider, { borderBottomColor: colors.accent }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    width: '100%',
  },

  headerRow: {
    marginHorizontal: Spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    marginBottom: Spacing.xl,
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.md,
    borderRadius: Radius.md,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 5,
  },

  title: {
    fontSize: Typography.size.xxl,
    fontWeight: '900',
    flex: 1,
  },

  divider: {
    marginHorizontal: Spacing.md,
    borderBottomWidth: 1,
    marginBottom: Spacing.md,
  },
});
