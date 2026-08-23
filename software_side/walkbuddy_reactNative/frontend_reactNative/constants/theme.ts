/**
 * Single source of truth for the app's design system: colors, spacing,
 * border radius, and typography. Import from here instead of hardcoding
 * hex values / magic numbers in a screen's own StyleSheet.
 *
 * The app is dark-mode-only in practice today, so `Colors.dark` is what
 * every screen should actually render with. `Colors.light` is kept for
 * forward-compatibility with `useThemeColor` but nothing switches to it yet.
 */

import { Platform } from 'react-native';

export const Colors = {
  dark: {
    background: '#0B1220',
    surface: '#141C2C',
    surfaceElevated: '#1C2740',
    border: '#2A3650',
    text: '#F5F7FA',
    textMuted: '#A7B3C6',

    accent: '#2DD4BF',
    accentText: '#04211C',

    // Semantic — mirrors the CRITICAL/HIGH/MEDIUM/LOW hazard-priority
    // system defined on the ML side, so future safety UI can reuse these
    // instead of inventing its own red/orange/yellow/green.
    danger: '#FF5A5F',
    warning: '#FF9F1C',
    success: '#2ECC71',
    info: '#3DA9FC',

    // Legacy aliases kept only so `useThemeColor(..., 'tint' | 'icon' | ...)`
    // calls already in the codebase (e.g. components/ui/collapsible.tsx)
    // don't break while screens are migrated one at a time.
    tint: '#2DD4BF',
    icon: '#A7B3C6',
    tabIconDefault: '#A7B3C6',
    tabIconSelected: '#2DD4BF',
  },
  light: {
    background: '#F7F9FC',
    surface: '#FFFFFF',
    surfaceElevated: '#FFFFFF',
    border: '#DDE3ED',
    text: '#10131A',
    textMuted: '#4A5568',

    accent: '#0E7C86',
    accentText: '#FFFFFF',

    danger: '#D8383D',
    warning: '#C97300',
    success: '#1E9E52',
    info: '#1D6FC4',

    tint: '#0E7C86',
    icon: '#4A5568',
    tabIconDefault: '#4A5568',
    tabIconSelected: '#0E7C86',
  },
};

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
};

export const Radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 22,
  pill: 999,
};

export const Typography = {
  size: {
    xs: 12,
    sm: 14,
    base: 16,
    md: 18,
    lg: 20,
    xl: 24,
    xxl: 30,
    display: 36,
  },
  weight: {
    regular: '400' as const,
    medium: '600' as const,
    bold: '800' as const,
  },
};

export const Fonts = Platform.select({
  ios: {
    /** iOS `UIFontDescriptorSystemDesignDefault` */
    sans: 'system-ui',
    /** iOS `UIFontDescriptorSystemDesignSerif` */
    serif: 'ui-serif',
    /** iOS `UIFontDescriptorSystemDesignRounded` */
    rounded: 'ui-rounded',
    /** iOS `UIFontDescriptorSystemDesignMonospaced` */
    mono: 'ui-monospace',
  },
  default: {
    sans: 'normal',
    serif: 'serif',
    rounded: 'normal',
    mono: 'monospace',
  },
  web: {
    sans: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    serif: "Georgia, 'Times New Roman', serif",
    rounded: "'SF Pro Rounded', 'Hiragino Maru Gothic ProN', Meiryo, 'MS PGothic', sans-serif",
    mono: "SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
  },
});
