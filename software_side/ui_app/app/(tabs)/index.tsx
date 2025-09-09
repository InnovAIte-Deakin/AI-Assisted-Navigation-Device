// app/(tabs)/index.tsx
import React from 'react';
import { Image, SafeAreaView, StatusBar, StyleSheet, Text, View } from 'react-native';

export default function HomeScreen() {
  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="light-content" backgroundColor="#000" />
      <View style={styles.container}>
        <Image source={require('../../assets/images/company_logo.png')} style={styles.logo} />
        <Text style={styles.title}>WalkBuddy</Text>
        <Text style={styles.subtitle}>InnovAIte</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#000' },
  container: {
    flex: 1,
    backgroundColor: '#000',
    alignItems: 'center',
    justifyContent: 'center',
  },
  logo: { width: 160, height: 160, resizeMode: 'contain', marginBottom: 24 },
  title: { fontSize: 36, fontWeight: '800', color: '#FFA500' },
  subtitle: {
    position: 'absolute',
    bottom: 56,
    fontSize: 22,
    fontWeight: '800',
    color: '#FFA500',
  },
});
