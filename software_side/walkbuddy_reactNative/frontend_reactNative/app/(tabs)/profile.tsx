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
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import * as Google from "expo-auth-session/providers/google";
import * as AuthSession from "expo-auth-session";
import Constants from "expo-constants";

import HomeHeader from "../HomeHeader";
import { useSession } from "../../src/context/SessionContext";
import { API_BASE } from "@/src/config";
import { Radius, Spacing, Typography } from "@/constants/theme";
import { useThemeColors } from "@/hooks/use-theme-colors";

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

function CardTitle({ children }: { children: string }) {
  const colors = useThemeColors();
  return <Text style={[styles.sectionTitle, { color: colors.textMuted }]}>{children}</Text>;
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
  const colors = useThemeColors();
  return (
    <Pressable
      onPress={onPress}
      disabled={loading}
      style={({ pressed }) => [
        styles.primaryBtn,
        { backgroundColor: colors.accent, shadowColor: colors.accent },
        pressed && styles.pressed,
        loading && styles.disabledBtn,
      ]}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      {loading ? (
        <ActivityIndicator size="small" color={colors.accentText} />
      ) : (
        <Text style={[styles.primaryBtnText, { color: colors.accentText }]}>{label}</Text>
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
  const colors = useThemeColors();
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.secondaryBtn,
        { borderColor: colors.accent + "66" },
        pressed && styles.pressed,
      ]}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      <Text style={[styles.secondaryBtnText, { color: colors.textMuted }]}>{label}</Text>
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
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  sublabel?: string;
  onPress: () => void;
  destructive?: boolean;
}) {
  const colors = useThemeColors();
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      <View style={styles.rowLeft}>
        <View style={[styles.rowIconWrap, { backgroundColor: colors.accent + "1F", borderColor: colors.accent + "40" }]}>
          <Ionicons name={icon} size={18} color={destructive ? colors.danger : colors.accent} />
        </View>
        <View style={styles.rowTextWrap}>
          <Text style={[styles.rowLabel, { color: colors.text }, destructive && { color: colors.danger }]}>{label}</Text>
          {!!sublabel && <Text style={[styles.rowSublabel, { color: colors.textMuted }]}>{sublabel}</Text>}
        </View>
      </View>
      <Ionicons name="chevron-forward-outline" size={14} color={colors.textMuted} />
    </Pressable>
  );
}

type Mode = "login" | "signup";

