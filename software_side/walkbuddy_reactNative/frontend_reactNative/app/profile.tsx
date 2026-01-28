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

import HomeHeader from "./HomeHeader";
import Footer from "./Footer";

import { useSession, ProfileRecord } from "./SessionContext";

const tokens = {
  bg: "#0D1B2A",
  tile: "#111",
  text: "#E0E1DD",
  muted: "#b8c6d4",
  gold: "#FCA311",
  divider: "rgba(252,163,17,0.35)",
  inputBg: "#0a121a",
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
      <View style={styles.heroCard}>
        <View style={styles.avatar}>
          <Icon name="user" size={22} color={tokens.bg} />
        </View>
        <View style={styles.heroText}>
          <Text style={styles.heroTitle}>Profile</Text>
          <Text style={styles.heroSubtitle}>
            Log in to view or create your profile. When logged out, nothing is kept on the device.
          </Text>
        </View>
      </View>

      <CardTitle>Log in</CardTitle>
      <View style={styles.card}>
        <Text style={styles.inputLabel}>Email</Text>
        <TextInput
          value={loginEmail}
          onChangeText={setLoginEmail}
          placeholder="name@example.com"
          placeholderTextColor="rgba(184,198,212,0.55)"
          autoCapitalize="none"
          keyboardType="email-address"
          style={styles.input}
        />

        <Text style={[styles.inputLabel, { marginTop: 12 }]}>Password</Text>
        <TextInput
          value={loginPass}
          onChangeText={setLoginPass}
          placeholder="Password"
          placeholderTextColor="rgba(184,198,212,0.55)"
          secureTextEntry
          style={styles.input}
        />

        <View style={styles.btnRow}>
          <PrimaryButton label="Log in" onPress={onLogin} />
        </View>

        <Text style={styles.note}>
          If you don’t have a profile yet, logging in will prompt you to create one.
        </Text>
      </View>

      <CardTitle>Quick links</CardTitle>
      <View style={styles.card}>
       <Text style={styles.note}>
          Settings unavailable while logged out.
        </Text>
      </View>
    </>
  );

  const renderCreateProfile = (email: string) => (
    <>
      <View style={styles.heroCard}>
        <View style={styles.avatar}>
          <Icon name="user" size={22} color={tokens.bg} />
        </View>
        <View style={styles.heroText}>
          <Text style={styles.heroTitle}>Create profile</Text>
          <Text style={styles.heroSubtitle}>
            Signed in as {email}. Enter a display name and (optional) photo string to create your profile.
          </Text>
        </View>
      </View>

      <CardTitle>Profile details</CardTitle>
      <View style={styles.card}>
        <Text style={styles.inputLabel}>Display name</Text>
        <TextInput
          value={createDisplayName}
          onChangeText={setCreateDisplayName}
          placeholder="Display name"
          placeholderTextColor="rgba(184,198,212,0.55)"
          style={styles.input}
        />

        <Text style={[styles.inputLabel, { marginTop: 12 }]}>Photo string (optional)</Text>
        <TextInput
          value={createPhotoString}
          onChangeText={setCreatePhotoString}
          placeholder="data:image/...base64 OR URL OR text"
          placeholderTextColor="rgba(184,198,212,0.55)"
          autoCapitalize="none"
          style={styles.input}
        />

        <View style={styles.previewWrap}>
          <Text style={styles.previewLabel}>Preview</Text>
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

        <Text style={styles.note}>
          This will be stored locally using encrypted storage once the secure persistence layer is wired in.
        </Text>
      </View>

      <CardTitle>Quick links</CardTitle>
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
      <View style={styles.profileTopCard}>
        <View style={styles.profileAvatar}>
          {profile.photoString?.trim() ? (
            <Image
              source={{ uri: profile.photoString.trim() }}
              style={styles.profileImage}
              resizeMode="cover"
              onError={() => {}}
            />
          ) : (
            <Icon name="user" size={28} color={tokens.muted} />
          )}
        </View>

        <View style={styles.profileMeta}>
          <Text style={styles.profileName} numberOfLines={1}>
            {profile.displayName}
          </Text>
          <Text style={styles.profileSub} numberOfLines={1}>
            {profile.email}
          </Text>
        </View>
      </View>

      <CardTitle>Profile</CardTitle>
      <View style={styles.card}>
        <RowLink
          icon="cog"
          label="Settings"
          sublabel="App settings (in progress)"
          onPress={goSettings}
        />
      </View>

      <CardTitle>Session</CardTitle>
      <View style={styles.card}>
        <Pressable
          onPress={toLoggedOut}
          style={({ pressed }) => [styles.row, pressed && styles.pressed]}
          accessibilityRole="button"
          accessibilityLabel="Log out"
        >
          <View style={styles.rowLeft}>
            <View style={styles.rowIconWrap}>
              <Icon name="sign-out" size={18} color={tokens.gold} />
            </View>
            <View style={styles.rowTextWrap}>
              <Text style={styles.rowLabel}>Log out</Text>
              <Text style={styles.rowSublabel}>
                Clears locally stored data on this device
              </Text>
            </View>
          </View>
          <Icon name="chevron-right" size={14} color={tokens.muted} />
        </Pressable>
      </View>
    </>
  );
  console.log("AUTH STATE", auth);

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
          >
            {auth.status === "loggedOut" && renderLoggedOut()}
            {auth.status === "loggedInNoProfile" &&
              renderCreateProfile(auth.email)}
            {auth.status === "loggedInWithProfile" &&
              renderProfile(auth.profile)}
          </ScrollView>

          <Footer />
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
    gap: 12,
  },

  heroCard: {
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 14,
    backgroundColor: tokens.tile,
    paddingVertical: 14,
    paddingHorizontal: 12,
    flexDirection: "row",
    alignItems: "center",
  },

  avatar: {
    width: 44,
    height: 44,
    borderRadius: 999,
    backgroundColor: tokens.gold,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },

  heroText: {
    flex: 1,
  },

  heroTitle: {
    color: tokens.text,
    fontSize: 16,
    fontWeight: "800",
    marginBottom: 4,
  },

  heroSubtitle: {
    color: tokens.muted,
    fontSize: 13,
    lineHeight: 18,
  },

  sectionTitle: {
    color: tokens.muted,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0.6,
    marginTop: 10,
  },

  card: {
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 14,
    backgroundColor: tokens.tile,
    paddingVertical: 14,
    paddingHorizontal: 12,
  },

  inputLabel: {
    color: tokens.muted,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0.4,
    marginBottom: 6,
  },

  input: {
    backgroundColor: tokens.inputBg,
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 12,
    color: tokens.text,
    fontSize: 14,
    fontWeight: "700",
  },

  btnRow: {
    marginTop: 14,
    flexDirection: "row",
    gap: 10,
    alignItems: "center",
  },

  primaryBtn: {
    flex: 1,
    borderWidth: 2,
    borderColor: tokens.gold,
    backgroundColor: tokens.gold,
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
    justifyContent: "center",
  },

  primaryBtnText: {
    color: "#111",
    fontSize: 14,
    fontWeight: "900",
    letterSpacing: 0.4,
  },

  secondaryBtn: {
    borderWidth: 2,
    borderColor: tokens.gold,
    backgroundColor: "transparent",
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 14,
    alignItems: "center",
    justifyContent: "center",
  },

  secondaryBtnText: {
    color: tokens.text,
    fontSize: 14,
    fontWeight: "900",
    letterSpacing: 0.4,
  },

  pressed: {
    opacity: 0.85,
  },

  note: {
    marginTop: 12,
    color: tokens.muted,
    fontSize: 12,
    lineHeight: 16,
    opacity: 0.9,
  },

  row: {
    paddingVertical: 10,
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
    width: 30,
    height: 30,
    borderRadius: 999,
    borderWidth: 2,
    borderColor: tokens.text,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 10,
  },

  rowTextWrap: {
    flex: 1,
  },

  rowLabel: {
    color: tokens.text,
    fontSize: 14,
    fontWeight: "800",
  },

  rowSublabel: {
    color: tokens.muted,
    fontSize: 12,
    marginTop: 2,
    lineHeight: 16,
  },

  previewWrap: {
    marginTop: 14,
    borderTopWidth: 1,
    borderTopColor: tokens.divider,
    paddingTop: 12,
  },

  previewLabel: {
    color: tokens.muted,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0.4,
    marginBottom: 8,
  },

  previewRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },

  previewAvatar: {
    width: 40,
    height: 40,
    borderRadius: 999,
    borderWidth: 2,
    borderColor: tokens.gold,
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
    fontSize: 13,
    fontWeight: "700",
  },

  profileTopCard: {
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 14,
    backgroundColor: tokens.tile,
    paddingVertical: 14,
    paddingHorizontal: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },

  profileAvatar: {
    width: 64,
    height: 64,
    borderRadius: 999,
    borderWidth: 2,
    borderColor: tokens.gold,
    backgroundColor: tokens.inputBg,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },

  profileImage: {
    width: "100%",
    height: "100%",
  },

  profileMeta: {
    flex: 1,
  },

  profileName: {
    color: tokens.text,
    fontSize: 18,
    fontWeight: "900",
    marginBottom: 4,
  },

  profileSub: {
    color: tokens.muted,
    fontSize: 13,
    fontWeight: "700",
  },
});
