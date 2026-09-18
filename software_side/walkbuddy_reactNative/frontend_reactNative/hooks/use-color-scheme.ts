import type { ColorSchemeName } from 'react-native';

/**
 * Forced to always report 'light' until dark mode is implemented app-wide.
 * Previously re-exported React Native's `useColorScheme`, which followed the
 * OS setting and disagreed with the web build (Expo's `userInterfaceStyle`
 * config only locks native appearance, not the browser). Swap back to
 * `export { useColorScheme } from 'react-native';` when dark mode lands.
 */
export function useColorScheme(): ColorSchemeName {
  return 'light';
}
