// Real routing API integration
import { API_BASE } from '../config';
import { Route, RouteStep, ManeuverType } from '../types/navigation';
import { stepToText } from './navigationHelpers';

export interface RoutingOptions {
  originLat: number;
  originLng: number;
  destLat: number;
  destLng: number;
  profile?: 'foot-walking' | 'driving-car' | 'cycling-regular';
}

// Convert OpenRouteService maneuver type to our ManeuverType
function convertManeuverType(orsType: string): ManeuverType {
  const mapping: Record<string, ManeuverType> = {
    'turn-left': 'left',
    'turn-right': 'right',
    'turn-sharp-left': 'left',
    'turn-sharp-right': 'right',
    'turn-slight-left': 'left',
    'turn-slight-right': 'right',
    'straight': 'straight',
    'enter-roundabout': 'roundabout',
    'exit-roundabout': 'roundabout',
    'uturn': 'uturn',
    'arrive': 'arrive',
    'depart': 'depart',
  };
  return mapping[orsType.toLowerCase()] || 'straight';
}

// Fetch route from backend API
export async function fetchRoute(options: RoutingOptions): Promise<Route> {
  try {
    const response = await fetch(`${API_BASE}/api/routing`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        origin: [options.originLng, options.originLat],
        destination: [options.destLng, options.destLat],
        profile: options.profile || 'foot-walking',
      }),
    });

    if (!response.ok) {
      throw new Error(`Routing API error: ${response.status}`);
    }

    const data = await response.json();
    return parseRouteResponse(data);
  } catch (error) {
    console.error('Failed to fetch route:', error);
    // Fallback to mock route if API fails
    return generateFallbackRoute(options);
  }
}

// Parse route response (handles both OSRM and OpenRouteService formats)
function parseRouteResponse(data: any): Route {
  // Check if it's GeoJSON format (OpenRouteService or converted OSRM)
  if (data.features && data.features.length > 0) {
    return parseGeoJSONResponse(data);
  }

  // Check if it's OSRM format (direct route object)
  if (data.geometry && Array.isArray(data.geometry)) {
    return parseOSRMResponse(data);
  }

  // Check if it's OSRM routes array format
  if (data.routes && data.routes.length > 0) {
    return parseOSRMResponse(data.routes[0]);
  }

  throw new Error('Unknown route format');
}

// Parse OSRM response format
function parseOSRMResponse(data: any): Route {
  const route = data.routes?.[0] || data;
  const leg = route.legs?.[0] || { steps: [], distance: route.distance || 0, duration: route.duration || 0 };
  
  // Extract geometry coordinates - OSRM gives [lon, lat], convert to [lat, lon] for Leaflet
  const geometry = route.geometry?.coordinates || [];
  const routeGeometry = geometry.map(([lon, lat]: number[]) => [lat, lon]);

  const steps: RouteStep[] = [];
  let totalDistance = route.distance || 0;

  // Parse OSRM steps
  if (leg.steps && leg.steps.length > 0) {
    leg.steps.forEach((step: any, index: number) => {
      const maneuver = step.maneuver || {};
      const stepGeometry = step.geometry?.coordinates || [];
      
      // Get start and end coordinates
      const startCoord = stepGeometry[0] || [];
      const endCoord = stepGeometry[stepGeometry.length - 1] || startCoord;

      // Convert from [lon, lat] to [lat, lon]
      const startLat = startCoord[1] || 0;
      const startLng = startCoord[0] || 0;
      const endLat = endCoord[1] || 0;
      const endLng = endCoord[0] || 0;

      // Generate instruction text from maneuver
      const instructionText = generateInstructionText(maneuver, step, index === leg.steps.length - 1);

      // Extract maneuver location - OSRM gives [lon, lat]
      const maneuverLoc = maneuver.location || endCoord;
      const maneuverLat = maneuverLoc[1] || endLat;
      const maneuverLng = maneuverLoc[0] || endLng;

      steps.push({
        instructionText,
        maneuverType: convertManeuverType(maneuver.type || 'straight'),
        distanceToNext: Math.round(step.distance || 0),
        lat: startLat,
        lng: startLng,
        endLat,
        endLng,
        maneuverLocation: [maneuverLat, maneuverLng], // [lat, lng] for easy use
        roadName: step.name || undefined,
      });
    });
  } else {
    // Fallback: create simple steps from geometry
    if (routeGeometry.length > 0) {
      const start = routeGeometry[0];
      const end = routeGeometry[routeGeometry.length - 1];
      steps.push({
        instructionText: 'Head towards destination',
        maneuverType: 'depart',
        distanceToNext: Math.round(totalDistance),
        lat: start[0],
        lng: start[1],
        endLat: end[0],
        endLng: end[1],
      });
    }
  }

  // Add arrival step
  if (routeGeometry.length > 0) {
    const destination = routeGeometry[routeGeometry.length - 1];
    steps.push({
      instructionText: 'You have arrived at your destination',
      maneuverType: 'arrive',
      distanceToNext: 0,
      lat: destination[0],
      lng: destination[1],
    });
  }

  const estimatedTime = Math.round((route.duration || totalDistance / 1.4)); // seconds

  return {
    steps,
    totalDistance: Math.round(totalDistance),
    estimatedTime,
    geometry: routeGeometry, // Full route polyline for map display
  };
}

