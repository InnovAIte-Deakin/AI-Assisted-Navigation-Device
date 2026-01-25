// Geocoding utilities
import { API_BASE } from '../config';

export interface GeocodeResult {
  name: string;
  lat: number;
  lng: number;
  address?: Record<string, string>;
}

/**
 * Geocode a place name to coordinates using backend Nominatim API
 */
export async function geocodePlaceName(placeName: string): Promise<GeocodeResult> {
  try {
    const response = await fetch(`${API_BASE}/api/geocode?q=${encodeURIComponent(placeName)}`);
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Geocoding failed' }));
      throw new Error(error.detail || `Geocoding failed: ${response.status}`);
    }

    const data = await response.json();
    return {
      name: data.name,
      lat: data.lat,
      lng: data.lng,
      address: data.address,
    };
  } catch (error) {
    console.error('Geocoding error:', error);
    throw error;
  }
}
