# Exterior Navigation Setup Guide

## Overview
The exterior navigation feature is now fully implemented with production-ready features including real routing API integration, destination input, route recalculation, milestone announcements, and ETA calculation.

## Features Implemented

### ✅ 1. Real Routing API Integration
- **Backend Endpoint**: `/api/routing` in `backend/main.py`
- **API Provider**: OpenRouteService (with fallback to mock routes)
- **Frontend Integration**: `src/utils/routingApi.ts`
- **Supports**: Walking, driving, and cycling profiles

### ✅ 2. Destination Input/Selection UI
- Modal dialog for entering destination coordinates
- Optional destination name
- Edit destination button in header when navigating
- Input validation

### ✅ 3. Route Recalculation on Deviation
- Automatically detects when user deviates >50m from route
- Recalculates route from current position
- Prevents excessive recalculations (10-second cooldown)

### ✅ 4. Distance Milestone Announcements
- Announces at 200m, 100m, and 50m before turn
- Respects voice settings toggle
- Prevents duplicate announcements

### ✅ 5. ETA Calculation and Display
- Real-time ETA based on remaining distance
- Walking speed: ~1.4 m/s
- Updates as user progresses
- Displayed in instruction card

## Setup Instructions

### Option 1: Use OpenRouteService (Recommended for Production)

1. **Get API Key**:
   - Sign up at https://openrouteservice.org/
   - Get your free API key from the dashboard

2. **Set Environment Variable**:
   ```bash
   # In your backend directory
   export ORS_API_KEY="your_api_key_here"
   
   # Or create a .env file in backend/
   echo "ORS_API_KEY=your_api_key_here" > backend/.env
   ```

3. **Install httpx** (if not already installed):
   ```bash
   pip install httpx==0.27.0
   ```

### Option 2: Use Mock Routes (Default)

If no API key is set, the system automatically falls back to mock routes. This is perfect for:
- Development and testing
- UI/UX testing
- Offline scenarios

## Usage

1. **Access Exterior Navigation**:
   - Via tab: "Exterior" tab in bottom navigation
   - Via Quick Nav: "Exterior Navigation" button

2. **Set Destination**:
   - Tap "DESTINATION" button
   - Enter latitude and longitude
   - Optionally add a name
   - Tap "Confirm"

3. **Start Navigation**:
   - Tap "START" button
   - Route will be fetched (from API or mock)
   - GPS tracking begins automatically

4. **During Navigation**:
   - Map shows current location and route
   - Instruction card shows current step
   - ETA updates in real-time
   - Voice announcements at milestones
   - Automatic route recalculation on deviation

5. **Stop Navigation**:
   - Tap "STOP" button
   - GPS tracking stops
   - Route cleared

## Settings

Access via **My Account** → **Navigation Settings**:
- **Show Map Visuals**: Toggle map display (default: ON)
- **Voice Instructions**: Toggle voice announcements (default: ON)

## API Endpoints

### Backend: `/api/routing`
**Method**: POST  
**Body**:
```json
{
  "origin": [lng, lat],
  "destination": [lng, lat],
  "profile": "foot-walking"  // or "driving-car", "cycling-regular"
}
```

**Response**: OpenRouteService format (GeoJSON)

## Testing

### Test with Mock Routes
1. Don't set `ORS_API_KEY`
2. Start navigation with any coordinates
3. System will use mock route generator

### Test with Real API
1. Set `ORS_API_KEY` environment variable
2. Start navigation
3. Route will be fetched from OpenRouteService

## Troubleshooting

### Route Not Loading
- Check backend is running on port 8000
- Check `API_BASE` in `src/config.ts`
- Check browser console for errors

### No Voice Announcements
- Check "Voice Instructions" is enabled in Settings
- Check device volume
- Check browser permissions for audio

### Route Recalculation Not Working
- Ensure GPS is enabled
- Check location permissions
- Deviation threshold is 50m (adjustable in code)

## Future Enhancements

Potential improvements:
- Geocoding (address to coordinates)
- Saved destinations/favorites
- Route alternatives
- Offline map caching
- Custom waypoints
- Route sharing

## Files Modified/Created

### Backend
- `backend/main.py` - Added `/api/routing` endpoint
- `backend/requirements.txt` - Added `httpx`

### Frontend
- `app/(tabs)/exterior.tsx` - Complete rewrite with all features
- `src/utils/routingApi.ts` - New routing API client
- `src/components/MapPanel.tsx` - Map display component
- `src/utils/settings.ts` - Settings storage
- `src/types/navigation.ts` - Type definitions
- `src/utils/routing.ts` - Routing utilities

## Notes

- The system gracefully falls back to mock routes if API is unavailable
- All features work with or without API key
- Voice announcements respect user settings
- Route recalculation prevents excessive API calls
