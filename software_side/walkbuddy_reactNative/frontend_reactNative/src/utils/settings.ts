// Settings storage utility
import AsyncStorage from '@react-native-async-storage/async-storage';

const SETTINGS_KEY = '@walkbuddy_settings';

export interface NavigationSettings {
  showMapVisuals: boolean;
  voiceEnabled: boolean;
}

const DEFAULT_SETTINGS: NavigationSettings = {
  showMapVisuals: true,
  voiceEnabled: true,
};

export async function loadSettings(): Promise<NavigationSettings> {
  try {
    const stored = await AsyncStorage.getItem(SETTINGS_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      return { ...DEFAULT_SETTINGS, ...parsed };
    }
  } catch (error) {
    console.error('Failed to load settings:', error);
  }
  return DEFAULT_SETTINGS;
}

export async function saveSettings(settings: NavigationSettings): Promise<void> {
  try {
    await AsyncStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch (error) {
    console.error('Failed to save settings:', error);
  }
}

export async function updateSetting<K extends keyof NavigationSettings>(
  key: K,
  value: NavigationSettings[K]
): Promise<void> {
  const current = await loadSettings();
  await saveSettings({ ...current, [key]: value });
}
