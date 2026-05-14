// app/profile.tsx
import React, { useMemo, useState } from "react";
import {
  StyleSheet,
  Text,
  View,
  Pressable,
  TextInput,
  Image,
  useWindowDimensions,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Icon from "react-native-vector-icons/FontAwesome";
import { useRouter } from "expo-router";

import HomeHeader from "../HomeHeader";

import { useSession, ProfileRecord } from "../SessionContext";

const tokens = {
  bg: "#0D1B2A",
  card: "#0d1f32",
  text: "#e8eef6",
  muted: "#6b7f99",
  gold: "#FCA311",
  inputBg: "#162233",
};

function CardTitle({ children }: { children: string }) {
  return <Text style={styles.sectionTitle}>{children}</Text>;
}

function PrimaryButton({
  label,
  onPress,
}: {
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.primaryBtn, pressed && styles.pressed]}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      <Text style={styles.primaryBtnText}>{label}</Text>
    </Pressable>
  );
}

function SecondaryButton({
  label,
  onPress,
}: {
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.secondaryBtn, pressed && styles.pressed]}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      <Text style={styles.secondaryBtnText}>{label}</Text>
    </Pressable>
  );
}

function RowLink({
  icon,
  label,
  sublabel,
  onPress,
}: {
  icon: string;
  label: string;
  sublabel?: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      <View style={styles.rowLeft}>
        <View style={styles.rowIconWrap}>
          <Icon name={icon} size={18} color={tokens.gold} />
        </View>
        <View style={styles.rowTextWrap}>
          <Text style={styles.rowLabel}>{label}</Text>
          {!!sublabel && <Text style={styles.rowSublabel}>{sublabel}</Text>}
        </View>
      </View>
      <Icon name="chevron-right" size={14} color={tokens.muted} />
    </Pressable>
  );
}

