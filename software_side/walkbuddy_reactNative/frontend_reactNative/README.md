# Frontend — WalkBuddy

The frontend is a React Native app built with Expo Router. It is the user-facing layer of WalkBuddy: it captures camera frames for detection, speaks guidance via TTS, lets the user ask voice questions, streams audiobooks, navigates indoors and outdoors, and connects users to sighted guides via Ask-a-Friend.

---

## Postmortem — Last Trimester

Last trimester produced a visually complete app but left a series of silent breakages at the integration boundary with the backend. The app compiles, runs, and looks functional — but several features fail at runtime in ways that are not immediately visible.

- **The API client calls endpoints that do not exist.** `src/api/client.ts` exports two functions used for AI inference: `detectObject()` posts to `/detect` and `askTwoBrain()` posts to `/two_brain`. Neither endpoint exists on the backend — the real routes are `/vision`, `/ocr`, and `/chat`. These functions have never successfully reached the backend. The camera screen (`app/(tabs)/camera.tsx`) works around this by calling `fetch` directly against the correct endpoints, but `client.ts` itself is broken and any screen that imports from it for inference will silently fail.

- **The expected response shape in `client.ts` does not match what the backend returns.** `SlowLaneResponse` in `client.ts` expects `{ events, answer, safe, source }`. The backend's `/chat` endpoint returns `{ response }`. The backend's `/vision` endpoint returns `{ detections, guidance_message, image_id }`. These shapes are completely misaligned. The types were written against a planned API that was never implemented.

- **Native STT sends audio to an endpoint that does not exist.** `STTService.ts` records audio via `expo-av` on native (iOS/Android) and uploads the file to `${API_BASE}/stt/transcribe`. This endpoint does not exist on the backend. Every native voice command attempt ends with a server error after the recording completes. Web STT works because it uses the browser's `SpeechRecognition` API directly and never calls the backend.

- **Screen Reader was never implemented.** `app/(tabs)/index.tsx` has an `ActionTile` labelled `SCREEN READER` that calls `goToScreenReader()`. That function shows an alert: `"Screen Reader is not implemented yet."` It has been in this state since the trimester began. The tile exists in the UI, gives the impression of a feature, and does nothing.

- **The helper web interface references auth endpoints that do not exist.** `app/helper-web.tsx` has a full signup and login form with fields for name, age, email, phone, address, emergency contact, experience level, and password. These forms post to auth endpoints (login, register, delete account) that the backend does not implement. A sighted guide attempting to sign up through the web interface will always get a failure.

- **The user greeting is hardcoded.** `app/(tabs)/index.tsx` renders `"Hi Daniel"` unconditionally. The `SessionContext` has an auth state with `displayName` available but the home screen does not read it.

The common thread: UI was built ahead of the backend contract, and the gaps were never closed. The coordination guidelines below are designed to close them before they accumulate further.

---

## Collaboration & Integration Guidelines

