# Quick Start - TTS Testing

## 🚀 Fast Track Commands

### 1. Navigate to App
```bash
cd "/Users/tizz/Desktop/AI Navigation/AI-Assisted-Navigation-Device/software_side/walkbuddy_reactNative/frontend_reactNative"
```

### 2. Install Dependencies
```bash
npm install
```

### 3. Start Expo (Choose One)

**Expo Go (Phone):**
```bash
npm start
# Scan QR code with Expo Go app
```

**iOS Simulator (Mac):**
```bash
npm run ios
```

**Android Emulator:**
```bash
npm run android
```

### 4. Test TTS
1. Navigate to "Navigate" screen in app
2. Scroll down to see TTS test buttons
3. Tap buttons to hear TTS

---

## ⚡ Troubleshooting Quick Fixes

**Metro bundler issues:**
```bash
npm start -- --reset-cache
```

**Port in use:**
```bash
lsof -ti:8081 | xargs kill -9
```

**Reinstall dependencies:**
```bash
rm -rf node_modules package-lock.json
npm install
```

**iOS pods (if needed):**
```bash
cd ios && pod install && cd ..
```

---

For detailed guide, see `TTS_TESTING_GUIDE.md`