export default function ProfilePage() {
  const router = useRouter();
  const { width } = useWindowDimensions();

  const { auth, setAuth } = useSession();

  const contentWidth = useMemo(() => {
    const padding = 24;
    const max = 720;
    return Math.min(max, Math.max(320, width - padding * 2));
  }, [width]);

  const [loginEmail, setLoginEmail] = useState("");
  const [loginPass, setLoginPass] = useState("");

  const [createDisplayName, setCreateDisplayName] = useState("");
  const [createPhotoString, setCreatePhotoString] = useState("");

  const goSettings = () => {
    router.push("/settings" as any);
  };

  const toLoggedOut = () => {
    setAuth({ status: "loggedOut" });
    setLoginEmail("");
    setLoginPass("");
    setCreateDisplayName("");
    setCreatePhotoString("");
  };

  const onLogin = () => {
    const email = loginEmail.trim();
    const pass = loginPass;
    if (!email || !pass) {
      Alert.alert("Missing details", "Enter email and password.");
      return;
    }
    setAuth({ status: "loggedInNoProfile", email });
  };

  const onCreateProfile = () => {
    if (auth.status !== "loggedInNoProfile") return;
    const email = auth.email.trim();
    const name = createDisplayName.trim();
    if (!name) {
      Alert.alert("Missing details", "Enter a display name.");
      return;
    }
    const profile: ProfileRecord = {
      email,
      displayName: name,
      photoString: createPhotoString.trim(),
    };
    setAuth({ status: "loggedInWithProfile", profile });
  };

  const renderLoggedOut = () => (
    <>
      {/* Hero */}
      <View style={styles.heroCard}>
        <View style={styles.heroAvatarWrap}>
          <View style={styles.heroAvatar}>
            <Icon name="user" size={32} color="#0D1B2A" />
          </View>
          <View style={styles.heroAvatarRing} />
        </View>
        <Text style={styles.heroTitle}>Welcome to WalkBuddy</Text>
        <Text style={styles.heroSubtitle}>
          Log in to access your profile and personalise your experience.
        </Text>
      </View>

      {/* Login form */}
      <CardTitle>LOG IN</CardTitle>
      <View style={styles.card}>
        <Text style={styles.inputLabel}>Email</Text>
        <View style={styles.inputWrap}>
          <Icon name="envelope" size={14} color={tokens.muted} style={styles.inputIcon} />
          <TextInput
            value={loginEmail}
            onChangeText={setLoginEmail}
            placeholder="name@example.com"
            placeholderTextColor={tokens.muted}
            autoCapitalize="none"
            keyboardType="email-address"
            style={styles.input}
          />
        </View>

        <Text style={[styles.inputLabel, { marginTop: 16 }]}>Password</Text>
        <View style={styles.inputWrap}>
          <Icon name="lock" size={16} color={tokens.muted} style={styles.inputIcon} />
          <TextInput
            value={loginPass}
            onChangeText={setLoginPass}
            placeholder="Password"
            placeholderTextColor={tokens.muted}
            secureTextEntry
            style={styles.input}
          />
        </View>

        <View style={styles.btnRow}>
          <PrimaryButton label="Log in" onPress={onLogin} />
        </View>

        <Text style={styles.note}>
          Don't have a profile yet? Logging in will prompt you to create one.
        </Text>
      </View>

      {/* Quick links */}
      <CardTitle>QUICK LINKS</CardTitle>
      <View style={styles.card}>
        <View style={styles.lockedRow}>
          <Icon name="lock" size={14} color={tokens.muted} />
          <Text style={styles.lockedText}>Settings unavailable while logged out.</Text>
        </View>
      </View>
    </>
  );

  const renderCreateProfile = (email: string) => (
    <>
      {/* Hero */}
      <View style={styles.heroCard}>
        <View style={styles.heroAvatarWrap}>
          <View style={styles.heroAvatar}>
            <Icon name="user-plus" size={28} color="#0D1B2A" />
          </View>
          <View style={styles.heroAvatarRing} />
        </View>
        <Text style={styles.heroTitle}>Create your profile</Text>
        <Text style={styles.heroSubtitle}>Signed in as {email}</Text>
      </View>

      <CardTitle>PROFILE DETAILS</CardTitle>
      <View style={styles.card}>
        <Text style={styles.inputLabel}>Display name</Text>
        <View style={styles.inputWrap}>
          <Icon name="user" size={14} color={tokens.muted} style={styles.inputIcon} />
          <TextInput
            value={createDisplayName}
            onChangeText={setCreateDisplayName}
            placeholder="Display name"
            placeholderTextColor={tokens.muted}
            style={styles.input}
          />
        </View>

        <Text style={[styles.inputLabel, { marginTop: 16 }]}>Photo (optional)</Text>
        <View style={styles.inputWrap}>
          <Icon name="image" size={14} color={tokens.muted} style={styles.inputIcon} />
          <TextInput
            value={createPhotoString}
            onChangeText={setCreatePhotoString}
            placeholder="URL or base64 image"
            placeholderTextColor={tokens.muted}
            autoCapitalize="none"
            style={styles.input}
          />
        </View>

        <View style={styles.previewWrap}>
          <Text style={styles.previewLabel}>PREVIEW</Text>
          <View style={styles.previewRow}>
            <View style={styles.previewAvatar}>
              {createPhotoString.trim() ? (
                <Image
                  source={{ uri: createPhotoString.trim() }}
                  style={styles.previewImage}
                  resizeMode="cover"
                  onError={() => {}}
                />
              ) : (
                <Icon name="user" size={18} color={tokens.muted} />
              )}
            </View>
            <Text style={styles.previewText} numberOfLines={2}>
              {createDisplayName.trim() || "Your display name will appear here"}
            </Text>
          </View>
        </View>

        <View style={styles.btnRow}>
          <PrimaryButton label="Create profile" onPress={onCreateProfile} />
          <SecondaryButton label="Log out" onPress={toLoggedOut} />
        </View>
      </View>

      <CardTitle>QUICK LINKS</CardTitle>
      <View style={styles.card}>
        <RowLink
          icon="cog"
          label="Settings"
          sublabel="App settings (in progress)"
          onPress={goSettings}
        />
      </View>
    </>
  );

  const renderProfile = (profile: ProfileRecord) => (
    <>
      {/* Profile hero */}
      <View style={styles.profileHeroCard}>
        <View style={styles.profileAvatarWrap}>
          {profile.photoString?.trim() ? (
            <Image
              source={{ uri: profile.photoString.trim() }}
              style={styles.profileImage}
              resizeMode="cover"
              onError={() => {}}
            />
          ) : (
            <Icon name="user" size={32} color="#0D1B2A" />
          )}
        </View>
        <Text style={styles.profileName} numberOfLines={1}>
          {profile.displayName}
        </Text>
        <Text style={styles.profileEmail} numberOfLines={1}>
          {profile.email}
        </Text>
        <View style={styles.profileBadge}>
          <Icon name="check-circle" size={12} color="#0D1B2A" />
          <Text style={styles.profileBadgeText}>Logged in</Text>
        </View>
      </View>

      <CardTitle>PROFILE</CardTitle>
      <View style={styles.card}>
        <RowLink
          icon="cog"
          label="Settings"
          sublabel="App settings (in progress)"
          onPress={goSettings}
        />
      </View>

      <CardTitle>SESSION</CardTitle>
      <View style={styles.card}>
        <Pressable
          onPress={toLoggedOut}
          style={({ pressed }) => [styles.logoutBtn, pressed && styles.pressed]}
          accessibilityRole="button"
          accessibilityLabel="Log out"
        >
          <Icon name="sign-out" size={18} color="#0D1B2A" />
          <Text style={styles.logoutBtnText}>Log out</Text>
        </Pressable>
      </View>
    </>
  );

  return (
    <SafeAreaView style={styles.screen} edges={["top"]}>
      <KeyboardAvoidingView
        style={styles.kb}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <View style={[styles.content, { width: contentWidth }]}>
          <HomeHeader appTitle="WalkBuddy" showDivider showLocation={true} />

          <ScrollView
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {auth.status === "loggedOut" && renderLoggedOut()}
            {auth.status === "loggedInNoProfile" && renderCreateProfile(auth.email)}
            {auth.status === "loggedInWithProfile" && renderProfile(auth.profile)}
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: tokens.bg,
    alignItems: "center",
  },

  kb: {
    flex: 1,
    width: "100%",
    alignItems: "center",
  },

  content: {
    flex: 1,
    paddingHorizontal: 12,
    paddingTop: 8,
  },

  scrollContent: {
    paddingBottom: 120,
    gap: 14,
  },

  // ─── Hero (logged out / create profile) ───
  heroCard: {
    backgroundColor: tokens.card,
    borderRadius: 24,
    borderWidth: 1.5,
    borderColor: "rgba(252,163,17,0.3)",
    padding: 28,
    alignItems: "center",
    gap: 12,
    shadowColor: tokens.gold,
    shadowOpacity: 0.12,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },

  heroAvatarWrap: {
    position: "relative",
    width: 80,
    height: 80,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 4,
  },

  heroAvatar: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: tokens.gold,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1,
  },

  heroAvatarRing: {
    position: "absolute",
    width: 80,
    height: 80,
    borderRadius: 40,
    borderWidth: 2,
    borderColor: "rgba(252,163,17,0.3)",
  },

  heroTitle: {
    color: tokens.text,
    fontSize: 20,
    fontWeight: "900",
    textAlign: "center",
    letterSpacing: 0.3,
  },

  heroSubtitle: {
    color: tokens.muted,
    fontSize: 13,
    textAlign: "center",
    lineHeight: 20,
    fontWeight: "500",
  },

  // ─── Profile hero (logged in) ───
  profileHeroCard: {
    backgroundColor: tokens.card,
    borderRadius: 24,
    borderWidth: 1.5,
    borderColor: "rgba(252,163,17,0.3)",
    padding: 28,
    alignItems: "center",
    gap: 8,
    shadowColor: tokens.gold,
    shadowOpacity: 0.12,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },

  profileAvatarWrap: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: tokens.gold,
    borderWidth: 3,
    borderColor: tokens.gold,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
    marginBottom: 4,
    shadowColor: tokens.gold,
    shadowOpacity: 0.4,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 0 },
    elevation: 8,
  },

  profileImage: {
    width: "100%",
    height: "100%",
  },

  profileName: {
    color: tokens.text,
    fontSize: 22,
    fontWeight: "900",
    textAlign: "center",
  },

  profileEmail: {
    color: tokens.muted,
    fontSize: 13,
    fontWeight: "600",
    textAlign: "center",
  },

  profileBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: tokens.gold,
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 999,
    marginTop: 4,
  },

  profileBadgeText: {
    color: "#0D1B2A",
    fontSize: 12,
    fontWeight: "800",
  },

  // ─── Section title ───
  sectionTitle: {
    color: tokens.muted,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 1.2,
    paddingHorizontal: 4,
  },

  // ─── Card ───
  card: {
    backgroundColor: tokens.card,
    borderRadius: 20,
    borderWidth: 1.5,
    borderColor: "rgba(252,163,17,0.2)",
    paddingVertical: 16,
    paddingHorizontal: 16,
    gap: 4,
  },

  // ─── Input ───
  inputLabel: {
    color: tokens.muted,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 0.8,
    textTransform: "uppercase",
    marginBottom: 8,
  },

  inputWrap: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: tokens.inputBg,
    borderWidth: 1.5,
    borderColor: "rgba(252,163,17,0.3)",
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 13,
    gap: 10,
  },

  inputIcon: {
    width: 18,
  },

  input: {
    flex: 1,
    color: tokens.text,
    fontSize: 15,
    fontWeight: "600",
  },

  // ─── Buttons ───
  btnRow: {
    marginTop: 20,
    flexDirection: "row",
    gap: 10,
    alignItems: "center",
  },

  primaryBtn: {
    flex: 1,
    backgroundColor: tokens.gold,
    borderRadius: 50,
    paddingVertical: 16,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: tokens.gold,
    shadowOpacity: 0.5,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 0 },
    elevation: 6,
  },

  primaryBtnText: {
    color: "#0D1B2A",
    fontSize: 15,
    fontWeight: "900",
    letterSpacing: 0.4,
  },

  secondaryBtn: {
    borderWidth: 1.5,
    borderColor: "rgba(252,163,17,0.4)",
    backgroundColor: "transparent",
    borderRadius: 50,
    paddingVertical: 16,
    paddingHorizontal: 20,
    alignItems: "center",
    justifyContent: "center",
  },

  secondaryBtnText: {
    color: tokens.muted,
    fontSize: 15,
    fontWeight: "800",
  },

  logoutBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    backgroundColor: tokens.gold,
    borderRadius: 50,
    paddingVertical: 16,
    shadowColor: tokens.gold,
    shadowOpacity: 0.4,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 0 },
    elevation: 6,
  },

  logoutBtnText: {
    color: "#0D1B2A",
    fontSize: 15,
    fontWeight: "900",
  },

  pressed: {
    opacity: 0.85,
  },

  note: {
    marginTop: 12,
    color: tokens.muted,
    fontSize: 12,
    lineHeight: 18,
  },

  lockedRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 4,
  },

  lockedText: {
    color: tokens.muted,
    fontSize: 13,
    fontWeight: "600",
  },

  // ─── Row links ───
  row: {
    paddingVertical: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },

  rowLeft: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
    paddingRight: 12,
  },

  rowIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 12,
    backgroundColor: "rgba(252,163,17,0.12)",
    borderWidth: 1,
    borderColor: "rgba(252,163,17,0.25)",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },

  rowTextWrap: {
    flex: 1,
  },

  rowLabel: {
    color: tokens.text,
    fontSize: 15,
    fontWeight: "800",
  },

  rowSublabel: {
    color: tokens.muted,
    fontSize: 12,
    marginTop: 2,
    lineHeight: 16,
  },

  // ─── Preview ───
  previewWrap: {
    marginTop: 20,
    borderTopWidth: 1,
    borderTopColor: "rgba(252,163,17,0.15)",
    paddingTop: 16,
  },

  previewLabel: {
    color: tokens.muted,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 1.2,
    marginBottom: 12,
  },

  previewRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },

  previewAvatar: {
    width: 44,
    height: 44,
    borderRadius: 22,
    borderWidth: 2,
    borderColor: "rgba(252,163,17,0.4)",
    backgroundColor: tokens.inputBg,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },

  previewImage: {
    width: "100%",
    height: "100%",
  },

  previewText: {
    flex: 1,
    color: tokens.text,
    fontSize: 14,
    fontWeight: "700",
  },
});