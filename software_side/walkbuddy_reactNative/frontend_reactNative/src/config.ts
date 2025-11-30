// frontend_reactNative/src/config.ts
import Constants from "expo-constants";

type Extra = {
  apiBaseUrl?: string;
  gradioUrl?: string;
};

const extra = (Constants.expoConfig?.extra || {}) as Extra;

export const API_BASE = extra.apiBaseUrl ?? "http://localhost:8000";

export const GRADIO_URL = extra.gradioUrl ?? "http://localhost:7860";
