package com.example.myapplication;

import android.Manifest;
import android.content.pm.PackageManager;
import android.location.Location;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.util.Size;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.camera.core.CameraSelector;
import androidx.camera.core.ImageAnalysis;
import androidx.camera.core.ImageProxy;
import androidx.camera.core.Preview;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.view.PreviewView;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.google.android.gms.location.FusedLocationProviderClient;
import com.google.android.gms.location.LocationCallback;
import com.google.android.gms.location.LocationRequest;
import com.google.android.gms.location.LocationResult;
import com.google.android.gms.location.LocationServices;
import com.google.common.util.concurrent.ListenableFuture;

import org.pytorch.IValue;
import org.pytorch.Module;
import org.pytorch.Tensor;
import org.pytorch.torchvision.TensorImageUtils;

import com.facebook.soloader.SoLoader;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Executors;

public class CameraNavigationActivity extends AppCompatActivity {

    private static final String TAG = "CameraNavigation";
    private static final int REQUEST_CODE_PERMISSIONS = 1001;
    private static final String[] REQUIRED_PERMISSIONS = {Manifest.permission.CAMERA};

    // UI Components
    private PreviewView cameraPreview;
    private TextView txtDestination;
    private TextView txtDistance;
    private TextView txtSteps;
    private TextView txtDetectedObjects;
    private TextView txtLastAnnouncement;
    private Button btnPauseResume;
    private Button btnRepeatLast;
    private ImageView btnBack;

    // Camera and ML
    private ProcessCameraProvider cameraProvider;
    private Module mlModel;
    private boolean isDetectionPaused = false;
    private boolean mlModelLoaded = false;

    // Navigation data
    private String destinationName;
    private double destinationLat;
    private double destinationLon;
    private String lastAnnouncement = "Camera ready";

    // Location tracking
    private FusedLocationProviderClient fusedLocationClient;
    private LocationCallback locationCallback;
    private double currentDistance = 0.0;
    private int stepCount = 0;

    // TTS
    private TTSAnnouncer announcer;

    // Object detection classes from your model
    private final String[] CLASSES = {"book", "books", "monitor", "office-chair", "whiteboard", "table", "tv"};
    
