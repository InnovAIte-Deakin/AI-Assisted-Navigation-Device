package com.example.myapplication;

import android.Manifest;
import android.content.pm.PackageManager;
import android.location.Location;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.util.Size;
import android.view.View;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
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

import android.graphics.RectF;
import java.util.ArrayList;
import java.util.List;
import com.google.android.gms.location.LocationServices;
import com.google.common.util.concurrent.ListenableFuture;

import org.pytorch.IValue;
import org.pytorch.Module;
import org.pytorch.Tensor;
import org.pytorch.torchvision.TensorImageUtils;
import org.pytorch.LiteModuleLoader;

import com.facebook.soloader.SoLoader;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.ByteBuffer;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Executors;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.ImageFormat;
import android.graphics.Rect;
import android.graphics.YuvImage;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;

public class CameraNavigationActivity extends AppCompatActivity {

    private static final String TAG = "CameraNavigation";
    private static final int REQUEST_CODE_PERMISSIONS = 1001;
    private static final String[] REQUIRED_PERMISSIONS = {Manifest.permission.CAMERA};

    // UI Components
    private PreviewView cameraPreview;
    private DetectionOverlay detectionOverlay;
    private TextView txtDestination;
    private TextView txtDistance;
    private TextView txtSteps;
    private TextView txtDetectedObjects;
    private TextView txtLastAnnouncement;
    private Button btnPauseResume;
    private Button btnRepeatLast;
    private ImageView btnBack;
    private TextView txtNavigatingTo;
    private LinearLayout statusBar;
    
    // Detection mode
    private boolean isDetectionOnlyMode = false;

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
    