export default function ProfilePage() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const { auth, setAuth } = useSession();
  const colors = useThemeColors();

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
      <View style={[styles.heroCard, { backgroundColor: colors.surface, borderColor: colors.accent + "4D", shadowColor: colors.accent }]}>
        <View style={styles.heroAvatarWrap}>
          <View style={[styles.heroAvatar, { backgroundColor: colors.accent }]}>
            <Ionicons name="person-outline" size={32} color={colors.accentText} />
          </View>
          <View style={[styles.heroAvatarRing, { borderColor: colors.accent + "4D" }]} />
        </View>
        <View style={styles.heroText}>
          <Text style={[styles.heroTitle, { color: colors.text }]}>Profile</Text>
          <Text style={[styles.heroSubtitle, { color: colors.textMuted }]}>
            {mode === "login"
              ? "Log in to your WalkBuddy helper account."
              : "Create a new WalkBuddy helper account."}
          </Text>
        </View>
      </View>

      {/* Tab switcher */}
      <View style={[styles.tabRow, { borderColor: colors.accent }]}>
        <Pressable
          onPress={() => { setMode("login"); setFieldError(""); }}
          style={[styles.tab, mode === "login" && { backgroundColor: colors.accent }]}
        >
          <Text style={[styles.tabText, { color: colors.textMuted }, mode === "login" && { color: colors.accentText }]}>Log In</Text>
        </Pressable>
        <Pressable
          onPress={() => { setMode("signup"); setFieldError(""); }}
          style={[styles.tab, mode === "signup" && { backgroundColor: colors.accent }]}
        >
          <Text style={[styles.tabText, { color: colors.textMuted }, mode === "signup" && { color: colors.accentText }]}>Sign Up</Text>
        </Pressable>
      </View>

      <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.accent + "33" }]}>
        {mode === "signup" && (
          <>
            <Text style={[styles.inputLabel, { color: colors.textMuted }]}>Full Name</Text>
            <TextInput
              value={name}
              onChangeText={setName}
              placeholder="Your name"
              placeholderTextColor={colors.textMuted}
              style={[styles.input, { color: colors.text, backgroundColor: colors.background, borderColor: colors.accent + "4D" }]}
            />
            <View style={{ height: 12 }} />
          </>
        )}

        <Text style={[styles.inputLabel, { color: colors.textMuted }]}>Email</Text>
        <TextInput
          value={email}
          onChangeText={setEmail}
          placeholder="name@example.com"
          placeholderTextColor={colors.textMuted}
          autoCapitalize="none"
          keyboardType="email-address"
          style={[styles.input, { color: colors.text, backgroundColor: colors.background, borderColor: colors.accent + "4D" }]}
        />

        <View style={{ height: 12 }} />
        <Text style={[styles.inputLabel, { color: colors.textMuted }]}>Password</Text>
        <TextInput
          value={password}
          onChangeText={setPassword}
          placeholder={mode === "signup" ? "At least 6 characters" : "Password"}
          placeholderTextColor={colors.textMuted}
          secureTextEntry
          style={[styles.input, { color: colors.text, backgroundColor: colors.background, borderColor: colors.accent + "4D" }]}
        />

        {!!fieldError && (
          <Text style={[styles.errorText, { color: colors.danger }]}>{fieldError}</Text>
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
          <Text style={[styles.toggleLink, { color: colors.textMuted }]}>
            {mode === "login"
              ? "Don't have an account? "
              : "Already have an account? "}
            <Text style={[styles.toggleLinkBold, { color: colors.accent }]}>
              {mode === "login" ? "Sign up here" : "Log in here"}
            </Text>
          </Text>
        </Pressable>
      </View>

      {/* Social login */}
      <View style={styles.dividerRow}>
        <View style={[styles.dividerLine, { backgroundColor: colors.accent + "4D" }]} />
        <Text style={[styles.dividerText, { color: colors.textMuted }]}>or continue with</Text>
        <View style={[styles.dividerLine, { backgroundColor: colors.accent + "4D" }]} />
      </View>

      {Constants.executionEnvironment === "storeClient" ? (
        <View style={[styles.socialNotice, { backgroundColor: colors.surface, borderColor: colors.accent + "4D" }]}>
          <Ionicons name="information-circle-outline" size={14} color={colors.textMuted} />
          <Text style={[styles.socialNoticeText, { color: colors.textMuted }]}>
            Google & Microsoft sign-in require the full app build. Use email & password above in Expo Go.
          </Text>
        </View>
      ) : (
        <View style={styles.socialRow}>
          <Pressable
            style={({ pressed }) => [styles.socialBtn, { borderColor: colors.accent, backgroundColor: colors.surface }, pressed && styles.pressed]}
            onPress={() => googlePromptAsync?.()}
            disabled={Platform.OS === "web" || !googleRequest || loading}
            accessibilityLabel="Continue with Google"
          >
            {/* Google's brand red is kept as-is — it's a third-party logo color, not part of the app palette */}
            <Ionicons name="logo-google" size={18} color="#EA4335" />
            <Text style={[styles.socialBtnText, { color: colors.text }]}>Google</Text>
          </Pressable>

          <Pressable
            style={({ pressed }) => [styles.socialBtn, { borderColor: colors.accent, backgroundColor: colors.surface }, pressed && styles.pressed]}
            onPress={() => msPromptAsync()}
            disabled={!msRequest || loading}
            accessibilityLabel="Continue with Microsoft"
          >
            {/* Microsoft's brand blue is kept as-is — it's a third-party logo color, not part of the app palette */}
            <Ionicons name="logo-windows" size={18} color="#00A4EF" />
            <Text style={[styles.socialBtnText, { color: colors.text }]}>Microsoft</Text>
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
        <View style={[styles.profileHeroCard, { backgroundColor: colors.surface, borderColor: colors.accent + "4D", shadowColor: colors.accent }]}>
          <View style={[styles.profileAvatarWrap, { backgroundColor: colors.accent, borderColor: colors.accent, shadowColor: colors.accent }]}>
            <Ionicons name="person-outline" size={32} color={colors.accentText} />
          </View>
          <Text style={[styles.profileName, { color: colors.text }]} numberOfLines={1}>
            {profile.displayName}
          </Text>
          <Text style={[styles.profileEmail, { color: colors.textMuted }]} numberOfLines={1}>
            {profile.email}
          </Text>
          <View style={[styles.profileBadge, { backgroundColor: colors.accent }]}>
            <Ionicons name="checkmark-circle" size={12} color={colors.accentText} />
            <Text style={[styles.profileBadgeText, { color: colors.accentText }]}>Logged in</Text>
          </View>
        </View>

        <CardTitle>Navigation</CardTitle>
        <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.accent + "33" }]}>
          <RowLink
            icon="settings-outline"
            label="Settings"
            sublabel="App preferences and voice settings"
            onPress={() => router.push("/settings" as any)}
          />
        </View>

        <CardTitle>Account</CardTitle>
        <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.accent + "33" }]}>
          <RowLink
            icon="log-out-outline"
            label="Log Out"
            sublabel="Clears your local session"
            onPress={handleLogout}
          />
          <View style={[styles.rowDivider, { backgroundColor: colors.accent + "59" }]} />
          <RowLink
            icon="trash-outline"
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
    <SafeAreaView style={[styles.screen, { backgroundColor: colors.background }]} edges={["top"]}>
      <Pressable
        onPress={handleBack}
        style={[styles.backBtnFloating, { backgroundColor: "rgba(27,38,59,0.65)", borderColor: colors.accent }]}
        accessibilityLabel="Go back"
      >
        <Ionicons name="arrow-back-outline" size={20} color={colors.accent} />
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
    paddingHorizontal: Spacing.md,
    paddingTop: 14,
  },

  backBtnFloating: {
    position: "absolute",
    top: Spacing.md,
    left: Spacing.md,
    width: 44,
    height: 44,
    borderRadius: Radius.xl,
    borderWidth: 1.5,
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
    borderRadius: 24,
    borderWidth: 1.5,
    padding: 28,
    alignItems: "center",
    gap: Spacing.md,
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
  },

  heroText: {
    flex: 1,
  },
  heroTitle: {
    fontSize: Typography.size.lg,
    fontWeight: "900",
    textAlign: "center",
    letterSpacing: 0.3,
  },
  heroSubtitle: {
    fontSize: 13,
    textAlign: "center",
    lineHeight: 20,
    fontWeight: "500",
  },

  tabRow: {
    flexDirection: "row",
    borderWidth: 2,
    borderRadius: Radius.md,
    overflow: "hidden",
  },
  tab: {
    flex: 1,
    paddingVertical: 10,
    alignItems: "center",
    backgroundColor: "transparent",
  },
  tabText: {
    fontSize: Typography.size.sm,
    fontWeight: "800",
  },

  // ─── Profile hero (logged in) ───
  profileHeroCard: {
    borderRadius: 24,
    borderWidth: 1.5,
    padding: 28,
    alignItems: "center",
    gap: Spacing.sm,
    shadowOpacity: 0.12,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },

  profileAvatarWrap: {
    width: 80,
    height: 80,
    borderRadius: 40,
    borderWidth: 3,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
    marginBottom: 4,
    shadowOpacity: 0.4,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 0 },
    elevation: 8,
  },

  profileName: {
    fontSize: 22,
    fontWeight: "900",
    textAlign: "center",
  },

  profileEmail: {
    fontSize: 13,
    fontWeight: "600",
    textAlign: "center",
  },

  profileBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: Spacing.md,
    paddingVertical: 5,
    borderRadius: Radius.pill,
    marginTop: 4,
  },

  profileBadgeText: {
    fontSize: Typography.size.xs,
    fontWeight: "800",
  },

  // ─── Section title ───
  sectionTitle: {
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 1.2,
    paddingHorizontal: 4,
  },

  // ─── Card ───
  card: {
    borderRadius: 20,
    borderWidth: 1.5,
    paddingVertical: Spacing.lg,
    paddingHorizontal: Spacing.lg,
    gap: 4,
  },

  // ─── Input ───
  inputLabel: {
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 0.8,
    textTransform: "uppercase",
    marginBottom: Spacing.sm,
  },

  input: {
    flex: 1,
    fontSize: 15,
    fontWeight: "600",
    borderWidth: 1.5,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 13,
  },
  errorText: {
    fontSize: 13,
    marginTop: 10,
    fontWeight: "600",
  },

  // ─── Buttons ───
  btnRow: {
    marginTop: Spacing.xl,
    flexDirection: "row",
    gap: 10,
    alignItems: "center",
  },
  primaryBtn: {
    flex: 1,
    borderRadius: 50,
    paddingVertical: Spacing.lg,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 46,
    shadowOpacity: 0.5,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 0 },
    elevation: 6,
  },
  primaryBtnText: {
    fontSize: 15,
    fontWeight: "900",
    letterSpacing: 0.4,
  },
  disabledBtn: {
    opacity: 0.7,
  },
  secondaryBtn: {
    borderWidth: 1.5,
    backgroundColor: "transparent",
    borderRadius: 50,
    paddingVertical: Spacing.lg,
    paddingHorizontal: Spacing.xl,
    alignItems: "center",
    justifyContent: "center",
  },
  secondaryBtnText: {
    fontSize: 15,
    fontWeight: "800",
  },

  pressed: {
    opacity: 0.85,
  },
  toggleLinkWrap: {
    alignItems: "center",
    paddingTop: 14,
  },
  toggleLink: {
    fontSize: 13,
    textAlign: "center",
  },
  toggleLinkBold: {
    fontWeight: "800",
  },
  dividerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    paddingVertical: 4,
  },
  dividerLine: {
    flex: 1,
    height: 1,
  },
  dividerText: {
    fontSize: Typography.size.xs,
    fontWeight: "700",
    letterSpacing: 0.3,
  },
  socialRow: {
    flexDirection: "row",
    gap: Spacing.md,
  },
  socialBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: Spacing.sm,
    borderWidth: 2,
    borderRadius: Radius.md,
    paddingVertical: Spacing.md,
  },
  socialBtnText: {
    fontSize: Typography.size.sm,
    fontWeight: "800",
  },
  socialNotice: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: Spacing.sm,
    borderWidth: 1,
    borderRadius: 10,
    padding: Spacing.md,
  },
  socialNoticeText: {
    flex: 1,
    fontSize: Typography.size.xs,
    lineHeight: 18,
  },

  // ─── Row links ───
  row: {
    paddingVertical: Spacing.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  rowDivider: {
    height: 1,
    marginVertical: 4,
  },
  rowLeft: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
    paddingRight: Spacing.md,
  },
  rowIconWrap: {
    width: 36,
    height: 36,
    borderRadius: Radius.md,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
    marginRight: Spacing.md,
  },
  rowTextWrap: {
    flex: 1,
  },
  rowLabel: {
    fontSize: 15,
    fontWeight: "800",
  },
  rowSublabel: {
    fontSize: Typography.size.xs,
    marginTop: 2,
    lineHeight: 16,
  },
});
