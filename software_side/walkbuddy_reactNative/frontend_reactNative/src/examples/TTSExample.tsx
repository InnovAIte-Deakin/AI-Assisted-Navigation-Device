/**
 * Example: Using TTS Service in React Native
 * 
 * This example demonstrates how to integrate the TTS service
 * with camera/navigation functionality.
 * 
 * Author: ML Engineering Team
 * Purpose: Sprint 2 - TTS Integration Example
 */

import React, { useEffect, useState } from 'react';
import { View, Text, Button, StyleSheet, Alert } from 'react-native';
import { getTTSService, RiskLevel } from '../services/TTSService';

export default function TTSExample() {
  const [ttsStatus, setTTSStatus] = useState<any>(null);
  const tts = getTTSService({ cooldownSeconds: 3.0 });

  useEffect(() => {
    // Update status periodically
    const interval = setInterval(() => {
      setTTSStatus(tts.getStatus());
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const handleSpeak = async (message: string, riskLevel: RiskLevel) => {
    try {
      const result = await tts.speak(message, riskLevel);
      if (result) {
        Alert.alert('TTS', `Spoke: "${message}"`);
      } else {
        Alert.alert('TTS', `Suppressed: "${message}" (anti-spam)`);
      }
    } catch (error) {
      Alert.alert('Error', `Failed to speak: ${error}`);
    }
  };

  const handleVisionTTS = async () => {
    // Example: Process image and speak guidance
    try {
      // In real app, you would capture image from camera
      const formData = new FormData();
      // formData.append('file', { uri: imageUri, type: 'image/jpeg', name: 'photo.jpg' });

      const response = await fetch('http://your-backend-url/api/vision/tts', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (data.spoken_message) {
        // Message was spoken by backend, or speak locally
        await tts.speak(data.spoken_message, RiskLevel.MEDIUM);
        Alert.alert('Vision TTS', `Spoke: "${data.spoken_message}"`);
      }
    } catch (error) {
      Alert.alert('Error', `Vision TTS failed: ${error}`);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>TTS Service Example</Text>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Basic Usage</Text>
        <Button
          title="Speak: Path clear"
          onPress={() => handleSpeak('Path ahead is clear', RiskLevel.CLEAR)}
        />
        <Button
          title="Speak: Chair left"
          onPress={() => handleSpeak('Chair on your left, nearby', RiskLevel.MEDIUM)}
        />
        <Button
          title="Speak: Obstacle"
          onPress={() => handleSpeak('Obstacle detected ahead', RiskLevel.HIGH)}
        />
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Anti-Spam Test</Text>
        <Button
          title="Speak same message twice (2nd suppressed)"
          onPress={async () => {
            await tts.speak('Test message', RiskLevel.LOW);
            setTimeout(async () => {
              await tts.speak('Test message', RiskLevel.LOW);
            }, 500);
          }}
        />
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Status</Text>
        {ttsStatus && (
          <View>
            <Text>Cooldown Active: {ttsStatus.cooldownActive ? 'Yes' : 'No'}</Text>
            <Text>Last Message: {ttsStatus.lastMessage || 'None'}</Text>
            <Text>Time Since Last: {ttsStatus.timeSinceLastMessage.toFixed(1)}s</Text>
          </View>
        )}
      </View>

      <View style={styles.section}>
        <Button title="Reset TTS" onPress={() => tts.reset()} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    backgroundColor: '#fff',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 20,
  },
  section: {
    marginBottom: 20,
    padding: 10,
    backgroundColor: '#f5f5f5',
    borderRadius: 8,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 10,
  },
});