The full contribution workflow — opening a GitHub issue with the right label, updating the [AIAND Progress Tracker](https://docs.google.com/spreadsheets/d/1NogkKQmUfVSwdF_XZ5LVf-zvVt_XMrCdbr67mCDDbcI/edit?usp=sharing), notifying the team on Microsoft Teams, and opening a PR — is documented in the [root README](../../../../README.md#how-we-work). The rules below are specific to the frontend integration contract.

### API Contract Rules

The backend README is the canonical source for all endpoint names, request shapes, and response shapes. Read it before writing any `fetch` call.

- **`src/api/client.ts` is the single place for typed backend calls.** Any direct `fetch` scattered across screen files is harder to find and fix when the backend changes. The goal is to move all backend calls into `client.ts` with correct typings matching the backend README. When you add a backend call, add it to `client.ts` first.
- **Align types with the actual backend response, not a planned one.** Before writing an interface for a response, read the endpoint's documented response in the backend README. Do not assume field names.
- **When the backend changes an endpoint, update `client.ts` and the relevant screens in the same PR.** Endpoint changes are invisible at compile time in TypeScript unless the types are kept aligned.
- **Use `EXPO_PUBLIC_API_BASE` for all non-local testing.** Never hardcode a new IP address. The existing fallback `172.20.10.2:8000` is a developer's personal hotspot — it should be treated as a last resort, not a default.

### Ownership & Storage

| Artifact | Location | Notes |
|---|---|---|
| API base URL | `src/config.ts` | Single source — never hardcode elsewhere |
| Persistent user data (favorites, history) | `AsyncStorage` via `src/utils/audiobookStorage.ts` | Keys prefixed with `@audiobooks_` |
| Auth state | `SessionContext` (`app/SessionContext.tsx`) | In-memory only — resets on app restart |
| Location state | `CurrentLocationProvider` (`app/lib/locationSaver.tsx`) | GPS-driven, in-memory |

### Collaboration Rules

- Read the Postmortem before touching `client.ts`, `STTService.ts`, or `helper-web.tsx` — these are the three most likely places to reintroduce old mistakes
- New screens that call the backend must use `client.ts` typed functions, not raw `fetch` calls
- Any new feature that touches the API must be checked against the backend README's API Reference before implementation
- Do not add UI tiles or entry points for features that are not yet implemented — the Screen Reader tile is the existing example of why this creates confusion

---

## Architecture

```
app/
├── _layout.tsx              Root stack — wraps entire app in SessionProvider + CurrentLocationProvider
│                            Stack screens: (tabs), modal
│
└── (tabs)/
    ├── _layout.tsx          Tab bar (rendered by custom Footer component)
    │
    ├── index.tsx            Home
    ├── audiobooks.tsx       Audiobooks browse
    ├── ask-a-friend-web.tsx Ask-a-Friend (user side)
    ├── camera.tsx           Camera / VISION / OCR
    ├── indoor.tsx           Indoor navigation
    ├── exterior.tsx         Outdoor navigation
    ├── profile.tsx          Profile
    ├── places.tsx           Saved places
    └── explore.tsx          Explore (scaffolded)

Stack routes (non-tab, accessible via router.push):
  /search                   Destination search
  /navigate                 Navigation assistant
  /location-map             Map view
  /interiorNav              Indoor navigation detail
  /audiobooks-player        Playback screen
  /audiobooks-favourites    Saved audiobooks
  /audiobooks-history       Listening history
  /audiobooks-listen-later  Watch list
  /settings                 App settings
  /helper-web               Guide-side web interface

src/
├── api/
│   └── client.ts           Typed backend API functions (partially broken — see Postmortem)
├── config.ts               API_BASE resolution
├── services/
│   ├── TTSService.ts       Text-to-speech (expo-speech / Web Speech API)
│   └── STTService.ts       Speech-to-text (Web Speech API / expo-av + /stt/transcribe)
├── nav/
│   ├── v2_graph.ts         Indoor map graph (15 nodes, Deakin Library)
│   ├── astar.ts            A* pathfinding (not used — indoor.tsx uses Dijkstra inline)
│   └── guidance.ts         Turn-by-turn guidance text generation
├── utils/
│   ├── audiobookStorage.ts AsyncStorage CRUD for favorites/history/listen-later
│   ├── collaboration.ts    WebSocket client for Ask-a-Friend sessions
│   ├── routingApi.ts       OSRM routing calls
│   ├── geocoding.ts        Geocoding utility
│   ├── autocomplete.ts     Place name autocomplete
│   ├── navigationHelpers.ts GPS step advancement, route snapping
│   ├── routing.ts          Route calculation helpers
│   ├── settings.ts         Navigation settings load/save
│   ├── webCameraCapture.ts Web camera stream capture for Ask-a-Friend
│   └── webTTS.ts           Web Speech API TTS wrapper (used by Ask-a-Friend)
└── types/
    └── navigation.ts       Shared navigation types (Location, Route, RouteStep)
```

**State providers at root:**

| Provider | File | What it provides |
|----------|------|-----------------|
| `SessionProvider` | `app/SessionContext.tsx` | Auth state: `loggedOut`, `loggedInNoProfile`, `loggedInWithProfile` |
| `CurrentLocationProvider` | `app/lib/locationSaver.tsx` | GPS location string, destination, route key, header toggle preference |

All other state is local to individual screens via `useState` and `useRef`.

---

## Screen Inventory

### Tab Screens

#### Home (`app/(tabs)/index.tsx`)

Entry point. Four action tiles in a 2×2 grid:

| Tile | Label | Action |
|------|-------|--------|
| Microphone | VOICE ASSIST | Pushes to `/camera` with `{ mode: "voice" }` |
| Map marker | PLACES | Pushes to `/places` |
| Volume | SCREEN READER | Shows "not implemented" alert |
| File text | TEXT READER | Pushes to `/camera` with `{ mode: "ocr" }` |

Vision Assist section below the grid: toggle switch enables/disables the feature; tapping the preview card loads a `ModelWebView` pointing at `${API_BASE}/vision/?v=${rev}`.

**Known gap:** Greeting is hardcoded to `"Hi Daniel"` — `SessionContext` profile is not read.

---

#### Camera (`app/(tabs)/camera.tsx`)

The primary AI interface. Two modes:

| Mode | Label | Endpoint | Behaviour |
|------|-------|----------|-----------|
| `vision` | Vision | `POST /vision` | YOLO detection, bbox overlay, guidance message spoken |
| `ocr` | Scan Text | `POST /ocr` | OCR detection, text displayed in panel, spoken |

**Auto-scan loop:** Starts automatically on permission grant (250ms delay). Fires every 2,500ms. Each tick calls `captureAndDetect()` — takes a photo at quality 0.5, builds `multipart/form-data`, posts to the appropriate endpoint, renders bbox overlays, and speaks the `guidance_message` via `TTSService`.

**Voice input:** Hold-to-speak mic button. On web: `SpeechRecognition` stream with interim results. On native: `expo-av` recording → POST to `/stt/transcribe` (which does not exist — see Known Gaps). Final transcript is checked for voice commands first (`"scan text"`, `"vision"`, `"start scan"`, `"stop scan"`); if not a command, it's sent to `POST /chat`.

**Dedup TTS:** `maybeSpeak()` suppresses the same message within 2,500ms to prevent repetition during continuous scanning.

**Note:** This screen calls `/vision`, `/ocr`, and `/chat` directly via `fetch` — it does not use `src/api/client.ts`.

---

#### Audiobooks (`app/(tabs)/audiobooks.tsx`)

LibriVox browse interface.

- Debounced search (500ms) sends `GET /audiobooks/search?q=...` with optional `language`, `genre`, `min_duration`, `max_duration`, `sort`, `limit` filters
- Filter state managed by `FilterBar` and `FilterModal` components
- Results rendered in a `FlatList`; covers loaded from `cover_url`
- Favorites and listen-later persisted via `audiobookStorage.ts` (AsyncStorage)
- Tapping a result pushes to `/audiobooks-player` with book metadata as params

---

#### Ask-a-Friend (`app/(tabs)/ask-a-friend-web.tsx`)

User-side of the live assistance feature.

1. App calls `POST /collaboration/create-session` to get an 8-character session code
2. User shares the code with a sighted guide
3. Guide opens `helper-web.tsx` and enters the code
4. Both connect via `WS /collaboration/ws/{session_id}/{role}`
5. WebRTC offer/answer/ICE messages are relayed through the backend WS
6. If WebRTC negotiation fails, falls back to periodic base64 frame streaming (`type: "frame"` messages)
7. Guide's audio arrives via WebRTC audio track; text guidance via `type: "guidance"` WS messages, spoken by `webTTS.ts`

Platform notes: camera uses `getUserMedia` (web only). On native, camera capture falls back to frame streaming mode.

---

#### Indoor Navigation (`app/(tabs)/indoor.tsx`)

Step-by-step indoor routing for Deakin Library.

- Graph: 15 named nodes (`V2_GRAPH` in `src/nav/v2_graph.ts`)
- Pathfinding: Dijkstra implemented inline in the screen (not the `astar.ts` module)
- Edge weights are in steps (relative, not meters)
- Route steps are spoken via `expo-speech` as the user advances
- User advances manually (tap button) — no GPS integration

POIs:
`Main Entrance`, `Exit`, `Help Desk`, `Display Area`, `Book Returns`, `Printing Area`, `Computer Zone`, `Quiet Study Area`, `Male Toilets`, `Female Toilets`, `Accessible Toilet`, `Lift`, `Staircase`, `Meeting Rooms`, `Office Area`

**Known gap:** Graph is hardcoded to one building. No map rendering — navigation is text-only.

---

#### Exterior Navigation (`app/(tabs)/exterior.tsx`)

GPS-based outdoor turn-by-turn navigation.

- Geocoding: `src/utils/geocoding.ts`
- Autocomplete: `src/utils/autocomplete.ts`
- Routing: OSRM via `src/utils/routingApi.ts` (`fetchRoute`)
- Map: `MapPanel` component (`src/components/MapPanel`)
- GPS tracking: `expo-location` watcher
- Step advancement: `src/utils/navigationHelpers.ts` (`updateStepIndex`, `snapToRoute`, `shouldAdvanceStep`)
- Voice input: `expo-speech-recognition` (`ExpoSpeechRecognitionModule`, `useSpeechRecognitionEvent`)
- Spoken guidance: `expo-speech` directly (not via `TTSService`)

---

#### Profile (`app/(tabs)/profile.tsx`)

User profile and account settings. Reads from `SessionContext`. Links to `/settings`.

---

#### Places (`app/(tabs)/places.tsx`)

Saved locations. Managed via `CurrentLocationProvider`.

---

### Stack Screens

| Route | File | Purpose |
|-------|------|---------|
| `/audiobooks-player` | `app/audiobooks-player.tsx` | Full player with expo-av, progress bar, playback controls |
| `/audiobooks-favourites` | `app/audiobooks-favourites.tsx` | Reads favorites from AsyncStorage |
| `/audiobooks-history` | `app/audiobooks-history.tsx` | Reads history from AsyncStorage |
| `/audiobooks-listen-later` | `app/audiobooks-listen-later.tsx` | Reads listen-later list from AsyncStorage |
| `/search` | `app/search.tsx` | Destination search input |
| `/navigate` | `app/navigate.tsx` | Navigation assistant |
| `/location-map` | `app/location-map.tsx` | Map view |
| `/interiorNav` | `app/interiorNav.tsx` | Indoor navigation detail |
| `/settings` | `app/settings.tsx` | App settings (navigation preferences via `src/utils/settings.ts`) |
| `/helper-web` | `app/helper-web.tsx` | Guide-side interface (web-only, auth broken — see Known Gaps) |

### Category Screens (Audiobook Genres)

Standalone screens for genre browsing: `/geography`, `/history`, `/kids`, `/quietstudyroom`, `/helpdesk`, `/IT`, `/SCI-FI`, `/FinanceScreen`. These exist as navigation targets from audiobooks-related flows.

---

## Services

### TTSService (`src/services/TTSService.ts`)

Cross-platform text-to-speech with anti-spam logic.

**Platform behaviour:**
- Web: `window.speechSynthesis` (Web Speech API). Handles `voiceschanged` async loading, suppresses Chrome's `"canceled"`/`"interrupted"` errors.
- Native: `expo-speech` with `onDone`/`onStopped`/`onError` callbacks.

**Anti-spam rules (same logic as backend `tts_service.py`, independently implemented):**
1. Cooldown: default 3 seconds between any two messages. Bypassed if risk level increases.
2. Dedup: identical message hash suppressed unless risk level increased.
3. Force flag bypasses all checks.

**Config:** `cooldownSeconds`, `language` (BCP-47), `pitch`, `rate`, `volume`.

**Singleton:** `getTTSService(config?)` — first call creates with the provided config, subsequent calls return the same instance regardless of config argument. The camera screen overrides cooldown to 1.2s on first use.

`RiskLevel` enum is exported from this module and used by the camera screen for risk-based TTS gating: `CLEAR=0`, `LOW=1`, `MEDIUM=2`, `HIGH=3`, `CRITICAL=4`.

---

### STTService (`src/services/STTService.ts`)

Cross-platform speech-to-text.

**Platform behaviour:**
- Web: `window.SpeechRecognition` / `webkitSpeechRecognition`. Streaming with interim results. Fully functional.
- Native: `expo-av` audio recording (HIGH_QUALITY preset) → POST `multipart/form-data` to `${API_BASE}/stt/transcribe`. **This endpoint does not exist on the backend.** Every native transcription attempt returns a server error.

**Validation:** Minimum recording duration 700ms; minimum file size 10,000 bytes. Short or empty recordings are rejected before upload.

**Singleton:** `getSTTService(config?)`.

---

### API Client (`src/api/client.ts`)

Currently exports three functions:

| Function | Calls | Status |
|----------|-------|--------|
| `fetchStatus()` | `GET /docs` | Works (health proxy) |
| `detectObject(imageBlob)` | `POST /detect` | **Broken** — endpoint doesn't exist (should be `/vision`) |
| `askTwoBrain(imageBlob, question)` | `POST /two_brain` | **Broken** — endpoint doesn't exist |

The `SlowLaneResponse` type expects `{ events, answer, safe, source }` — this shape does not match any backend response.

The camera screen bypasses this module entirely and calls `/vision`, `/ocr`, and `/chat` directly with inline `fetch`. `client.ts` needs to be rebuilt to match the real API contract before any other screen should import from it.

---

### Collaboration Client (`src/utils/collaboration.ts`)

WebSocket session management for Ask-a-Friend.

- `normalizeCode(code)` — trims and uppercases session ID
- `roomFor(code)` — constructs `askafriend:{CODE}` room key (used internally)
- `collaborationService` — wraps WebSocket connect/disconnect and message dispatch

Message types are typed as `CollaborationMessage` with `type`, `role`, `image`, `text`, `audio`, `sdp`, `candidate`. Matches the backend WS protocol documented in the backend README.

---

## State Management

| Scope | Mechanism | Where |
|-------|-----------|-------|
| Auth state | `SessionContext` (React Context) | `app/SessionContext.tsx` — wraps entire app |
| GPS & destination | `CurrentLocationProvider` (React Context) | `app/lib/locationSaver.tsx` — wraps entire app |
| Audiobook library | AsyncStorage | `src/utils/audiobookStorage.ts` — keys: `@audiobooks_favorites`, `@audiobooks_history`, `@audiobooks_listen_later` |
| Per-screen UI state | `useState` / `useRef` | Local to each screen |
| Settings | AsyncStorage | `src/utils/settings.ts` |

There is no global UI state management (no Redux, Zustand, or similar). Each screen is self-contained. Cross-screen coordination (e.g., the camera screen writing to memory that the chat screen reads) happens entirely on the backend via `NavigationMemory` — the frontend has no shared detection state.

---

## Known Gaps

**Critical**

- **`client.ts` calls wrong endpoints.** `detectObject()` → `/detect` (should be `/vision`). `askTwoBrain()` → `/two_brain` (no backend equivalent). The types in `client.ts` also don't match backend response shapes. Any screen importing these functions for inference will fail silently. The camera screen currently avoids this by using raw `fetch` directly.

- **Native STT is broken.** `STTService.ts` on iOS/Android uploads audio to `${API_BASE}/stt/transcribe`. This endpoint does not exist on the backend. Voice commands on native will always fail after the user finishes recording. Web voice commands work because they use the browser `SpeechRecognition` API.

**Moderate**

- **Screen Reader is not implemented.** The SCREEN READER tile on the home screen shows an alert: `"Screen Reader is not implemented yet."`. This has been the state since the feature was added to the UI. There is no code path beyond the alert.

- **Helper web auth is broken.** `helper-web.tsx` has a full signup/login form that calls auth endpoints (login, register, delete account) that do not exist on the backend. A guide cannot successfully register or log in through this interface.

- **User greeting is hardcoded.** `app/(tabs)/index.tsx` renders `"Hi Daniel"`. The `SessionContext` contains the user's `displayName` but the home screen does not read it.

- **Indoor graph is not generalizable.** `V2_GRAPH` is hardcoded to 15 nodes representing a specific Deakin Library floor. Adding a new building requires editing the source file. There is no dynamic loading, no admin interface, and no map rendering — navigation is text-only.

- **`astar.ts` is unused.** `src/nav/astar.ts` implements A* pathfinding. The indoor screen uses Dijkstra implemented inline instead. One of these should be removed.

**Minor**

- **`API_BASE` hardcoded fallback.** `172.20.10.2:8000` is a specific developer's personal hotspot IP. It breaks on any other network. The `EXPO_PUBLIC_API_BASE` env var is the correct path.

- **TTS singleton config is set on first call only.** `getTTSService()` ignores the `config` argument after the first instantiation. The camera screen passes `{ cooldownSeconds: 1.2 }` on first mount. If another screen calls `getTTSService()` with different config first, the camera gets the wrong cooldown.

- **`explore` tab is scaffolded but empty.** It exists in `(tabs)/_layout.tsx` and appears in the tab bar but has no meaningful content.

- **No global error boundary.** Unhandled promise rejections or render errors in any screen will crash the entire app without a fallback UI.

---

## Future Directions

### Tier 1 — Fix What Is Broken

- **Rebuild `client.ts` to match the real API.** Replace `detectObject`/`askTwoBrain` with typed wrappers for `POST /vision`, `POST /ocr`, and `POST /chat` using the response shapes from the backend README. Update the camera screen to use these typed functions. This fixes the contract mismatch and makes all backend calls type-safe.

- **Fix native STT or remove the fallback.** Either implement `POST /stt/transcribe` on the backend (Whisper or equivalent), or drop the native recording path and rely on `expo-speech-recognition` (which the exterior screen already uses successfully). Using `expo-speech-recognition` on the camera screen would eliminate the dependency on a non-existent endpoint.

- **Use `SessionContext` in the home screen.** Read `profile.displayName` and display it instead of `"Hi Daniel"`. Conditional rendering for logged-out state.

### Tier 2 — Quality Improvements

- **Either implement Screen Reader or remove the tile.** A tile that shows "not implemented" damages the credibility of the app for demos. Remove it until the feature is built, or implement it — the most accessible version would use the accessibility APIs to describe visible screen elements.

- **Fix `helper-web.tsx` auth.** Implement the missing auth endpoints on the backend (or scope down — a simple name-entry flow with no signup would be a smaller, working alternative to the current broken form).

- **Refactor indoor navigation to use the existing `astar.ts`.** Delete the inline Dijkstra in `indoor.tsx`, use `src/nav/astar.ts`, and move graph definition to a separate config file that can be updated without touching screen code. This also enables rendering the graph as a visual map.

- **Consolidate TTS usage in exterior navigation.** The exterior screen calls `expo-speech` directly rather than using `TTSService`. This means it bypasses all anti-spam logic. Moving it to `TTSService` makes TTS behaviour consistent across the app.

### Tier 3 — Architectural Improvements

- **Add a shared error boundary.** Wrap the root layout in an error boundary that catches render errors and shows a recovery UI. This prevents crashes from taking down the entire app.

- **Generalise the indoor graph.** Load the graph from a JSON config file rather than hardcoding it in `v2_graph.ts`. This allows adding new buildings without a code change. Long-term, the graph could be fetched from the backend.

- **Implement on-device inference (TFLite).** The ML side has exported `best.tflite` and `best_float16.tflite`. Integrating these into the app via a TFLite library would remove the need for the backend `/vision` round-trip — critical for low-connectivity navigation use. This would reduce camera-to-guidance latency significantly.

- **Add global state for detections.** Currently the camera screen writes detections to a backend memory buffer, and the chat screen reads them back via the LLM. An in-app detection store (e.g. Zustand slice) would allow other screens to react to recent detections without a network round-trip — useful for the indoor navigation screen surfacing real-time obstacles.

---

## Directory Structure

```
frontend_reactNative/
├── app/
│   ├── _layout.tsx                     Root stack + providers (SessionProvider, CurrentLocationProvider)
│   ├── SessionContext.tsx              Auth state context (loggedOut | loggedInNoProfile | loggedInWithProfile)
│   ├── Footer.tsx                      Custom tab bar component
│   ├── HomeHeader.tsx                  Header with greeting, location, profile button
│   ├── (tabs)/
│   │   ├── _layout.tsx                 Tab definitions (Footer as tabBar)
│   │   ├── index.tsx                   Home — action tiles, vision preview toggle
│   │   ├── camera.tsx                  Camera — vision/OCR modes, scan loop, voice input
│   │   ├── audiobooks.tsx              Audiobooks browse — LibriVox search + filters
│   │   ├── ask-a-friend-web.tsx        Ask-a-Friend user side — WebRTC + WS
│   │   ├── indoor.tsx                  Indoor navigation — Dijkstra on V2_GRAPH
│   │   ├── exterior.tsx                Outdoor navigation — OSRM + GPS + MapPanel
│   │   ├── profile.tsx                 User profile
│   │   ├── places.tsx                  Saved locations
│   │   └── explore.tsx                 Explore (scaffolded)
│   ├── audiobooks-player.tsx           Playback screen (expo-av)
│   ├── audiobooks-favourites.tsx       Favorites list (AsyncStorage)
│   ├── audiobooks-history.tsx          History list (AsyncStorage)
│   ├── audiobooks-listen-later.tsx     Watch list (AsyncStorage)
│   ├── search.tsx                      Destination search
│   ├── navigate.tsx                    Navigation assistant
│   ├── location-map.tsx                Map view
│   ├── interiorNav.tsx                 Indoor navigation detail
│   ├── settings.tsx                    App settings
│   ├── helper-web.tsx                  Guide-side interface (web, auth broken)
│   ├── lib/
│   │   ├── locationSaver.tsx           CurrentLocationProvider — GPS + destination context
│   │   ├── liveLocation.tsx            Live location utilities
│   │   └── favourites.tsx              Favourites helpers
│   ├── geography.tsx                   Audiobook genre screen
│   ├── history.tsx                     Audiobook genre screen
│   ├── kids.tsx                        Audiobook genre screen
│   ├── quietstudyroom.tsx              Audiobook category screen
│   ├── helpdesk.tsx                    Audiobook category screen
│   ├── IT.tsx                          Audiobook category screen
│   ├── SCI-FI.tsx                      Audiobook genre screen
│   └── FinanceScreen.tsx               Audiobook category screen
│
├── src/
│   ├── api/
│   │   └── client.ts                   Typed backend functions (broken — see Known Gaps)
│   ├── config.ts                       API_BASE: env override → LAN IP → 172.20.10.2:8000
│   ├── components/
│   │   ├── ModelWebView.tsx            WebView embedding vision preview iframe
│   │   ├── MapPanel.tsx                Map component used by exterior navigation
│   │   ├── FilterBar.tsx               Audiobook filter controls
│   │   ├── FilterModal.tsx             Audiobook filter modal
│   │   └── UserGuideModal.tsx          Audiobook user guide overlay
│   ├── services/
│   │   ├── TTSService.ts               TTS: expo-speech (native) / speechSynthesis (web), anti-spam
│   │   └── STTService.ts               STT: SpeechRecognition (web) / expo-av + /stt/transcribe (native, broken)
│   ├── nav/
│   │   ├── v2_graph.ts                 Indoor graph — 15 POIs, Deakin Library
│   │   ├── astar.ts                    A* implementation (not used by indoor screen)
│   │   └── guidance.ts                 Turn-by-turn text generation
│   ├── utils/
│   │   ├── audiobookStorage.ts         AsyncStorage CRUD — favorites/history/listen-later
│   │   ├── collaboration.ts            WebSocket client — Ask-a-Friend session management
│   │   ├── routingApi.ts               OSRM route fetch
│   │   ├── geocoding.ts                Place name → coordinates
│   │   ├── autocomplete.ts             Place name suggestions
│   │   ├── navigationHelpers.ts        GPS step advancement, route snapping, distance calc
│   │   ├── routing.ts                  Route calculation utilities
│   │   ├── settings.ts                 Navigation settings (AsyncStorage)
│   │   ├── webCameraCapture.ts         getUserMedia frame capture for Ask-a-Friend
│   │   ├── webTTS.ts                   speechSynthesis wrapper for Ask-a-Friend
│   │   └── api.ts                      Misc API utilities
│   └── types/
│       └── navigation.ts               Location, Route, RouteStep types
│
├── components/                         Shared component directory (FilterBar, FilterModal, UserGuideModal)
├── hooks/
│   └── use-color-scheme.ts            Dark/light mode hook
├── package.json
├── tsconfig.json
└── app.json                            Expo config (app name, slug, icon, splash)
```

---

## Setup

```bash
cd software_side/walkbuddy_reactNative/frontend_reactNative
npm install

# LAN (device and backend on the same network)
npm run dev

# Tunnel (backend behind Cloudflare/ngrok)
npm start
```

Set `EXPO_PUBLIC_API_BASE` in a `.env.local` file if the backend is not on the same LAN.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EXPO_PUBLIC_API_BASE` | (none) | Backend URL override. Takes precedence over all auto-detection. Set for any deployment beyond local LAN. |
