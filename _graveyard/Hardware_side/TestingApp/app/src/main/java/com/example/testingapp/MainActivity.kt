@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package com.example.testingapp

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Rect
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.speech.tts.TextToSpeech
import android.util.Size
import android.view.ViewGroup
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.example.testingapp.ui.components.BottomBar
import com.example.testingapp.ui.theme.InnovAIteTheme
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.objects.DetectedObject
import com.google.mlkit.vision.objects.ObjectDetection
import com.google.mlkit.vision.objects.defaults.ObjectDetectorOptions
import java.util.Locale
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicLong
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

// ------------------ Navigation ------------------
enum class Screen { HOME, VISION, SENSORS, STEPS }

// ------------------ Vision model ------------------
data class DetectionBox(
    val rect: Rect,
    val label: String?,
    val score: Float,
    val imgW: Int,
    val imgH: Int,
)

// ------------------ Activity ------------------
class MainActivity : ComponentActivity() {

    private val requestCameraPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* show rationale if you want */ }

    private val requestActivityPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* show rationale if you want */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
            != PackageManager.PERMISSION_GRANTED
        ) {
            requestCameraPermission.launch(Manifest.permission.CAMERA)
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACTIVITY_RECOGNITION)
                != PackageManager.PERMISSION_GRANTED
            ) {
                requestActivityPermission.launch(Manifest.permission.ACTIVITY_RECOGNITION)
            }
        }

        setContent { InnovAIteTheme { AppRoot() } }
    }
}

// ------------------ App root ------------------
@Composable
fun AppRoot() {
    var screen by remember { mutableStateOf(Screen.HOME) }

    BackHandler(enabled = screen != Screen.HOME) { screen = Screen.HOME }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        when (screen) {
                            Screen.HOME    -> "InnovAIte"
                            Screen.VISION  -> "Camera (Vision)"
                            Screen.SENSORS -> "Sensors"
                            Screen.STEPS   -> "Steps"
                        }
                    )
                }
            )
        },
        bottomBar = {
            if (screen != Screen.HOME) {
                BottomBar(current = screen, onSelect = { screen = it })
            }
        }
    ) { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            when (screen) {
                Screen.HOME -> HomeMenu(
                    onOpenVision = { screen = Screen.VISION },
                    onOpenSensors = { screen = Screen.SENSORS },
                    onOpenSteps = { screen = Screen.STEPS },
                )
                Screen.VISION  -> ObstacleDetectorScreen()
                Screen.SENSORS -> SensorReaderScreen()
                Screen.STEPS   -> StepCounterScreen()
            }
        }
    }
}

