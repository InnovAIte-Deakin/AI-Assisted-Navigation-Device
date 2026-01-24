package com.example.myapplication;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.util.Log;
import android.util.Size;
import android.view.View;
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

import com.google.android.material.floatingactionbutton.FloatingActionButton;
import com.google.common.util.concurrent.ListenableFuture;

import org.pytorch.IValue;
import org.pytorch.LiteModuleLoader;
import org.pytorch.Module;
import org.pytorch.Tensor;
import org.pytorch.torchvision.TensorImageUtils;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.ImageFormat;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.YuvImage;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Executors;

/**
 * Voice Assistant Activity with Live Camera Scanning
 *
 * Features:
 * - Real-time camera view with YOLO object detection
 * - Voice interaction (tap mic to ask questions)
 * - AI responds based on what camera sees
 * - Overlay shows detected objects
 */
public class VoiceAssistantActivity extends AppCompatActivity {

    private static final String TAG = "VoiceAssistant";
    private static final int REQUEST_PERMISSIONS = 100;
    private static final String[] REQUIRED_PERMISSIONS = {
            Manifest.permission.CAMERA,
            Manifest.permission.RECORD_AUDIO
    };

    // UI Components
    private PreviewView cameraPreview;
    private DetectionOverlay detectionOverlay;
    private FloatingActionButton btnMicrophone;  // ✅ FIXED: Changed from ImageView
    private ImageView btnBack;
    private TextView txtStatus;
    private TextView txtDetectedObjects;
    private View overlayControls;

    // Services
    private VoiceNavigationHelper voiceHelper;
    private TTSAnnouncer announcer;

    // Camera
    private ProcessCameraProvider cameraProvider;

    // Detection state
    private List<String> currentDetections = new ArrayList<>();
    private boolean isDetecting = true;

