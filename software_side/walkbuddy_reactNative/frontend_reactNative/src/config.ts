import Constants from "expo-constants";
import { Platform } from "react-native";

// If EXPO_PUBLIC_API_BASE is set (e.g. a Cloudflare tunnel URL for hotspot use),
// use it. Otherwise derive the backend host from Metro's LAN IP automatically.
const tunnelOverride = process.env.EXPO_PUBLIC_API_BASE;

const lanHost = Constants.expoConfig?.hostUri?.split(":")[0];
const isIp = (h?: string) => !!h && /^\d+\.\d+\.\d+\.\d+$/.test(h);

export const API_BASE =
  tunnelOverride ||
  (Platform.OS === "web"
    ? (typeof window !== "undefined"
        ? `${window.location.protocol}//${window.location.hostname}:8000`
        : "http://localhost:8000")
    : isIp(lanHost)
      ? `http://${lanHost}:8000`
      : "http://172.20.10.2:8000");

// Base URL for the Expo web frontend (port 8081).
// Used to generate shareable helper links.
export const WEB_BASE =
  Platform.OS === "web"
    ? (typeof window !== "undefined" ? window.location.origin : "http://localhost:8081")
    : isIp(lanHost)
      ? `http://${lanHost}:8081`
      : API_BASE.replace(":8000", ":8081");
