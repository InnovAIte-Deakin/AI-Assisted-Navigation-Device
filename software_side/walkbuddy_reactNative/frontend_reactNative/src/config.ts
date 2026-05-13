import Constants from "expo-constants";
import { Platform } from "react-native";

// If EXPO_PUBLIC_API_BASE is set (e.g. a Cloudflare tunnel URL for hotspot use),
// use it. Otherwise derive the backend host from Metro's LAN IP automatically.
//Now can override API base URL using EXPO_PUBLIC_API_BASE
const tunnelOverride = process.env.EXPO_PUBLIC_API_BASE;

export const API_KEY = process.env.EXPO_PUBLIC_WALKBUDDY_API_KEY || "";

export const GRADIO_URL =
  process.env.EXPO_PUBLIC_GRADIO_URL || "http://localhost:7860";


const lanHost = Constants.expoConfig?.hostUri?.split(":")[0];
const isIp = (h?: string) => !!h && /^\d+\.\d+\.\d+\.\d+$/.test(h);

export const API_BASE =
  tunnelOverride ||
  (Platform.OS === "web"
    ? "http://localhost:8000"
    : isIp(lanHost)
      ? `http://${lanHost}:8000`
      : "http://localhost:8000");