// Parse GeoJSON response format (OpenRouteService)
function parseGeoJSONResponse(data: any): Route {
  const feature = data.features[0];
  const geometry = feature.geometry;
  const segments = feature.properties.segments || [];

  // Extract geometry coordinates - GeoJSON gives [lon, lat], convert to [lat, lon]
  const coordinates = geometry.coordinates || [];
  const routeGeometry = coordinates.map(([lon, lat]: number[]) => [lat, lon]);

  const steps: RouteStep[] = [];
  let totalDistance = 0;

  // Parse segments into steps
  segments.forEach((segment: any, index: number) => {
    const distance = segment.distance || 0;
    totalDistance += distance;

    const instruction = segment.steps?.[0];
    if (instruction) {
      const wayPoints = segment.steps[0].way_points || [];
      const startIdx = wayPoints[0] || 0;
      const endIdx = wayPoints[1] || Math.min(startIdx + 1, coordinates.length - 1);
      
      const coords = coordinates[startIdx] || [];
      const endCoords = coordinates[endIdx] || [];

      // Extract maneuver location if available
      let maneuverLocation: [number, number] | undefined;
      if (instruction.maneuver_location) {
        // OSRM gives [lon, lat], convert to [lat, lon]
        const [maneuverLon, maneuverLat] = instruction.maneuver_location;
        maneuverLocation = [maneuverLat, maneuverLon];
      } else {
        // Fallback to end coordinates
        maneuverLocation = [endCoords[1], endCoords[0]];
      }

      // Use stepToText helper for better instruction text
      const stepData = {
        maneuver: {
          type: instruction.type,
          modifier: instruction.modifier,
        },
        name: instruction.name,
      };
      const instructionText = stepToText(stepData);

      steps.push({
        instructionText: instructionText || instruction.instruction || `Continue for ${Math.round(distance)} meters`,
        maneuverType: convertManeuverType(instruction.type || 'straight'),
        distanceToNext: Math.round(distance),
        lat: coords[1], // GeoJSON is [lon, lat]
        lng: coords[0],
        endLat: endCoords[1],
        endLng: endCoords[0],
        maneuverLocation,
        roadName: instruction.name || undefined,
      });
    }
  });

  // Add arrival step
  if (routeGeometry.length > 0) {
    const destination = routeGeometry[routeGeometry.length - 1];
    steps.push({
      instructionText: 'You have arrived at your destination',
      maneuverType: 'arrive',
      distanceToNext: 0,
      lat: destination[0],
      lng: destination[1],
    });
  }

  const estimatedTime = Math.round((totalDistance / 1.4) * 60); // ~1.4 m/s walking speed

  return {
    steps,
    totalDistance: Math.round(totalDistance),
    estimatedTime,
    geometry: routeGeometry, // Full route polyline for map display
  };
}

// Generate human-readable instruction text from OSRM maneuver
function generateInstructionText(maneuver: any, step: any, isLast: boolean): string {
  if (isLast) {
    return 'You have arrived at your destination';
  }

  const type = maneuver.type || 'straight';
  const modifier = maneuver.modifier || '';
  const name = step.name || '';

  let instruction = '';

  switch (type) {
    case 'turn':
      instruction = `Turn ${modifier}`;
      break;
    case 'new name':
      instruction = `Continue ${modifier}`;
      break;
    case 'depart':
      instruction = 'Head towards destination';
      break;
    case 'arrive':
      instruction = 'You have arrived';
      break;
    case 'roundabout':
      instruction = `Enter roundabout and take ${modifier} exit`;
      break;
    default:
      instruction = modifier ? `Continue ${modifier}` : 'Continue straight';
  }

  if (name) {
    instruction += ` on ${name}`;
  }

  const distance = Math.round(step.distance || 0);
  if (distance > 0) {
    instruction += ` for ${distance} meters`;
  }

  return instruction;
}

// Fallback route generator (mock) if API fails
function generateFallbackRoute(options: RoutingOptions): Route {
  const steps: RouteStep[] = [
    {
      instructionText: 'Head towards destination',
      maneuverType: 'depart',
      distanceToNext: 100,
      lat: options.originLat,
      lng: options.originLng,
      endLat: options.originLat + (options.destLat - options.originLat) * 0.3,
      endLng: options.originLng + (options.destLng - options.originLng) * 0.3,
    },
    {
      instructionText: 'Continue straight',
      maneuverType: 'straight',
      distanceToNext: 150,
      lat: options.originLat + (options.destLat - options.originLat) * 0.3,
      lng: options.originLng + (options.destLng - options.originLng) * 0.3,
      endLat: options.originLat + (options.destLat - options.originLat) * 0.6,
      endLng: options.originLng + (options.destLng - options.originLng) * 0.6,
    },
    {
      instructionText: 'You have arrived at your destination',
      maneuverType: 'arrive',
      distanceToNext: 0,
      lat: options.destLat,
      lng: options.destLng,
    },
  ];

  const totalDistance = steps.reduce((sum, s) => sum + s.distanceToNext, 0);
  const estimatedTime = Math.round((totalDistance / 1.4) * 60);

  // Generate simple geometry for mock route
  const numPoints = 10;
  const geometry: number[][] = [];
  for (let i = 0; i <= numPoints; i++) {
    const t = i / numPoints;
    geometry.push([
      options.originLat + (options.destLat - options.originLat) * t,
      options.originLng + (options.destLng - options.originLng) * t,
    ]);
  }

  return {
    steps,
    totalDistance,
    estimatedTime,
    geometry, // Mock route geometry
  };
}
