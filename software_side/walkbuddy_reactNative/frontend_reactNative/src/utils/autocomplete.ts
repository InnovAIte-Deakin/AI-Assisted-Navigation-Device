// Autocomplete/geocoding suggestions utility
import { API_BASE } from '../config';

export interface AutocompleteSuggestion {
  name: string;
  lat: number;
  lng: number;
  address?: Record<string, string>;
  displayName: string; // Full formatted address
}

/**
 * Get autocomplete suggestions for a place name query
 * Returns multiple results for dropdown selection
 */
export async function getAutocompleteSuggestions(query: string): Promise<AutocompleteSuggestion[]> {
  if (!query || query.trim().length < 2) {
    return [];
  }

  try {
    // Call Nominatim directly for autocomplete with multiple results
    const response = await fetch(
      `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=5&addressdetails=1`,
      {
        headers: {
          'User-Agent': 'WalkBuddie/1.0',
        },
      }
    );

    if (!response.ok) {
      console.error('Autocomplete API error:', response.status);
      return [];
    }

    const data = await response.json();
    
    if (!Array.isArray(data) || data.length === 0) {
      return [];
    }

    return data.map((item: any) => ({
      name: item.display_name.split(',')[0] || item.name || query, // Short name
      lat: parseFloat(item.lat),
      lng: parseFloat(item.lon),
      address: item.address || {},
      displayName: item.display_name || item.name || query, // Full address
    }));
  } catch (error) {
    console.error('Autocomplete error:', error);
    return [];
  }
}

/**
 * Format suggestion for display (e.g., "Monash University, Clayton")
 */
export function formatSuggestion(suggestion: AutocompleteSuggestion): string {
  // Extract key parts from display name
  const parts = suggestion.displayName.split(',');
  
  // For Monash University specifically, try to extract campus/suburb
  if (suggestion.displayName.toLowerCase().includes('monash')) {
    // Look for suburb/campus in the address parts
    const suburb = parts.find(p => 
      p.toLowerCase().includes('clayton') ||
      p.toLowerCase().includes('caulfield') ||
      p.toLowerCase().includes('parkville') ||
      p.toLowerCase().includes('peninsula') ||
      p.toLowerCase().includes('berwick')
    );
    
    if (suburb) {
      return `Monash University, ${suburb.trim()}`;
    }
  }
  
  // For other locations, show first 2-3 parts
  if (parts.length >= 2) {
    return `${parts[0]}, ${parts[1]}`;
  }
  
  return suggestion.displayName;
}