// ------------------ Home ------------------
@Composable
fun HomeMenu(
    onOpenVision: () -> Unit,
    onOpenSensors: () -> Unit,
    onOpenSteps: () -> Unit,
) {
    Column(
        Modifier.fillMaxSize().padding(20.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Button(onClick = onOpenVision, modifier = Modifier.fillMaxWidth()) { Text("Camera (Vision)") }
        Spacer(Modifier.height(16.dp))
        Button(onClick = onOpenSensors, modifier = Modifier.fillMaxWidth()) { Text("Sensors") }
        Spacer(Modifier.height(16.dp))
        Button(onClick = onOpenSteps, modifier = Modifier.fillMaxWidth()) { Text("Step Counter") }
    }
}

// =====================================================
// ===============  CAMERA / VISION  ===================
// =====================================================
@Composable
fun ObstacleDetectorScreen() {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    var status by remember { mutableStateOf("Starting…") }
    var detections by remember { mutableStateOf(emptyList<DetectionBox>()) }
    var confThreshold by remember { mutableFloatStateOf(0.50f) }
    var sizeThreshold by remember { mutableFloatStateOf(0.14f) }
    var buzzEnabled by remember { mutableStateOf(true) }
    var speechEnabled by remember { mutableStateOf(true) }
    var multimode by remember { mutableStateOf(true) }

    fun vibrator(): Vibrator? =
        if (Build.VERSION.SDK_INT >= 31) {
            val vm = context.getSystemService(VibratorManager::class.java)
            vm?.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        }

    fun buzz(ms: Long = 35L) {
        val vib = vibrator() ?: return
        if (!vib.hasVibrator()) return
        if (Build.VERSION.SDK_INT >= 26) {
            vib.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            @Suppress("DEPRECATION") vib.vibrate(ms)
        }
    }

    fun buzzPattern(level: String) {
        val vib = vibrator() ?: return
        if (!vib.hasVibrator() || !buzzEnabled) return
        if (Build.VERSION.SDK_INT >= 26) {
            when (level) {
                "far" -> vib.vibrate(VibrationEffect.createWaveform(longArrayOf(0, 25, 120), intArrayOf(150, 180, 0), -1))
                "mid" -> vib.vibrate(VibrationEffect.createWaveform(longArrayOf(0, 35, 90, 35, 140), intArrayOf(180, 220, 0, 220, 0), -1))
                "near" -> vib.vibrate(VibrationEffect.createWaveform(longArrayOf(0, 120), intArrayOf(255, 255), -1))
            }
        } else {
            when (level) { "far" -> buzz(25); "mid" -> buzz(35); "near" -> buzz(120) }
        }
    }

    val lastHaptic = remember { AtomicLong(0L) }
    fun tryHaptic(level: String, minGapMs: Long) {
        if (!buzzEnabled) return
        val now = SystemClock.elapsedRealtime()
        if (now - lastHaptic.get() > minGapMs) {
            lastHaptic.set(now)
            buzzPattern(level)
        }
    }

    var ttsRef by remember { mutableStateOf<TextToSpeech?>(null) }
    DisposableEffect(context) {
        var localTts: TextToSpeech? = null
        localTts = TextToSpeech(context) { st ->
            if (st == TextToSpeech.SUCCESS) {
                try { localTts?.language = Locale.UK } catch (_: Throwable) {}
                localTts?.setSpeechRate(1.05f)
            }
        }
        ttsRef = localTts
        onDispose { localTts?.shutdown(); ttsRef = null }
    }

    val lastSpeak = remember { AtomicLong(0L) }
    fun speakOnce(text: String, minGapMs: Long = 2200L) {
        if (!speechEnabled) return
        val now = SystemClock.elapsedRealtime()
        if (now - lastSpeak.get() < minGapMs) return
        ttsRef?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "nav-hint")
        lastSpeak.set(now)
    }

    val detector = remember {
        ObjectDetection.getClient(
            ObjectDetectorOptions.Builder()
                .setDetectorMode(ObjectDetectorOptions.STREAM_MODE)
                .enableMultipleObjects()
                .enableClassification()
                .build()
        )
    }
    DisposableEffect(Unit) { onDispose { detector.close() } }

    val previewView = remember {
        PreviewView(context).apply {
            layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            implementationMode = PreviewView.ImplementationMode.COMPATIBLE
            scaleType = PreviewView.ScaleType.FILL_CENTER
        }
    }

    val analysisExecutor = remember { Executors.newSingleThreadExecutor() }
    DisposableEffect(Unit) { onDispose { analysisExecutor.shutdown() } }

    LaunchedEffect(Unit) {
        val provider = ProcessCameraProvider.getInstance(context).get()
        val preview = Preview.Builder().build().also { it.setSurfaceProvider(previewView.surfaceProvider) }
        val analysis = ImageAnalysis.Builder()
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)
            .setTargetResolution(Size(1280, 720))
            .build()

        val analyzer = object : ImageAnalysis.Analyzer {
            @androidx.camera.core.ExperimentalGetImage
            override fun analyze(imageProxy: ImageProxy) {
                val mediaImage = imageProxy.image ?: run { imageProxy.close(); return }
                val rotation = imageProxy.imageInfo.rotationDegrees
                val input = InputImage.fromMediaImage(mediaImage, rotation)

                detector.process(input)
                    .addOnSuccessListener { objects ->
                        status = "Running"
                        val filtered = objects
                            .filter { obj ->
                                val best = obj.labels.maxByOrNull { it.confidence }
                                (best?.confidence ?: 0f) >= confThreshold
                            }
                            .map { obj -> toBox(obj, input.width, input.height) }

                        detections = filtered

                        val imgArea = (input.width * input.height).toFloat()
                        val candidate = filtered
                            .filter { b -> isInCenter(b.rect, input.width, input.height) }
                            .maxByOrNull { b -> (b.rect.width() * b.rect.height()).toFloat() }

                        if (candidate != null) {
                            val r = candidate.rect
                            val areaFrac = (r.width() * r.height()).toFloat() / imgArea
                            val level = bucketByAreaFrac(areaFrac, sizeThreshold)
                            if (level != "none") {
                                if (multimode || !speechEnabled) {
                                    when (level) {
                                        "far" -> tryHaptic("far", 950)
                                        "mid" -> tryHaptic("mid", 800)
                                        "near" -> tryHaptic("near", 600)
                                    }
                                }
                                if (multimode || !buzzEnabled) {
                                    val dir = directionOf(r, input.width)
                                    when (level) {
                                        "near" -> speakOnce("Stop", 1800)
                                        "mid" -> speakOnce(
                                            when (dir) { "left" -> "Left obstacle"; "right" -> "Right obstacle"; else -> "Ahead obstacle" },
                                            2200
                                        )
                                        "far" -> speakOnce(
                                            when (dir) { "left" -> "Left"; "right" -> "Right"; else -> "Ahead" },
                                            2600
                                        )
                                    }
                                }
                            }
                        }
                    }
                    .addOnFailureListener { e -> status = "Detector error: ${e.message}" }
                    .addOnCompleteListener { imageProxy.close() }
            }
        }
        analysis.setAnalyzer(analysisExecutor, analyzer)

        try {
            provider.unbindAll()
            provider.bindToLifecycle(
                lifecycleOwner,
                CameraSelector.DEFAULT_BACK_CAMERA,
                preview, analysis
            )
        } catch (e: Exception) {
            status = "Camera error: ${e.message}"
        }
    }

    Box(Modifier.fillMaxSize()) {
        AndroidView(factory = { previewView }, modifier = Modifier.fillMaxSize())
        DetectionOverlay(previewView = previewView, boxes = detections)

        Column(Modifier.align(Alignment.TopStart).padding(12.dp)) {
            Text(status, style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Buzz"); Spacer(Modifier.width(8.dp))
                Switch(checked = buzzEnabled, onCheckedChange = { buzzEnabled = it })
            }
            Spacer(Modifier.height(6.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Speech"); Spacer(Modifier.width(8.dp))
                Switch(checked = speechEnabled, onCheckedChange = { speechEnabled = it })
            }
            Spacer(Modifier.height(6.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Multimode"); Spacer(Modifier.width(8.dp))
                Switch(checked = multimode, onCheckedChange = { multimode = it })
            }
            Spacer(Modifier.height(10.dp))
            Text("Label confidence ≥ ${"%.0f".format(confThreshold * 100)}%")
            Slider(value = confThreshold, onValueChange = { confThreshold = it }, valueRange = 0f..1f, modifier = Modifier.width(260.dp))
            Spacer(Modifier.height(8.dp))
            Text("Trigger when center object fills ≥ ${"%.0f".format(sizeThreshold * 100)}% of the frame")
            Slider(value = sizeThreshold, onValueChange = { sizeThreshold = it }, valueRange = 0.05f..0.35f, modifier = Modifier.width(260.dp))
            Spacer(Modifier.height(6.dp))
            Text("Tip: raise % to buzz only when very close; lower it to warn sooner.")
        }
    }
}

// ---------- Vision helpers ----------
private fun toBox(obj: DetectedObject, imgW: Int, imgH: Int): DetectionBox {
    val best = obj.labels.maxByOrNull { it.confidence }
    val name = best?.text
    val score = best?.confidence ?: 0f
    return DetectionBox(obj.boundingBox, name, score, imgW, imgH)
}

private fun isInCenter(r: Rect, imgW: Int, imgH: Int): Boolean {
    val cx1 = imgW * 0.3f
    val cy1 = imgH * 0.3f
    val cx2 = imgW * 0.7f
    val cy2 = imgH * 0.7f
    val xOverlap = max(0f, min(r.right.toFloat(), cx2) - max(r.left.toFloat(), cx1))
    val yOverlap = max(0f, min(r.bottom.toFloat(), cy2) - max(r.top.toFloat(), cy1))
    return xOverlap > 0f && yOverlap > 0f
}

private fun bucketByAreaFrac(areaFrac: Float, sizeThreshold: Float): String =
    when {
        areaFrac >= sizeThreshold -> "near"
        areaFrac >= sizeThreshold * 0.55f -> "mid"
        areaFrac >= sizeThreshold * 0.32f -> "far"
        else -> "none"
    }

private fun directionOf(r: Rect, imgW: Int): String {
    val cx = (r.left + r.right) * 0.5f
    val leftBand = imgW * 0.45f
    val rightBand = imgW * 0.55f
    return when {
        cx < leftBand -> "left"
        cx > rightBand -> "right"
        else -> "ahead"
    }
}

@Composable
fun DetectionOverlay(previewView: PreviewView, boxes: List<DetectionBox>) {
    val vw = previewView.width.toFloat().coerceAtLeast(1f)
    val vh = previewView.height.toFloat().coerceAtLeast(1f)

    fun mapper(imgW: Int, imgH: Int): (Rect) -> Rect {
        val sx = vw / imgW
        the@ val sy = vh / imgH
        val s = max(sx, sy)
        val dx = (imgW * s - vw) / 2f
        val dy = (imgH * s - vh) / 2f
        return { r ->
            Rect(
                ((r.left * s) - dx).toInt(),
                ((r.top * s) - dy).toInt(),
                ((r.right * s) - dx).toInt(),
                ((r.bottom * s) - dy).toInt()
            )
        }
    }

    val stroke = Stroke(
        width = 4f,
        miter = 10f,
        cap = StrokeCap.Round,
        join = StrokeJoin.Round,
        pathEffect = PathEffect.dashPathEffect(floatArrayOf(16f, 12f), 0f)
    )

    Canvas(Modifier.fillMaxSize()) {
        boxes.groupBy { it.imgW to it.imgH }.forEach { (size, group) ->
            val (iw, ih) = size
            val map = mapper(iw, ih)
            group.forEach { b ->
                val r = map(b.rect)
                drawRect(
                    color = Color.Green,
                    topLeft = Offset(r.left.toFloat(), r.top.toFloat()),
                    size = androidx.compose.ui.geometry.Size(
                        (r.right - r.left).toFloat(),
                        (r.bottom - r.top).toFloat()
                    ),
                    style = stroke
                )
                val cx = (r.left + r.right) / 2f
                val cy = (r.top + r.bottom) / 2f
                drawCircle(color = Color.Green, radius = 4f, center = Offset(cx, cy))
            }
        }
    }
}

// =====================================================
// ==================  SENSORS  ========================
// =====================================================
enum class SensorChoice { ACCELEROMETER, GYROSCOPE, MAGNETOMETER, ROTATION_VECTOR }

@Composable
fun SensorReaderScreen() {
    val context = LocalContext.current
    val sensorManager = remember { context.getSystemService(Context.SENSOR_SERVICE) as SensorManager }

    var speechEnabled by remember { mutableStateOf(true) }
    var buzzEnabled by remember { mutableStateOf(true) }

    fun vibrator(): Vibrator? =
        if (Build.VERSION.SDK_INT >= 31) {
            val vm = context.getSystemService(VibratorManager::class.java)
            vm?.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        }
    fun buzz(ms: Long = 30L) {
        if (!buzzEnabled) return
        val vib = vibrator() ?: return
        if (!vib.hasVibrator()) return
        if (Build.VERSION.SDK_INT >= 26) vib.vibrate(VibrationEffect.createOneShot(ms, VibrationEffect.DEFAULT_AMPLITUDE))
        else @Suppress("DEPRECATION") vib.vibrate(ms)
    }

    var ttsRef by remember { mutableStateOf<TextToSpeech?>(null) }
    val lastSpeak = remember { AtomicLong(0L) }
    DisposableEffect(context) {
        var engine: TextToSpeech? = null
        engine = TextToSpeech(context) { st ->
            if (st == TextToSpeech.SUCCESS) {
                try { engine?.language = Locale.UK } catch (_: Throwable) {}
                engine?.setSpeechRate(1.05f)
            }
        }
        ttsRef = engine
        onDispose { engine?.shutdown(); ttsRef = null }
    }
    fun speakOnce(text: String, minGapMs: Long = 1500L) {
        if (!speechEnabled) return
        val now = SystemClock.elapsedRealtime()
        if (now - lastSpeak.get() < minGapMs) return
        ttsRef?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "sensors-talk")
        lastSpeak.set(now)
    }

    var headingDeg by remember { mutableStateOf(0f) }
    var headingCardinal by remember { mutableStateOf("north") }
    var pitchDeg by remember { mutableStateOf(0f) }
    var tiltStatus by remember { mutableStateOf("OK") }
    var steps by remember { mutableStateOf(0) }
    var lastMilestone by remember { mutableStateOf(0) }
    var lastSpokenCardinal by remember { mutableStateOf<String?>(null) }

    DisposableEffect(Unit) {
        val rotSensor = sensorManager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR)
        val stepCounter = sensorManager.getDefaultSensor(Sensor.TYPE_STEP_COUNTER)
        val stepDetector = sensorManager.getDefaultSensor(Sensor.TYPE_STEP_DETECTOR)

        var baseline: Float? = null

        val listener = object : SensorEventListener {
            override fun onSensorChanged(event: SensorEvent) {
                when (event.sensor.type) {
                    Sensor.TYPE_ROTATION_VECTOR -> {
                        val rMat = FloatArray(9)
                        val ori = FloatArray(3)
                        SensorManager.getRotationMatrixFromVector(rMat, event.values)
                        SensorManager.getOrientation(rMat, ori)

                        val yaw = (ori[0] * 180f / PI.toFloat())
                        headingDeg = ((yaw + 360f) % 360f)

                        pitchDeg = (ori[1] * 180f / PI.toFloat())

                        tiltStatus = when {
                            pitchDeg < -25f -> "Camera tilted DOWN"
                            pitchDeg > 35f -> "Camera tilted UP"
                            else -> "OK"
                        }
                        if (tiltStatus != "OK") { buzz(20); speakOnce(tiltStatus, 2500) }

                        val c = toCardinal(headingDeg)
                        headingCardinal = c
                        if (c != lastSpokenCardinal) {
                            lastSpokenCardinal = c
                            speakOnce("Facing $c", 1800)
                        }
                    }
                    Sensor.TYPE_STEP_COUNTER -> {
                        val v = event.values[0]
                        if (baseline == null) baseline = v
                        val base = baseline ?: v
                        val diff = (v - base).roundToInt()
                        steps = if (diff >= 0) diff else 0

                        val nextMilestone = (steps / 10) * 10
                        if (nextMilestone >= 10 && nextMilestone != lastMilestone) {
                            lastMilestone = nextMilestone
                            buzz(35); speakOnce("Walked $nextMilestone steps", 2000)
                        }
                    }
                    Sensor.TYPE_STEP_DETECTOR -> {
                        steps += event.values.size
                        val nextMilestone = (steps / 10) * 10
                        if (nextMilestone >= 10 && nextMilestone != lastMilestone) {
                            lastMilestone = nextMilestone
                            buzz(35); speakOnce("Walked $nextMilestone steps", 2000)
                        }
                    }
                }
            }
            override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
        }

        if (rotSensor != null) {
            sensorManager.registerListener(listener, rotSensor, SensorManager.SENSOR_DELAY_GAME)
        }
        var registered = false
        if (stepCounter != null) {
            registered = sensorManager.registerListener(listener, stepCounter, SensorManager.SENSOR_DELAY_NORMAL)
        }
        if (!registered && stepDetector != null) {
            sensorManager.registerListener(listener, stepDetector, SensorManager.SENSOR_DELAY_GAME)
        }

        onDispose { sensorManager.unregisterListener(listener) }
    }

    var xVal by remember { mutableStateOf(0f) }
    var yVal by remember { mutableStateOf(0f) }
    var zVal by remember { mutableStateOf(0f) }
    var status by remember { mutableStateOf("Ready") }
    var unit by remember { mutableStateOf("") }
    var currentChoice by remember { mutableStateOf(SensorChoice.ACCELEROMETER) }

    DisposableEffect(currentChoice) {
        xVal = 0f; yVal = 0f; zVal = 0f

        val (sensor, unitText, onMsg) = when (currentChoice) {
            SensorChoice.ACCELEROMETER -> Triple(sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER), "m/s²", "Accelerometer")
            SensorChoice.GYROSCOPE     -> Triple(sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE), "rad/s", "Gyroscope")
            SensorChoice.MAGNETOMETER  -> Triple(sensorManager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD), "µT", "Magnetometer")
            SensorChoice.ROTATION_VECTOR -> Triple(sensorManager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR), "deg (yaw/pitch/roll)", "Fused orientation")
        }
        unit = unitText
        status = if (sensor == null) "$onMsg not available" else "$onMsg active"

        val listener = object : SensorEventListener {
            override fun onSensorChanged(event: SensorEvent) {
                when (event.sensor.type) {
                    Sensor.TYPE_ACCELEROMETER,
                    Sensor.TYPE_GYROSCOPE,
                    Sensor.TYPE_MAGNETIC_FIELD -> {
                        xVal = event.values[0]; yVal = event.values[1]; zVal = event.values[2]
                    }
                    Sensor.TYPE_ROTATION_VECTOR -> {
                        val rotMat = FloatArray(9)
                        val ori = FloatArray(3)
                        SensorManager.getRotationMatrixFromVector(rotMat, event.values)
                        SensorManager.getOrientation(rotMat, ori)
                        xVal = (ori[0] * 180f / PI.toFloat())
                        yVal = (ori[1] * 180f / PI.toFloat())
                        zVal = (ori[2] * 180f / PI.toFloat())
                    }
                }
            }
            override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
        }

        if (sensor != null) {
            sensorManager.registerListener(listener, sensor, SensorManager.SENSOR_DELAY_GAME)
        }
        onDispose { sensorManager.unregisterListener(listener) }
    }

    val scroll = rememberScrollState()
    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp).verticalScroll(scroll),
        horizontalAlignment = Alignment.Start
    ) {
        Text("Sensor Assistant", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(8.dp))

        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Speech"); Spacer(Modifier.width(8.dp))
            Switch(checked = speechEnabled, onCheckedChange = { speechEnabled = it })
            Spacer(Modifier.width(16.dp))
            Text("Buzz"); Spacer(Modifier.width(8.dp))
            Switch(checked = buzzEnabled, onCheckedChange = { buzzEnabled = it })
        }

        Spacer(Modifier.height(16.dp))

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp)) {
                Text("Direction & Tilt", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(6.dp))
                Text("Facing: $headingCardinal (${headingDeg.roundToInt()}°)")
                Text("Tilt: $tiltStatus (pitch ${"%.0f".format(pitchDeg)}°)")
            }
        }

        Spacer(Modifier.height(12.dp))

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp)) {
                Text("Walking Progress", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(6.dp))
                Text("Steps: $steps")
                Text("Milestones every 10 steps will be announced.")
            }
        }

        Spacer(Modifier.height(20.dp))

        Text("Raw Sensor Reader", style = MaterialTheme.typography.titleMedium)
        Text(status, style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(12.dp))

        FlowRowMainAxisWrap {
            ChoiceButton("Accelerometer", currentChoice == SensorChoice.ACCELEROMETER) { currentChoice = SensorChoice.ACCELEROMETER }
            ChoiceButton("Gyroscope", currentChoice == SensorChoice.GYROSCOPE) { currentChoice = SensorChoice.GYROSCOPE }
            ChoiceButton("Magnetometer", currentChoice == SensorChoice.MAGNETOMETER) { currentChoice = SensorChoice.MAGNETOMETER }
            ChoiceButton("Fused (Rotation Vector)", currentChoice == SensorChoice.ROTATION_VECTOR) { currentChoice = SensorChoice.ROTATION_VECTOR }
        }

        Spacer(Modifier.height(16.dp))
        Text(
            text = when (currentChoice) {
                SensorChoice.ACCELEROMETER -> "Accelerometer (X/Y/Z in $unit)"
                SensorChoice.GYROSCOPE     -> "Gyroscope (X/Y/Z in $unit)"
                SensorChoice.MAGNETOMETER  -> "Magnetometer (X/Y/Z in $unit)"
                SensorChoice.ROTATION_VECTOR -> "Orientation (Yaw/Pitch/Roll in $unit)"
            },
            style = MaterialTheme.typography.titleSmall
        )
        Spacer(Modifier.height(8.dp))
        Text("X: ${"%.3f".format(xVal)}")
        Text("Y: ${"%.3f".format(yVal)}")
        Text("Z: ${"%.3f".format(zVal)}")

        Spacer(Modifier.height(16.dp))
        AxisGuide(currentChoice)

        Spacer(Modifier.height(12.dp))
        Text("Tip: The assistant warns if the camera is tilted, announces facing (N/E/S/W), and speaks every 10 steps.")
    }
}

