// Navigation types for exterior routing

export type ManeuverType =
  | 'left'
  | 'right'
  | 'straight'
  | 'roundabout'
  | 'uturn'
  | 'arrive'
  | 'depart';

export interface RouteStep {
  instructionText: string;
  maneuverType: ManeuverType;
  distanceToNext: number; // meters
  lat?: number;
  lng?: number;
  endLat?: number;
  endLng?: number;
  maneuverLocation?: [number, number]; // [lat, lng] - location where maneuver happens
  roadName?: string; // Street/road name
}

export interface Route {
  steps: RouteStep[];
  totalDistance: number; // meters
  estimatedTime: number; // seconds
  geometry?: number[][]; // Full route polyline coordinates [[lat, lng], ...]
  destination?: {
    lat: number;
    lng: number;
    name?: string;
  };
}

export interface Location {
  latitude: number;
  longitude: number;
  accuracy?: number;
  heading?: number;
}

// Interior Navigation Types
export type NavStep =
  | { type: "walk"; steps: number; headingDeg?: number }
  | { type: "turn"; direction: "left" | "right" | "uturn" }
  | { type: "arrive" };

export interface SavedRoute {
  id: string;
  name: string; // "Fiction section"
  startLabel: string; // "Library Entrance"
  createdAt: number;
  steps: NavStep[];
}
