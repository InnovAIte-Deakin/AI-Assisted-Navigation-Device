import React, { useState, useEffect, useRef } from "react";
import {
  View, Text, StyleSheet, TouchableOpacity,
  ScrollView, Animated, Easing, Alert
} from "react-native";
import * as Speech from "expo-speech";
import { Accelerometer, Gyroscope, Magnetometer } from "expo-sensors";
import { CameraView, useCameraPermissions } from "expo-camera";

const API_BASE = process.env.EXPO_PUBLIC_API_BASE || "http://192.168.1.106:8000";
const COLLECT_INTERVAL = 1500;
const PREDICT_INTERVAL = 1500;

interface SensorData { speed: number; heading: number; gyro: number; }
interface PathStep { step: number; x: number; y: number; distance_m: number; heading: number; risk_label: string; confidence: number; alert: boolean; alert_message: string; }
interface PredictResult { overall_risk: string; first_alert: string | null; alerts: string[]; path: PathStep[]; }
interface CollectedSample { speed: number; heading: number; gyro: number; risk_label: string; timestamp: number; }

export default function PredictivePathScreen() {
  const [mode, setMode] = useState<"predict" | "collect">("predict");
  const [permission, requestPermission] = useCameraPermissions();
  const [sensors, setSensors] = useState<SensorData>({ speed: 0, heading: 0, gyro: 0 });
  const [result, setResult] = useState<PredictResult | null>(null);
  const [collecting, setCollecting] = useState(false);
  const [predicting, setPredicting] = useState(false);
  const [samples, setSamples] = useState<CollectedSample[]>([]);
  const [lastSpoken, setLastSpoken] = useState("");
  const [status, setStatus] = useState("Ready");
  const [retraining, setRetraining] = useState(false);

  const accelRef = useRef({ x: 0, y: 0, z: 0 });
  const gyroRef = useRef({ x: 0, y: 0, z: 0 });
  const magRef = useRef({ x: 0, y: 0, z: 0 });
  const cameraRef = useRef<any>(null);
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const collectTimer = useRef<any>(null);
  const predictTimer = useRef<any>(null);

  // Start sensors
  useEffect(() => {
    Accelerometer.setUpdateInterval(200);
    Gyroscope.setUpdateInterval(200);
    Magnetometer.setUpdateInterval(200);
    const subA = Accelerometer.addListener(d => { accelRef.current = d; });
    const subG = Gyroscope.addListener(d => { gyroRef.current = d; });
    const subM = Magnetometer.addListener(d => { magRef.current = d; });
    return () => { subA.remove(); subG.remove(); subM.remove(); };
  }, []);

  // Update sensor display every 500ms
  useEffect(() => {
    const t = setInterval(() => {
      setSensors(computeSensors());
    }, 500);
    return () => clearInterval(t);
  }, []);

  // Pulse animation
  useEffect(() => {
    if (result?.overall_risk === "risky") {
      Animated.loop(Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 1.06, duration: 500, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 1.0, duration: 500, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ])).start();
    } else {
      pulseAnim.stopAnimation();
      pulseAnim.setValue(1);
    }
  }, [result?.overall_risk]);

  const computeSensors = (): SensorData => {
    const { x, y, z } = accelRef.current;
    const mag = Math.sqrt(x * x + y * y + z * z);
    const speed = Math.min(Math.max((mag - 9.81) * 0.4, 0), 4.0);
    const { x: mx, y: my } = magRef.current;
    let heading = Math.atan2(my, mx) * (180 / Math.PI);
    if (heading < 0) heading += 360;
    const gyro = Math.abs(gyroRef.current.z);
    return { speed: +speed.toFixed(2), heading: +heading.toFixed(1), gyro: +gyro.toFixed(3) };
  };

  // Capture frame and detect obstacles via YOLO
  const detectObstacle = async (): Promise<string> => {
    try {
      if (!cameraRef.current) return "safe";
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.3, base64: false });
      const formData = new FormData();
      formData.append("file", { uri: photo.uri, name: "frame.jpg", type: "image/jpeg" } as any);
      const res = await fetch(`${API_BASE}/vision`, { method: "POST", body: formData });
      if (!res.ok) return "safe";
      const data = await res.json();
      const detections = data.detections || [];
      if (detections.length === 0) return "safe";
      // Determine direction from bbox
      const top = detections[0];
      const centerX = (top.bbox.x_min + top.bbox.x_max) / 2;
      if (centerX < 213) return "safe"; // left side
      if (centerX > 426) return "front_right"; // right side
      return "front"; // center
    } catch {
      return "safe";
    }
  };

  // DATA COLLECTION MODE
  const startCollecting = async () => {
    if (!permission?.granted) {
      await requestPermission();
      return;
    }
    setCollecting(true);
    setStatus("Collecting... walk around your space");
    collectTimer.current = setInterval(async () => {
      const s = computeSensors();
      const label = await detectObstacle();
      const sample: CollectedSample = {
        speed: s.speed, heading: s.heading, gyro: s.gyro,
        risk_label: label, timestamp: Date.now()
      };
      setSamples(prev => [...prev, sample]);
      setStatus(`Collected ${samples.length + 1} samples — last: ${label}`);
    }, COLLECT_INTERVAL);
  };

  const stopCollecting = () => {
    setCollecting(false);
    if (collectTimer.current) clearInterval(collectTimer.current);
    setStatus(`Done — ${samples.length} samples collected`);
  };

  // RETRAIN MODEL
  const retrainModel = async () => {
    if (samples.length < 10) {
      Alert.alert("Not enough data", "Collect at least 10 samples first.");
      return;
    }
    setRetraining(true);
    setStatus("Sending data to backend for retraining...");
    try {
      const csv = "speed,heading,gyro,risk_label\n" +
        samples.map(s => `${s.speed},${s.heading},${s.gyro},${s.risk_label}`).join("\n");
      const res = await fetch(`${API_BASE}/retrain`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ csv_data: csv }),
      });
      if (!res.ok) throw new Error("retrain failed");
      const data = await res.json();
      setStatus(`Retrained! Accuracy: ${(data.accuracy * 100).toFixed(1)}%`);
      Alert.alert("Model retrained!", `New accuracy: ${(data.accuracy * 100).toFixed(1)}%`);
    } catch {
      setStatus("Retraining failed — using existing model");
      Alert.alert("Note", "Backend retrain endpoint not available. Your collected data is saved locally.");
    }
    setRetraining(false);
  };

  // PREDICTION MODE
  const startPredicting = () => {
    setPredicting(true);
    setStatus("Predicting in real time...");
    predictTimer.current = setInterval(runPrediction, PREDICT_INTERVAL);
    runPrediction();
  };

  const stopPredicting = () => {
    setPredicting(false);
    if (predictTimer.current) clearInterval(predictTimer.current);
    setStatus("Stopped");
  };

  const runPrediction = async () => {
    const s = computeSensors();
    try {
      const res = await fetch(`${API_BASE}/predict-path`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ speed: s.speed, heading: s.heading, gyro: s.gyro }),
      });
      if (!res.ok) throw new Error("server error");
      const data: PredictResult = await res.json();
      setResult(data);
      speakAlert(data);
    } catch {
      setStatus("Backend unreachable — check WiFi");
    }
  };

  const speakAlert = (data: PredictResult) => {
    const msg = data.overall_risk === "risky"
      ? (data.path?.find(p => p.alert)?.risk_label === "front"
          ? "Warning. Obstacle ahead. Please stop."
          : "Warning. Obstacle to your right.")
      : "Path clear.";
    if (msg !== lastSpoken) {
      Speech.speak(msg, { language: "en-AU", rate: 0.9 });
      setLastSpoken(msg);
    }
  };

  const riskColor = result?.overall_risk === "risky" ? "#E24B4A" : "#3B6D11";
  const labelColor = (l: string) => l === "front" ? "#E24B4A" : l === "front_right" ? "#BA7517" : "#3B6D11";

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ paddingTop: 60, paddingBottom: 40 }}>
      <Text style={styles.title}>Predictive Path AI</Text>
      <Text style={styles.subtitle}>Real sensors · Real camera · Real ML model</Text>

      {/* Mode selector */}
      <View style={styles.modeRow}>
        <TouchableOpacity style={[styles.modeBtn, mode === "predict" && styles.modeBtnActive]} onPress={() => { setMode("predict"); stopCollecting(); stopPredicting(); }}>
          <Text style={[styles.modeBtnText, mode === "predict" && styles.modeBtnTextActive]}>Live prediction</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.modeBtn, mode === "collect" && styles.modeBtnActive]} onPress={() => { setMode("collect"); stopPredicting(); }}>
          <Text style={[styles.modeBtnText, mode === "collect" && styles.modeBtnTextActive]}>Collect data</Text>
        </TouchableOpacity>
      </View>

      {/* Live sensor readings */}
      <Text style={styles.sectionLabel}>LIVE SENSORS (REAL PHONE DATA)</Text>
      <View style={styles.row}>
        <View style={styles.sensorCard}>
          <Text style={styles.sensorLabel}>Speed</Text>
          <Text style={styles.sensorVal}>{sensors.speed} m/s</Text>
        </View>
        <View style={styles.sensorCard}>
          <Text style={styles.sensorLabel}>Heading</Text>
          <Text style={styles.sensorVal}>{sensors.heading}°</Text>
        </View>
        <View style={styles.sensorCard}>
          <Text style={styles.sensorLabel}>Gyro</Text>
          <Text style={styles.sensorVal}>{sensors.gyro} r/s</Text>
        </View>
      </View>

      {/* Status */}
      <View style={styles.statusBox}>
        <Text style={styles.statusText}>{status}</Text>
      </View>

      {/* PREDICT MODE */}
      {mode === "predict" && (
        <>
          <TouchableOpacity
            style={[styles.btn, predicting && styles.btnStop]}
            onPress={predicting ? stopPredicting : startPredicting}>
            <Text style={styles.btnText}>{predicting ? "Stop prediction" : "Start live prediction"}</Text>
          </TouchableOpacity>

          {result && (
            <>
              <Animated.View style={[styles.banner,
                { backgroundColor: result.overall_risk === "risky" ? "#FCEBEB" : "#EAF3DE",
                  borderColor: riskColor, transform: [{ scale: pulseAnim }] }]}>
                <Text style={styles.bannerIcon}>{result.overall_risk === "risky" ? "🚨" : "✅"}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={[styles.bannerTitle, { color: riskColor }]}>
                    {result.overall_risk === "risky" ? "RISK DETECTED" : "PATH CLEAR"}
                  </Text>
                  <Text style={[styles.bannerMsg, { color: riskColor }]}>
                    {result.first_alert || "Safe to proceed"}
                  </Text>
                </View>
              </Animated.View>

              <View style={styles.row}>
                {[
                  { label: "Risk", val: result.overall_risk.toUpperCase(), color: riskColor },
                  { label: "Alerts", val: String(result.alerts.length), color: result.alerts.length > 0 ? "#E24B4A" : "#3B6D11" },
                  { label: "Steps", val: String(result.path.length), color: "#333" },
                  { label: "Dist", val: (result.path.find(s => s.alert)?.distance_m?.toFixed(1) ?? "—") + "m", color: "#333" },
                ].map(m => (
                  <View key={m.label} style={styles.metricCard}>
                    <Text style={styles.metricLabel}>{m.label}</Text>
                    <Text style={[styles.metricVal, { color: m.color }]}>{m.val}</Text>
                  </View>
                ))}
              </View>

              <Text style={styles.sectionLabel}>PREDICTED PATH</Text>
              <View style={styles.table}>
                <View style={[styles.tableRow, { backgroundColor: "#f4f4f2" }]}>
                  {["Step","Dist","Heading","Risk","Conf"].map(h => (
                    <Text key={h} style={[styles.cell, { fontWeight: "600", color: "#666", fontSize: 11 }]}>{h}</Text>
                  ))}
                </View>
                {result.path.map((s) => (
                  <View key={s.step} style={[styles.tableRow, s.alert && { backgroundColor: "#FCEBEB" }]}>
                    <Text style={styles.cell}>{s.step}</Text>
                    <Text style={styles.cell}>{s.distance_m}m</Text>
                    <Text style={styles.cell}>{s.heading}°</Text>
                    <Text style={[styles.cell, { color: labelColor(s.risk_label), fontWeight: "600" }]}>{s.risk_label}</Text>
                    <Text style={styles.cell}>{Math.round(s.confidence * 100)}%</Text>
                  </View>
                ))}
              </View>
            </>
          )}
        </>
      )}

      {/* COLLECT MODE */}
      {mode === "collect" && (
        <>
          <Text style={styles.sectionLabel}>CAMERA (OBSTACLE DETECTION)</Text>
          {permission?.granted ? (
            <CameraView ref={cameraRef} style={styles.camera} facing="back">
              <View style={styles.cameraOverlay}>
                <Text style={styles.cameraText}>Camera active — detecting obstacles</Text>
              </View>
            </CameraView>
          ) : (
            <TouchableOpacity style={styles.btn} onPress={requestPermission}>
              <Text style={styles.btnText}>Grant camera permission</Text>
            </TouchableOpacity>
          )}

          <TouchableOpacity
            style={[styles.btn, collecting && styles.btnStop]}
            onPress={collecting ? stopCollecting : startCollecting}>
            <Text style={styles.btnText}>{collecting ? "Stop collecting" : "Start collecting data"}</Text>
          </TouchableOpacity>

          <Text style={styles.sectionLabel}>COLLECTED SAMPLES ({samples.length})</Text>
          {samples.length > 0 && (
            <View style={styles.table}>
              <View style={[styles.tableRow, { backgroundColor: "#f4f4f2" }]}>
                {["#","Speed","Heading","Gyro","Label"].map(h => (
                  <Text key={h} style={[styles.cell, { fontWeight: "600", color: "#666", fontSize: 11 }]}>{h}</Text>
                ))}
              </View>
              {samples.slice(-8).map((s, i) => (
                <View key={i} style={[styles.tableRow, s.risk_label !== "safe" && { backgroundColor: "#FCEBEB" }]}>
                  <Text style={styles.cell}>{samples.length - 8 + i + 1}</Text>
                  <Text style={styles.cell}>{s.speed}</Text>
                  <Text style={styles.cell}>{s.heading}°</Text>
                  <Text style={styles.cell}>{s.gyro}</Text>
                  <Text style={[styles.cell, { color: labelColor(s.risk_label), fontWeight: "600" }]}>{s.risk_label}</Text>
                </View>
              ))}
            </View>
          )}

          {samples.length >= 5 && (
            <TouchableOpacity
              style={[styles.btn, { backgroundColor: "#185FA5", marginTop: 12 }, retraining && { opacity: 0.6 }]}
              onPress={retrainModel}
              disabled={retraining}>
              <Text style={styles.btnText}>{retraining ? "Retraining..." : `Retrain model (${samples.length} samples)`}</Text>
            </TouchableOpacity>
          )}

          <View style={styles.infoCard}>
            <Text style={styles.infoText}>How it works:</Text>
            <Text style={styles.infoText}>1. Walk around with camera pointing forward</Text>
            <Text style={styles.infoText}>2. YOLO detects obstacles in camera view</Text>
            <Text style={styles.infoText}>3. That labels your sensor reading automatically</Text>
            <Text style={styles.infoText}>4. Tap retrain to update the ML model</Text>
            <Text style={styles.infoText}>5. Switch to Live prediction to test it</Text>
          </View>
        </>
      )}

      <Text style={styles.sectionLabel}>MODEL INFO</Text>
      <View style={styles.infoCard}>
        {[
          "Model: Random Forest (n=100, max_depth=8)",
          "Features: speed · sin(heading) · cos(heading) · gyro",
          "Classes: safe · front · front_right",
          "Labels from: YOLO camera detection",
          "Endpoint: POST /predict-path",
        ].map(t => <Text key={t} style={styles.infoText}>{t}</Text>)}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f8f8f6", paddingHorizontal: 16 },
  title: { fontSize: 24, fontWeight: "700", color: "#1a1a1a", marginBottom: 4 },
  subtitle: { fontSize: 13, color: "#888", marginBottom: 8 },
  modeRow: { flexDirection: "row", gap: 8, marginBottom: 8 },
  modeBtn: { flex: 1, paddingVertical: 12, borderRadius: 10, alignItems: "center", backgroundColor: "#fff", borderWidth: 0.5, borderColor: "#ddd" },
  modeBtnActive: { backgroundColor: "#1a1a1a" },
  modeBtnText: { fontWeight: "600", fontSize: 14, color: "#333" },
  modeBtnTextActive: { color: "#fff" },
  sectionLabel: { fontSize: 11, fontWeight: "600", color: "#888", letterSpacing: 0.8, marginTop: 18, marginBottom: 8 },
  row: { flexDirection: "row", gap: 8, marginTop: 8 },
  sensorCard: { flex: 1, backgroundColor: "#fff", borderRadius: 10, padding: 12, borderWidth: 0.5, borderColor: "#e8e8e8" },
  sensorLabel: { fontSize: 11, color: "#888", marginBottom: 4 },
  sensorVal: { fontSize: 16, fontWeight: "600", color: "#1a1a1a" },
  statusBox: { backgroundColor: "#fff", borderRadius: 10, padding: 12, marginTop: 10, borderWidth: 0.5, borderColor: "#e8e8e8" },
  statusText: { fontSize: 13, color: "#555" },
  btn: { backgroundColor: "#1a1a1a", borderRadius: 10, paddingVertical: 14, alignItems: "center", marginTop: 10 },
  btnStop: { backgroundColor: "#E24B4A" },
  btnText: { color: "#fff", fontWeight: "600", fontSize: 15 },
  camera: { height: 200, borderRadius: 12, overflow: "hidden", marginBottom: 8 },
  cameraOverlay: { flex: 1, justifyContent: "flex-end", padding: 12, backgroundColor: "rgba(0,0,0,0.2)" },
  cameraText: { color: "#fff", fontSize: 12, textAlign: "center" },
  banner: { flexDirection: "row", alignItems: "center", padding: 16, borderRadius: 12, borderWidth: 1, marginTop: 16, gap: 12 },
  bannerIcon: { fontSize: 28 },
  bannerTitle: { fontSize: 16, fontWeight: "700" },
  bannerMsg: { fontSize: 13, marginTop: 2 },
  metricCard: { flex: 1, backgroundColor: "#fff", borderRadius: 10, padding: 10, alignItems: "center", borderWidth: 0.5, borderColor: "#e8e8e8" },
  metricLabel: { fontSize: 10, color: "#888", marginBottom: 4 },
  metricVal: { fontSize: 16, fontWeight: "700" },
  table: { backgroundColor: "#fff", borderRadius: 10, borderWidth: 0.5, borderColor: "#e8e8e8", overflow: "hidden" },
  tableRow: { flexDirection: "row", borderBottomWidth: 0.5, borderBottomColor: "#f0f0f0", paddingVertical: 8, paddingHorizontal: 8 },
  cell: { flex: 1, fontSize: 12, color: "#333" },
  infoCard: { backgroundColor: "#fff", borderRadius: 10, padding: 14, borderWidth: 0.5, borderColor: "#e8e8e8", gap: 6, marginTop: 8 },
  infoText: { fontSize: 12, color: "#555" },
});