private fun toCardinal(deg: Float): String {
    val d = ((deg % 360f) + 360f) % 360f
    val candidates = listOf(
        0f to "north", 90f to "east", 180f to "south", 270f to "west", 360f to "north"
    )
    val nearest = candidates.minByOrNull { (ref, _) -> kotlin.math.abs(d - ref) } ?: (0f to "north")
    return nearest.second
}

@Composable
fun AxisGuide(choice: SensorChoice) {
    Spacer(Modifier.height(8.dp))
    Text("Axis guide", style = MaterialTheme.typography.titleSmall)
    Spacer(Modifier.height(6.dp))

    val lines: List<String> = when (choice) {
        SensorChoice.ACCELEROMETER -> listOf(
            "X → left/right tilt. Positive when tilted left; negative when tilted right.",
            "Y → forward/back tilt. Positive when the top tilts forward; negative when it tilts back.",
            "Z → up/down (gravity). ~+9.8 m/s² at rest (screen up), ~-9.8 m/s² screen-down."
        )
        SensorChoice.GYROSCOPE -> listOf(
            "X → pitch rate (nose up/down). Positive when pitching up.",
            "Y → roll rate (side tilt). Positive when rolling left.",
            "Z → yaw rate (turn). Positive when turning left (CCW)."
        )
        SensorChoice.MAGNETOMETER -> listOf(
            "X/Y/Z → magnetic field (µT) along phone axes.",
            "Values change with orientation and nearby magnets/metal.",
            "Use fused orientation for a stable compass."
        )
        SensorChoice.ROTATION_VECTOR -> listOf(
            "Yaw (azimuth) ≈ heading; Pitch = up/down; Roll = side tilt.",
            "These come from fused sensors (accel + gyro + mag)."
        )
    }
    lines.forEach { Text("• $it", style = MaterialTheme.typography.bodySmall) }
}

