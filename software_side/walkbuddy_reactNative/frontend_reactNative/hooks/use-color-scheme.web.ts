import type { ColorSchemeName } from 'react-native';

/**
 * Forced to always report 'light' until dark mode is implemented app-wide.
 * Previously followed the browser's `prefers-color-scheme`, which meant a
 * user with OS-level dark mode enabled saw a different background here than
 * on native (native is locked light via app.config.js's `userInterfaceStyle`,
 * a setting Expo does not apply to web). Swap back to reading
 * `useRNColorScheme()` (with a hydration guard, for static rendering) when
 * dark mode lands.
 */
export function useColorScheme(): ColorSchemeName {
  return 'light';
}
