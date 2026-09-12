# WalkBuddy Ask a Friend — Agora Video Calling

The **Ask a Friend** function provides real-time video and two-way audio between a WalkBuddy Android user and a remote helper. It uses Agora RTC, a server-side token service, a browser-based helper interface, and Cloudflare Quick Tunnels for development testing.

## Important requirement

This function does not run in Expo Go because `react-native-agora` contains native Android code. It must be run using the WalkBuddy Expo Development Build.

The current setup supports Android development on Windows.

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
            ├── android/
            ├── app/
            ├── scripts/
            │   ├── setup-android-windows.ps1
            │   └── start-dev.js
            ├── services/
            │   ├── agoraCallService.ts
            │   └── agoraSessionService.ts
            ├── package.json
            └── README.md
```

## Prerequisites

Install the following before running the setup:

- Git
- Node.js and npm
- Android Studio with the Android SDK and platform tools
- JDK 17, such as the JDK bundled with Android Studio
- An Android phone with Developer Options and USB debugging enabled, or an Android emulator
- An Agora project using App ID and App Certificate authentication
- An internet connection the first time `start-dev.js` downloads Cloudflared

Cloudflared does not need to be installed manually. `start-dev.js` uses a global installation when one exists, otherwise uses its cached project copy, and automatically downloads it when neither is available.

## 1. Clone the repository or update your branch

Clone your fork if the repository is not already available:

```powershell
git clone https://github.com/YOUR-USERNAME/AI-Assisted-Navigation-Device.git
cd AI-Assisted-Navigation-Device
```

If it is already cloned, switch to the branch containing the Agora function:

```powershell
git switch feature/agora-video-call
git pull origin feature/agora-video-call
```

## 2. Open the React Native project

All remaining commands should be run from `frontend_reactNative` unless stated otherwise:

```powershell
cd software_side\walkbuddy_reactNative\frontend_reactNative
```

## 3. Configure the Agora session server

On how to obtain credentials for this, please do the following steps:

1. Sign in to the [Agora Console](https://console.agora.io/).

2. Open **Project Management** and select **Create a Project**.

3. Enter a project name, such as `Agora Video Call Prototype`.

4. Select the secured authentication option that uses an **App ID and App Certificate**.

5. Open the project and copy its **App ID**.

6. Enable the primary **App Certificate** if necessary.

7. Copy the App Certificate and keep it private.

Agora may take a few minutes to enable a new certificate.

Create or update:

```text
agora_session_server/.env
```

Add the credentials for the Agora project:

```env
AGORA_APP_ID=your_agora_app_id
AGORA_APP_CERTIFICATE=your_agora_app_certificate
PORT=3001
```

Do not add spaces around the values. The App Certificate must remain on the server and must never be placed in application code or an `EXPO_PUBLIC_` variable.

The server generates Agora RTC tokens automatically. Users do not manually create temporary tokens in the Agora Console.

Install the session server dependencies once after cloning, and whenever its `package.json` changes:

```powershell
cd .\agora_session_server
npm install
cd ..
```

## 4. Install the Agora Session Server Dependencies

The Agora session server is a separate Node.js project with its own `package.json`. It requires its own dependency installation in addition to the main React Native application.

From `frontend_reactNative`, run:

```powershell
cd .\agora_session_server
npm install
cd ..
```

## 5. Run the Windows Android setup script

Connect the Android phone by USB and enable USB debugging. Confirm that Android Debug Bridge can see it:

```powershell
adb devices
```

From `frontend_reactNative`, run:

```powershell
npm run setup:android
```

Follow any prompts displayed by the script. Keep the phone unlocked and accept the USB debugging or application installation prompt if Android displays one.

The setup script copies the frontend source to a shorter build path, installs the frontend dependencies there, verifies or installs `react-native-agora` and `expo-dev-client`, runs `npx expo prebuild`, and installs the Android development build with `npx expo run:android`. It does not download Cloudflared. Let it finish completely before starting the development environment.

Run this setup script only for the initial installation. `expo prebuild --clean` unless the project maintainers specifically require it, because the repository already contains an `android` directory and a clean prebuild can replace native changes.

## 6. Start the complete development environment

After the setup script finishes successfully, remain in `frontend_reactNative` and run:

```powershell
npm run dev:call
```

The development launcher:

1. Detects a global or cached Cloudflared executable, or downloads it automatically.
2. Starts the Agora session server on port `3001`.
3. Serves the helper page on port `3002`.
4. Creates separate Cloudflare Quick Tunnels for both services.
5. Starts Expo with `--dev-client --clear`.
6. Passes the generated URLs to Expo as `EXPO_PUBLIC_AGORA_SESSION_URL` and `EXPO_PUBLIC_HELPER_PAGE_URL` for that process.

Wait until the terminal confirms that the services and tunnels have started. Keep this terminal open while testing the function. Then open the installed WalkBuddy development build on the Android device.

Do not open the project using Expo Go.

For later development sessions, when the development build is already installed and native dependencies have not changed, normally run only:

```powershell
cd software_side\walkbuddy_reactNative\frontend_reactNative
node .\scripts\start-dev.js
```

## 7. Test the Ask a Friend call

1. Open the installed WalkBuddy development build.
2. Grant camera and microphone permissions when requested.
3. Open **Ask a Friend** and start a call.
4. Copy or share the generated helper invitation link.
5. Open the link in a browser on the helper's device.
6. Join the session from the helper page.
7. Confirm that both participants can see and hear each other.
8. Test mute, camera switching or camera disabling, and leaving the call.
9. Confirm that the camera and microphone are released after leaving.

## Normal command sequence

### First installation or native dependency change

```powershell
cd software_side\walkbuddy_reactNative\frontend_reactNative
cd .\agora_session_server
npm install
cd ..
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup-android-windows.ps1
node .\scripts\start-dev.js
```

### Normal development session

```powershell
cd software_side\walkbuddy_reactNative\frontend_reactNative
node .\scripts\start-dev.js
```

## Environment variables

| Variable | Location | Purpose |
| --- | --- | --- |
| `AGORA_APP_ID` | `agora_session_server/.env` | Identifies the Agora project |
| `AGORA_APP_CERTIFICATE` | `agora_session_server/.env` | Signs RTC access tokens and must remain private |
| `PORT` | `agora_session_server/.env` | Configures the session-server port; normally `3001` |
| `EXPO_PUBLIC_AGORA_SESSION_URL` | Set in the Expo child process by `start-dev.js` | Current public URL for the session server |
| `EXPO_PUBLIC_HELPER_PAGE_URL` | Set in the Expo child process by `start-dev.js` | Current public URL for the helper interface |

The launcher does not need to write these public URLs to `.env.local`; it passes them directly to the Expo process. Cloudflare Quick Tunnel URLs are temporary and can change whenever the development environment restarts.

## Security requirements

- Never commit `agora_session_server/.env`.
- Never expose the Agora App Certificate through an `EXPO_PUBLIC_` variable.
- Do not commit `.env.local`, access tokens, `node_modules`, build output, or downloaded tunnel executables.
- Generate RTC access tokens on the backend using the App ID and App Certificate.
- Revoke and replace any credential accidentally pushed to GitHub.


## Troubleshooting

### PowerShell will not run the setup script

Run this in the same PowerShell window and try again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup-android-windows.ps1
```

