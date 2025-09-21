package com.example.myapplication;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.location.Address;
import android.location.Geocoder;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;

import com.google.android.gms.location.FusedLocationProviderClient;
import com.google.android.gms.location.LocationCallback;
import com.google.android.gms.location.LocationRequest;
import com.google.android.gms.location.LocationResult;
import com.google.android.gms.location.LocationServices;

import java.io.IOException;
import java.util.List;
import java.util.Locale;

public class HomeActivity extends AppCompatActivity {

    private static final int REQ_LOCATION = 2001;
    private static final long INTERVAL_NORMAL_MS = 30_000L;

    private FusedLocationProviderClient fusedClient;
    private LocationCallback locationCallback;
    private TTSAnnouncer announcer;
    private TextView addressText;
    private Handler handler;
    private long currentInterval = INTERVAL_NORMAL_MS;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_home);

        announcer = new TTSAnnouncer(this);
        fusedClient = LocationServices.getFusedLocationProviderClient(this);
        handler = new Handler(Looper.getMainLooper());

        addressText = findViewById(R.id.txtAddress);

        findViewById(R.id.cardNavigation).setOnClickListener(v -> {
            // Immediate refresh when user taps Navigation
            requestSingleUpdate();
        });

        // Header icon click handlers
        findViewById(R.id.btnMicrophone).setOnClickListener(v -> {
            // Toggle microphone or start voice input
            Toast.makeText(this, "Microphone (placeholder)", Toast.LENGTH_SHORT).show();
        });

        findViewById(R.id.btnProfile).setOnClickListener(v -> {
            // Open profile or settings
            Toast.makeText(this, "Profile (placeholder)", Toast.LENGTH_SHORT).show();
        });

        // My Current section action buttons
        findViewById(R.id.btnStar).setOnClickListener(v -> {
            // Add current location to favorites
            Toast.makeText(this, "Added to favorites", Toast.LENGTH_SHORT).show();
        });

        findViewById(R.id.btnShare).setOnClickListener(v -> {
            // Share current location
            Toast.makeText(this, "Share location (placeholder)", Toast.LENGTH_SHORT).show();
        });

        // Action grid click handlers
        findViewById(R.id.cardSaved).setOnClickListener(v -> {
            Toast.makeText(this, "Saved locations (placeholder)", Toast.LENGTH_SHORT).show();
        });

        findViewById(R.id.cardSearch).setOnClickListener(v -> {
            Intent intent = new Intent(HomeActivity.this, SearchActivityOSM.class);
            startActivity(intent);
        });

        findViewById(R.id.cardFavourites).setOnClickListener(v -> {
            Toast.makeText(this, "Favourites (placeholder)", Toast.LENGTH_SHORT).show();
        });

        ensureLocationPermissionThenStart();

        // Bottom bar click handlers
        findViewById(R.id.btnBottomHome).setOnClickListener(v -> {
            // Already on home, just show feedback
            Toast.makeText(this, "Home", Toast.LENGTH_SHORT).show();
        });
        
        findViewById(R.id.btnBottomCamera).setOnClickListener(v -> {
            Intent intent = new Intent(HomeActivity.this, CameraNavigationActivity.class);
            intent.putExtra("detection_only_mode", true);
            startActivity(intent);
        });
        
        findViewById(R.id.btnBottomAccount).setOnClickListener(v -> {
            Toast.makeText(this, "My Account (placeholder)", Toast.LENGTH_SHORT).show();
        });
    }

    private void ensureLocationPermissionThenStart() {
        boolean fine = ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED;
        boolean coarse = ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
        if (!fine && !coarse) {
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION}, REQ_LOCATION);
            return;
        }
        // Start periodic updates and attempt an immediate fetch
        startLocationUpdates();
        requestSingleUpdate();
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
                ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
            fusedClient.getLastLocation().addOnSuccessListener(location -> {
                if (location != null) updateAddress(location.getLatitude(), location.getLongitude());
            });
        }
    }

    private void startLocationUpdates() {
        LocationRequest request = new LocationRequest.Builder(currentInterval)
                .setMinUpdateIntervalMillis(currentInterval)
                .setPriority(LocationRequest.PRIORITY_HIGH_ACCURACY)
                .build();

        if (locationCallback == null) {
            locationCallback = new LocationCallback() {
                @Override
                public void onLocationResult(@NonNull LocationResult locationResult) {
                    if (locationResult.getLastLocation() == null) return;
                    double lat = locationResult.getLastLocation().getLatitude();
                    double lng = locationResult.getLastLocation().getLongitude();
                    updateAddress(lat, lng);
                }
            };
        }

        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED && ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            return;
        }
        fusedClient.removeLocationUpdates(locationCallback);
        fusedClient.requestLocationUpdates(request, locationCallback, Looper.getMainLooper());
    }

    private void requestSingleUpdate() {
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED && ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            return;
        }
        fusedClient.getCurrentLocation(com.google.android.gms.location.Priority.PRIORITY_HIGH_ACCURACY, null)
                .addOnSuccessListener(location -> {
                    if (location != null) updateAddress(location.getLatitude(), location.getLongitude());
                });
    }

    private String lastSpoken = "";
    private void updateAddress(double lat, double lng) {
        String spoken;
        String text;
        try {
            Geocoder geocoder = new Geocoder(this, Locale.getDefault());
            List<Address> addresses = geocoder.getFromLocation(lat, lng, 1);
            if (addresses != null && !addresses.isEmpty()) {
                Address a = addresses.get(0);
                String line = a.getMaxAddressLineIndex() >= 0 ? a.getAddressLine(0) : a.getThoroughfare();
                text = line != null ? line : String.format(Locale.getDefault(), "%.5f, %.5f", lat, lng);
            } else {
                text = String.format(Locale.getDefault(), "%.5f, %.5f", lat, lng);
            }
        } catch (IOException e) {
            text = String.format(Locale.getDefault(), "%.5f, %.5f", lat, lng);
        }

        addressText.setText(text);
        spoken = "Current address: " + text;
        if (!spoken.equals(lastSpoken)) {
            announcer.speak(spoken);
            lastSpoken = spoken;
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_LOCATION) {
            boolean granted = false;
            for (int r : grantResults) granted = granted || (r == PackageManager.PERMISSION_GRANTED);
            if (granted) {
                startLocationUpdates();
                requestSingleUpdate();
                if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
                        ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
                    fusedClient.getLastLocation().addOnSuccessListener(location -> {
                        if (location != null) updateAddress(location.getLatitude(), location.getLongitude());
                    });
                }
            } else {
                Toast.makeText(this, "Location permission required", Toast.LENGTH_LONG).show();
            }
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (fusedClient != null && locationCallback != null) fusedClient.removeLocationUpdates(locationCallback);
        if (announcer != null) announcer.shutdown();
    }
}


