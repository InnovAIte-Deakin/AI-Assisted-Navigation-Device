# WalkBuddy Ask a Friend — Agora Video Calling

The **Ask a Friend** function provides real-time video and two-way audio between a WalkBuddy mobile user and a remote helper. It uses Agora RTC, a server-side token service, a browser-based helper interface, and Cloudflare Quick Tunnels for development testing.

## Important requirement

This function does not run in Expo Go because `react-native-agora` contains native code. It must be run using the WalkBuddy Expo Development Build.

The current development setup supports:

- **Android development on Windows**
- **iOS development on Apple macOS with Xcode and a physical iPhone**

## Relevant project structure

```text
AI-Assisted-Navigation-Device/
└── software_side/
    └── walkbuddy_reactNative/
        └── frontend_reactNative/
            ├── agora_session_server/
            │   ├── .env
            │   ├── package.json
            │   └── server.js
            ├── app/
            ├── scripts/
            │   ├── setup-android-windows.ps1
            │   ├── setup-ios-macos.sh
            │   └── start-dev.js
            ├── services/
            │   ├── agoraCallService.android.ts
            │   ├── agoraCallService.ios.ts
            │   ├── agoraCallService.web.ts
            │   └── agoraSessionService.ts
            ├── package.json
            └── README.md
```

## Prerequisites

### Common requirements

- Git
- An Agora project using App ID and App Certificate authentication
- Internet access
- A configured `agora_session_server/.env` for actual Agora calls

### Android on Windows

- Node.js and npm
- Android Studio with the Android SDK and platform tools
- JDK 17, such as the JDK bundled with Android Studio
- An Android phone with Developer Options and USB debugging enabled, or an Android emulator

### iOS on macOS

- An Apple Silicon Mac
- Full Xcode installed and opened at least once
- Xcode first-launch/license setup completed
- A physical iPhone for device testing
- An Apple Account available in Xcode for development signing

The macOS setup script installs the WalkBuddy-specific Node.js, Ruby, CocoaPods, Cloudflared, and supporting command-line dependencies in the user's home directory without requiring Homebrew. Xcode itself must already be installed and usable.

## 1. Clone the repository or update your branch

Clone your fork if the repository is not already available:

```bash
git clone https://github.com/YOUR-USERNAME/AI-Assisted-Navigation-Device.git
cd AI-Assisted-Navigation-Device
```

If it is already cloned, switch to the branch containing the Agora function and update it as appropriate for your fork/workflow.

## 2. Open the React Native project

All remaining commands should be run from `frontend_reactNative` unless stated otherwise.

### Windows

```powershell
cd software_side\walkbuddy_reactNative\frontend_reactNative
```

### macOS

```bash
cd software_side/walkbuddy_reactNative/frontend_reactNative
```

## 3. Configure the Agora session server

1. Sign in to the Agora Console.
2. Open **Project Management** and create or select a project.
3. Use secured authentication with an **App ID and App Certificate**.
4. Copy the project's **App ID**.
5. Enable and copy the primary **App Certificate**.
6. Keep the App Certificate private.

Create or update:

```text
agora_session_server/.env
```

Add:

```env
AGORA_APP_ID=your_agora_app_id
AGORA_APP_CERTIFICATE=your_agora_app_certificate
PORT=3001
```

Do not add spaces around the values. The App Certificate must remain on the server and must never be placed in application code or an `EXPO_PUBLIC_` variable.

The session server generates Agora RTC tokens automatically. Users do not need to manually create temporary RTC tokens in the Agora Console.

Do **not** commit `agora_session_server/.env`.

## 4. Android — first development build on Windows

Connect the Android phone by USB and enable USB debugging. Confirm that ADB can see it:

```powershell
adb devices
```

From `frontend_reactNative`, run:

```powershell
npm run setup:android
```

Follow any prompts displayed by the script. Keep the phone unlocked and accept USB debugging or application-installation prompts if Android displays them.

The Android setup installs the required frontend/session-server dependencies, prepares the native project and installs the Expo Development Build. Do not use Expo Go for the Agora function.

Avoid running `expo prebuild --clean` unless the project maintainers specifically require it, because cleaning a generated native project can replace native changes.

## 5. iOS — first development build on macOS

Connect and unlock the iPhone, then run from `frontend_reactNative`:

```bash
bash scripts/setup-ios-macos.sh
```

