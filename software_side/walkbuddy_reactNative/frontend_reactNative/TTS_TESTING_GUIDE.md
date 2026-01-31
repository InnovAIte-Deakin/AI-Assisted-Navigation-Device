# TTS Testing Guide - React Native (Expo) App

Complete step-by-step guide to run the React Native app and test the Text-to-Speech feature.

## 📍 Location

**App Folder:** `software_side/walkbuddy_reactNative/frontend_reactNative/`

---

## ✅ Step-by-Step Checklist

### Step 1: Verify Prerequisites

Check if you have the required tools installed:

```bash
# Check Node.js version (should be 18+)
node --version

# Check npm version
npm --version

# Check if Expo CLI is installed globally
npx expo --version
```

**If missing:**
- **Node.js**: Download from [nodejs.org](https://nodejs.org/) (LTS version recommended)
- **npm**: Comes with Node.js
- **Expo CLI**: Will be installed via npx (no need to install globally)

---

### Step 2: Navigate to App Directory

```bash
cd "/Users/tizz/Desktop/AI Navigation/AI-Assisted-Navigation-Device/software_side/walkbuddy_reactNative/frontend_reactNative"
```

**Verify you're in the right place:**
```bash
# Should show package.json
ls package.json

# Should show expo-speech in dependencies
grep "expo-speech" package.json
```

---

### Step 3: Install Dependencies

The project uses **npm** (package-lock.json exists).

```bash
# Install all dependencies
npm install
```

**Expected output:** Dependencies installed, including `expo-speech` (already in package.json).

**If you see errors:**
- Delete `node_modules` and `package-lock.json`, then run `npm install` again
- Check Node.js version (should be 18+)

---

### Step 4: Verify TTS Service Files

Check that TTS files exist:

```bash
# Check TTS service exists
ls src/services/TTSService.ts

# Check TTS example exists
ls src/examples/TTSExample.tsx

# Verify navigate.tsx has TTS test buttons
grep "TTS Test" app/navigate.tsx
```

---

### Step 5: Start Expo Development Server

Choose one of the following options:

#### Option A: Expo Go (Recommended for Quick Testing)

```bash
# Start Expo with tunnel (works on any network)
npm start

# OR with cache clear (if you have issues)
npm run dev
```

**What happens:**
- Metro bundler starts
- QR code appears in terminal
- Expo DevTools opens in browser

**Next steps:**
1. Install **Expo Go** app on your phone (iOS App Store or Google Play)
2. Scan the QR code with:
   - **iOS**: Camera app
   - **Android**: Expo Go app
3. App loads on your phone

---

#### Option B: iOS Simulator (Mac Only)

**Prerequisites:**
- Xcode installed (from App Store)
- iOS Simulator available

```bash
# Start Expo and open iOS simulator
npm run ios

# OR manually:
npm start
# Then press 'i' in the terminal to open iOS simulator
```

**First time setup:**
```bash
# Install CocoaPods dependencies (if needed)
cd ios
pod install
cd ..
npm run ios
```

---

#### Option C: Android Emulator

**Prerequisites:**
- Android Studio installed
- Android emulator created and running

```bash
# Start Expo and open Android emulator
npm run android

# OR manually:
npm start
# Then press 'a' in the terminal to open Android emulator
```

**First time setup:**
```bash
# Make sure Android emulator is running first
# Then:
npm run android
```

---

### Step 6: Test TTS Feature

Once the app is running:

1. **Navigate to the Navigate Screen:**
   - Look for navigation/navigate option in the app
   - Or navigate to `/navigate` route

2. **Find TTS Test Buttons:**
   - Scroll down on the Navigate screen
   - You should see three test buttons:
     - "Test: 'Path ahead is clear'"
     - "Test: 'Chair on your left'"
     - "Test: 'Obstacle ahead'"

3. **Test Each Button:**
   - Tap each button
   - You should hear the text-to-speech output
   - An alert will show if the message was spoken or suppressed

4. **Test Anti-Spam Logic:**
   - Tap the same button twice quickly
   - Second tap should be suppressed (alert will say "Suppressed")
   - Wait 3 seconds, then tap again - should work

---

## 🔧 Troubleshooting

### Metro Bundler Issues

**Problem:** Metro bundler won't start or crashes

**Solutions:**
```bash
# Clear Metro cache
npm start -- --reset-cache

# OR
npm run dev  # This uses -c flag to clear cache

# Clear watchman (if installed)
watchman watch-del-all

# Clear npm cache
npm cache clean --force
```

---

### Expo Go Connection Issues

**Problem:** Can't connect to Expo Go on phone

**Solutions:**
```bash
# Use tunnel mode (already in npm start script)
npm start  # Uses --tunnel flag

# Make sure phone and laptop are on same WiFi
# OR use tunnel mode (slower but works on different networks)

# Check firewall settings
# Allow Node.js through firewall
```

---

### iOS Simulator Issues

**Problem:** iOS simulator won't open or app crashes

**Solutions:**
```bash
# Install CocoaPods dependencies
cd ios
pod install
cd ..

# Reset iOS simulator
# In Xcode: Device > Erase All Content and Settings

# Clear build cache
rm -rf ios/build
npm run ios
```

---

### Android Emulator Issues

**Problem:** Android emulator won't connect

**Solutions:**
```bash
# Make sure emulator is running first
# Check with:
adb devices

# If no devices, start emulator from Android Studio

# Clear Android build
cd android
./gradlew clean
cd ..

# Reset Metro cache
npm start -- --reset-cache
```

---

### TTS Not Working

**Problem:** No sound when tapping TTS buttons

**Solutions:**
1. **Check device volume** - Make sure device/simulator volume is up
2. **Check permissions** - Expo Go should request permissions automatically
3. **Check console logs** - Look for errors in terminal or Expo DevTools
4. **Test on real device** - Simulators sometimes have TTS issues

```bash
# Check if expo-speech is installed
npm list expo-speech

# Reinstall if needed
npm install expo-speech@~14.0.7
```

---

### TypeScript Errors

**Problem:** TypeScript compilation errors

**Solutions:**
```bash
# Check TypeScript version
npx tsc --version

# Should be 5.9.2 (in devDependencies)

# Reinstall TypeScript
npm install --save-dev typescript@5.9.2

# Restart Metro bundler
npm start
```

---

### Module Not Found Errors

**Problem:** Can't find '@/services/TTSService'

**Solutions:**
```bash
# Check tsconfig.json has path mapping
cat tsconfig.json | grep paths

# Should show:
# "@/*": ["./*"]

# If not, check tsconfig.json configuration
```

---

### Port Already in Use

**Problem:** Port 8081 (Metro) or 19000 (Expo) is already in use

**Solutions:**
```bash
# Kill process on port 8081
lsof -ti:8081 | xargs kill -9

# Kill process on port 19000
lsof -ti:19000 | xargs kill -9

# OR use different port
npm start -- --port 8082
```

---

## 📱 Quick Test Commands

### Test TTS Service Directly (if you add a test script)

You can also test the TTS service programmatically by adding this to any screen:

```typescript
import { getTTSService, RiskLevel } from '@/services/TTSService';

const tts = getTTSService();
await tts.speak('Path ahead is clear', RiskLevel.CLEAR);
```

---

## 🎯 Expected Behavior

When you tap a TTS test button:

1. **First tap:** Message is spoken, alert shows "Spoke: [message]"
2. **Second tap (within 3 seconds):** Message is suppressed, alert shows "Suppressed: [message] (anti-spam)"
3. **After 3 seconds:** Message can be spoken again
4. **Different message:** Always spoken (different content)
5. **Higher risk level:** Always spoken (risk escalation)

---

## 📝 Notes

- **expo-speech** is already installed (version ~14.0.7)
- TTS test buttons are added to `app/navigate.tsx`
- TTS service is at `src/services/TTSService.ts`
- The app uses **npm** (not yarn) - package-lock.json exists
- Expo version: ~54.0.9
- React Native version: 0.81.4

---

## 🆘 Still Having Issues?

1. Check Expo documentation: [docs.expo.dev](https://docs.expo.dev)
2. Check Metro bundler logs in terminal
3. Check Expo DevTools in browser (opens automatically)
4. Try on a real device instead of simulator
5. Check device/simulator volume settings

---

## ✅ Success Checklist

- [ ] Node.js installed (18+)
- [ ] npm installed
- [ ] Dependencies installed (`npm install`)
- [ ] Expo server started (`npm start`)
- [ ] App running on device/simulator
- [ ] Navigate screen accessible
- [ ] TTS test buttons visible
- [ ] TTS buttons produce sound
- [ ] Anti-spam logic works (second tap suppressed)

---

**Happy Testing! 🎉**



