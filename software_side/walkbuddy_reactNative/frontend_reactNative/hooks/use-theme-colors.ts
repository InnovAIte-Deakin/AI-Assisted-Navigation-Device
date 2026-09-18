import { useMemo } from 'react';

import { Colors } from '@/constants/theme';
import { useColorScheme } from '@/hooks/use-color-scheme';

/**
 * Returns the full color palette for the current system color scheme,
 * re-computed whenever the scheme changes. Use this (rather than reaching
 * into `Colors.dark`/`Colors.light` directly) in any component that should
 * actually respond to the user's light/dark preference.
 *
 * Defaults to dark when the scheme is unknown (e.g. mid-hydration) since
 * that's the app's primary designed-for theme.
 */
export function useThemeColors() {
  const scheme = useColorScheme();
  return useMemo(() => Colors[scheme === 'light' ? 'light' : 'dark'], [scheme]);
}