    // Performance monitoring
    private long perfStartMs;
    private long totalInferenceMs = 0;
    private int perfFrames = 0;
    private long lastFpsTick = 0;
    private int framesSinceTick = 0;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_camera_navigation);

        initializeViews();
        
        // Initialize TTS first (needed for detection mode)
        announcer = new TTSAnnouncer(this);
        
        getNavigationData();
        if (!isDetectionOnlyMode) {
            setupLocationTracking();
        }
        setupClickListeners();

        // Initialize SoLoader for PyTorch Lite
        try {
            SoLoader.init(this, false);
            Log.d(TAG, "SoLoader initialized successfully");
            
            // Manually load PyTorch Lite libraries in correct order
            try {
                System.loadLibrary("c++_shared");
                Log.d(TAG, "c++_shared loaded");
            } catch (Exception e) {
                Log.w(TAG, "c++_shared not loaded: " + e.getMessage());
            }
            
            try {
                System.loadLibrary("fbjni");
                Log.d(TAG, "fbjni loaded");
            } catch (Exception e) {
                Log.w(TAG, "fbjni not loaded: " + e.getMessage());
            }
            
            try {
                System.loadLibrary("pytorch_jni_lite");
                Log.d(TAG, "pytorch_jni_lite loaded");
            } catch (Exception e) {
                Log.w(TAG, "pytorch_jni_lite not loaded: " + e.getMessage());
            }
            
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
        detectionOverlay = findViewById(R.id.detectionOverlay);
        txtDestination = findViewById(R.id.txtDestination);
        txtNavigatingTo = findViewById(R.id.txtNavigatingTo);
        txtDistance = findViewById(R.id.txtDistance);
        txtSteps = findViewById(R.id.txtSteps);
        txtDetectedObjects = findViewById(R.id.txtDetectedObjects);
        txtLastAnnouncement = findViewById(R.id.txtLastAnnouncement);
        btnPauseResume = findViewById(R.id.btnPauseResume);
        btnRepeatLast = findViewById(R.id.btnRepeatLast);
        btnBack = findViewById(R.id.btnBack);
        statusBar = findViewById(R.id.statusBar);
    }

    private void getNavigationData() {
        // Check if this is detection-only mode
        isDetectionOnlyMode = getIntent().getBooleanExtra("detection_only_mode", false);
        
        if (isDetectionOnlyMode) {
            Log.d(TAG, "Starting in DETECTION-ONLY mode");
            setupDetectionOnlyMode();
        } else {
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
    }

    private void setupDetectionOnlyMode() {
        Log.d(TAG, "Setting up detection-only mode");
        
        // Update UI for detection mode
        txtNavigatingTo.setText("Object Detection Mode");
        txtDestination.setText("Or go back to Home Screen");
        
        // Hide navigation-specific UI
        statusBar.setVisibility(View.GONE);
        
        // Update announcement (with null check)
        if (announcer != null) {
            announcer.speak("Object detection mode activated");
        } else {
            Log.w(TAG, "TTSAnnouncer not initialized yet");
        }
        
        Log.d(TAG, "Detection-only mode setup complete");
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
            if (isDetectionOnlyMode) {
                Log.d(TAG, "Returning to home from detection mode");
                announcer.speak("Returning to home");
            } else {
                Log.d(TAG, "Attempting to speak: Returning to search");
                announcer.speak("Returning to search");
            }
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
            String modelPath = copyAssetToFile("models/best_lite_fixed.ptl");
            
            // Use LiteModuleLoader for PyTorch Lite
            Log.d(TAG, "Loading model with PyTorch Lite: " + modelPath);
            mlModel = LiteModuleLoader.load(modelPath);
            mlModelLoaded = true;
            Log.d(TAG, "FIXED ML Model loaded successfully with PyTorch Lite");
            announcer.speak("Fixed object detection model loaded");
            
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

        perfStartMs = System.currentTimeMillis();
        
        try {
            if (mlModelLoaded && mlModel != null) {
                Log.d(TAG, "Running REAL inference with best.pt model");
                
                // Convert ImageProxy to Tensor
                Tensor inputTensor = preprocessImage(image);
                
                // Run inference
                Log.d(TAG, "Input tensor shape: " + java.util.Arrays.toString(inputTensor.shape()));
                IValue output = mlModel.forward(IValue.from(inputTensor));
                
                // Handle YOLOv8 tuple output
                Tensor outputTensor;
                if (output.isTuple()) {
                    Log.d(TAG, "Model output is tuple (YOLOv8 format)");
                    IValue[] outputs = output.toTuple();
                    Log.d(TAG, "Tuple has " + outputs.length + " elements");
                    // Use the first output (main detection tensor)
                    outputTensor = outputs[0].toTensor();
                } else {
                    Log.d(TAG, "Model output is tensor");
                    outputTensor = output.toTensor();
                }
                
                // Process results
                runOnUiThread(() -> processModelOutput(outputTensor));
                
            } else {
                Log.d(TAG, "Model not loaded, using simulation");
                //runOnUiThread(() -> simulateObjectDetection());
            }
            
        } catch (Exception e) {
            Log.e(TAG, "Error in real inference, falling back to simulation", e);
            //runOnUiThread(() -> simulateObjectDetection());
        } finally {
            // Performance monitoring
            long elapsed = System.currentTimeMillis() - perfStartMs;
            totalInferenceMs += elapsed;
            perfFrames++;
            framesSinceTick++;

            // Log average latency every 30 frames
            if (perfFrames % 30 == 0) {
                long avg = totalInferenceMs / perfFrames;
                Log.d(TAG, "Avg inference latency: " + avg + " ms over " + perfFrames + " frames");
            }

            // Compute FPS every second
            long now = System.currentTimeMillis();
            if (lastFpsTick == 0) lastFpsTick = now;
            if (now - lastFpsTick >= 1000) {
                int fps = framesSinceTick;
                Log.d(TAG, "FPS: " + fps);
                framesSinceTick = 0;
                lastFpsTick = now;
            }
            
            image.close();
        }
    }

    private Tensor preprocessImage(ImageProxy image) {
        try {
            // TEMPORARILY DISABLED: Use static training image instead of camera
            // Bitmap testBitmap = loadTestImageFromAssets();
            // if (testBitmap != null) {
            //     Log.d(TAG, "Using STATIC TRAINING IMAGE for testing");
            //     return preprocessBitmap(testBitmap);
            // }
            
            // Fallback to camera image
            Log.d(TAG, "Input image size: " + image.getWidth() + "x" + image.getHeight());
            
            // Convert ImageProxy to Bitmap
            Bitmap bitmap = imageProxyToBitmap(image);
            Log.d(TAG, "Bitmap size: " + bitmap.getWidth() + "x" + bitmap.getHeight());
            
            // Resize to model input size (assuming 640x640 for YOLO)
            Bitmap resized = Bitmap.createScaledBitmap(bitmap, 640, 640, true);
            Log.d(TAG, "Resized to: 640x640");
            
            // Convert to tensor with SIMPLE YOLOv8 normalization (0-1, no ImageNet mean/std)
            // YOLOv8 expects RGB channel order, simple pixel/255.0 normalization
            float[] mean = new float[]{0.0f, 0.0f, 0.0f}; // No mean subtraction
            float[] std = new float[]{1.0f, 1.0f, 1.0f};   // No std division
            
            // IMPORTANT: TensorImageUtils.bitmapToFloat32Tensor uses RGB order (correct for YOLOv8)
            Tensor tensor = TensorImageUtils.bitmapToFloat32Tensor(resized, mean, std);
            
            Log.d(TAG, "Input tensor shape: " + java.util.Arrays.toString(tensor.shape()));
            
            // DEBUG: Check tensor values to verify preprocessing
            float[] tensorData = tensor.getDataAsFloatArray();
            if (tensorData.length >= 10) {
                Log.d(TAG, "Input tensor first 10 values: " + java.util.Arrays.toString(
                    java.util.Arrays.copyOfRange(tensorData, 0, 10)));
                
                // Calculate statistics
                float sum = 0, min = Float.MAX_VALUE, max = Float.MIN_VALUE;
                for (int i = 0; i < Math.min(1000, tensorData.length); i++) { // Sample first 1000 values
                    float val = tensorData[i];
                    sum += val;
                    min = Math.min(min, val);
                    max = Math.max(max, val);
                }
                float sampleMean = sum / Math.min(1000, tensorData.length);
                Log.d(TAG, "Input tensor stats (first 1000): mean=" + String.format("%.6f", sampleMean) + 
                          ", min=" + String.format("%.6f", min) + ", max=" + String.format("%.6f", max));
            }
            
            return tensor;
                
        } catch (Exception e) {
            Log.e(TAG, "Error preprocessing image", e);
            throw e;
        }
    }
    
    private Bitmap imageProxyToBitmap(ImageProxy image) {
        ImageProxy.PlaneProxy[] planes = image.getPlanes();
        ByteBuffer yBuffer = planes[0].getBuffer();
        ByteBuffer uBuffer = planes[1].getBuffer();
        ByteBuffer vBuffer = planes[2].getBuffer();

        int ySize = yBuffer.remaining();
        int uSize = uBuffer.remaining();
        int vSize = vBuffer.remaining();

        byte[] nv21 = new byte[ySize + uSize + vSize];
        yBuffer.get(nv21, 0, ySize);
        vBuffer.get(nv21, ySize, vSize);
        uBuffer.get(nv21, ySize + vSize, uSize);

        YuvImage yuvImage = new YuvImage(nv21, ImageFormat.NV21, image.getWidth(), image.getHeight(), null);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        yuvImage.compressToJpeg(new Rect(0, 0, yuvImage.getWidth(), yuvImage.getHeight()), 100, out);
        byte[] imageBytes = out.toByteArray();
        
        return android.graphics.BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.length);
    }
    
    private void processModelOutput(Tensor output) {
        try {
            long[] shape = output.shape();
            float[] scores = output.getDataAsFloatArray();
            
            Log.d(TAG, "Model output shape: " + java.util.Arrays.toString(shape));
            Log.d(TAG, "Model output size: " + scores.length);
            
            // YOLOv8 output format: [1, num_classes + 4, num_anchors]
            // For your model: [1, 11, 8400] = [batch, classes+coords, anchors]
            if (shape.length != 3 || shape[0] != 1) {
                Log.e(TAG, "Unexpected output shape for YOLOv8");
                return;
            }
            
            int numClasses = (int)shape[1] - 4; // 11 - 4 = 7 classes
            int numAnchors = (int)shape[2]; // 8400
            
            Log.d(TAG, "Processing YOLOv8 output: " + numClasses + " classes, " + numAnchors + " anchors");
            
            String bestDetection = processYOLOv8Output(scores, numClasses, numAnchors);
            
            String detectionResult;
            if (bestDetection != null) {
                detectionResult = "REAL MODEL: " + bestDetection;
                Log.d(TAG, "DETECTION: " + detectionResult);
            } else {
                detectionResult = "REAL MODEL: No confident detections";
                Log.d(TAG, "NO DETECTION: " + detectionResult);
            }
            
            // Update UI
            txtDetectedObjects.setText("Objects detected: " + detectionResult);
            lastAnnouncement = detectionResult;
            txtLastAnnouncement.setText("Last: " + lastAnnouncement);
            
            // Announce with timing control
            announceObjects(detectionResult);
            
        } catch (Exception e) {
            Log.e(TAG, "Error processing model output", e);
            // Show error in UI
            txtDetectedObjects.setText("Error: " + e.getMessage());
        }
    }
    
    private String processYOLOv8Output(float[] output, int numClasses, int numAnchors) {
        // YOLOv8 format: [batch, num_classes + 4_coords, num_anchors]
        // For shape [1, 11, 8400]: 
        // - First 4 channels are bbox coords (x, y, w, h)
        // - Last 7 channels are class scores
        // - Data is stored as: [all_anchors_channel_0, all_anchors_channel_1, ...]
        
        float confidenceThreshold = 0.4f; // Temporarily lower to see detections
        float debugThreshold = 0.49999f; // For debugging
        int maxDetections = 10; // Limit to top 10 detections
        float minBoxSize = 0.02f; // Minimum box size (2% of image)
        
        List<DetectionOverlay.Detection> detections = new ArrayList<>();
        
        // Debug: Log raw values (reduced logging for performance)
        Log.d(TAG, "Processing YOLOv8 output with bounding boxes");
        
        // YOLOv8 output format: [batch, channels, anchors] where channels = [x, y, w, h, class1, class2, ...]
        // Channel layout: [x0,x1,...,x8399, y0,y1,...,y8399, w0,w1,...,w8399, h0,h1,...,h8399, cls0_0,cls0_1,...,cls0_8399, ...]
        
        for (int anchor = 0; anchor < numAnchors; anchor++) {
            // Extract bounding box coordinates (channels 0-3)
            float x = output[0 * numAnchors + anchor]; // Center X (normalized)
            float y = output[1 * numAnchors + anchor]; // Center Y (normalized)
            float w = output[2 * numAnchors + anchor]; // Width (normalized)
            float h = output[3 * numAnchors + anchor]; // Height (normalized)
            
            // Find best class for this anchor
            float maxClassConf = 0;
            int bestClassIdx = -1;
            
            for (int classIdx = 0; classIdx < numClasses && classIdx < CLASSES.length; classIdx++) {
                int channelIdx = 4 + classIdx; // Class scores start after bbox coordinates
                int outputIndex = channelIdx * numAnchors + anchor;
                
                if (outputIndex < output.length) {
                    float rawScore = output[outputIndex];
                    float confidence = sigmoid(rawScore);
                    
                    if (confidence > maxClassConf) {
                        maxClassConf = confidence;
                        bestClassIdx = classIdx;
                    }
                }
            }
            
            // Check if this detection meets our threshold and size requirements
            if (maxClassConf > confidenceThreshold && bestClassIdx >= 0) {
                // Filter out tiny boxes (likely false positives)
                if (w > minBoxSize && h > minBoxSize) {
                    // Convert normalized coordinates to pixel coordinates
                    DetectionOverlay.Detection detection = createDetection(
                        CLASSES[bestClassIdx], 
                        maxClassConf, 
                        x, y, w, h, 
                        anchor
                    );
                    
                    if (detection != null) {
                        detections.add(detection);
                        Log.d(TAG, "Detection: " + detection.toString());
                    }
                }
            }
            
            // Debug logging for first few anchors
            if (anchor < 10 && maxClassConf > debugThreshold) {
                Log.d(TAG, "  Anchor " + anchor + " best: " + (bestClassIdx >= 0 ? CLASSES[bestClassIdx] : "none") + 
                      " conf=" + String.format("%.6f", maxClassConf) + 
                      " bbox=[" + String.format("%.3f,%.3f,%.3f,%.3f", x, y, w, h) + "]");
                
                // Show raw values for first few
                if (anchor < 3 && bestClassIdx >= 0) {
                    int channelIdx = 4 + bestClassIdx;
                    int outputIndex = channelIdx * numAnchors + anchor;
                    float rawScore = output[outputIndex];
                    Log.d(TAG, "    Raw score: " + String.format("%.6f", rawScore) + " -> sigmoid: " + String.format("%.6f", sigmoid(rawScore)));
                }
            }
        }
        
        // Sort detections by confidence (highest first) and limit to maxDetections
        detections.sort((a, b) -> Float.compare(b.confidence, a.confidence));
        if (detections.size() > maxDetections) {
            detections = detections.subList(0, maxDetections);
        }
        
        // Apply Non-Maximum Suppression to remove overlapping boxes
        final List<DetectionOverlay.Detection> finalDetections = applyNMS(detections, 0.3f); // 30% overlap threshold
        
        // Update overlay with filtered detections
        runOnUiThread(() -> {
            if (detectionOverlay != null) {
                detectionOverlay.updateDetections(finalDetections);
            }
        });
        
        // Return summary for TTS
        if (!finalDetections.isEmpty()) {
            DetectionOverlay.Detection bestDetection = finalDetections.get(0);
            float maxConf = bestDetection.confidence;
            
            // Find highest confidence detection
            for (DetectionOverlay.Detection det : finalDetections) {
                if (det.confidence > maxConf) {
                    maxConf = det.confidence;
                    bestDetection = det;
                }
            }
            
            Log.d(TAG, "Found " + finalDetections.size() + " detections, best: " + bestDetection.toString());
            return bestDetection.className + " detected (conf: " + String.format("%.3f", bestDetection.confidence) + 
                   ") + " + (finalDetections.size() - 1) + " others";
        }
        
        // Clear overlay if no detections
        runOnUiThread(() -> {
            if (detectionOverlay != null) {
                detectionOverlay.clearDetections();
            }
        });
        
        return null;
    }
    
    private DetectionOverlay.Detection createDetection(String className, float confidence, 
                                                      float x, float y, float w, float h, int anchor) {
        // Get camera preview dimensions
        if (cameraPreview == null) return null;
        
        int previewWidth = cameraPreview.getWidth();
        int previewHeight = cameraPreview.getHeight();
        
        if (previewWidth <= 0 || previewHeight <= 0) return null;
        
        // Convert from normalized coordinates (0-1) to pixel coordinates
        // YOLOv8 uses center-based coordinates
        float centerX = x * previewWidth;
        float centerY = y * previewHeight;
        float width = w * previewWidth;
        float height = h * previewHeight;
        
        // Convert to corner coordinates (left, top, right, bottom)
        float left = centerX - width / 2;
        float top = centerY - height / 2;
        float right = centerX + width / 2;
        float bottom = centerY + height / 2;
        
        // Clamp to view bounds
        left = Math.max(0, Math.min(left, previewWidth));
        top = Math.max(0, Math.min(top, previewHeight));
        right = Math.max(0, Math.min(right, previewWidth));
        bottom = Math.max(0, Math.min(bottom, previewHeight));
        
        RectF boundingBox = new RectF(left, top, right, bottom);
        
        return new DetectionOverlay.Detection(className, confidence, boundingBox, anchor);
    }
    
    /**
     * Apply Non-Maximum Suppression to remove overlapping bounding boxes
     */
    private List<DetectionOverlay.Detection> applyNMS(List<DetectionOverlay.Detection> detections, float iouThreshold) {
        if (detections.isEmpty()) return detections;
        
        List<DetectionOverlay.Detection> result = new ArrayList<>();
        List<DetectionOverlay.Detection> remaining = new ArrayList<>(detections);
        
        while (!remaining.isEmpty()) {
            // Take the detection with highest confidence
            DetectionOverlay.Detection best = remaining.get(0);
            result.add(best);
            remaining.remove(0);
            
            // Remove all detections that overlap significantly with the best one
            remaining.removeIf(detection -> {
                float iou = calculateIoU(best.boundingBox, detection.boundingBox);
                return iou > iouThreshold;
            });
        }
        
        return result;
    }
    
    /**
     * Calculate Intersection over Union (IoU) between two bounding boxes
     */
    private float calculateIoU(RectF box1, RectF box2) {
        // Calculate intersection area
        float intersectLeft = Math.max(box1.left, box2.left);
        float intersectTop = Math.max(box1.top, box2.top);
        float intersectRight = Math.min(box1.right, box2.right);
        float intersectBottom = Math.min(box1.bottom, box2.bottom);
        
        if (intersectLeft >= intersectRight || intersectTop >= intersectBottom) {
            return 0.0f; // No intersection
        }
        
        float intersectionArea = (intersectRight - intersectLeft) * (intersectBottom - intersectTop);
        
        // Calculate union area
        float area1 = (box1.right - box1.left) * (box1.bottom - box1.top);
        float area2 = (box2.right - box2.left) * (box2.bottom - box2.top);
        float unionArea = area1 + area2 - intersectionArea;
        
        return unionArea > 0 ? intersectionArea / unionArea : 0.0f;
    }
    
    private float sigmoid(float x) {
        return (float) (1.0 / (1.0 + Math.exp(-x)));
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

    private Bitmap loadTestImageFromAssets() {
        try {
            InputStream inputStream = getAssets().open("test_image.jpg");
            Bitmap bitmap = BitmapFactory.decodeStream(inputStream);
            inputStream.close();
            Log.d(TAG, "Successfully loaded test image from assets: " + bitmap.getWidth() + "x" + bitmap.getHeight());
            return bitmap;
        } catch (IOException e) {
            Log.w(TAG, "Could not load test image from assets, falling back to camera", e);
            return null;
        }
    }
    
    private Tensor preprocessBitmap(Bitmap bitmap) {
        try {
            Log.d(TAG, "Preprocessing bitmap: " + bitmap.getWidth() + "x" + bitmap.getHeight());
            
            // Resize to model input size (assuming 640x640 for YOLO)
            Bitmap resized = Bitmap.createScaledBitmap(bitmap, 640, 640, true);
            Log.d(TAG, "Resized to: 640x640");
            
            // Convert to normalized float tensor
            float[] pixels = new float[3 * 640 * 640];
            int[] intPixels = new int[640 * 640];
            resized.getPixels(intPixels, 0, 640, 0, 0, 640, 640);
            
            // Convert ARGB to RGB and apply YOLOv8/ImageNet normalization
            // YOLOv8 expects: (pixel/255.0 - mean) / std
            // ImageNet: mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
            float[] mean = {0.485f, 0.456f, 0.406f};
            float[] std = {0.229f, 0.224f, 0.225f};
            
            for (int i = 0; i < intPixels.length; i++) {
                int pixel = intPixels[i];
                
                // Extract RGB channels
                float r = ((pixel >> 16) & 0xFF) / 255.0f;
                float g = ((pixel >> 8) & 0xFF) / 255.0f;
                float b = (pixel & 0xFF) / 255.0f;
                
                // Apply ImageNet normalization
                pixels[i] = (r - mean[0]) / std[0]; // R
                pixels[i + 640 * 640] = (g - mean[1]) / std[1]; // G  
                pixels[i + 2 * 640 * 640] = (b - mean[2]) / std[2]; // B
            }
            
            Log.d(TAG, "Converted to float array, creating tensor...");
            return Tensor.fromBlob(pixels, new long[]{1, 3, 640, 640});
            
        } catch (Exception e) {
            Log.e(TAG, "Error preprocessing bitmap", e);
            return null;
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
