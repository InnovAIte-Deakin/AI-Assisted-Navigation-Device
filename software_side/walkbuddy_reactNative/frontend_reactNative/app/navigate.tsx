import { Ionicons, MaterialIcons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { Magnetometer, Gyroscope, Accelerometer } from 'expo-sensors';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { predictPath, PredictivePathResponse } from '../src/api/client';
import { getTTSService, RiskLevel } from '../src/services/TTSService';

const GOLD = '#f9b233';
const DARK = '#1B263B';
const POLL_MS = 1500;

function riskColor(risk: 'safe' | 'risky' | null) {
  if (risk === 'risky') return '#e74c3c';
  if (risk === 'safe') return '#2ecc71';
  return GOLD;
}

function riskToTTSLevel(risk: 'safe' | 'risky'): RiskLevel {
  return risk === 'risky' ? RiskLevel.HIGH : RiskLevel.CLEAR;
}

export default function NavigateScreen() {
  const router = useRouter();
  const tts = getTTSService({ cooldownSeconds: 4.0 });

  const [active, setActive] = useState(false);
  const [result, setResult] = useState<PredictivePathResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Sensor state refs (avoid re-render on every sensor tick)
  const speed   = useRef(0);
  const heading = useRef(0);
  const gyroZ   = useRef(0);

  // Subscribe to sensors when active
  useEffect(() => {
    if (!active) return;

    Magnetometer.setUpdateInterval(500);
    Gyroscope.setUpdateInterval(500);
    Accelerometer.setUpdateInterval(500);

    const magSub = Magnetometer.addListener(({ x, y }) => {
      // Convert magnetometer to compass heading (0–360)
      let angle = Math.atan2(y, x) * (180 / Math.PI);
      if (angle < 0) angle += 360;
      heading.current = angle;
    });

    const gyroSub = Gyroscope.addListener(({ z }) => {
      gyroZ.current = z;
    });

    const accelSub = Accelerometer.addListener(({ x, y, z }) => {
      // Approximate horizontal speed magnitude from acceleration (m/s² → m/s crude)
      speed.current = Math.sqrt(x * x + y * y + z * z);
    });

    return () => {
      magSub.remove();
      gyroSub.remove();
      accelSub.remove();
    };
  }, [active]);

  // Polling loop
  useEffect(() => {
    if (!active) return;

    const poll = async () => {
      try {
        const res = await predictPath(speed.current, heading.current, gyroZ.current);
        setResult(res);
        setError(null);

        if (res.overall_risk === 'risky' && res.first_alert) {
          const a = res.first_alert;
          const msg = `Warning: ${a.risk_label} risk ${Math.round(a.distance)} metres ahead`;
          tts.speak(msg, riskToTTSLevel(res.overall_risk));
        } else if (res.overall_risk === 'safe') {
          tts.speak('Path ahead is clear', RiskLevel.CLEAR);
        }
      } catch (e: any) {
        setError('Could not reach backend');
      }
    };

    poll();
    const id = setInterval(poll, POLL_MS);
    return () => clearInterval(id);
  }, [active]);

  const toggle = useCallback(() => {
    setActive(a => !a);
    if (active) {
      setResult(null);
      setError(null);
    }
  }, [active]);

  const overallRisk = result?.overall_risk ?? null;

  return (
    <View style={styles.wrap}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={10}>
          <MaterialIcons name="arrow-back" size={26} color={GOLD} />
        </Pressable>
        <Text style={styles.headerTitle}>NAVIGATE</Text>
      </View>
      <View style={styles.headerRule} />

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>

        {/* Predictive Path section */}
        <Text style={styles.sectionTitle}>Predictive Path</Text>

        {/* Risk indicator */}
        <View style={[styles.riskBadge, { borderColor: riskColor(overallRisk) }]}>
          <Text style={[styles.riskText, { color: riskColor(overallRisk) }]}>
            {overallRisk === null
              ? active ? 'Scanning…' : 'Not started'
              : overallRisk === 'risky' ? '⚠ RISK DETECTED' : '✓ PATH CLEAR'}
          </Text>
        </View>

        {/* Start / Stop button */}
        <Pressable
          style={[styles.toggleBtn, { backgroundColor: active ? '#e74c3c' : GOLD }]}
          onPress={toggle}
        >
          <Ionicons
            name={active ? 'stop-circle-outline' : 'play-circle-outline'}
            size={22}
            color={DARK}
          />
          <Text style={styles.toggleBtnText}>
            {active ? 'Stop Monitoring' : 'Start Monitoring'}
          </Text>
        </Pressable>

        {/* Error */}
        {error && <Text style={styles.errorText}>{error}</Text>}

        {/* Alerts list */}
        {result && result.alerts.length > 0 && (
          <View style={styles.alertsBox}>
            <Text style={styles.alertsHeader}>Alerts</Text>
            {result.alerts.map((a, i) => (
              <View key={i} style={styles.alertRow}>
                <MaterialIcons name="warning" size={18} color="#e74c3c" />
                <Text style={styles.alertText}>
                  Step {a.step} · {a.risk_label} · {Math.round(a.distance)}m · {Math.round(a.confidence * 100)}%
                </Text>
              </View>
            ))}
          </View>
        )}

        {result && result.alerts.length === 0 && result.overall_risk === 'safe' && (
          <Text style={styles.clearText}>No hazards predicted in the next 2.5 seconds.</Text>
        )}

        {/* Live sensor readout */}
        {active && (
          <View style={styles.sensorBox}>
            <Text style={styles.sensorLabel}>Live Sensors</Text>
            <SensorReadout speedRef={speed} headingRef={heading} gyroRef={gyroZ} />
          </View>
        )}

      </ScrollView>

      {/* Bottom bar */}
      <View style={styles.bottomBar}>
        <Pressable style={styles.bottomItem} onPress={() => router.push('/')}>
          <Ionicons name="home-outline" size={26} color={GOLD} />
        </Pressable>
        <View style={styles.bottomDivider} />
        <Pressable style={styles.bottomItem} onPress={() => router.push('/camera')}>
          <Ionicons name="camera-outline" size={26} color={GOLD} />
        </Pressable>
        <View style={styles.bottomDivider} />
        <Pressable style={styles.bottomItem} onPress={() => router.push('/settings')}>
          <View style={styles.accountBadge}>
            <MaterialIcons name="person" size={20} color={DARK} />
          </View>
        </Pressable>
      </View>
    </View>
  );
}

// Separate component so it can re-render on an interval without the whole screen re-rendering
function SensorReadout({
  speedRef,
  headingRef,
  gyroRef,
}: {
  speedRef: React.MutableRefObject<number>;
  headingRef: React.MutableRefObject<number>;
  gyroRef: React.MutableRefObject<number>;
}) {
  const [vals, setVals] = useState({ s: 0, h: 0, g: 0 });

  useEffect(() => {
    const id = setInterval(() => {
      setVals({ s: speedRef.current, h: headingRef.current, g: gyroRef.current });
    }, 500);
    return () => clearInterval(id);
  }, []);

  return (
    <View>
      <Text style={styles.sensorValue}>Speed:   {vals.s.toFixed(2)} m/s</Text>
      <Text style={styles.sensorValue}>Heading: {vals.h.toFixed(1)}°</Text>
      <Text style={styles.sensorValue}>Gyro Z:  {vals.g.toFixed(3)} rad/s</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: DARK, paddingHorizontal: 16, paddingTop: 18 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  headerTitle: { color: GOLD, fontSize: 22, fontWeight: '800' },
  headerRule: { height: 2, backgroundColor: GOLD, marginTop: 10, marginBottom: 16 },

  content: { alignItems: 'center', paddingBottom: 100 },

  sectionTitle: { color: GOLD, fontSize: 20, fontWeight: '800', marginBottom: 20 },

  riskBadge: {
    borderWidth: 2,
    borderRadius: 12,
    paddingVertical: 16,
    paddingHorizontal: 32,
    marginBottom: 20,
    minWidth: 260,
    alignItems: 'center',
  },
  riskText: { fontSize: 20, fontWeight: '800' },

  toggleBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 14,
    paddingHorizontal: 28,
    borderRadius: 10,
    marginBottom: 24,
  },
  toggleBtnText: { color: DARK, fontSize: 16, fontWeight: '800' },

  errorText: { color: '#e74c3c', fontSize: 14, marginBottom: 12 },

  alertsBox: {
    width: '100%',
    backgroundColor: 'rgba(231,76,60,0.12)',
    borderRadius: 10,
    padding: 14,
    marginBottom: 16,
  },
  alertsHeader: { color: '#e74c3c', fontWeight: '800', fontSize: 15, marginBottom: 8 },
  alertRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginVertical: 3 },
  alertText: { color: '#fff', fontSize: 13 },

  clearText: { color: '#2ecc71', fontSize: 14, marginTop: 4, marginBottom: 16 },

  sensorBox: {
    width: '100%',
    backgroundColor: 'rgba(249,178,51,0.08)',
    borderRadius: 10,
    padding: 14,
    marginTop: 8,
  },
  sensorLabel: { color: GOLD, fontWeight: '700', fontSize: 13, marginBottom: 6 },
  sensorValue: { color: '#ccc', fontSize: 13, fontFamily: 'monospace', lineHeight: 22 },

  bottomBar: {
    position: 'absolute', left: 0, right: 0, bottom: 0,
    height: 78, backgroundColor: DARK, borderTopWidth: 2, borderTopColor: GOLD,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around',
  },
  bottomItem: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  bottomDivider: { width: 2, height: '70%', backgroundColor: GOLD },
  accountBadge: {
    width: 52, height: 52, borderRadius: 26,
    backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center',
  },
});
