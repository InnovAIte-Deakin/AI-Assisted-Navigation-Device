# Nearby Obstacle Alert Testing Notes

## Feature Tested
Nearby obstacle voice and vibration alert in CameraNavigationActivity.

## Purpose
The purpose of this feature is to improve accessibility for visually impaired users by providing non-visual feedback when an object is detected close to the camera.

## Changes Tested
- Added Android VIBRATE permission in AndroidManifest.xml.
- Added nearby obstacle detection logic using bounding box size.
- Added voice warning through TTSAnnouncer.
- Added vibration feedback using Android Vibrator.
- Added timing control to reduce repeated warning announcements.

## Test Cases

| Test Case | Action | Expected Result | Current Result | Status |
|---|---|---|---|---|
| Camera navigation screen | Open CameraNavigationActivity | Camera screen opens | App reached install/run stage | In Progress |
| Object detection | Point camera at object | Object label appears on screen | Detection logic implemented | In Progress |
| Nearby object alert | Move object close to camera | Voice warning is spoken | Alert logic added in code | In Progress |
| Vibration feedback | Nearby object detected | Device vibrates | Vibration method added | In Progress |
| Repeated warning control | Keep object in frame | Alerts should not repeat too quickly | Timing control added | Pass in code review |

## Current Testing Result
The app built and reached the emulator installation stage. The emulator installation failed because of insufficient emulator storage, not because of a code error.

## Remaining Work
Further testing will be completed after wiping emulator data or using a physical Android device. The nearby object threshold may also be adjusted if alerts trigger too early or too late during practical testing.