import { Ionicons, MaterialIcons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React from 'react';
import { Pressable, StyleSheet, Text, View, Alert } from 'react-native';
import { getTTSService, RiskLevel } from '../src/services/TTSService';
 
const GOLD = '#f9b233';
 
export default function NavigateScreen() {
  const router = useRouter();
  const tts = getTTSService({ cooldownSeconds: 3.0 });

  const handleTTSTest = async (message: string, riskLevel: RiskLevel) => {
    try {
      const result = await tts.speak(message, riskLevel);
      if (result) {
        Alert.alert('TTS', `Spoke: "${message}"`);
      } else {
        Alert.alert('TTS', `Suppressed: "${message}" (anti-spam)`);
      }
    } catch (error) {
      Alert.alert('Error', `TTS failed: ${error}`);
    }
  };
 
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
 
      {/* Navigation info */}
      <View style={styles.content}>
        <Text style={styles.text}>From: Your current location</Text>
        <Text style={styles.text}>To: Finance Sections</Text>
        <Text style={[styles.text, { marginTop: 16 }]}>ETA: 2 minutes</Text>
        <Text style={styles.text}>Walk 3 ft, 2 o'clock</Text>
        <Text style={[styles.text, { marginTop: 24 }]}>2% completed</Text>
        
        {/* TTS Test Buttons */}
        <View style={styles.ttsTestContainer}>
          <Text style={[styles.text, { marginTop: 32, marginBottom: 12 }]}>TTS Test</Text>
          <Pressable 
            style={styles.ttsButton} 
            onPress={() => handleTTSTest('Path ahead is clear', RiskLevel.CLEAR)}
          >
            <Text style={styles.ttsButtonText}>Test: "Path ahead is clear"</Text>
          </Pressable>
          <Pressable 
            style={styles.ttsButton} 
            onPress={() => handleTTSTest('Chair on your left, nearby', RiskLevel.MEDIUM)}
          >
            <Text style={styles.ttsButtonText}>Test: "Chair on your left"</Text>
          </Pressable>
          <Pressable 
            style={styles.ttsButton} 
            onPress={() => handleTTSTest('Obstacle detected ahead', RiskLevel.HIGH)}
          >
            <Text style={styles.ttsButtonText}>Test: "Obstacle ahead"</Text>
          </Pressable>
        </View>
      </View>
 
      {/* Bottom bar */}
      <View style={styles.bottomBar}>
        <Pressable style={styles.bottomItem} onPress={() => router.push('/home')}>
          <Ionicons name="home-outline" size={26} color={GOLD} />
        </Pressable>
        <View style={styles.bottomDivider} />
        <Pressable style={styles.bottomItem} onPress={() => router.push('/camera')}>
          <Ionicons name="camera-outline" size={26} color={GOLD} />
        </Pressable>
        <View style={styles.bottomDivider} />
        <Pressable style={styles.bottomItem} onPress={() => router.push('/account')}>
          <View style={styles.accountBadge}>
            <MaterialIcons name="person" size={20} color="#1B263B" />
            <Text style={styles.accountText}>My{'\n'}Account</Text>
          </View>
        </Pressable>
      </View>
    </View>
  );
}
 
const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#1B263B', paddingHorizontal: 16, paddingTop: 18 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  headerTitle: { color: GOLD, fontSize: 22, fontWeight: '800' },
  headerRule: { height: 2, backgroundColor: GOLD, marginTop: 10, marginBottom: 16 },
 
  content: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  text: { color: GOLD, fontSize: 18, fontWeight: '600', marginVertical: 4 },
 
  bottomBar: {
    position: 'absolute', left: 0, right: 0, bottom: 0,
    height: 78, backgroundColor: '#1B263B', borderTopWidth: 2, borderTopColor: GOLD,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around',
  },
  bottomItem: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  bottomDivider: { width: 2, height: '70%', backgroundColor: GOLD },
  accountBadge: {
    width: 52, height: 52, borderRadius: 26,
    backgroundColor: GOLD, alignItems: 'center', justifyContent: 'center',
  },
  accountText: {
    position: 'absolute', bottom: -26, width: 60,
    textAlign: 'center', fontSize: 11, fontWeight: '800', color: GOLD,
  },
  ttsTestContainer: {
    marginTop: 20,
    alignItems: 'center',
    width: '100%',
  },
  ttsButton: {
    backgroundColor: GOLD,
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 8,
    marginVertical: 6,
    minWidth: 250,
    alignItems: 'center',
  },
  ttsButtonText: {
    color: '#1B263B',
    fontSize: 14,
    fontWeight: '700',
  },
});
