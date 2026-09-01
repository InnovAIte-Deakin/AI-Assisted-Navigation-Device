import { StyleSheet, Text, type TextProps } from 'react-native';

import { useThemeColor } from '@/hooks/use-theme-color';

import { Colors, Typography } from '@/constants/theme';

export type ThemedTextProps = TextProps & {
  lightColor?: string;
  darkColor?: string;
  type?: 'default' | 'title' | 'defaultSemiBold' | 'subtitle' | 'link' | 'label' | 'caption';
};

export function ThemedText({
  style,
  lightColor,
  darkColor,
  type = 'default',
  ...rest
}: ThemedTextProps) {
  const color = useThemeColor({ light: lightColor, dark: darkColor }, 'text');

  return (
    <Text
      style={[
        { color },
        type === 'default' ? styles.default : undefined,
        type === 'title' ? styles.title : undefined,
        type === 'defaultSemiBold' ? styles.defaultSemiBold : undefined,
        type === 'subtitle' ? styles.subtitle : undefined,
        type === 'link' ? styles.link : undefined,
        type === 'label' ? styles.label : undefined,
        type === 'caption' ? styles.caption : undefined,
        style,
      ]}
      {...rest}
    />
  );
}

const styles = StyleSheet.create({
  default: {
    fontSize: Typography.size.base,
    lineHeight: 24,
  },
  defaultSemiBold: {
    fontSize: Typography.size.base,
    lineHeight: 24,
    fontWeight: '600',
  },
  title: {
    fontSize: Typography.size.display,
    fontWeight: 'bold',
    lineHeight: 32,
  },
  subtitle: {
    fontSize: Typography.size.lg,
    fontWeight: 'bold',
  },
  link: {
    lineHeight: 30,
    fontSize: Typography.size.base,
    color: Colors.dark.accent,
  },
  // Small uppercase-style section labels (e.g. "LOCATION", "DESTINATION")
  label: {
    fontSize: Typography.size.xs,
    fontWeight: Typography.weight.bold,
    letterSpacing: 0.6,
  },
  // Secondary/supporting text, smaller and muted
  caption: {
    fontSize: Typography.size.sm,
    fontWeight: Typography.weight.regular,
    color: Colors.dark.textMuted,
  },
});
