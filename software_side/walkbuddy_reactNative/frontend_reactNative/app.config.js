// frontend_reactNative/app.config.js
export default ({ config }) => ({
  ...config,
  name: config.name || "MyApp",
  slug: config.slug || "my-app",
  version: config.version || "1.0.0",
  scheme: "walkbuddy",
  plugins: ["expo-speech-recognition"],
  orientation: "portrait",
  icon: "./assets/images/icon.png",
  userInterfaceStyle: "light",
  splash: {
    image: "./assets/images/splash-icon.png",
    resizeMode: "contain",
    backgroundColor: "#0D1B2A",
  },
  updates: {
    fallbackToCacheTimeout: 0,
  },
  assetBundlePatterns: ["**/*"],
  ios: {
    supportsTablet: true,
    infoPlist: {
      NSAppTransportSecurity: {
        NSAllowsArbitraryLoads: true,
      },
    },
  },
  android: {
    adaptiveIcon: {
      foregroundImage: "./assets/images/icon.png",
      backgroundColor: "#ffffff",
    },
  },
  web: {
    favicon: "./assets/images/favicon.png",
    headers: {
      "Content-Security-Policy":
        "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:;",
    },
  },
});