`-Scope Process` affects only the current PowerShell session.

### Cloudflared is not installed

No manual installation is required. Run `node .\scripts\start-dev.js`; it downloads a project-local copy into `.tools` when no global or cached copy exists. Ensure the computer has internet access and `.tools/` is ignored by Git.

### `expo` is not recognized

Run commands through the locally installed package:

```powershell
npx expo --version
```

If necessary, reinstall project dependencies:

```powershell
npm install
```

### The Agora session URL is not configured

Stop the current processes and run the development launcher again:

```powershell
node .\scripts\start-dev.js
```

Wait for both tunnel URLs to be created and for Expo to start before opening or reloading the Android app. The relevant variable is `EXPO_PUBLIC_AGORA_SESSION_URL` in the supplied `start-dev.js`.

### `spawn C:\Windows\System32\cmd.exe ENOENT`

Check that the `ComSpec` environment variable points to:

```text
C:\Windows\System32\cmd.exe
```

Also confirm that `C:\Windows\System32` is included in the Windows `Path`, then restart VS Code.

### Android device is not detected

- Enable Developer Options and USB debugging.
- Unlock the phone and accept its USB debugging prompt.
- Try a USB cable that supports data transfer.
- Run `adb devices` again.
- Restart the ADB service if required: `adb kill-server`, followed by `adb start-server`.

### Native Agora module is missing

The app is being opened in Expo Go or an outdated development build. Close Expo Go and rerun:

```powershell
.\scripts\setup-android-windows.ps1
```

Then start development with:

```powershell
npm run dev:call
```

### Agora joins without audio or video

- Grant camera and microphone permissions on both devices.
- Confirm both participants joined the same channel.
- Ensure participants use the UIDs assigned by the session server.
- Restart the session if its token has expired.
- Check the session-server, Metro, browser, and Android logs for errors.

## Current development limitations

- The current native development workflow targets Android on Windows.
- Expo Go is not supported.
- Cloudflare Quick Tunnel URLs change between development sessions.
- In-memory sessions disappear when the server restarts.
- Agora tokens expire and must be regenerated by the server.
- The development setup does not replace production authentication, persistent session storage, monitoring, or a permanently deployed HTTPS backend.