    // ===== YOLO Model Fields =====
    private Module mlModel;
    private boolean mlModelLoaded = false;
    private final String[] CLASSES = {"book", "books", "monitor", "office-chair", "whiteboard", "table", "tv"};

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_voice_assistant);

        initializeViews();
        setupClickListeners();

        // Initialize TTS
        announcer = new TTSAnnouncer(this);

        // ===== Load YOLO Model =====
        loadMLModel();

        // Initialize Voice Navigation
        initializeVoiceNavigation();

        // Request permissions and start camera
        if (allPermissionsGranted()) {
            startCamera();
        } else {
            ActivityCompat.requestPermissions(this, REQUIRED_PERMISSIONS, REQUEST_PERMISSIONS);
        }

        // Welcome message
        announcer.speak("Voice assistant ready. Tap microphone to ask a question about your surroundings.");
    }

    private void initializeViews() {
        cameraPreview = findViewById(R.id.cameraPreview);
        detectionOverlay = findViewById(R.id.detectionOverlay);
        btnMicrophone = findViewById(R.id.btnMicrophone);
        btnBack = findViewById(R.id.btnBack);
        txtStatus = findViewById(R.id.txtStatus);
        txtDetectedObjects = findViewById(R.id.txtDetectedObjects);
        overlayControls = findViewById(R.id.overlayControls);
    }

    private void setupClickListeners() {
        // Microphone button - Start voice interaction
        btnMicrophone.setOnClickListener(v -> {
            Log.d(TAG, "Microphone button clicked");
            voiceHelper.startVoiceInteraction();
        });

        // Back button - Return to home
        btnBack.setOnClickListener(v -> {
            announcer.speak("Returning to home");
            finish();
        });

        // Camera preview tap - Show/hide controls
        cameraPreview.setOnClickListener(v -> {
            toggleControlsVisibility();
        });
    }

    private void toggleControlsVisibility() {
        if (overlayControls.getVisibility() == View.VISIBLE) {
            overlayControls.setVisibility(View.GONE);
        } else {
            overlayControls.setVisibility(View.VISIBLE);
        }
    }

    /**
     * Initialize Voice Navigation Helper
     */
    private void initializeVoiceNavigation() {
        voiceHelper = new VoiceNavigationHelper(this);

        // Use existing TTS
        voiceHelper.setTTSAnnouncer(announcer);

        // Provide current YOLO detections
        voiceHelper.setDetectionProvider(new VoiceNavigationHelper.DetectionProvider() {
            @Override
            public List<String> getCurrentDetections() {
                return new ArrayList<>(currentDetections);
            }
        });

        // Initialize
        voiceHelper.initialize();

        Log.d(TAG, "Voice navigation initialized");
    }

    /**
     * ===== LOAD YOLO MODEL =====
     */
    private void loadMLModel() {
        try {
            // Initialize SoLoader for PyTorch
            try {
                com.facebook.soloader.SoLoader.init(this, false);
                Log.d(TAG, "SoLoader initialized");
            } catch (Exception e) {
                Log.w(TAG, "SoLoader initialization failed", e);
            }

            // Copy model from assets to internal storage
            String modelPath = copyAssetToFile("models/best_lite_fixed.ptl");

            // Load model with PyTorch Lite
            Log.d(TAG, "Loading YOLO model: " + modelPath);
            mlModel = LiteModuleLoader.load(modelPath);
            mlModelLoaded = true;

            Log.d(TAG, "YOLO model loaded successfully");
            announcer.speak("Object detection model loaded");

        } catch (Exception e) {
            Log.e(TAG, "Error loading YOLO model", e);
            mlModelLoaded = false;
            announcer.speak("Running in simulation mode");
        }
    }

    /**
     * Copy asset file to internal storage
     */
    private String copyAssetToFile(String assetName) throws java.io.IOException {
        File file = new File(getFilesDir(), assetName.replace("/", "_"));

        if (file.exists()) {
            Log.d(TAG, "Model file already exists: " + file.getAbsolutePath());
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

            Log.d(TAG, "Model copied to: " + file.getAbsolutePath());
        }

        return file.getAbsolutePath();
    }

    /**
     * Start camera with object detection
     */
    private void startCamera() {
        ListenableFuture<ProcessCameraProvider> cameraProviderFuture =
                ProcessCameraProvider.getInstance(this);

        cameraProviderFuture.addListener(() -> {
            try {
                cameraProvider = cameraProviderFuture.get();
                bindCameraUseCases();
            } catch (ExecutionException | InterruptedException e) {
                Log.e(TAG, "Error starting camera", e);
                Toast.makeText(this, "Camera error: " + e.getMessage(),
                        Toast.LENGTH_SHORT).show();
            }
        }, ContextCompat.getMainExecutor(this));
    }

    /**
     * Bind camera preview and image analysis
     */
    private void bindCameraUseCases() {
        if (cameraProvider == null) {
            Log.e(TAG, "Camera provider is null");
            return;
        }

        // Preview
        Preview preview = new Preview.Builder().build();
        preview.setSurfaceProvider(cameraPreview.getSurfaceProvider());

        // Image Analysis for object detection
        ImageAnalysis imageAnalysis = new ImageAnalysis.Builder()
                .setTargetResolution(new Size(640, 480))
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build();

        imageAnalysis.setAnalyzer(Executors.newSingleThreadExecutor(), this::analyzeImage);

        // Camera selector (back camera)
        CameraSelector cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA;

        try {
            // Unbind all before rebinding
            cameraProvider.unbindAll();

            // Bind to lifecycle
            cameraProvider.bindToLifecycle(
                    this,
                    cameraSelector,
                    preview,
                    imageAnalysis
            );

            Log.d(TAG, "Camera bound successfully");

        } catch (Exception e) {
            Log.e(TAG, "Error binding camera", e);
            Toast.makeText(this, "Failed to start camera", Toast.LENGTH_SHORT).show();
        }
    }

    /**
     * ===== ANALYZE IMAGE WITH REAL YOLO =====
     */
    private void analyzeImage(ImageProxy image) {
        if (!isDetecting) {
            image.close();
            return;
        }

        try {
            if (mlModelLoaded && mlModel != null) {
                // REAL YOLO Detection
                runYOLODetection(image);
            } else {
                // Fallback to simulation
                simulateObjectDetection();
            }
        } catch (Exception e) {
            Log.e(TAG, "Error in detection", e);
            // Fallback to simulation on error
            simulateObjectDetection();
        } finally {
            image.close();
        }
    }

    /**
     * Run YOLO detection on image
     */
    private void runYOLODetection(ImageProxy image) {
        try {
            // Convert ImageProxy to Tensor
            Tensor inputTensor = preprocessImage(image);

            // Run inference
            IValue output = mlModel.forward(IValue.from(inputTensor));

            // Handle YOLOv8 output
            Tensor outputTensor;
            if (output.isTuple()) {
                IValue[] outputs = output.toTuple();
                outputTensor = outputs[0].toTensor();
            } else {
                outputTensor = output.toTensor();
            }

            // Process results on UI thread
            runOnUiThread(() -> processYOLOOutput(outputTensor));

        } catch (Exception e) {
            Log.e(TAG, "YOLO detection error", e);
            runOnUiThread(this::simulateObjectDetection);
        }
    }

    /**
     * Preprocess image for YOLO
     */
    private Tensor preprocessImage(ImageProxy image) {
        // Convert ImageProxy to Bitmap
        Bitmap bitmap = imageProxyToBitmap(image);

        // Resize to 640x640
        Bitmap resized = Bitmap.createScaledBitmap(bitmap, 640, 640, true);

        // Convert to tensor (YOLOv8 expects 0-1 normalized RGB)
        float[] mean = new float[]{0.0f, 0.0f, 0.0f};
        float[] std = new float[]{1.0f, 1.0f, 1.0f};

        return TensorImageUtils.bitmapToFloat32Tensor(resized, mean, std);
    }

    /**
     * Convert ImageProxy to Bitmap
     */
    private Bitmap imageProxyToBitmap(ImageProxy image) {
        ImageProxy.PlaneProxy[] planes = image.getPlanes();
        java.nio.ByteBuffer yBuffer = planes[0].getBuffer();
        java.nio.ByteBuffer uBuffer = planes[1].getBuffer();
        java.nio.ByteBuffer vBuffer = planes[2].getBuffer();

        int ySize = yBuffer.remaining();
        int uSize = uBuffer.remaining();
        int vSize = vBuffer.remaining();

        byte[] nv21 = new byte[ySize + uSize + vSize];
        yBuffer.get(nv21, 0, ySize);
        vBuffer.get(nv21, ySize, vSize);
        uBuffer.get(nv21, ySize + vSize, uSize);

        YuvImage yuvImage = new YuvImage(
                nv21, ImageFormat.NV21,
                image.getWidth(), image.getHeight(), null);

        ByteArrayOutputStream out = new ByteArrayOutputStream();
        yuvImage.compressToJpeg(new Rect(0, 0, yuvImage.getWidth(), yuvImage.getHeight()), 100, out);
        byte[] imageBytes = out.toByteArray();

        return BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.length);
    }

    /**
     * Process YOLO output tensor
     */
    private void processYOLOOutput(Tensor output) {
        long[] shape = output.shape();
        float[] scores = output.getDataAsFloatArray();

        Log.d(TAG, "YOLO output shape: " + java.util.Arrays.toString(shape));

        if (shape.length != 3 || shape[0] != 1) {
            Log.e(TAG, "Unexpected YOLO output shape");
            return;
        }

        int numClasses = (int)shape[1] - 4; // Subtract bbox coords
        int numAnchors = (int)shape[2];

        // Process detections
        List<DetectionOverlay.Detection> detections = new ArrayList<>();
        currentDetections.clear();

        float confidenceThreshold = 0.4f;

        for (int anchor = 0; anchor < numAnchors; anchor++) {
            // Extract bbox coordinates
            float x = scores[0 * numAnchors + anchor];
            float y = scores[1 * numAnchors + anchor];
            float w = scores[2 * numAnchors + anchor];
            float h = scores[3 * numAnchors + anchor];

            // Find best class
            float maxConf = 0;
            int bestClass = -1;

            for (int cls = 0; cls < numClasses && cls < CLASSES.length; cls++) {
                int channelIdx = 4 + cls;
                int outputIdx = channelIdx * numAnchors + anchor;

                if (outputIdx < scores.length) {
                    float rawScore = scores[outputIdx];
                    float confidence = sigmoid(rawScore);

                    if (confidence > maxConf) {
                        maxConf = confidence;
                        bestClass = cls;
                    }
                }
            }

            // Add detection if above threshold
            if (maxConf > confidenceThreshold && bestClass >= 0 && w > 0.02f && h > 0.02f) {
                DetectionOverlay.Detection detection = createDetection(
                        CLASSES[bestClass], maxConf, x, y, w, h, anchor);

                if (detection != null) {
                    detections.add(detection);

                    // Add to current detections (for voice)
                    if (!currentDetections.contains(CLASSES[bestClass])) {
                        currentDetections.add(CLASSES[bestClass]);
                    }
                }
            }
        }

        // Apply Non-Maximum Suppression
        List<DetectionOverlay.Detection> finalDetections = applyNMS(detections, 0.3f);

        // Update overlay
        if (detectionOverlay != null) {
            detectionOverlay.updateDetections(finalDetections);
        }

        // Update UI
        updateDetectionDisplay();

        Log.d(TAG, "Final detections: " + currentDetections.size() + " objects");
    }

    /**
     * Create detection with bounding box
     */
    private DetectionOverlay.Detection createDetection(String className, float confidence,
                                                       float x, float y, float w, float h, int anchor) {
        if (cameraPreview == null) return null;

        int previewWidth = cameraPreview.getWidth();
        int previewHeight = cameraPreview.getHeight();

        if (previewWidth <= 0 || previewHeight <= 0) return null;

        // Convert normalized coords to pixel coords
        float centerX = x * previewWidth;
        float centerY = y * previewHeight;
        float width = w * previewWidth;
        float height = h * previewHeight;

        // Convert to corner coords
        float left = Math.max(0, centerX - width / 2);
        float top = Math.max(0, centerY - height / 2);
        float right = Math.min(previewWidth, centerX + width / 2);
        float bottom = Math.min(previewHeight, centerY + height / 2);

        RectF boundingBox = new RectF(left, top, right, bottom);

        return new DetectionOverlay.Detection(className, confidence, boundingBox, anchor);
    }

    /**
     * Apply Non-Maximum Suppression
     */
    private List<DetectionOverlay.Detection> applyNMS(List<DetectionOverlay.Detection> detections, float iouThreshold) {
        if (detections.isEmpty()) return detections;

        // Sort by confidence
        detections.sort((a, b) -> Float.compare(b.confidence, a.confidence));

        List<DetectionOverlay.Detection> result = new ArrayList<>();
        List<DetectionOverlay.Detection> remaining = new ArrayList<>(detections);

        while (!remaining.isEmpty()) {
            DetectionOverlay.Detection best = remaining.get(0);
            result.add(best);
            remaining.remove(0);

            remaining.removeIf(detection -> {
                float iou = calculateIoU(best.boundingBox, detection.boundingBox);
                return iou > iouThreshold;
            });
        }

        return result;
    }

    /**
     * Calculate Intersection over Union
     */
    private float calculateIoU(RectF box1, RectF box2) {
        float intersectLeft = Math.max(box1.left, box2.left);
        float intersectTop = Math.max(box1.top, box2.top);
        float intersectRight = Math.min(box1.right, box2.right);
        float intersectBottom = Math.min(box1.bottom, box2.bottom);

        if (intersectLeft >= intersectRight || intersectTop >= intersectBottom) {
            return 0.0f;
        }

        float intersectionArea = (intersectRight - intersectLeft) * (intersectBottom - intersectTop);
        float area1 = (box1.right - box1.left) * (box1.bottom - box1.top);
        float area2 = (box2.right - box2.left) * (box2.bottom - box2.top);
        float unionArea = area1 + area2 - intersectionArea;

        return unionArea > 0 ? intersectionArea / unionArea : 0.0f;
    }

    /**
     * Sigmoid activation function
     */
    private float sigmoid(float x) {
        return (float) (1.0 / (1.0 + Math.exp(-x)));
    }

    /**
     * Simulate object detection (fallback when model not loaded)
     */
    private void simulateObjectDetection() {
        runOnUiThread(() -> {
            currentDetections.clear();

            // Randomly add some objects
            double random = Math.random();
            if (random > 0.7) {
                currentDetections.add("table");
            }
            if (random > 0.5) {
                currentDetections.add("chair");
            }
            if (random > 0.3) {
                currentDetections.add("monitor");
            }

            // Update UI
            updateDetectionDisplay();
        });
    }

    /**
     * Update detection display in UI
     */
    private void updateDetectionDisplay() {
        if (currentDetections.isEmpty()) {
            txtDetectedObjects.setText("No objects detected");
            txtStatus.setText("Status: Scanning room...");
        } else {
            String objectList = String.join(", ", currentDetections);
            txtDetectedObjects.setText("Detected: " + objectList);
            txtStatus.setText("Status: " + currentDetections.size() + " objects found");
        }
    }

    /**
     * Check if all permissions are granted
     */
    private boolean allPermissionsGranted() {
        for (String permission : REQUIRED_PERMISSIONS) {
            if (ContextCompat.checkSelfPermission(this, permission)
                    != PackageManager.PERMISSION_GRANTED) {
                return false;
            }
        }
        return true;
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions,
                                           @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);

        if (requestCode == REQUEST_PERMISSIONS) {
            if (allPermissionsGranted()) {
                startCamera();
            } else {
                Toast.makeText(this,
                        "Camera and microphone permissions required",
                        Toast.LENGTH_LONG).show();
                finish();
            }
        } else {
            // Forward to voice helper
            voiceHelper.onPermissionResult(requestCode, grantResults);
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();

        if (cameraProvider != null) {
            cameraProvider.unbindAll();
        }

        if (voiceHelper != null) {
            voiceHelper.release();
        }

        if (announcer != null) {
            announcer.shutdown();
        }
    }
}