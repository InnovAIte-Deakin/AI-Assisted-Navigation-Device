// app/(tabs)/index.tsx
import React, { useEffect, useRef } from 'react';
import { Image, SafeAreaView, StatusBar, StyleSheet, Text, View, Animated, Easing } from 'react-native';
import { useRouter } from 'expo-router';

export default function HomeScreen() {
  const router = useRouter();

  // three pulsing dots -- animation of loading

  //initializing the dots
  const dot1 = useRef(new Animated.Value(0.3)).current;
  const dot2 = useRef(new Animated.Value(0.3)).current;
  const dot3 = useRef(new Animated.Value(0.3)).current;

  //animating the dots
  useEffect(() => {
    const makePulse = (val: Animated.Value, delay: number) =>
      Animated.loop(
        Animated.sequence([
          Animated.timing(val, { toValue: 1, duration: 400, delay, useNativeDriver: true, easing: Easing.inOut(Easing.quad) }),
          Animated.timing(val, { toValue: 0.3, duration: 400, useNativeDriver: true, easing: Easing.inOut(Easing.quad) }),
        ])
      ).start();
  
    makePulse(dot1, 0);
    makePulse(dot2, 150);
    makePulse(dot3, 300);
  
    // auto redirect after 3 seconds to the home page
    const t = setTimeout(() => {
      router.replace('/home'); // go directly to home and remove splash from back stack
    }, 3000);

    return () => clearTimeout(t);
  }, [router, dot1, dot2, dot3]);

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="light-content" backgroundColor="#000" />
      <View style={styles.container}>
        <Image source={require('../../assets/images/company_logo.png')} style={styles.logo} />
        <Text style={styles.title}>WalkBuddie</Text>

        {/* view which will show the animated loading sign */}
        {/* Loading … */}
        <View style={styles.loadingRow}>
          <Text style={styles.loadingText}>Loading</Text>
          <Animated.Text style={[styles.dot, { opacity: dot1 }]}>.</Animated.Text>
          <Animated.Text style={[styles.dot, { opacity: dot2 }]}>.</Animated.Text>
          <Animated.Text style={[styles.dot, { opacity: dot3 }]}>.</Animated.Text>
        </View>

        <Text style={styles.subtitle}>InnovAIte</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#000' },
  container: {
    flex: 1, backgroundColor: '#000', alignItems: 'center', justifyContent: 'center',
  },
  logo: { width: 160, height: 160, resizeMode: 'contain', marginBottom: 24 },
  title: { fontSize: 36, fontWeight: '800', color: '#FFA500' },
  subtitle: { position: 'absolute', bottom: 56, fontSize: 22, fontWeight: '800', color: '#FFA500' },
  loadingRow: { flexDirection: 'row', alignItems: 'center', marginTop: 12 },
  loadingText: { color: '#FFA500', fontWeight: '700', fontSize: 16 },
  dot: { color: '#FFA500', fontWeight: '900', fontSize: 18, marginLeft: 2 },
});
