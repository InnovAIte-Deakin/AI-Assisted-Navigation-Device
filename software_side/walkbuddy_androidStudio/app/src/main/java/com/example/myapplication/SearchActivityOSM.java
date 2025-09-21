package com.example.myapplication;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.location.Address;
import android.location.Geocoder;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognizerIntent;
import android.text.Editable;
import android.text.TextWatcher;
import android.util.Log;
import android.view.View;
import android.widget.AutoCompleteTextView;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;

import com.google.android.gms.location.FusedLocationProviderClient;
import com.google.android.gms.location.LocationServices;

import org.osmdroid.api.IMapController;
import org.osmdroid.config.Configuration;
import org.osmdroid.tileprovider.tilesource.TileSourceFactory;
import org.osmdroid.util.GeoPoint;
import org.osmdroid.views.MapView;
import org.osmdroid.views.overlay.Marker;
import org.osmdroid.views.overlay.Polyline;

import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public class SearchActivityOSM extends AppCompatActivity {

    private static final int REQ_LOCATION = 3001;
    private static final int REQ_VOICE_INPUT = 4001;
    private static final String TAG = "SearchActivityOSM";

    private FusedLocationProviderClient fusedClient;
    private MapView mapView;
    private TTSAnnouncer announcer;
    
    private AutoCompleteTextView searchField;
    private Button btnSearch;
    private Button btnVoiceInput;
    private Button btnStartNavigation;
    private ImageView btnBack;
    private TextView txtCurrentLocation;
    private TextView txtDestination;
    private TextView txtDistance;
    private TextView txtDuration;
    
    private GeoPoint currentLocation;
    private GeoPoint destinationLocation;
    private String currentAddress = "";
    private PlaceSuggestionAdapter searchAdapter;
    
    // Offline place database
    private Map<String, PlaceInfo> offlinePlaces;
    
    // Search debouncing
    private Handler searchHandler;
    private Runnable searchRunnable;
    
    // Current search result for navigation
    private PlaceInfo currentDestination;

    private static class PlaceInfo {
        final GeoPoint geoPoint;
        final String fullName;
        final String address;
        final double distance;
        final int walkingMinutes;

        PlaceInfo(GeoPoint geoPoint, String fullName, String address, double distance, int walkingMinutes) {
            this.geoPoint = geoPoint;
            this.fullName = fullName;
            this.address = address;
            this.distance = distance;
            this.walkingMinutes = walkingMinutes;
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        // Initialize OSMDroid configuration
        Configuration.getInstance().setUserAgentValue(getPackageName());
        
        setContentView(R.layout.activity_search_osm);

        initializeViews();
        setupOfflinePlaces();
        setupLocationServices();
        setupMap();
        setupSearchField();
        setupClickListeners();
        
        // Announce activity start
        announcer.speak("Search activity opened using OpenStreetMap. Enter your destination or use voice input.");
    }

    private void initializeViews() {
        announcer = new TTSAnnouncer(this);
        searchField = findViewById(R.id.searchField);
        btnSearch = findViewById(R.id.btnSearch);
        btnVoiceInput = findViewById(R.id.btnVoiceInput);
        btnStartNavigation = findViewById(R.id.btnStartNavigation);
        btnBack = findViewById(R.id.btnBack);
        txtCurrentLocation = findViewById(R.id.txtCurrentLocation);
        txtDestination = findViewById(R.id.txtDestination);
        txtDistance = findViewById(R.id.txtDistance);
        txtDuration = findViewById(R.id.txtDuration);
        
        // Initialize search debouncing
        searchHandler = new Handler(Looper.getMainLooper());
    }

    private void setupOfflinePlaces() {
        offlinePlaces = new HashMap<>();
        
        // Popular universities
        offlinePlaces.put("deakin university geelong", new PlaceInfo(
            new GeoPoint(-38.1946, 144.3054), 
            "Deakin University - Geelong Campus", 
            "Geelong Waurn Ponds Campus, 75 Pigdons Road, Waurn Ponds VIC 3216",
            0, 0));
        
        offlinePlaces.put("deakin university burwood", new PlaceInfo(
            new GeoPoint(-37.8471, 145.1151), 
            "Deakin University - Burwood Campus", 
            "221 Burwood Highway, Burwood VIC 3125",
            0, 0));
        
        offlinePlaces.put("melbourne university", new PlaceInfo(
            new GeoPoint(-37.7964, 144.9612), 
            "University of Melbourne - Parkville Campus", 
            "Grattan Street, Parkville VIC 3010",
            0, 0));
        
        offlinePlaces.put("monash university", new PlaceInfo(
            new GeoPoint(-37.9105, 145.1362), 
            "Monash University - Clayton Campus", 
            "Wellington Road, Clayton VIC 3800",
            0, 0));
        
        // Popular locations
        offlinePlaces.put("melbourne central", new PlaceInfo(
            new GeoPoint(-37.8100, 144.9633), 
            "Melbourne Central", 
            "211 La Trobe Street, Melbourne VIC 3000",
            0, 0));
        
        offlinePlaces.put("melbourne", new PlaceInfo(
            new GeoPoint(-37.8136, 144.9631), 
            "Melbourne CBD", 
            "Melbourne VIC 3000, Australia",
            0, 0));
        
        offlinePlaces.put("flinders street station", new PlaceInfo(
            new GeoPoint(-37.8183, 144.9671), 
            "Flinders Street Station", 
            "Flinders Street, Melbourne VIC 3000",
            0, 0));
        
        offlinePlaces.put("southern cross station", new PlaceInfo(
            new GeoPoint(-37.8184, 144.9525), 
            "Southern Cross Station", 
            "99 Spencer Street, Melbourne VIC 3000",
            0, 0));
        
        // Shopping centers
        offlinePlaces.put("chadstone", new PlaceInfo(
            new GeoPoint(-37.8859, 145.0839), 
            "Chadstone Shopping Centre", 
            "1341 Dandenong Road, Chadstone VIC 3148",
            0, 0));
        
        offlinePlaces.put("chapel street", new PlaceInfo(
            new GeoPoint(-37.8467, 144.9894), 
            "Chapel Street - Prahran", 
            "Chapel Street, Prahran VIC 3181",
            0, 0));
    }

    private void setupLocationServices() {
        fusedClient = LocationServices.getFusedLocationProviderClient(this);
        ensureLocationPermission();
    }

    private void setupMap() {
        mapView = findViewById(R.id.mapView);
        if (mapView != null) {
            mapView.setTileSource(TileSourceFactory.MAPNIK);
            mapView.setMultiTouchControls(true);
            
            IMapController mapController = mapView.getController();
            mapController.setZoom(15.0);
            
            // Default to Melbourne CBD
            GeoPoint startPoint = new GeoPoint(-37.8136, 144.9631);
            mapController.setCenter(startPoint);
        }
    }

    private void setupSearchField() {
        // Set up autocomplete for search field
        searchAdapter = new PlaceSuggestionAdapter(this);
        searchField.setAdapter(searchAdapter);
        
        searchField.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {}

            @Override
            public void onTextChanged(CharSequence s, int start, int before, int count) {
                // Cancel previous search if still pending
                if (searchRunnable != null) {
                    searchHandler.removeCallbacks(searchRunnable);
                }
                
                // Only search if we have enough characters
                if (s.length() > 2) {
                    searchRunnable = () -> performOfflineSearch(s.toString());
                    // Debounce search by 300ms to avoid excessive calls
                    searchHandler.postDelayed(searchRunnable, 300);
                } else {
                    // Clear suggestions for short queries
                    searchAdapter.updateSuggestions(new ArrayList<>());
                }
            }

            @Override
            public void afterTextChanged(Editable s) {}
        });

        // Handle item selection
        searchField.setOnItemClickListener((parent, view, position, id) -> {
            String selectedPlace = (String) parent.getItemAtPosition(position);
            String primaryText = selectedPlace.contains(" - ") ? 
                    selectedPlace.split(" - ", 2)[0] : selectedPlace;
            searchField.setText(primaryText);
            announcer.speak("Selected: " + primaryText);
            
            // Use the full selected place for search to ensure exact match
            performSearchFromSelection(selectedPlace);
        });
    }

    private void setupClickListeners() {
        btnBack.setOnClickListener(v -> {
            announcer.speak("Returning to home");
            finish();
        });

        btnSearch.setOnClickListener(v -> {
            String query = searchField.getText().toString().trim();
            if (!query.isEmpty()) {
                announcer.speak("Searching for " + query);
                performSearch(query);
            } else {
                announcer.speak("Please enter a destination");
            }
        });

        btnVoiceInput.setOnClickListener(v -> {
            startVoiceInput();
        });

        btnStartNavigation.setOnClickListener(v -> {
            if (currentDestination != null) {
                startCameraNavigation();
            } else {
                announcer.speak("Please search for a destination first");
            }
        });
    }

    private void ensureLocationPermission() {
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.ACCESS_FINE_LOCATION}, REQ_LOCATION);
        } else {
            getCurrentLocation();
        }
    }

    private void getCurrentLocation() {
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
            fusedClient.getLastLocation().addOnSuccessListener(this, location -> {
                if (location != null) {
                    currentLocation = new GeoPoint(location.getLatitude(), location.getLongitude());
                    updateCurrentLocationDisplay();
                    updateMapLocation();
                    announcer.speak("Current location found: " + currentAddress);
                } else {
                    // Fallback to Melbourne CBD for testing
                    currentLocation = new GeoPoint(-37.8136, 144.9631);
                    currentAddress = "Melbourne CBD (simulated)";
                    txtCurrentLocation.setText("Current: " + currentAddress);
                    updateMapLocation();
                    announcer.speak("Using simulated location: " + currentAddress);
                }
            });
        }
    }

    private void updateMapLocation() {
        if (mapView != null && currentLocation != null) {
            IMapController mapController = mapView.getController();
            mapController.setCenter(currentLocation);
            
            // Add current location marker
            Marker currentMarker = new Marker(mapView);
            currentMarker.setPosition(currentLocation);
            currentMarker.setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_BOTTOM);
            currentMarker.setTitle("Current Location");
            mapView.getOverlays().add(currentMarker);
            mapView.invalidate();
        }
    }

    private void updateCurrentLocationDisplay() {
        if (currentLocation != null) {
            try {
                Geocoder geocoder = new Geocoder(this, Locale.getDefault());
                List<Address> addresses = geocoder.getFromLocation(currentLocation.getLatitude(), currentLocation.getLongitude(), 1);
                if (addresses != null && !addresses.isEmpty()) {
                    currentAddress = addresses.get(0).getAddressLine(0);
                    txtCurrentLocation.setText("Current: " + currentAddress);
                }
            } catch (IOException e) {
                currentAddress = String.format(Locale.getDefault(), "%.5f, %.5f", 
                        currentLocation.getLatitude(), currentLocation.getLongitude());
                txtCurrentLocation.setText("Current: " + currentAddress);
            }
        }
    }

    private void performOfflineSearch(String query) {
        Log.d(TAG, "Performing flexible search for: " + query);
        
        List<String> suggestions = new ArrayList<>();
        String lowerQuery = query.toLowerCase();
        
        // 1. First priority: Search through curated offline places
        for (Map.Entry<String, PlaceInfo> entry : offlinePlaces.entrySet()) {
            if (entry.getKey().contains(lowerQuery) || entry.getValue().fullName.toLowerCase().contains(lowerQuery)) {
                String suggestion = entry.getValue().fullName + " - " + entry.getValue().address;
                suggestions.add(suggestion);
            }
        }
        
        // 2. Second priority: Use Android Geocoder for real places
        try {
            Geocoder geocoder = new Geocoder(this, Locale.getDefault());
            List<Address> addresses = geocoder.getFromLocationName(query, 5); // Get up to 5 results
            
            for (Address address : addresses) {
                if (address.getFeatureName() != null) {
                    String placeName = address.getFeatureName();
                    String fullAddress = address.getAddressLine(0);
                    
                    // Avoid duplicates
                    String suggestion = placeName + " - " + fullAddress;
                    if (!suggestions.contains(suggestion)) {
                        suggestions.add(suggestion);
                    }
                }
            }
        } catch (IOException e) {
            Log.w(TAG, "Geocoder failed, using fallback suggestions");
        }
        
        // 3. Third priority: Smart suggestions based on common patterns
        if (suggestions.size() < 3) {
            addSmartSuggestions(query, suggestions);
        }
        
        // 4. Limit to reasonable number of suggestions
        if (suggestions.size() > 8) {
            suggestions = suggestions.subList(0, 8);
        }
        
        searchAdapter.updateSuggestions(suggestions);
        if (!suggestions.isEmpty()) {
            searchField.showDropDown();
        }
    }
    
    private void addSmartSuggestions(String query, List<String> suggestions) {
        String lowerQuery = query.toLowerCase();
        
        // For specific institutions, provide more targeted suggestions
        if (lowerQuery.contains("truman")) {
            suggestions.add("Truman State University - Kirksville, Missouri");
            suggestions.add("Truman College - Chicago, Illinois");
            suggestions.add("Harry S. Truman Library - Independence, Missouri");
        } else if (lowerQuery.contains("university") || lowerQuery.contains("uni") || lowerQuery.contains("college")) {
            // Don't add generic "University Campus" - let geocoder handle it
            suggestions.add("Search for '" + query + "' globally");
            suggestions.add(query + " - Main Campus");
        } else if (lowerQuery.contains("hospital") || lowerQuery.contains("medical") || lowerQuery.contains("health")) {
            suggestions.add("Search for '" + query + "' globally");
            suggestions.add(query + " - Medical Center");
        } else if (lowerQuery.contains("station") || lowerQuery.contains("train") || lowerQuery.contains("tram")) {
            suggestions.add("Search for '" + query + "' globally");
            suggestions.add(query + " - Transport Hub");
        } else {
            // More helpful generic suggestions
            suggestions.add("Search for '" + query + "' globally");
            suggestions.add(query + " - Worldwide");
            if (!lowerQuery.contains("australia")) {
                suggestions.add(query + " - Australia");
            }
        }
    }

    private void performSearchFromSelection(String selectedPlace) {
        Log.d(TAG, "=== PERFORMING SEARCH FROM SELECTION ===");
        Log.d(TAG, "Selected place: " + selectedPlace);
        
        // For dropdown selections, we want to find the exact match
        PlaceInfo foundPlace = null;
        
        // First, try to find exact match by full name
        for (Map.Entry<String, PlaceInfo> entry : offlinePlaces.entrySet()) {
            String fullName = entry.getValue().fullName;
            String fullSuggestion = fullName + " - " + entry.getValue().address;
            
            Log.d(TAG, "Comparing selection '" + selectedPlace + "' with '" + fullSuggestion + "'");
            
            if (selectedPlace.equals(fullSuggestion) || selectedPlace.startsWith(fullName)) {
                Log.d(TAG, "EXACT MATCH FOUND: " + fullName);
                foundPlace = entry.getValue();
                break;
            }
        }
        
        // If no exact match in curated places, try geocoder
        if (foundPlace == null) {
            Log.d(TAG, "No exact match in curated places, trying geocoder for selection...");
            foundPlace = searchWithGeocoder(selectedPlace);
        }
        
        if (foundPlace != null) {
            displaySearchResult(foundPlace);
        } else {
            announcer.speak("Selected location not found. Please try a different search.");
            txtDestination.setText("Destination: Not found");
            txtDistance.setText("Distance: --");
            txtDuration.setText("Walking time: --");
        }
    }

    private void performSearch(String query) {
        Log.d(TAG, "=== PERFORMING SEARCH ===");
        Log.d(TAG, "Original query: " + query);
        announcer.speak("Searching for " + query);
        
        String searchTerm = query.toLowerCase();
        if (searchTerm.contains(" - ")) {
            searchTerm = searchTerm.split(" - ", 2)[0];
        }
        Log.d(TAG, "Search term after processing: " + searchTerm);
        
        PlaceInfo foundPlace = null;
        
        // 1. First try: Search curated offline places with smart priority matching
        Log.d(TAG, "Searching curated places...");
        
        // Use a list to track all matches and then pick the best one
        List<PlaceInfo> matches = new ArrayList<>();
        List<String> matchTypes = new ArrayList<>();
        
        for (Map.Entry<String, PlaceInfo> entry : offlinePlaces.entrySet()) {
            String key = entry.getKey();
            String fullName = entry.getValue().fullName.toLowerCase();
            
            Log.d(TAG, "Checking: " + key + " vs " + searchTerm);
            
            // Check for exact key match (highest priority)
            if (key.equals(searchTerm)) {
                Log.d(TAG, "Exact key match");
                matches.add(entry.getValue());
                matchTypes.add("exact");
            }
            // Smart campus/location matching (high priority)
            else if (isSmartCampusMatch(searchTerm, key, fullName)) {
                Log.d(TAG, "Smart campus match");
                matches.add(entry.getValue());
                matchTypes.add("campus");
            }
            // Check for specific name matches in full name (medium priority)
            else if (isSpecificMatch(searchTerm, fullName)) {
                Log.d(TAG, "Specific match in full name");
                matches.add(entry.getValue());
                matchTypes.add("specific");
            }
            // Check if key starts with search term (lowest priority)
            else if (key.startsWith(searchTerm)) {
                Log.d(TAG, "Key starts with search term");
                matches.add(entry.getValue());
                matchTypes.add("starts_with");
            }
        }
        
        // Pick the best match based on priority
        if (!matches.isEmpty()) {
            foundPlace = getBestMatch(matches, matchTypes, searchTerm);
            if (foundPlace != null) {
                Log.d(TAG, "BEST MATCH FOUND in curated places: " + foundPlace.fullName);
            }
        }
        
        if (foundPlace == null) {
            Log.d(TAG, "No match found in curated places, trying geocoder...");
        }
        
        // 2. Second try: Use Android Geocoder to find real places
        if (foundPlace == null) {
            foundPlace = searchWithGeocoder(query);
        }
        
        if (foundPlace != null) {
            displaySearchResult(foundPlace);
        } else {
            announcer.speak("Location not found. Please try a different search term or be more specific.");
            txtDestination.setText("Destination: Not found");
            txtDistance.setText("Distance: --");
            txtDuration.setText("Walking time: --");
        }
    }
    
    private void displaySearchResult(PlaceInfo foundPlace) {
        destinationLocation = foundPlace.geoPoint;
        currentDestination = foundPlace; // Store for navigation
        
        if (currentLocation != null) {
            double distance = calculateDistance(currentLocation, destinationLocation);
            int walkingMinutes = calculateWalkingTime(distance);
            
            updateMapWithRoute();
            announcer.speak(String.format("Route found to %s. Distance: %.1f kilometers. Estimated walking time: %d minutes.", 
                foundPlace.fullName, distance, walkingMinutes));
            
            txtDestination.setText("Destination: " + foundPlace.fullName);
            txtDistance.setText(String.format("Distance: %.1f km", distance));
            txtDuration.setText(String.format("Walking time: %d min", walkingMinutes));
        } else {
            updateMapWithRoute();
            announcer.speak("Route found to " + foundPlace.fullName + ". Please wait for location services to calculate distance.");
            
            txtDestination.setText("Destination: " + foundPlace.fullName);
            txtDistance.setText("Distance: Calculating...");
            txtDuration.setText("Walking time: Calculating...");
        }
        
        // Show navigation button when destination is found
        btnStartNavigation.setVisibility(View.VISIBLE);
    }
    
    private void startCameraNavigation() {
        Intent intent = new Intent(this, CameraNavigationActivity.class);
        intent.putExtra("destination_name", currentDestination.fullName);
        intent.putExtra("destination_lat", currentDestination.geoPoint.getLatitude());
        intent.putExtra("destination_lon", currentDestination.geoPoint.getLongitude());
        
        // Calculate current distance if possible
        if (currentLocation != null) {
            double distance = calculateDistance(currentLocation, destinationLocation);
            intent.putExtra("current_distance", distance);
        }
        
        announcer.speak("Starting camera navigation to " + currentDestination.fullName);
        startActivity(intent);
    }
    
    private PlaceInfo searchWithGeocoder(String query) {
        try {
            Geocoder geocoder = new Geocoder(this, Locale.getDefault());
            
            // Check if Geocoder is available on this device
            if (!Geocoder.isPresent()) {
                Log.w(TAG, "Geocoder not available on this device");
                return null;
            }
            
            Log.d(TAG, "Searching with geocoder for: " + query);
            List<Address> addresses = geocoder.getFromLocationName(query, 3); // Get up to 3 results
            
            if (addresses != null && !addresses.isEmpty()) {
                Address address = addresses.get(0);
                
                String placeName = extractBestPlaceName(query, address);
                
                Log.d(TAG, "Place name extraction: featureName='" + address.getFeatureName() + 
                    "', thoroughfare='" + address.getThoroughfare() + 
                    "', locality='" + address.getLocality() + 
                    "', selected='" + placeName + "'");
                
                String fullAddress = address.getAddressLine(0);
                if (fullAddress == null || fullAddress.isEmpty()) {
                    fullAddress = placeName;
                    if (address.getLocality() != null) {
                        fullAddress += ", " + address.getLocality();
                    }
                    if (address.getCountryName() != null) {
                        fullAddress += ", " + address.getCountryName();
                    }
                }
                
                GeoPoint geoPoint = new GeoPoint(address.getLatitude(), address.getLongitude());
                
                // Calculate distance if we have current location
                double distance = 0;
                int walkingMinutes = 0;
                if (currentLocation != null) {
                    distance = calculateDistance(currentLocation, geoPoint);
                    walkingMinutes = calculateWalkingTime(distance);
                }
                
                Log.d(TAG, "Geocoder found: " + placeName + " at " + fullAddress);
                Log.d(TAG, "Coordinates: " + address.getLatitude() + ", " + address.getLongitude());
                return new PlaceInfo(geoPoint, placeName, fullAddress, distance, walkingMinutes);
            } else {
                Log.d(TAG, "Geocoder returned no results for: " + query);
            }
        } catch (IOException e) {
            Log.w(TAG, "Geocoder search failed for: " + query, e);
        } catch (Exception e) {
            Log.e(TAG, "Unexpected error in geocoder search: " + query, e);
        }
        return null;
    }
    
    private String extractBestPlaceName(String originalQuery, Address address) {
        // Clean up the original query to remove common suffixes
        String cleanQuery = originalQuery;
        if (cleanQuery.contains(" - ")) {
            cleanQuery = cleanQuery.split(" - ")[0];
        }
        
        String featureName = address.getFeatureName();
        String thoroughfare = address.getThoroughfare();
        String locality = address.getLocality();
        String subLocality = address.getSubLocality();
        
        // If feature name looks like a number or is very short, it's probably not useful
        if (featureName != null && !featureName.isEmpty()) {
            try {
                // If it's just a number, skip it
                Integer.parseInt(featureName);
                Log.d(TAG, "Skipping numeric feature name: " + featureName);
            } catch (NumberFormatException e) {
                // Not a number, could be a good name
                if (featureName.length() > 3) {
                    return featureName;
                }
            }
        }
        
        // For institutions like universities, prefer the original query
        String lowerQuery = cleanQuery.toLowerCase();
        if (lowerQuery.contains("university") || lowerQuery.contains("college") || 
            lowerQuery.contains("school") || lowerQuery.contains("hospital")) {
            return cleanQuery;
        }
        
        // Try thoroughfare (street name)
        if (thoroughfare != null && !thoroughfare.isEmpty() && thoroughfare.length() > 3) {
            return thoroughfare;
        }
        
        // Try sub-locality (suburb/district)
        if (subLocality != null && !subLocality.isEmpty()) {
            return subLocality;
        }
        
        // Try locality (city)
        if (locality != null && !locality.isEmpty()) {
            return locality;
        }
        
        // Fallback to original query
        return cleanQuery;
    }
    
    private boolean isSmartCampusMatch(String searchTerm, String key, String fullName) {
        // Handle specific cases like "deakin burwood" vs "deakin university geelong"
        String[] searchWords = searchTerm.split(" ");
        String[] keyWords = key.split(" ");
        
        // Must have at least 2 words for campus matching
        if (searchWords.length < 2) {
            return false;
        }
        
        // Skip if search term is too generic (just institution + "university")
        // e.g., "deakin university" should NOT match specific campuses
        if (searchWords.length == 2 && 
            (searchWords[1].equals("university") || searchWords[1].equals("uni") || 
             searchWords[1].equals("college") || searchWords[1].equals("school"))) {
            Log.d(TAG, "Skipping generic institution search: " + searchTerm);
            return false;
        }
        
        // Check if we have the institution name and a location/campus identifier
        String institutionWord = searchWords[0]; // e.g., "deakin"
        String locationWord = searchWords[searchWords.length - 1]; // e.g., "burwood"
        
        // The key must contain the institution name
        boolean hasInstitution = false;
        for (String keyWord : keyWords) {
            if (keyWord.equals(institutionWord)) {
                hasInstitution = true;
                break;
            }
        }
        
        if (!hasInstitution) {
            return false;
        }
        
        // The key or full name must contain the location/campus
        boolean hasLocation = key.contains(locationWord) || fullName.contains(locationWord);
        
        Log.d(TAG, "Campus match check: institution='" + institutionWord + "' location='" + locationWord + "' hasInstitution=" + hasInstitution + " hasLocation=" + hasLocation);
        
        return hasLocation;
    }
    
    private PlaceInfo getBestMatch(List<PlaceInfo> matches, List<String> matchTypes, String searchTerm) {
        // Priority order: exact > campus > specific > starts_with
        
        // First, look for exact matches
        for (int i = 0; i < matchTypes.size(); i++) {
            if ("exact".equals(matchTypes.get(i))) {
                Log.d(TAG, "Selecting exact match: " + matches.get(i).fullName);
                return matches.get(i);
            }
        }
        
        // Then, look for campus matches (e.g., "deakin burwood")
        for (int i = 0; i < matchTypes.size(); i++) {
            if ("campus".equals(matchTypes.get(i))) {
                Log.d(TAG, "Selecting campus match: " + matches.get(i).fullName);
                return matches.get(i);
            }
        }
        
        // Then, look for specific matches
        for (int i = 0; i < matchTypes.size(); i++) {
            if ("specific".equals(matchTypes.get(i))) {
                Log.d(TAG, "Selecting specific match: " + matches.get(i).fullName);
                return matches.get(i);
            }
        }
        
        // Finally, if we only have "starts_with" matches, be smart about it
        if (matchTypes.contains("starts_with")) {
            // For "starts_with" matches, prefer shorter, more specific matches
            PlaceInfo bestMatch = null;
            String shortestKey = null;
            
            for (int i = 0; i < matchTypes.size(); i++) {
                if ("starts_with".equals(matchTypes.get(i))) {
                    PlaceInfo candidate = matches.get(i);
                    // Find the corresponding key for this match
                    String candidateKey = null;
                    for (Map.Entry<String, PlaceInfo> entry : offlinePlaces.entrySet()) {
                        if (entry.getValue() == candidate) {
                            candidateKey = entry.getKey();
                            break;
                        }
                    }
                    
                    if (candidateKey != null) {
                        if (shortestKey == null || candidateKey.length() < shortestKey.length()) {
                            bestMatch = candidate;
                            shortestKey = candidateKey;
                        }
                    }
                }
            }
            
            if (bestMatch != null) {
                Log.d(TAG, "Selecting best starts_with match: " + bestMatch.fullName + " (key: " + shortestKey + ")");
                return bestMatch;
            }
        }
        
        // Fallback to first match
        if (!matches.isEmpty()) {
            Log.d(TAG, "Fallback to first match: " + matches.get(0).fullName);
            return matches.get(0);
        }
        
        return null;
    }

    private boolean isSpecificMatch(String searchTerm, String fullName) {
        // This method checks for specific, meaningful matches
        // Avoid matching common words like "university", "hospital", "station"
        
        String[] commonWords = {"university", "hospital", "station", "center", "centre", "school", "college", "building", "road", "street", "avenue"};
        String[] searchWords = searchTerm.split(" ");
        
        // Count meaningful word matches (excluding common words)
        int meaningfulMatches = 0;
        int totalMeaningfulWords = 0;
        
        for (String searchWord : searchWords) {
            // Skip common words
            boolean isCommonWord = false;
            for (String commonWord : commonWords) {
                if (searchWord.equalsIgnoreCase(commonWord)) {
                    isCommonWord = true;
                    break;
                }
            }
            
            if (!isCommonWord && searchWord.length() > 2) { // Only count meaningful words (length > 2)
                totalMeaningfulWords++;
                if (fullName.contains(searchWord)) {
                    meaningfulMatches++;
                }
            }
        }
        
        // Require at least 1 meaningful match and that most meaningful words match
        return meaningfulMatches > 0 && (totalMeaningfulWords == 0 || meaningfulMatches >= totalMeaningfulWords);
    }
    
    private boolean containsKeyWords(String searchTerm, String key) {
        // This method is now deprecated in favor of more specific matching
        String[] searchWords = searchTerm.split(" ");
        String[] keyWords = key.split(" ");
        
        int matchCount = 0;
        for (String searchWord : searchWords) {
            for (String keyWord : keyWords) {
                if (keyWord.contains(searchWord) || searchWord.contains(keyWord)) {
                    matchCount++;
                    break;
                }
            }
        }
        
        return matchCount >= Math.max(1, searchWords.length / 2);
    }
    
    private double calculateDistance(GeoPoint start, GeoPoint end) {
        if (start == null || end == null) return 0;
        
        final int R = 6371; // Radius of the Earth in kilometers
        
        double latDistance = Math.toRadians(end.getLatitude() - start.getLatitude());
        double lonDistance = Math.toRadians(end.getLongitude() - start.getLongitude());
        
        double a = Math.sin(latDistance / 2) * Math.sin(latDistance / 2)
                + Math.cos(Math.toRadians(start.getLatitude())) * Math.cos(Math.toRadians(end.getLatitude()))
                * Math.sin(lonDistance / 2) * Math.sin(lonDistance / 2);
        
        double c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        
        return R * c; // Distance in kilometers
    }
    
    private int calculateWalkingTime(double distanceKm) {
        if (distanceKm <= 0) return 0;
        
        double walkingSpeedKmh = 5.0;
        double timeHours = distanceKm / walkingSpeedKmh;
        
        return (int) Math.ceil(timeHours * 60);
    }

    private void startVoiceInput() {
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "Say your destination");
        startActivityForResult(intent, REQ_VOICE_INPUT);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        
        if (requestCode == REQ_VOICE_INPUT && resultCode == RESULT_OK) {
            ArrayList<String> results = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
            if (results != null && !results.isEmpty()) {
                String spokenText = results.get(0);
                searchField.setText(spokenText);
                announcer.speak("You said: " + spokenText);
                performSearch(spokenText);
            }
        }
    }

    private void updateMapWithRoute() {
        if (mapView != null && currentLocation != null && destinationLocation != null) {
            // Clear existing overlays
            mapView.getOverlays().clear();
            
            // Add current location marker
            Marker currentMarker = new Marker(mapView);
            currentMarker.setPosition(currentLocation);
            currentMarker.setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_BOTTOM);
            currentMarker.setTitle("Current Location");
            mapView.getOverlays().add(currentMarker);
            
            // Add destination marker
            Marker destMarker = new Marker(mapView);
            destMarker.setPosition(destinationLocation);
            destMarker.setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_BOTTOM);
            destMarker.setTitle("Destination");
            mapView.getOverlays().add(destMarker);
            
            // Add route line
            Polyline line = new Polyline();
            List<GeoPoint> points = new ArrayList<>();
            points.add(currentLocation);
            points.add(destinationLocation);
            line.setPoints(points);
            line.setWidth(8.0f);
            line.setColor(0xFF2196F3); // Blue color
            mapView.getOverlays().add(line);
            
            // Center map to show both locations
            double centerLat = (currentLocation.getLatitude() + destinationLocation.getLatitude()) / 2;
            double centerLon = (currentLocation.getLongitude() + destinationLocation.getLongitude()) / 2;
            GeoPoint center = new GeoPoint(centerLat, centerLon);
            
            IMapController mapController = mapView.getController();
            mapController.setCenter(center);
            mapController.setZoom(12.0);
            
            mapView.invalidate();
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_LOCATION) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                getCurrentLocation();
            } else {
                announcer.speak("Location permission required for navigation");
            }
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (mapView != null) {
            mapView.onResume();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (mapView != null) {
            mapView.onPause();
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (announcer != null) announcer.shutdown();
    }
}