    // Simulation timing
    private long lastAnnouncementTime = 0;
    private static final long ANNOUNCEMENT_INTERVAL = 3000; // 3 seconds

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_camera_navigation);

        initializeViews();
        getNavigationData();
        setupLocationTracking();
        setupClickListeners();

        // Initialize TTS
        announcer = new TTSAnnouncer(this);

        // Initialize SoLoader for PyTorch
        try {
            SoLoader.init(this, false);
            Log.d(TAG, "SoLoader initialized successfully");
        } catch (Exception e) {
            Log.w(TAG, "SoLoader initialization failed", e);
        }

        // Request camera permissions
        if (allPermissionsGranted()) {
            startCamera();
            loadMLModel();
        } else {
            ActivityCompat.requestPermissions(this, REQUIRED_PERMISSIONS, REQUEST_CODE_PERMISSIONS);
        }

        // Announce activity start
        Log.d(TAG, "Attempting to speak: Camera navigation started");
        announcer.speak("Camera navigation started. Destination: " + destinationName);
        
        // Also show visual feedback for debugging
        Toast.makeText(this, "Camera navigation started for: " + destinationName, Toast.LENGTH_LONG).show();
    }

    private void initializeViews() {
        cameraPreview = findViewById(R.id.cameraPreview);
        txtDestination = findViewById(R.id.txtDestination);
        txtDistance = findViewById(R.id.txtDistance);
        txtSteps = findViewById(R.id.txtSteps);
        txtDetectedObjects = findViewById(R.id.txtDetectedObjects);
        txtLastAnnouncement = findViewById(R.id.txtLastAnnouncement);
        btnPauseResume = findViewById(R.id.btnPauseResume);
        btnRepeatLast = findViewById(R.id.btnRepeatLast);
        btnBack = findViewById(R.id.btnBack);
    }

    private void getNavigationData() {
        // Get data passed from SearchActivity
        destinationName = getIntent().getStringExtra("destination_name");
        destinationLat = getIntent().getDoubleExtra("destination_lat", 0.0);
        destinationLon = getIntent().getDoubleExtra("destination_lon", 0.0);
        currentDistance = getIntent().getDoubleExtra("current_distance", 0.0);

        // Update UI
        if (destinationName != null) {
            txtDestination.setText(destinationName);
        }
        updateDistanceDisplay();
    }

    private void setupLocationTracking() {
        fusedLocationClient = LocationServices.getFusedLocationProviderClient(this);

        locationCallback = new LocationCallback() {
            @Override
            public void onLocationResult(@NonNull LocationResult locationResult) {
                if (locationResult.getLastLocation() != null) {
                    updateLocationAndDistance(locationResult.getLastLocation());
                }
            }
        };

        startLocationUpdates();
    }

    private void startLocationUpdates() {
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
            LocationRequest locationRequest = LocationRequest.create()
                    .setInterval(5000) // Update every 5 seconds
                    .setFastestInterval(2000)
                    .setPriority(LocationRequest.PRIORITY_HIGH_ACCURACY);

            fusedLocationClient.requestLocationUpdates(locationRequest, locationCallback, Looper.getMainLooper());
        }
    }

    private void updateLocationAndDistance(Location currentLocation) {
        if (destinationLat != 0.0 && destinationLon != 0.0) {
            float[] results = new float[1];
            Location.distanceBetween(
                    currentLocation.getLatitude(), currentLocation.getLongitude(),
                    destinationLat, destinationLon, results);

            currentDistance = results[0] / 1000.0; // Convert to kilometers
            updateDistanceDisplay();

            // Simulate step counting (in real app, use step detector sensor)
            stepCount += (int) (Math.random() * 5) + 1;
            txtSteps.setText("Steps: " + stepCount);
        }
    }

    private void updateDistanceDisplay() {
        txtDistance.setText(String.format("Distance: %.1f km", currentDistance));
    }

    private void setupClickListeners() {
        btnBack.setOnClickListener(v -> {
            Log.d(TAG, "Attempting to speak: Returning to search");
            announcer.speak("Returning to search");
            finish();
        });

        btnPauseResume.setOnClickListener(v -> {
            isDetectionPaused = !isDetectionPaused;
            String action = isDetectionPaused ? "paused" : "resumed";
            btnPauseResume.setText(isDetectionPaused ? "Resume" : "Pause");
            Log.d(TAG, "Attempting to speak: Object detection " + action);
            announcer.speak("Object detection " + action);
            Toast.makeText(this, "Detection " + action, Toast.LENGTH_SHORT).show();
        });

        btnRepeatLast.setOnClickListener(v -> {
            if (!lastAnnouncement.isEmpty()) {
                Log.d(TAG, "Attempting to repeat: " + lastAnnouncement);
                announcer.speak(lastAnnouncement);
                Toast.makeText(this, "Repeating: " + lastAnnouncement, Toast.LENGTH_SHORT).show();
            }
        });
    }

    private boolean allPermissionsGranted() {
        for (String permission : REQUIRED_PERMISSIONS) {
            if (ContextCompat.checkSelfPermission(this, permission) != PackageManager.PERMISSION_GRANTED) {
                return false;
            }
        }
        return true;
    }

    private void startCamera() {
        ListenableFuture<ProcessCameraProvider> cameraProviderFuture = ProcessCameraProvider.getInstance(this);

        cameraProviderFuture.addListener(() -> {
            try {
                cameraProvider = cameraProviderFuture.get();
                bindPreview();
            } catch (ExecutionException | InterruptedException e) {
                Log.e(TAG, "Error starting camera", e);
            }
        }, ContextCompat.getMainExecutor(this));
    }

    private void bindPreview() {
        if (cameraProvider == null) return;

        Preview preview = new Preview.Builder().build();
        preview.setSurfaceProvider(cameraPreview.getSurfaceProvider());

        ImageAnalysis imageAnalysis = new ImageAnalysis.Builder()
                .setTargetResolution(new Size(640, 480))
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build();

        imageAnalysis.setAnalyzer(Executors.newSingleThreadExecutor(), this::analyzeImage);

        CameraSelector cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA;

        try {
            cameraProvider.unbindAll();
            cameraProvider.bindToLifecycle(this, cameraSelector, preview, imageAnalysis);
        } catch (Exception e) {
            Log.e(TAG, "Error binding camera", e);
        }
    }

    private void loadMLModel() {
        try {
            // Copy model from assets to internal storage
            String modelPath = copyAssetToFile("models/best.pt");
            mlModel = Module.load(modelPath);
            mlModelLoaded = true;
            Log.d(TAG, "ML Model loaded successfully");
            announcer.speak("Object detection model loaded");
        } catch (UnsatisfiedLinkError e) {
            Log.w(TAG, "PyTorch native libraries not available - running in simulation mode", e);
            mlModelLoaded = false;
            announcer.speak("Running in simulation mode - object detection simulated");
        } catch (IOException e) {
            Log.e(TAG, "Error loading ML model file", e);
            mlModelLoaded = false;
            announcer.speak("Object detection model not found - using simulation");
        } catch (Exception e) {
            Log.e(TAG, "Unexpected error loading ML model", e);
            mlModelLoaded = false;
            announcer.speak("Object detection using simulation mode");
        }
    }

    private String copyAssetToFile(String assetName) throws IOException {
        File file = new File(getFilesDir(), assetName.replace("/", "_"));
        
        if (file.exists()) {
            return file.getAbsolutePath();
        }

        try (InputStream inputStream = getAssets().open(assetName);
             OutputStream outputStream = new FileOutputStream(file)) {
            
            byte[] buffer = new byte[4 * 1024];
            int read;
            while ((read = inputStream.read(buffer)) != -1) {
                outputStream.write(buffer, 0, read);
            }
            outputStream.flush();
        }
        return file.getAbsolutePath();
    }

    private void analyzeImage(ImageProxy image) {
        if (isDetectionPaused) {
            image.close();
            return;
        }

        try {
            if (mlModelLoaded && mlModel != null) {
                // TODO: Real ML inference will go here
                // Convert ImageProxy to Tensor, run inference, process results
                runOnUiThread(() -> simulateObjectDetection());
            } else {
                // Simulation mode for testing
                runOnUiThread(() -> simulateObjectDetection());
            }
            
        } catch (Exception e) {
            Log.e(TAG, "Error analyzing image", e);
        } finally {
            image.close();
        }
    }

    private void simulateObjectDetection() {
        // Simulate finding objects for testing purposes
        // This will be replaced with actual ML inference
        
        // Randomly simulate different scenarios
        String[] scenarios = {
            "No objects detected",
            "Table detected ahead",
            "Office chair to the right",
            "Monitor on table ahead",
            "Whiteboard on left wall",
            "Books on table"
        };
        
        int scenario = (int) (Math.random() * scenarios.length);
        String detectionResult = scenarios[scenario];
        
        // Update UI
        if (scenario == 0) {
            txtDetectedObjects.setText("Objects detected: None");
        } else {
            txtDetectedObjects.setText("Objects detected: " + detectionResult);
            
            // Create spatial announcement
            String announcement = detectionResult;
            lastAnnouncement = announcement;
            txtLastAnnouncement.setText("Last: " + announcement);
            
            // Announce with timing control
            announceObjects(announcement);
        }
    }

    private void announceObjects(String announcement) {
        // Announce detected objects with spatial information
        // Control timing to avoid announcement spam
        long currentTime = System.currentTimeMillis();
        if (currentTime - lastAnnouncementTime > ANNOUNCEMENT_INTERVAL) {
            Log.d(TAG, "Attempting to speak object detection: " + announcement);
            announcer.speak(announcement);
            lastAnnouncementTime = currentTime;
            
            // Visual feedback for debugging (will remove later)
            Toast.makeText(this, "TTS: " + announcement, Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_CODE_PERMISSIONS) {
            if (allPermissionsGranted()) {
                startCamera();
                loadMLModel();
            } else {
                Toast.makeText(this, "Camera permission required for navigation", Toast.LENGTH_SHORT).show();
                finish();
            }
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (cameraProvider != null) {
            cameraProvider.unbindAll();
        }
        if (fusedLocationClient != null && locationCallback != null) {
            fusedLocationClient.removeLocationUpdates(locationCallback);
        }
        if (announcer != null) {
            announcer.shutdown();
        }
    }
}
