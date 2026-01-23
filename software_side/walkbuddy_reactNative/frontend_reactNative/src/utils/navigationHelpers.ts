// Navigation helper functions for turn-by-turn navigation

/**
 * Convert OSRM step to human-readable instruction text
 */
export function stepToText(step: any): string {
  const m = step.maneuver || {};
  const type = (m.type || "").toLowerCase();
  const mod = (m.modifier || "").toLowerCase();
  const road = step.name ? ` onto ${step.name}` : "";

  if (type === "depart") return "Start navigation.";
  if (type === "arrive") return "You have arrived at your destination.";
  if (type === "roundabout") return `Enter the roundabout${road}.`;
  if (type === "merge") return `Merge${road}.`;
  if (type === "continue") return `Continue${road}.`;
  if (type === "turn") {
    const modifierText = mod || "ahead";
    return `Turn ${modifierText}${road}.`;
  }
  if (type === "new name") {
    return `Continue${road}.`;
  }

  // Fallback
  return `${type || "Continue"} ${mod || ""}${road}`.trim() || "Continue straight.";
}

/**
 * Calculate distance between two coordinates in meters (Haversine formula)
 */
export function metersBetween(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371000; // Earth radius in meters
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/**
 * Find the nearest point on a line segment to a given point
 * Returns the closest point on the segment and the distance
 */
function nearestPointOnSegment(
  pointLat: number,
  pointLng: number,
  segStartLat: number,
  segStartLng: number,
  segEndLat: number,
  segEndLng: number
): { lat: number; lng: number; distance: number; t: number } {
  // Vector from segment start to end
  const dx = segEndLng - segStartLng;
  const dy = segEndLat - segStartLat;
  
  // If segment is a point, return that point
  if (dx === 0 && dy === 0) {
    const dist = metersBetween(pointLat, pointLng, segStartLat, segStartLng);
    return { lat: segStartLat, lng: segStartLng, distance: dist, t: 0 };
  }
  
  // Vector from segment start to point
  const px = pointLng - segStartLng;
  const py = pointLat - segStartLat;
  
  // Calculate t (parameter along segment, 0-1)
  const t = Math.max(0, Math.min(1, (px * dx + py * dy) / (dx * dx + dy * dy)));
  
  // Closest point on segment
  const closestLat = segStartLat + t * dy;
  const closestLng = segStartLng + t * dx;
  
  const distance = metersBetween(pointLat, pointLng, closestLat, closestLng);
  
  return { lat: closestLat, lng: closestLng, distance, t };
}

/**
 * Find the nearest point on route geometry to user's current position
 * Returns the closest point and the distance along the route
 */
export function snapToRoute(
  userLat: number,
  userLng: number,
  routeGeometry: number[][], // [[lat, lng], ...]
  maxSnapDistanceM: number = 100
): { snappedLat: number; snappedLng: number; distanceAlongRoute: number; distanceToRoute: number } | null {
  if (!routeGeometry || routeGeometry.length < 2) {
    return null;
  }
  
  let minDistance = Infinity;
  let bestPoint: { lat: number; lng: number; distance: number; t: number } | null = null;
  let bestSegmentIndex = 0;
  let distanceAlongRoute = 0;
  
  // Check each segment of the route
  for (let i = 0; i < routeGeometry.length - 1; i++) {
    const segStart = routeGeometry[i];
    const segEnd = routeGeometry[i + 1];
    
    if (!segStart || !segEnd) continue;
    
    const nearest = nearestPointOnSegment(
      userLat,
      userLng,
      segStart[0], segStart[1],
      segEnd[0], segEnd[1]
    );
    
    if (nearest.distance < minDistance) {
      minDistance = nearest.distance;
      bestPoint = nearest;
      bestSegmentIndex = i;
      
      // Calculate distance along route to this point
      let dist = 0;
      for (let j = 0; j < i; j++) {
        const p1 = routeGeometry[j];
        const p2 = routeGeometry[j + 1];
        if (p1 && p2) {
          dist += metersBetween(p1[0], p1[1], p2[0], p2[1]);
        }
      }
      // Add distance along current segment
      const segStartPt = routeGeometry[i];
      const segEndPt = routeGeometry[i + 1];
      if (segStartPt && segEndPt) {
        dist += metersBetween(segStartPt[0], segStartPt[1], bestPoint.lat, bestPoint.lng);
      }
      distanceAlongRoute = dist;
    }
  }
  
  if (!bestPoint || minDistance > maxSnapDistanceM) {
    return null; // User is too far from route
  }
  
  return {
    snappedLat: bestPoint.lat,
    snappedLng: bestPoint.lng,
    distanceAlongRoute,
    distanceToRoute: minDistance
  };
}

/**
 * Calculate remaining distance along route from current position
 */
export function calculateRemainingDistance(
  userLat: number,
  userLng: number,
  routeGeometry: number[][],
  destinationLat: number,
  destinationLng: number,
  maxSnapDistanceM: number = 100
): number {
  if (!routeGeometry || routeGeometry.length === 0) {
    // Fallback: direct distance to destination
    return metersBetween(userLat, userLng, destinationLat, destinationLng);
  }
  
  const snapped = snapToRoute(userLat, userLng, routeGeometry, maxSnapDistanceM);
  
  if (!snapped) {
    // Too far from route, use direct distance
    return metersBetween(userLat, userLng, destinationLat, destinationLng);
  }
  
  // Calculate distance from snapped point to destination along route
  const totalRouteDistance = routeGeometry.reduce((sum, point, i) => {
    if (i === 0) return 0;
    const prev = routeGeometry[i - 1];
    if (prev && point) {
      return sum + metersBetween(prev[0], prev[1], point[0], point[1]);
    }
    return sum;
  }, 0);
  
  const remaining = totalRouteDistance - snapped.distanceAlongRoute;
  
  // Add distance from snapped point to destination if we're past the route end
  const routeEnd = routeGeometry[routeGeometry.length - 1];
  if (routeEnd && remaining < 0) {
    return metersBetween(userLat, userLng, destinationLat, destinationLng);
  }
  
  return Math.max(0, remaining);
}

/**
 * Update step index based on GPS position and route progression
 * Only advances when user has actually progressed along the route
 * Returns new step index if advanced, otherwise current index
 */
export function updateStepIndex(
  currentLat: number,
  currentLng: number,
  steps: any[],
  stepIndex: number,
  arrivalThresholdM: number = 20,
  routeGeometry?: number[][]
): number {
  const step = steps[stepIndex];
  if (!step) return stepIndex;
  
  // If this is the last step (arrive), check actual distance to destination
  if (step.maneuverType === 'arrive') {
    const destLat = step.endLat || step.lat;
    const destLng = step.endLng || step.lng;
    if (destLat && destLng) {
      const distanceToDest = metersBetween(currentLat, currentLng, destLat, destLng);
      // Only stay on "arrive" step if actually close to destination
      if (distanceToDest <= arrivalThresholdM) {
        return stepIndex; // At destination
      }
      // If far from destination, go back to previous step
      return Math.max(0, stepIndex - 1);
    }
    return stepIndex;
  }

  // Use maneuver location if available, otherwise use endLat/endLng
  let maneuverLat: number;
  let maneuverLng: number;

  if (step.maneuverLocation) {
    [maneuverLat, maneuverLng] = step.maneuverLocation;
  } else if (step.endLat && step.endLng) {
    maneuverLat = step.endLat;
    maneuverLng = step.endLng;
  } else {
    return stepIndex; // Can't determine maneuver location
  }

  const distance = metersBetween(currentLat, currentLng, maneuverLat, maneuverLng);

  // Only advance if user is close to the maneuver point
  // AND (if route geometry available) user has progressed along the route
  if (distance < arrivalThresholdM) {
    // If we have route geometry, verify user has progressed along route
    if (routeGeometry && routeGeometry.length > 0) {
      const snapped = snapToRoute(currentLat, currentLng, routeGeometry, 100);
      if (snapped) {
        // Check if we've passed the maneuver point along the route
        // This is a simplified check - in production, you'd want more sophisticated logic
        const maneuverDistance = calculateRemainingDistance(
          maneuverLat,
          maneuverLng,
          routeGeometry,
          routeGeometry[routeGeometry.length - 1][0],
          routeGeometry[routeGeometry.length - 1][1]
        );
        const userDistance = snapped.distanceAlongRoute;
        
        // Only advance if user has passed or reached the maneuver point
        if (userDistance >= maneuverDistance - arrivalThresholdM) {
          return Math.min(stepIndex + 1, steps.length - 1);
        }
      }
    } else {
      // No route geometry, use simple distance check
      return Math.min(stepIndex + 1, steps.length - 1);
    }
  }

  return stepIndex;
}