The setup script checks or installs the WalkBuddy development dependencies, including Node.js, the compatible local Ruby toolchain, CocoaPods and Cloudflared. It installs project dependencies, prepares the iOS native project when required, installs CocoaPods, checks Apple Development signing and performs a basic code-signing access test before starting:

```bash
npx expo run:ios --device
```

Keep the iPhone unlocked and respond to any trust/signing prompts from macOS or Xcode.

### Apple Development signing

If the script reports that no Apple Development signing identity is available:

1. Open the generated workspace:

```bash
open ios/*.xcworkspace
```

2. In Xcode, open **Xcode → Settings → Apple Accounts**.
3. Sign in with your Apple Account.
4. Select the application target.
5. Open **Signing & Capabilities**.
6. Enable **Automatically manage signing**.
7. Select the appropriate Development Team or Personal Team.
8. Allow Xcode to create an Apple Development certificate if required.
9. Rerun:

```bash
bash scripts/setup-ios-macos.sh
```

Do not place Apple Account passwords or Keychain passwords in scripts or project files.

### Keychain/code-signing prompts

The setup script performs a small code-signing test, but the first full Xcode device build may still request access to the Apple Development private key.

If macOS asks once, enter the Mac login Keychain password locally and choose **Always Allow** when appropriate.

If the same `codesign wants to access key...` dialog repeatedly appears, stop the current build with `Ctrl+C` and run:

```bash
security set-key-partition-list \
  -S apple-tool:,apple:,codesign: \
  -s \
  "$HOME/Library/Keychains/login.keychain-db"
```

Enter the Mac login Keychain password locally when macOS requests it. Never paste, save or commit that password.

Then rerun:

```bash
bash scripts/setup-ios-macos.sh
```

### After the first iOS build

The initial `npx expo run:ios --device` build creates/installs the native development build, but it does **not** by itself start the Agora session server, helper server or Cloudflare tunnels.

Therefore, if Ask a Friend reports:

```text
EXPO_PUBLIC_AGORA_SESSION_URL is not configured
```

immediately after the initial native build, this is expected. Start the complete development environment as described below.

When the initial build succeeds, `Ctrl+C` can be used to stop its Metro process before starting the complete development launcher.

## 6. Start the complete development environment

For normal Agora development on either platform, run from `frontend_reactNative`:

```bash
npm run dev:call
```

On Windows, run the same command in PowerShell:

```powershell
npm run dev:call
```

On macOS, if the setup script was run in the **same existing terminal**, reload the shell profile first so that Node.js and the locally installed tools are available:

```bash
source ~/.bash_profile
npm run dev:call
```

A newly opened Terminal should load the configured environment automatically.

The development launcher:

1. Finds the required Cloudflared executable.
2. Starts the Agora session server on port `3001`.
3. Serves the helper page on port `3002`.
4. Creates separate Cloudflare Quick Tunnels for both services.
5. Starts Expo for the development client.
6. Passes the generated URLs to Expo as `EXPO_PUBLIC_AGORA_SESSION_URL` and `EXPO_PUBLIC_HELPER_PAGE_URL` for that process.

Wait until the terminal confirms that the services and tunnels have started. Keep this terminal open while testing.

For later development sessions, if the development build is already installed and native dependencies have not changed, normally only this command is required:

```bash
npm run dev:call
```

A Mac is still required when the iOS native project/dependencies need to be rebuilt, but the normal JavaScript/TypeScript development environment can otherwise be started from a supported development machine with the existing development build installed.

## 7. Test the Ask a Friend call

1. Open the installed WalkBuddy development build.
2. Grant camera and microphone permissions when requested.
3. Open **Ask a Friend** and start a call.
4. Copy or share the generated helper invitation link.
5. Open the link in a browser on the helper's device.
6. Join the session from the helper page.
7. Confirm that both participants can see and hear each other.
8. Test mute/unmute.
9. Test camera switching or camera disabling where supported.
10. End/leave the call and confirm the camera and microphone are released.

## Normal command sequence

### Android — first installation or native dependency change

```powershell
cd software_side\walkbuddy_reactNative\frontend_reactNative
npm run setup:android
npm run dev:call
```

### iOS — first installation or native dependency change

```bash
cd software_side/walkbuddy_reactNative/frontend_reactNative
bash scripts/setup-ios-macos.sh
```

