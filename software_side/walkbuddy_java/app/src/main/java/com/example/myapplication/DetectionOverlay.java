package com.example.myapplication;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.RectF;
import android.util.AttributeSet;
import android.view.View;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Custom overlay view for drawing object detection bounding boxes on camera preview
 */
public class DetectionOverlay extends View {
    
    private static final String TAG = "DetectionOverlay";
    
    // Paint objects for drawing
    private Paint boundingBoxPaint;
    private Paint textPaint;
    private Paint backgroundPaint;
    
    // Detection results
    private List<Detection> detections = new ArrayList<>();
    
    // Color mapping for different classes
    private Map<String, Integer> classColors = new HashMap<>();
    
    public DetectionOverlay(Context context) {
        super(context);
        init();
    }
    
    public DetectionOverlay(Context context, AttributeSet attrs) {
        super(context, attrs);
        init();
    }
    
    public DetectionOverlay(Context context, AttributeSet attrs, int defStyleAttr) {
        super(context, attrs, defStyleAttr);
        init();
    }
    
    private void init() {
        // Initialize paint objects
        boundingBoxPaint = new Paint();
        boundingBoxPaint.setStyle(Paint.Style.STROKE);
        boundingBoxPaint.setStrokeWidth(4f);
        boundingBoxPaint.setAntiAlias(true);
        
        textPaint = new Paint();
        textPaint.setTextSize(32f);
        textPaint.setColor(Color.WHITE);
        textPaint.setAntiAlias(true);
        textPaint.setStyle(Paint.Style.FILL);
        
        backgroundPaint = new Paint();
        backgroundPaint.setStyle(Paint.Style.FILL);
        backgroundPaint.setAlpha(180); // Semi-transparent
        
        // Initialize class colors
        setupClassColors();
    }
    
    private void setupClassColors() {
        classColors.put("book", Color.GREEN);
        classColors.put("books", Color.rgb(0, 200, 0)); // Darker green
        classColors.put("monitor", Color.BLUE);
        classColors.put("office-chair", Color.RED);
        classColors.put("whiteboard", Color.MAGENTA);
        classColors.put("table", Color.CYAN);
        classColors.put("tv", Color.YELLOW);
    }
    
    /**
     * Update detections and redraw overlay
     */
    public void updateDetections(List<Detection> newDetections) {
        this.detections = new ArrayList<>(newDetections);
        invalidate(); // Trigger redraw
    }
    
    /**
     * Clear all detections
     */
    public void clearDetections() {
        detections.clear();
        invalidate();
    }
    
    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        
        // Draw each detection
        for (Detection detection : detections) {
            drawDetection(canvas, detection);
        }
    }
    
    private void drawDetection(Canvas canvas, Detection detection) {
        // Get color for this class
        int color = classColors.getOrDefault(detection.className, Color.WHITE);
        boundingBoxPaint.setColor(color);
        backgroundPaint.setColor(color);
        
        // Draw bounding box
        RectF boundingBox = detection.boundingBox;
        canvas.drawRect(boundingBox, boundingBoxPaint);
        
        // Prepare label text
        String label = detection.className + " " + String.format("%.2f", detection.confidence);
        
        // Calculate text dimensions
        Rect textBounds = new Rect();
        textPaint.getTextBounds(label, 0, label.length(), textBounds);
        
        // Draw text background
        float textX = boundingBox.left;
        float textY = boundingBox.top - 8f;
        float backgroundWidth = textBounds.width() + 16f;
        float backgroundHeight = textBounds.height() + 16f;
        
        // Ensure text background stays within view bounds
        if (textY - backgroundHeight < 0) {
            textY = boundingBox.top + backgroundHeight;
        }
        
        RectF textBackground = new RectF(
            textX, 
            textY - backgroundHeight, 
            textX + backgroundWidth, 
            textY
        );
        canvas.drawRect(textBackground, backgroundPaint);
        
        // Draw text
        canvas.drawText(label, textX + 8f, textY - 8f, textPaint);
    }
    
    /**
     * Detection data class
     */
    public static class Detection {
        public String className;
        public float confidence;
        public RectF boundingBox; // In pixel coordinates
        public int anchorIndex;
        
        public Detection(String className, float confidence, RectF boundingBox, int anchorIndex) {
            this.className = className;
            this.confidence = confidence;
            this.boundingBox = boundingBox;
            this.anchorIndex = anchorIndex;
        }
        
        @Override
        public String toString() {
            return String.format("%s (%.3f) [%.1f,%.1f,%.1f,%.1f]", 
                className, confidence, 
                boundingBox.left, boundingBox.top, boundingBox.right, boundingBox.bottom);
        }
    }
}
