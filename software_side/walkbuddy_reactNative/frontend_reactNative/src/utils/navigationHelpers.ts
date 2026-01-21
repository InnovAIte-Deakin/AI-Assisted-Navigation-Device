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
 * Update step index based on GPS position
 * Returns new step index if advanced, otherwise current index
 */
export function updateStepIndex(
  currentLat: number,
  currentLng: number,
  steps: any[],
  stepIndex: number,
  arrivalThresholdM: number = 20
): number {
  const step = steps[stepIndex];
  if (!step) return stepIndex;

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

  // If very close -> advance to next step
  if (distance < arrivalThresholdM) {
    return Math.min(stepIndex + 1, steps.length - 1);
  }

  return stepIndex;
}
