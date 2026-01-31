// Routing engine utilities
import { Route, RouteStep } from '../types/navigation';

// Mock route generator for testing
export function generateMockRoute(
  originLat: number,
  originLng: number,
  destLat: number,
  destLng: number
): Route {
  // Simple mock route with 5 steps
  const steps: RouteStep[] = [
    {
      instructionText: 'Head north on Main Street',
      maneuverType: 'depart',
      distanceToNext: 150,
      lat: originLat,
      lng: originLng,
      endLat: originLat + 0.001,
      endLng: originLng,
    },
    {
      instructionText: 'Turn right onto Oak Avenue',
      maneuverType: 'right',
      distanceToNext: 200,
      lat: originLat + 0.001,
      lng: originLng,
      endLat: originLat + 0.001,
      endLng: originLng + 0.002,
    },
    {
      instructionText: 'Continue straight for 200 meters',
      maneuverType: 'straight',
      distanceToNext: 200,
      lat: originLat + 0.001,
      lng: originLng + 0.002,
      endLat: originLat + 0.002,
      endLng: originLng + 0.002,
    },
    {
      instructionText: 'Turn left onto Park Road',
      maneuverType: 'left',
      distanceToNext: 100,
      lat: originLat + 0.002,
      lng: originLng + 0.002,
      endLat: originLat + 0.002,
      endLng: originLng + 0.001,
    },
    {
      instructionText: 'You have arrived at your destination',
      maneuverType: 'arrive',
      distanceToNext: 0,
      lat: destLat,
      lng: destLng,
    },
  ];

  const totalDistance = steps.reduce((sum, step) => sum + step.distanceToNext, 0);
  const estimatedTime = Math.round((totalDistance / 1.4) * 60); // ~1.4 m/s walking speed

  return {
    steps,
    totalDistance,
    estimatedTime,
  };
}

// Calculate distance between two coordinates (Haversine formula)
export function calculateDistance(
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number
): number {
  const R = 6371000; // Earth radius in meters
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLng = ((lng2 - lng1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLng / 2) *
      Math.sin(dLng / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

// Check if user is close enough to current step endpoint
export function shouldAdvanceStep(
  currentLat: number,
  currentLng: number,
  stepEndLat: number,
  stepEndLng: number,
  threshold: number = 20 // meters
): boolean {
  const distance = calculateDistance(currentLat, currentLng, stepEndLat, stepEndLng);
  return distance <= threshold;
}
