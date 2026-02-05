package com.example.myapplication;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.location.Address;
import android.location.Geocoder;
import android.os.Bundle;
import android.speech.RecognizerIntent;
import android.text.Editable;
import android.text.TextWatcher;
import android.util.Log;
import android.widget.AutoCompleteTextView;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;

import com.google.android.gms.location.FusedLocationProviderClient;
import com.google.android.gms.location.LocationServices;
import com.google.android.gms.maps.CameraUpdateFactory;
import com.google.android.gms.maps.GoogleMap;
import com.google.android.gms.maps.OnMapReadyCallback;
import com.google.android.gms.maps.SupportMapFragment;
import com.google.android.gms.maps.model.LatLng;
import com.google.android.gms.maps.model.MarkerOptions;
import com.google.android.gms.maps.model.PolylineOptions;

import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public class SearchActivityWorking extends AppCompatActivity implements OnMapReadyCallback {

    private static final int REQ_LOCATION = 3001;
    private static final int REQ_VOICE_INPUT = 4001;
    private static final String TAG = "SearchActivityWorking";

    private FusedLocationProviderClient fusedClient;
    private GoogleMap googleMap;
    private TTSAnnouncer announcer;
    
    private AutoCompleteTextView searchField;
    private Button btnSearch;
    private Button btnVoiceInput;
    private ImageView btnBack;
    private TextView txtCurrentLocation;
    private TextView txtDestination;
    private TextView txtDistance;
    private TextView txtDuration;
    
    private LatLng currentLocation;
    private LatLng destinationLocation;
    private String currentAddress = "";
    private PlaceSuggestionAdapter searchAdapter;
    
    // Offline place database
    private Map<String, PlaceInfo> offlinePlaces;

    private static class PlaceInfo {
        final LatLng latLng;
        final String fullName;
        final String address;
        final double distance;
        final int walkingMinutes;

        PlaceInfo(LatLng latLng, String fullName, String address, double distance, int walkingMinutes) {
            this.latLng = latLng;
            this.fullName = fullName;
            this.address = address;
            this.distance = distance;
            this.walkingMinutes = walkingMinutes;
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_search);

        initializeViews();
        setupOfflinePlaces();
        setupLocationServices();
        setupMap();
        setupSearchField();
        setupClickListeners();
        
        // Announce activity start
        announcer.speak("Search activity opened. Enter your destination or use voice input. Currently using offline mode with local database.");
    }

    private void initializeViews() {
        announcer = new TTSAnnouncer(this);
        searchField = findViewById(R.id.searchField);
        btnSearch = findViewById(R.id.btnSearch);
        btnVoiceInput = findViewById(R.id.btnVoiceInput);
        btnBack = findViewById(R.id.btnBack);
        txtCurrentLocation = findViewById(R.id.txtCurrentLocation);
        txtDestination = findViewById(R.id.txtDestination);
        txtDistance = findViewById(R.id.txtDistance);
        txtDuration = findViewById(R.id.txtDuration);
    }

    private void setupOfflinePlaces() {
        offlinePlaces = new HashMap<>();
        
        // Popular universities - distances will be calculated dynamically
        offlinePlaces.put("deakin university geelong", new PlaceInfo(
            new LatLng(-38.1946, 144.3054), 
            "Deakin University - Geelong Campus", 
            "Geelong Waurn Ponds Campus, 75 Pigdons Road, Waurn Ponds VIC 3216",
            0, 0)); // Will be calculated
        
        offlinePlaces.put("deakin university burwood", new PlaceInfo(
            new LatLng(-37.8471, 145.1151), 
            "Deakin University - Burwood Campus", 
            "221 Burwood Highway, Burwood VIC 3125",
            0, 0)); // Will be calculated
        
        offlinePlaces.put("melbourne university", new PlaceInfo(
            new LatLng(-37.7964, 144.9612), 
            "University of Melbourne - Parkville Campus", 
            "Grattan Street, Parkville VIC 3010",
            0, 0)); // Will be calculated
        
        offlinePlaces.put("monash university", new PlaceInfo(
            new LatLng(-37.9105, 145.1362), 
            "Monash University - Clayton Campus", 
            "Wellington Road, Clayton VIC 3800",
            0, 0)); // Will be calculated
        
        // Popular locations
        offlinePlaces.put("melbourne central", new PlaceInfo(
            new LatLng(-37.8100, 144.9633), 
            "Melbourne Central", 
            "211 La Trobe Street, Melbourne VIC 3000",
            0, 0)); // Will be calculated
        
        offlinePlaces.put("melbourne", new PlaceInfo(
            new LatLng(-37.8136, 144.9631), 
            "Melbourne CBD", 
            "Melbourne VIC 3000, Australia",
            0, 0)); // Will be calculated
        
        offlinePlaces.put("flinders street station", new PlaceInfo(
            new LatLng(-37.8183, 144.9671), 
            "Flinders Street Station", 
            "Flinders Street, Melbourne VIC 3000",
            0, 0)); // Will be calculated
        
        offlinePlaces.put("southern cross station", new PlaceInfo(
            new LatLng(-37.8184, 144.9525), 
            "Southern Cross Station", 
            "99 Spencer Street, Melbourne VIC 3000",
            0, 0)); // Will be calculated
        
        // Shopping centers
        offlinePlaces.put("chadstone", new PlaceInfo(
            new LatLng(-37.8859, 145.0839), 
            "Chadstone Shopping Centre", 
            "1341 Dandenong Road, Chadstone VIC 3148",
            0, 0)); // Will be calculated
        
        offlinePlaces.put("chapel street", new PlaceInfo(
            new LatLng(-37.8467, 144.9894), 
            "Chapel Street - Prahran", 
            "Chapel Street, Prahran VIC 3181",
            0, 0)); // Will be calculated
    }

    private void setupLocationServices() {
        fusedClient = LocationServices.getFusedLocationProviderClient(this);
        ensureLocationPermission();
    }

    private void setupMap() {
        SupportMapFragment mapFragment = (SupportMapFragment) getSupportFragmentManager()
                .findFragmentById(R.id.mapFragment);
        if (mapFragment != null) {
            mapFragment.getMapAsync(this);
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
                if (s.length() > 2) {
                    performOfflineSearch(s.toString());
                }
            }

            @Override
            public void afterTextChanged(Editable s) {}
        });

        // Handle item selection
        searchField.setOnItemClickListener((parent, view, position, id) -> {
            String selectedPlace = (String) parent.getItemAtPosition(position);
            // Extract just the primary text for the search field
            String primaryText = selectedPlace.contains(" - ") ? 
                    selectedPlace.split(" - ", 2)[0] : selectedPlace;
            searchField.setText(primaryText);
            announcer.speak("Selected: " + primaryText);
            performSearch(selectedPlace);
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
                    currentLocation = new LatLng(location.getLatitude(), location.getLongitude());
                    updateCurrentLocationDisplay();
                    announcer.speak("Current location found: " + currentAddress);
                } else {
                    // Fallback to Melbourne CBD for testing
                    currentLocation = new LatLng(-37.8136, 144.9631);
                    currentAddress = "Melbourne CBD (simulated)";
                    txtCurrentLocation.setText("Current: " + currentAddress);
                    announcer.speak("Using simulated location: " + currentAddress);
                }
            });
        }
    }

    private void updateCurrentLocationDisplay() {
        if (currentLocation != null) {
            try {
                Geocoder geocoder = new Geocoder(this, Locale.getDefault());
                List<Address> addresses = geocoder.getFromLocation(currentLocation.latitude, currentLocation.longitude, 1);
                if (addresses != null && !addresses.isEmpty()) {
                    currentAddress = addresses.get(0).getAddressLine(0);
                    txtCurrentLocation.setText("Current: " + currentAddress);
                }
            } catch (IOException e) {
                currentAddress = String.format(Locale.getDefault(), "%.5f, %.5f", 
                        currentLocation.latitude, currentLocation.longitude);
                txtCurrentLocation.setText("Current: " + currentAddress);
            }
        }
    }

    private void performOfflineSearch(String query) {
        Log.d(TAG, "Performing offline search for: " + query);
        
        List<String> suggestions = new ArrayList<>();
        String lowerQuery = query.toLowerCase();
        
        // Search through offline places
        for (Map.Entry<String, PlaceInfo> entry : offlinePlaces.entrySet()) {
            if (entry.getKey().contains(lowerQuery) || entry.getValue().fullName.toLowerCase().contains(lowerQuery)) {
                String suggestion = entry.getValue().fullName + " - " + entry.getValue().address;
                suggestions.add(suggestion);
            }
        }
        
        // Add some generic suggestions if no matches found
        if (suggestions.isEmpty()) {
            suggestions.add(query + " - Melbourne, Victoria, Australia");
            suggestions.add(query + " - Burwood, Victoria, Australia");
            suggestions.add(query + " - Geelong, Victoria, Australia");
        }
        
        searchAdapter.updateSuggestions(suggestions);
        searchField.showDropDown();
    }

    private void performSearch(String query) {
        Log.d(TAG, "Performing search for: " + query);
        announcer.speak("Searching for " + query);
        
        // Extract the primary text if it's a full suggestion (e.g., "Deakin University - Geelong Campus" -> "deakin university")
        String searchTerm = query.toLowerCase();
        if (searchTerm.contains(" - ")) {
            searchTerm = searchTerm.split(" - ", 2)[0];
        }
        
        PlaceInfo foundPlace = null;
        
        // Search for match using key terms
        for (Map.Entry<String, PlaceInfo> entry : offlinePlaces.entrySet()) {
            String key = entry.getKey();
            String fullName = entry.getValue().fullName.toLowerCase();
            
            // Check if search term matches key or full name
            if (key.contains(searchTerm) || fullName.contains(searchTerm) || 
                searchTerm.contains(key) || containsKeyWords(searchTerm, key)) {
                foundPlace = entry.getValue();
                break;
            }
        }
        
        if (foundPlace != null) {
            destinationLocation = foundPlace.latLng;
            
            // Calculate real distance and time based on current location
            if (currentLocation != null) {
                double distance = calculateDistance(currentLocation, destinationLocation);
                int walkingMinutes = calculateWalkingTime(distance);
                
                updateMapWithRoute();
                announcer.speak(String.format("Route found to %s. Distance: %.1f kilometers. Estimated walking time: %d minutes.", 
                    foundPlace.fullName, distance, walkingMinutes));
                
                // Update display
                txtDestination.setText("Destination: " + foundPlace.fullName);
                txtDistance.setText(String.format("Distance: %.1f km", distance));
                txtDuration.setText(String.format("Walking time: %d min", walkingMinutes));
            } else {
                updateMapWithRoute();
                announcer.speak("Route found to " + foundPlace.fullName + ". Please wait for location services to calculate distance.");
                
                // Update display
                txtDestination.setText("Destination: " + foundPlace.fullName);
                txtDistance.setText("Distance: Calculating...");
                txtDuration.setText("Walking time: Calculating...");
            }
        } else {
            announcer.speak("Location not found in offline database. Please try searching for universities, Melbourne CBD, or popular landmarks.");
        }
    }
    
    private boolean containsKeyWords(String searchTerm, String key) {
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
        
        // Consider it a match if at least half the words match
        return matchCount >= Math.max(1, searchWords.length / 2);
    }
    
    /**
     * Calculate the distance between two LatLng points using the Haversine formula
     * @param start Starting location
     * @param end Ending location
     * @return Distance in kilometers
     */
    private double calculateDistance(LatLng start, LatLng end) {
        if (start == null || end == null) return 0;
        
        final int R = 6371; // Radius of the Earth in kilometers
        
        double latDistance = Math.toRadians(end.latitude - start.latitude);
        double lonDistance = Math.toRadians(end.longitude - start.longitude);
        
        double a = Math.sin(latDistance / 2) * Math.sin(latDistance / 2)
                + Math.cos(Math.toRadians(start.latitude)) * Math.cos(Math.toRadians(end.latitude))
                * Math.sin(lonDistance / 2) * Math.sin(lonDistance / 2);
        
        double c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        
        return R * c; // Distance in kilometers
    }
    
    /**
     * Calculate walking time based on distance
     * Uses average walking speed of 5 km/h
     * @param distanceKm Distance in kilometers
     * @return Walking time in minutes
     */
    private int calculateWalkingTime(double distanceKm) {
        if (distanceKm <= 0) return 0;
        
        // Average walking speed: 5 km/h
        double walkingSpeedKmh = 5.0;
        double timeHours = distanceKm / walkingSpeedKmh;
        
        // Convert to minutes and round up
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

    @Override
    public void onMapReady(GoogleMap map) {
        googleMap = map;
        
        if (currentLocation != null) {
            googleMap.addMarker(new MarkerOptions()
                    .position(currentLocation)
                    .title("Current Location"));
            googleMap.moveCamera(CameraUpdateFactory.newLatLngZoom(currentLocation, 15));
        }
    }

    private void updateMapWithRoute() {
        if (googleMap != null && currentLocation != null && destinationLocation != null) {
            // Clear existing markers
            googleMap.clear();
            
            // Add current location marker
            googleMap.addMarker(new MarkerOptions()
                    .position(currentLocation)
                    .title("Current Location"));
            
            // Add destination marker
            googleMap.addMarker(new MarkerOptions()
                    .position(destinationLocation)
                    .title("Destination"));
            
            // Add route line (simplified - straight line)
            googleMap.addPolyline(new PolylineOptions()
                    .add(currentLocation, destinationLocation)
                    .width(8)
                    .color(0xFF2196F3)); // Blue color
            
            // Move camera to show both locations
            LatLng center = new LatLng(
                    (currentLocation.latitude + destinationLocation.latitude) / 2,
                    (currentLocation.longitude + destinationLocation.longitude) / 2
            );
            googleMap.moveCamera(CameraUpdateFactory.newLatLngZoom(center, 12));
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
    protected void onDestroy() {
        super.onDestroy();
        if (announcer != null) announcer.shutdown();
    }
}