@Composable
fun FlowRowMainAxisWrap(content: @Composable RowScope.() -> Unit) {
    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, content = content)
}

@Composable
fun RowScope.ChoiceButton(text: String, selected: Boolean, onClick: () -> Unit) {
    Button(
        onClick = onClick,
        modifier = Modifier.padding(end = 8.dp, bottom = 8.dp).weight(1f, fill = false),
        colors = ButtonDefaults.buttonColors(
            containerColor = if (selected) MaterialTheme.colorScheme.primary
            else MaterialTheme.colorScheme.secondaryContainer
        )
    ) { Text(text) }
}

// =====================================================
// ==================  STEPS SCREEN  ===================
// =====================================================
@Composable
fun StepCounterScreen() {
    val context = LocalContext.current
    val sensorManager = remember { context.getSystemService(Context.SENSOR_SERVICE) as SensorManager }

    val needsPerm = Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q
    var hasActivityPerm by remember {
        mutableStateOf(
            !needsPerm || ContextCompat.checkSelfPermission(
                context, Manifest.permission.ACTIVITY_RECOGNITION
            ) == PackageManager.PERMISSION_GRANTED
        )
    }

    val activityPermLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        hasActivityPerm = granted || !needsPerm
    }

    LaunchedEffect(Unit) {
        if (needsPerm && !hasActivityPerm) {
            activityPermLauncher.launch(Manifest.permission.ACTIVITY_RECOGNITION)
        }
    }

    val stepCounter = remember { sensorManager.getDefaultSensor(Sensor.TYPE_STEP_COUNTER) }
    val stepDetector = remember { sensorManager.getDefaultSensor(Sensor.TYPE_STEP_DETECTOR) }

    var isRunning by remember { mutableStateOf(false) }
    var baseline by remember { mutableStateOf<Float?>(null) }
    var steps by remember { mutableStateOf(0) }
    var usingDetector by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf("Ready") }

    DisposableEffect(isRunning, hasActivityPerm) {
        if (!isRunning || !hasActivityPerm) {
            status = if (!hasActivityPerm) "Permission required" else "Paused"
            onDispose { }
        } else {
            val listener = object : SensorEventListener {
                override fun onSensorChanged(event: SensorEvent) {
                    when (event.sensor.type) {
                        Sensor.TYPE_STEP_COUNTER -> {
                            usingDetector = false
                            val value = event.values[0]
                            if (baseline == null) baseline = value
                            val base = baseline ?: 0f
                            val diff = (value - base).toInt()
                            steps = if (diff >= 0) diff else 0
                            status = "Counting (counter)"
                        }
                        Sensor.TYPE_STEP_DETECTOR -> {
                            usingDetector = true
                            steps += event.values.size
                            status = "Counting (detector)"
                        }
                    }
                }
                override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
            }

            var registered = false
            if (stepCounter != null) {
                registered = sensorManager.registerListener(
                    listener, stepCounter, SensorManager.SENSOR_DELAY_NORMAL
                )
            }
            if (!registered && stepDetector != null) {
                sensorManager.registerListener(
                    listener, stepDetector, SensorManager.SENSOR_DELAY_GAME
                )
            }

            onDispose { sensorManager.unregisterListener(listener) }
        }
    }

    Column(
        Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text("Step Counter", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(8.dp))

        if (!hasActivityPerm) {
            Text(
                "Activity Recognition permission is not granted. Steps may not be available.",
                color = MaterialTheme.colorScheme.error
            )
            Spacer(Modifier.height(8.dp))
            Button(onClick = {
                activityPermLauncher.launch(Manifest.permission.ACTIVITY_RECOGNITION)
            }) { Text("Grant Activity Permission") }
            Spacer(Modifier.height(16.dp))
        }

        if (stepCounter == null && stepDetector == null) {
            Text("No step sensors available on this device.")
            Spacer(Modifier.height(16.dp))
        } else {
            Text("Status: $status")
            Spacer(Modifier.height(6.dp))
            Text("Source: " + when {
                stepCounter != null && !usingDetector -> "TYPE_STEP_COUNTER"
                stepDetector != null && usingDetector -> "TYPE_STEP_DETECTOR"
                else -> "Unknown"
            })
            Spacer(Modifier.height(12.dp))
            Text("Steps: $steps", style = MaterialTheme.typography.titleLarge)
            Spacer(Modifier.height(16.dp))

            Row(verticalAlignment = Alignment.CenterVertically) {
                Button(
                    onClick = {
                        if (needsPerm && !hasActivityPerm) {
                            activityPermLauncher.launch(Manifest.permission.ACTIVITY_RECOGNITION)
                        } else {
                            isRunning = !isRunning
                        }
                    }
                ) { Text(if (isRunning) "Pause" else "Start") }

                Spacer(Modifier.width(12.dp))

                OutlinedButton(
                    onClick = {
                        baseline = null
                        steps = 0
                    }
                ) { Text("Reset Baseline") }
            }

            Spacer(Modifier.height(10.dp))
            Text("Tip: baseline resets to the current counter reading when new data arrives.")
        }
    }
}
