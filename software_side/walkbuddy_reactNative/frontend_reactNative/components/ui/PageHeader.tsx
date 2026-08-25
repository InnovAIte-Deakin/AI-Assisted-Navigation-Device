import { ReactNode } from 'react';
import { View, Text, StyleSheet } from 'react-native';

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
 */
export function PageHeader({ title, onBackPress, right }: PageHeaderProps) {
  const colors = useThemeColors();

  return (
    <View style={styles.wrap}>
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
    paddingTop: Spacing.md,
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
