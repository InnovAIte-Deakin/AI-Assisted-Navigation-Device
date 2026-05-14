// app/profile.tsx
import React, { useMemo, useState, useEffect } from "react";
import {
  StyleSheet,
  Text,
  View,
  Pressable,
  TextInput,
  useWindowDimensions,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Icon from "react-native-vector-icons/FontAwesome";
import { useRouter } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import * as Google from "expo-auth-session/providers/google";
import * as AuthSession from "expo-auth-session";
import Constants from "expo-constants";

import HomeHeader from "../HomeHeader";
import { useSession } from "../../src/context/SessionContext";
import { API_BASE } from "@/src/config";

WebBrowser.maybeCompleteAuthSession();

// ─── Fill in your OAuth Client IDs ──────────────────────────────────────────
// Google: https://console.cloud.google.com  → APIs & Services → Credentials
const GOOGLE_EXPO_CLIENT_ID = "358598369481-48h64mbe64oaqvnpfaoptrbqrspv7tga.apps.googleusercontent.com";
const GOOGLE_IOS_CLIENT_ID = "358598369481-48h64mbe64oaqvnpfaoptrbqrspv7tga.apps.googleusercontent.com";
const GOOGLE_ANDROID_CLIENT_ID = "358598369481-48h64mbe64oaqvnpfaoptrbqrspv7tga.apps.googleusercontent.com";
// Microsoft: https://portal.azure.com → App registrations
const MICROSOFT_CLIENT_ID = "4cdcb61f-dbf8-4272-9683-d9ddb14dee04";
// Redirect URI — must match what's registered in Azure (Mobile and desktop applications platform)
const EXPO_REDIRECT_URI = "walkbuddy://auth";
// ─────────────────────────────────────────────────────────────────────────────

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

const tokens = {
  bg: "#0D1B2A",
  card: "#0d1f32",
  text: "#e8eef6",
  muted: "#6b7f99",
  gold: "#FCA311",
  divider: "rgba(252,163,17,0.35)",
  inputBg: "#0a121a",
  error: "#FF6B6B",
};

function CardTitle({ children }: { children: string }) {
  return <Text style={styles.sectionTitle}>{children}</Text>;
}

function PrimaryButton({
  label,
  onPress,
  loading,
}: {
  label: string;
  onPress: () => void;
  loading?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={loading}
      style={({ pressed }) => [styles.primaryBtn, pressed && styles.pressed, loading && styles.disabledBtn]}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      {loading ? (
        <ActivityIndicator size="small" color="#111" />
      ) : (
        <Text style={styles.primaryBtnText}>{label}</Text>
      )}
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
  destructive,
}: {
  icon: string;
  label: string;
  sublabel?: string;
  onPress: () => void;
  destructive?: boolean;
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
          <Icon name={icon} size={18} color={destructive ? tokens.error : tokens.gold} />
        </View>
        <View style={styles.rowTextWrap}>
          <Text style={[styles.rowLabel, destructive && { color: tokens.error }]}>{label}</Text>
          {!!sublabel && <Text style={styles.rowSublabel}>{sublabel}</Text>}
        </View>
      </View>
      <Icon name="chevron-right" size={14} color={tokens.muted} />
    </Pressable>
  );
}

type Mode = "login" | "signup";

export default function ProfilePage() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const { auth, setAuth } = useSession();

  const contentWidth = useMemo(() => {
    const padding = 24;
    const max = 720;
    return Math.min(max, Math.max(320, width - padding * 2));
  }, [width]);

  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [fieldError, setFieldError] = useState("");

  // ── Google OAuth ────────────────────────────────────────────────────────────
  // webClientId must be a non-empty string on web or the hook throws.
  // Google sign-in is disabled on web (button is disabled), so we pass a
  // placeholder to satisfy the requirement without enabling the flow.
  const [googleRequest, googleResponse, googlePromptAsync] = Google.useAuthRequest(
    Platform.OS === "web"
      ? { webClientId: "not-configured-web-disabled" }
      : {
          expoClientId: GOOGLE_EXPO_CLIENT_ID,
          iosClientId: GOOGLE_IOS_CLIENT_ID,
          androidClientId: GOOGLE_ANDROID_CLIENT_ID,
          redirectUri: EXPO_REDIRECT_URI,
        }
  );

  useEffect(() => {
    if (googleResponse?.type === "success") {
      const token = googleResponse.authentication?.accessToken;
      if (token) handleSocialLogin("google", token);
    }
  }, [googleResponse]);

  // ── Microsoft OAuth ─────────────────────────────────────────────────────────
  const msDiscovery = AuthSession.useAutoDiscovery(
    "https://login.microsoftonline.com/common/v2.0"
  );
  const [msRequest, msResponse, msPromptAsync] = AuthSession.useAuthRequest(
    {
      clientId: MICROSOFT_CLIENT_ID,
      scopes: ["openid", "profile", "email", "User.Read"],
      responseType: AuthSession.ResponseType.Token,
      redirectUri: EXPO_REDIRECT_URI,
    },
    msDiscovery
  );

  useEffect(() => {
    if (msResponse?.type === "success") {
      const token = (msResponse as any).params?.access_token;
      if (token) handleSocialLogin("microsoft", token);
    }
  }, [msResponse]);

  const resetForm = () => {
    setEmail("");
    setPassword("");
    setName("");
    setFieldError("");
  };

  const handleSocialLogin = async (provider: "google" | "microsoft", accessToken: string) => {
    setLoading(true);
    setFieldError("");
    try {
      const res = await fetch(`${API_BASE}/helpers/oauth`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, access_token: accessToken }),
      });
      const data = await res.json();
      if (!res.ok) {
        setFieldError(data.detail || "Social login failed.");
        return;
      }
      setAuth({
        status: "loggedInWithProfile",
        token: data.token,
        profile: {
          id: String(data.helper.id),
          email: data.helper.email,
          displayName: data.helper.name,
          photoString: "",
        },
      });
    } catch {
      setFieldError("Could not connect to server. Check your connection.");
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async () => {
    const trimEmail = email.trim().toLowerCase();
    const trimPass = password;

    if (!trimEmail || !trimPass) {
      setFieldError("Please enter your email and password.");
      return;
    }
    if (!EMAIL_RE.test(trimEmail)) {
      setFieldError("Please enter a valid email address.");
      return;
    }

    setLoading(true);
    setFieldError("");
    try {
      const res = await fetch(`${API_BASE}/helpers/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: trimEmail, password: trimPass }),
      });

      const data = await res.json();

      if (!res.ok) {
        setFieldError(data.detail || "Login failed. Please check your credentials.");
        return;
      }

      setAuth({
        status: "loggedInWithProfile",
        token: data.token,
        profile: {
          id: String(data.helper.id),
          email: data.helper.email,
          displayName: data.helper.name,
          photoString: "",
        },
      });
      resetForm();
    } catch {
      setFieldError("Could not connect to server. Check your connection.");
    } finally {
      setLoading(false);
    }
  };

  const handleSignup = async () => {
    const trimEmail = email.trim().toLowerCase();
    const trimName = name.trim();
    const trimPass = password;

    if (!trimName || !trimEmail || !trimPass) {
      setFieldError("Please fill in all fields.");
      return;
    }
    if (!EMAIL_RE.test(trimEmail)) {
      setFieldError("Please enter a valid email address.");
      return;
    }
    if (trimPass.length < 6) {
      setFieldError("Password must be at least 6 characters.");
      return;
    }

    setLoading(true);
    setFieldError("");
    try {
      const res = await fetch(`${API_BASE}/helpers/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimName, email: trimEmail, password: trimPass }),
      });

      const data = await res.json();

      if (!res.ok) {
        setFieldError(data.detail || "Sign up failed.");
        return;
      }

      // Auto-login after signup
      const loginRes = await fetch(`${API_BASE}/helpers/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: trimEmail, password: trimPass }),
      });
      const loginData = await loginRes.json();
      if (loginRes.ok) {
        setAuth({
          status: "loggedInWithProfile",
          token: loginData.token,
          profile: {
            id: String(loginData.helper.id),
            email: loginData.helper.email,
            displayName: loginData.helper.name,
            photoString: "",
          },
        });
        resetForm();
      } else {
        // Signup worked but auto-login failed — switch to login mode
        setMode("login");
        setFieldError("Account created! Please log in.");
      }
    } catch {
      setFieldError("Could not connect to server. Check your connection.");
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    const canGoBack = (router as any)?.canGoBack?.() ?? false;
    if (canGoBack) router.back();
    else router.replace("/" as any);
  };

  const handleLogout = () => {
    setAuth({ status: "loggedOut" });
    resetForm();
  };

  const handleDeleteAccount = async () => {
    if (auth.status !== "loggedInWithProfile") return;

    Alert.alert(
      "Delete Account",
      "This will permanently delete your account and all data. This cannot be undone.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            try {
              const res = await fetch(`${API_BASE}/helpers/delete-account`, {
                method: "DELETE",
                headers: { Authorization: `Bearer ${auth.token}` },
              });
              if (res.ok) {
                setAuth({ status: "loggedOut" });
              } else {
                Alert.alert("Error", "Failed to delete account.");
              }
            } catch {
              Alert.alert("Error", "Could not connect to server.");
            }
          },
        },
      ]
    );
  };

  const renderAuth = () => (
    <>
      {/* Hero */}
      <View style={styles.heroCard}>
        <View style={styles.heroAvatarWrap}>
          <View style={styles.heroAvatar}>
            <Icon name="user" size={32} color="#0D1B2A" />
          </View>
          <View style={styles.heroAvatarRing} />
        </View>
        <View style={styles.heroText}>
          <Text style={styles.heroTitle}>Profile</Text>
          <Text style={styles.heroSubtitle}>
            {mode === "login"
              ? "Log in to your WalkBuddy helper account."
              : "Create a new WalkBuddy helper account."}
          </Text>
        </View>
      </View>

      {/* Tab switcher */}
      <View style={styles.tabRow}>
        <Pressable
          onPress={() => { setMode("login"); setFieldError(""); }}
          style={[styles.tab, mode === "login" && styles.tabActive]}
        >
          <Text style={[styles.tabText, mode === "login" && styles.tabTextActive]}>Log In</Text>
        </Pressable>
        <Pressable
          onPress={() => { setMode("signup"); setFieldError(""); }}
          style={[styles.tab, mode === "signup" && styles.tabActive]}
        >
          <Text style={[styles.tabText, mode === "signup" && styles.tabTextActive]}>Sign Up</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        {mode === "signup" && (
          <>
            <Text style={styles.inputLabel}>Full Name</Text>
            <TextInput
              value={name}
              onChangeText={setName}
              placeholder="Your name"
              placeholderTextColor="rgba(184,198,212,0.55)"
              style={styles.input}
            />
            <View style={{ height: 12 }} />
          </>
        )}

        <Text style={styles.inputLabel}>Email</Text>
        <TextInput
          value={email}
          onChangeText={setEmail}
          placeholder="name@example.com"
          placeholderTextColor="rgba(184,198,212,0.55)"
          autoCapitalize="none"
          keyboardType="email-address"
          style={styles.input}
        />

        <View style={{ height: 12 }} />
        <Text style={styles.inputLabel}>Password</Text>
        <TextInput
          value={password}
          onChangeText={setPassword}
          placeholder={mode === "signup" ? "At least 6 characters" : "Password"}
          placeholderTextColor="rgba(184,198,212,0.55)"
          secureTextEntry
          style={styles.input}
        />

        {!!fieldError && (
          <Text style={styles.errorText}>{fieldError}</Text>
        )}

        <View style={styles.btnRow}>
          <PrimaryButton
            label={mode === "login" ? "Log In" : "Create Account"}
            onPress={mode === "login" ? handleLogin : handleSignup}
            loading={loading}
          />
        </View>

        {/* Toggle link */}
        <Pressable
          onPress={() => { setMode(mode === "login" ? "signup" : "login"); setFieldError(""); }}
          style={styles.toggleLinkWrap}
        >
          <Text style={styles.toggleLink}>
            {mode === "login"
              ? "Don't have an account? "
              : "Already have an account? "}
            <Text style={styles.toggleLinkBold}>
              {mode === "login" ? "Sign up here" : "Log in here"}
            </Text>
          </Text>
        </Pressable>
      </View>

      {/* Social login */}
      <View style={styles.dividerRow}>
        <View style={styles.dividerLine} />
        <Text style={styles.dividerText}>or continue with</Text>
        <View style={styles.dividerLine} />
      </View>

      {Constants.executionEnvironment === "storeClient" ? (
        <View style={styles.socialNotice}>
          <Icon name="info-circle" size={14} color={tokens.muted} />
          <Text style={styles.socialNoticeText}>
            Google & Microsoft sign-in require the full app build. Use email & password above in Expo Go.
          </Text>
        </View>
      ) : (
        <View style={styles.socialRow}>
          <Pressable
            style={({ pressed }) => [styles.socialBtn, pressed && styles.pressed]}
            onPress={() => googlePromptAsync?.()}
            disabled={Platform.OS === "web" || !googleRequest || loading}
            accessibilityLabel="Continue with Google"
          >
            <Icon name="google" size={18} color="#EA4335" />
            <Text style={styles.socialBtnText}>Google</Text>
          </Pressable>

          <Pressable
            style={({ pressed }) => [styles.socialBtn, pressed && styles.pressed]}
            onPress={() => msPromptAsync()}
            disabled={!msRequest || loading}
            accessibilityLabel="Continue with Microsoft"
          >
            <Icon name="windows" size={18} color="#00A4EF" />
            <Text style={styles.socialBtnText}>Microsoft</Text>
          </Pressable>
        </View>
      )}
    </>
  );

  const renderProfile = () => {
    if (auth.status !== "loggedInWithProfile") return null;
    const profile = auth.profile;
    return (
      <>
        {/* Profile hero */}
        <View style={styles.profileHeroCard}>
          <View style={styles.profileAvatarWrap}>
            <Icon name="user" size={32} color="#0D1B2A" />
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

        <CardTitle>Navigation</CardTitle>
        <View style={styles.card}>
          <RowLink
            icon="cog"
            label="Settings"
            sublabel="App preferences and voice settings"
            onPress={() => router.push("/settings" as any)}
          />
        </View>

        <CardTitle>Account</CardTitle>
        <View style={styles.card}>
          <RowLink
            icon="sign-out"
            label="Log Out"
            sublabel="Clears your local session"
            onPress={handleLogout}
          />
          <View style={styles.rowDivider} />
          <RowLink
            icon="trash"
            label="Delete Account"
            sublabel="Permanently removes your account"
            onPress={handleDeleteAccount}
            destructive
          />
        </View>
      </>
    );
  };

  return (
    <SafeAreaView style={styles.screen} edges={["top"]}>
      <Pressable
        onPress={handleBack}
        style={styles.backBtnFloating}
        accessibilityLabel="Go back"
      >
        <Icon name="arrow-left" size={20} color={tokens.gold} />
      </Pressable>
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
            {auth.status === "loggedOut" ? renderAuth() : renderProfile()}
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
    position: "relative",
  },
  kb: {
    flex: 1,
    width: "100%",
    alignItems: "center",
  },
  content: {
    flex: 1,
    paddingHorizontal: 12,
    paddingTop: 14,
  },

  backBtnFloating: {
    position: "absolute",
    top: 12,
    left: 12,
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: "rgba(27,38,59,0.65)",
    borderWidth: 1.5,
    borderColor: tokens.gold,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 20,
  },
  scrollContent: {
    paddingBottom: 120,
    gap: 14,
  },

  // ─── Hero (logged out) ───
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

  heroText: {
    flex: 1,
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

  tabRow: {
    flexDirection: "row",
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 12,
    overflow: "hidden",
  },
  tab: {
    flex: 1,
    paddingVertical: 10,
    alignItems: "center",
    backgroundColor: "transparent",
  },
  tabActive: {
    backgroundColor: tokens.gold,
  },
  tabText: {
    color: tokens.muted,
    fontSize: 14,
    fontWeight: "800",
  },
  tabTextActive: {
    color: "#111",
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
    backgroundColor: tokens.inputBg,
    borderWidth: 1.5,
    borderColor: "rgba(252,163,17,0.3)",
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 13,
  },
  errorText: {
    color: tokens.error,
    fontSize: 13,
    marginTop: 10,
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
    minHeight: 46,
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
  disabledBtn: {
    opacity: 0.7,
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
  toggleLinkWrap: {
    alignItems: "center",
    paddingTop: 14,
  },
  toggleLink: {
    color: tokens.muted,
    fontSize: 13,
    textAlign: "center",
  },
  toggleLinkBold: {
    color: tokens.gold,
    fontWeight: "800",
  },
  dividerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 4,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: "rgba(252,163,17,0.3)",
  },
  dividerText: {
    color: tokens.muted,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.3,
  },
  socialRow: {
    flexDirection: "row",
    gap: 12,
  },
  socialBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    borderWidth: 2,
    borderColor: tokens.gold,
    borderRadius: 12,
    paddingVertical: 12,
    backgroundColor: tokens.card,
  },
  socialBtnText: {
    color: tokens.text,
    fontSize: 14,
    fontWeight: "800",
  },
  socialNotice: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    backgroundColor: tokens.card,
    borderWidth: 1,
    borderColor: "rgba(252,163,17,0.3)",
    borderRadius: 10,
    padding: 12,
  },
  socialNoticeText: {
    flex: 1,
    color: tokens.muted,
    fontSize: 12,
    lineHeight: 18,
  },

  // ─── Row links ───
  row: {
    paddingVertical: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  rowDivider: {
    height: 1,
    backgroundColor: tokens.divider,
    marginVertical: 4,
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
});
