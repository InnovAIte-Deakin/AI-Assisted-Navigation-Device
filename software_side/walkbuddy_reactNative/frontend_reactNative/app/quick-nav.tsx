// app/quick-nav.tsx
import { Ionicons, MaterialIcons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React from 'react';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';

const GOLD = '#f9b233';

export default function QuickNavScreen() {
  const router = useRouter();

  const goHome = () => router.push('/home');        // opens your tab layout
  const goCamera = () => router.push('/camera');       // create later when ready
  const goAccount = () => router.push('/myaccount');     // or route you prefer

  return (
    <View style={styles.wrap}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={10}>
          <MaterialIcons name="arrow-back" size={26} color={GOLD} />
        </Pressable>
        <Text style={styles.headerTitle}>QUICK NAV</Text>
      </View>
      <View style={styles.headerRule} />

      {/* Intro */}
      <Text style={styles.intro}>
        Welcome to Quick Navigation.{'\n'}Select location from recent travel.
      </Text>

      {/* Buttons
      <Pressable style={styles.btn}><Text style={styles.btnText}>Finance</Text></Pressable>
      <Pressable style={styles.btn}><Text style={styles.btnText}>Science</Text></Pressable>
      <Pressable style={styles.btn}><Text style={styles.btnText}>Quiet Study Room</Text></Pressable> */}
       {/* Buttons with explicit routes */}
      <Pressable
        style={styles.btn}
        onPress={() => router.push("/FinanceScreen")}   // later change to "/finance"
      >
        <Text style={styles.btnText}>Finance</Text>
      </Pressable>

      <Pressable
        style={styles.btn}
        onPress={() => router.push("/science")}   // later change to "/science"
      >
        <Text style={styles.btnText}>Science</Text>
      </Pressable>

      <Pressable
        style={styles.btn}
        onPress={() => router.push("/quietstudyroom")}   // later change to "/quiet-study-room"
      >
        <Text style={styles.btnText}>Quiet Study Room</Text>
      </Pressable>

      {/* Spacer so content doesn't hide behind bottom bar */}
      <View style={{ height: 100 }} />

      {/* ---- Bottom Bar ---- */}
      <View style={styles.bottomBar}>
        <Pressable style={styles.bottomItem} onPress={goHome} hitSlop={10}>
          <Ionicons name="home-outline" size={26} color={GOLD} />
        </Pressable>

        <View style={styles.bottomDivider} />

        <Pressable style={styles.bottomItem} onPress={goCamera} hitSlop={10}>
          <Ionicons name="camera-outline" size={26} color={GOLD} />
        </Pressable>

        <View style={styles.bottomDivider} />

        <Pressable style={styles.bottomItem} onPress={goAccount} hitSlop={10}>
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
  intro: { color: GOLD, fontSize: 18, fontWeight: '600', lineHeight: 26, marginBottom: 20 },

  btn: { backgroundColor: '#2a2a2a', borderRadius: 12, paddingVertical: 14, alignItems: 'center', marginBottom: 12 },
  btnText: { color: GOLD, fontSize: 16, fontWeight: '700' },

  bottomBar: {
    position: 'absolute',
    left: 0, right: 0,
    bottom: 0,
    height: 78,
    paddingHorizontal: 24,
    backgroundColor: '#0b0b0b',
    borderTopWidth: 2,
    borderTopColor: GOLD,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    // on web, keep it fixed even when content scrolls
    ...(Platform.OS === 'web' ? { position: 'fixed' as any } : null),
  },
  bottomItem: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  bottomDivider: { width: 2, height: '70%', backgroundColor: GOLD, opacity: 0.9 },
  accountBadge: {
    width: 52, height: 52, borderRadius: 26,
    backgroundColor: GOLD,
    alignItems: 'center', justifyContent: 'center',
  },
  accountText: {
    position: 'absolute',
    bottom: -26,
    width: 60,
    textAlign: 'center',
    fontSize: 11,
    fontWeight: '800',
    color: GOLD,
  },
});
