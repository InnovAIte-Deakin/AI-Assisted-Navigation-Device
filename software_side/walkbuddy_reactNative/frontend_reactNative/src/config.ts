// frontend_reactNative/src/config.ts
import Constants from "expo-constants";

type Extra = {
  apiBaseUrl?: string;
};

const extra = (Constants.expoConfig?.extra || {}) as Extra;

export const API_BASE = extra.apiBaseUrl ?? "http://192.168.1.114:8000";
