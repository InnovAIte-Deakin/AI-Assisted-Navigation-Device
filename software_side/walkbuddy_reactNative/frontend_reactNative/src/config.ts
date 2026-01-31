import Constants from "expo-constants";

const extra = (Constants.expoConfig?.extra ?? {}) as any;

// IMPORTANT: phones cannot access localhost on your laptop
const defaultApiBase =
  extra.apiBaseUrl ??
  (process.env.EXPO_PUBLIC_API_BASE as string) ??
  "http://172.20.10.2:8000";

export const API_BASE = defaultApiBase;
