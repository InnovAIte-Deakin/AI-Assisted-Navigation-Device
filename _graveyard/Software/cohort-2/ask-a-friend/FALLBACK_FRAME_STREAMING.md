# Fallback Frame Streaming Implementation

## Overview

This document describes the fallback frame streaming system implemented for the "Ask a Friend" feature. When WebRTC fails (due to ICE issues, network problems, or timing), the system automatically switches to a reliable WebSocket-based frame streaming mode.

## Architecture

### Flow Diagram

```
User Camera → Canvas Capture → JPEG Encoding → WebSocket → Server → Helper Display
```

### Components

1. **User Side (`ask-a-friend-web.tsx`)**
   - Tries WebRTC first
   - Monitors WebRTC connection state
   - Falls back to frame streaming if WebRTC fails
   - Captures frames using HTML5 Canvas at ~8 FPS
   - Encodes frames as JPEG (quality 0.6)
   - Sends frames via WebSocket

2. **Helper Side (`helper-web.tsx`)**
   - Receives WebRTC offer/answer/ICE
   - If WebRTC track not received within 10 seconds, switches to fallback
   - Displays frames using `<img>` element (web) or `<Image>` (React Native)
   - Shows "Fallback mode" indicator in UI

3. **Backend (`main.py`)**
   - Receives frames from user
   - Broadcasts frames to helper in same session
   - Rate limiting: max 10 FPS (100ms interval)
   - Size limit: 500KB per frame

## Fallback Triggers

The system switches to fallback mode when:

1. **WebRTC Timeout**: No video track received within 8 seconds (user side) or 10 seconds (helper side)
2. **ICE Failure**: ICE connection state becomes "failed"
3. **Peer Connection Failure**: WebRTC peer connection state becomes "failed" or "disconnected"
4. **Helper Receives Frames**: If helper receives frames but no WebRTC track, automatically switches

## Frame Streaming Details

### Capture Method
- Uses HTML5 `<canvas>` element to capture frames from `<video>` element
- Canvas size: 640x480 (reasonable for streaming)
- Frame rate: ~8 FPS (125ms interval)
- Encoding: JPEG with quality 0.6 (balance between quality and size)

### Frame Format
```javascript
{
  type: "frame",
  image: "data:image/jpeg;base64,...",  // Base64-encoded JPEG
  session_id: "ABC12345",
  timestamp: "2024-01-01T12:00:00.000Z"
}
```

### Server Processing
- Rate limiting: Drops frames if received faster than 100ms apart
- Size check: Rejects frames larger than 500KB
- Broadcasting: Forwards frames to helper WebSocket in same session

## UI Indicators

### User Side
- **Normal**: "Camera Active - Helper viewing your camera"
- **Connecting**: "Camera Active - Connecting video..."
- **Fallback**: "Camera Active - Fallback mode (frame stream)"
- **Subtext**: "Using reliable frame streaming"

### Helper Side
- **Normal**: "Viewing user's camera"
- **Fallback**: "Viewing user's camera (Fallback mode)"
- **Subtext**: "Using reliable frame streaming"
- **Waiting**: "Waiting for camera feed..."

## Advantages of Fallback Mode

1. **Reliability**: Works even when WebRTC fails (NAT traversal issues, firewall, etc.)
2. **Simplicity**: No complex peer-to-peer negotiation
3. **Compatibility**: Works across different networks and devices
4. **Guaranteed Delivery**: Helper always sees what user sees (even if lower FPS)

## Performance Considerations

- **Frame Rate**: 8 FPS is sufficient for navigation assistance (not real-time video)
- **Quality**: JPEG quality 0.6 balances quality and bandwidth
- **Bandwidth**: ~50-100 KB/s per frame stream (depends on scene complexity)
- **Latency**: ~200-500ms (frame capture + encoding + network + display)

## Code Locations

### User Side
- Frame capture: `ask-a-friend-web.tsx` → `startFrameStreaming()`
- Fallback activation: `ask-a-friend-web.tsx` → `activateFallbackMode()`
- WebRTC monitoring: `ask-a-friend-web.tsx` → `startWebRTC()`

### Helper Side
- Frame display: `helper-web.tsx` → Camera display section
- Fallback detection: `helper-web.tsx` → Message handlers
- WebRTC timeout: `helper-web.tsx` → `handleWebRTCOffer()`

### Backend
- Frame forwarding: `main.py` → WebSocket handler → `frame` message type
- Rate limiting: `main.py` → `MIN_FRAME_INTERVAL_MS` (100ms)

## Testing

To test fallback mode:

1. **Force WebRTC Failure**:
   - Block STUN servers in firewall
   - Use different networks (user and helper on different NATs)
   - Wait 8-10 seconds after connection

2. **Verify Fallback**:
   - User UI shows "Fallback mode (frame stream)"
   - Helper UI shows "Viewing user's camera (Fallback mode)"
   - Frames update at ~8 FPS
   - Console logs show frame capture/transmission

3. **Verify Recovery**:
   - If WebRTC recovers, system switches back automatically
   - User UI updates to "Helper viewing your camera"
   - Helper UI updates to "Viewing user's camera"

## Future Improvements

1. **Adaptive Quality**: Adjust JPEG quality based on network conditions
2. **Frame Skipping**: Skip frames if helper is slow to process
3. **Compression**: Use more efficient codecs (WebP, AVIF)
4. **Buffering**: Add frame buffer for smoother playback
5. **Metrics**: Track fallback usage and performance
