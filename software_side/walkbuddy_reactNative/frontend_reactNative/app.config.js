// frontend_reactNative/app.config.js
export default ({ config }) => ({
  ...config,
  name: config.name || "MyApp",
  slug: config.slug || "my-app",
  version: config.version || "1.0.0",
  orientation: "portrait",
  icon: "./assets/images/icon.png", // Fixed: use correct path to match app.json
  userInterfaceStyle: "light",
  splash: {
    image: "./assets/splash.png",
    resizeMode: "contain",
    backgroundColor: "#ffffff",
  },
  updates: {
    fallbackToCacheTimeout: 0,
  },
  assetBundlePatterns: ["**/*"],
  ios: {
    supportsTablet: true,
  },
  android: {
    adaptiveIcon: {
      foregroundImage: "./assets/adaptive-icon.png",
      backgroundColor: "#ffffff",
    },
  },
  web: {
    favicon: "./assets/favicon.png",
    headers: {
      "Content-Security-Policy":
        "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:;",
    },
  },
  extra: {
    apiBaseUrl: "http://192.168.1.122:8000",

  },
});