After the native build succeeds, stop its Metro process, then in a new Terminal:

```bash
cd software_side/walkbuddy_reactNative/frontend_reactNative
npm run dev:call
```

If continuing in the same Terminal instead:

```bash
source ~/.bash_profile
npm run dev:call
```

### Normal development session

```bash
npm run dev:call
```

## Environment variables

| Variable | Location | Purpose |
| --- | --- | --- |
| `AGORA_APP_ID` | `agora_session_server/.env` | Identifies the Agora project |
| `AGORA_APP_CERTIFICATE` | `agora_session_server/.env` | Signs RTC access tokens and must remain private |
| `PORT` | `agora_session_server/.env` | Configures the session-server port; normally `3001` |
| `EXPO_PUBLIC_AGORA_SESSION_URL` | Set in the Expo child process by `start-dev.js` | Current public URL for the session server |
| `EXPO_PUBLIC_HELPER_PAGE_URL` | Set in the Expo child process by `start-dev.js` | Current public URL for the helper interface |

The launcher passes the public URLs directly to the Expo process. Cloudflare Quick Tunnel URLs are temporary and can change whenever the development environment restarts.

## Security requirements

- Never commit `agora_session_server/.env`.
- Never expose the Agora App Certificate through an `EXPO_PUBLIC_` variable.
- Do not commit `.env.local`, access tokens, `node_modules`, build output or downloaded tunnel executables.
- Generate RTC access tokens on the backend using the App ID and App Certificate.
- Revoke and replace any credential accidentally exposed or pushed to Git.
- Never store Apple Account or login Keychain passwords in the setup script.

## Troubleshooting

### PowerShell will not run the Android setup script

If direct PowerShell script execution is required, use a process-scoped execution-policy change:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup-android-windows.ps1
```

`-Scope Process` affects only the current PowerShell session.

### `expo` is not recognized

Run Expo through the locally installed package:

```bash
npx expo --version
```

If it didn't work, then do the following:

```bash
npm install
```

### `npm` is not found on macOS after setup

If `setup-ios-macos.sh` has just completed but the parent Terminal does not recognize `npm`, reload the configured shell profile:

```bash
source ~/.bash_profile
```

Alternatively, open a new Terminal and return to `frontend_reactNative`.

### The Agora session URL is not configured

If this appears immediately after the first native iOS build, start the full development environment:

```bash
npm run dev:call
```

Wait for the session server, helper server, Cloudflare tunnels and Expo development server to start before opening/reloading Ask a Friend.

### Repeated macOS `codesign` Keychain dialog

Stop the build and run:

```bash
security set-key-partition-list \
  -S apple-tool:,apple:,codesign: \
  -s \
  "$HOME/Library/Keychains/login.keychain-db"
```

Enter the login Keychain password locally, then rerun:

```bash
bash scripts/setup-ios-macos.sh
```

### Android `spawn C:\Windows\System32\cmd.exe ENOENT`

Check that the `ComSpec` environment variable points to:

```text
C:\Windows\System32\cmd.exe
```

Also confirm `C:\Windows\System32` is included in the Windows `Path`, then restart the development terminal/VS Code.

### Android device is not detected

- Enable Developer Options and USB debugging.
- Unlock the phone and accept its USB debugging prompt.
- Try a USB cable that supports data transfer.
- Run `adb devices` again.
- Restart ADB if required with `adb kill-server` followed by `adb start-server`.

### Native Agora module is missing

The application may be running in Expo Go or using an outdated development build.

For Android, rerun the Android native setup. For iOS, rerun:

```bash
bash scripts/setup-ios-macos.sh
```

Then start normal development with:

```bash
npm run dev:call
```

### Agora joins without audio or video

- Grant camera and microphone permissions on both devices.
- Confirm both participants joined the same channel.
- Ensure participants use the UIDs assigned by the session server.
- Restart the session if its token has expired.
- Check the session-server, Metro, browser and device logs for errors.

## Current development limitations

- Expo Go is not supported because Agora requires native modules.
- iOS native builds require macOS/Xcode.
- Cloudflare Quick Tunnel URLs change between development sessions.
- In-memory sessions disappear when the session server restarts.
- Agora tokens expire and must be regenerated by the server.
- The development setup does not replace production authentication, persistent session storage, monitoring or a permanently deployed HTTPS backend.
