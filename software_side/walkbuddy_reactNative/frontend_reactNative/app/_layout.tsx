// app/_layout.tsx
import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from "expo-router";
import { StatusBar } from "expo-status-bar";
import "react-native-reanimated";

import { useColorScheme } from "@/hooks/use-color-scheme";
import { CurrentLocationProvider } from "../src/utils/locationSaver";
import { SessionProvider } from "../src/context/SessionContext";
import { WakeWordProvider } from "../src/context/ForegroundWakeWordContext";

export const unstable_settings = {
  anchor: "(tabs)",
};

export default function RootLayout() {
  const colorScheme = useColorScheme();

  return (
    <SessionProvider>
      <CurrentLocationProvider>
        <WakeWordProvider>
          <ThemeProvider value={colorScheme === "dark" ? DarkTheme : DefaultTheme}>
            <Stack
              screenOptions={{
                headerShown: false,
              }}
            >
              <Stack.Screen name="(tabs)" />
            </Stack>
            <StatusBar style="auto" />
          </ThemeProvider>
        </WakeWordProvider>
      </CurrentLocationProvider>
    </SessionProvider>
  );
}
