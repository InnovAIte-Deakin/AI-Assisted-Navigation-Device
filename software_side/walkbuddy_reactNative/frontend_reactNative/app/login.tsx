import React, { useState } from "react";
import { useRouter } from "expo-router";
import {
  SafeAreaView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  ActivityIndicator,
} from "react-native";
import { useAuth } from "../src/context/AuthContext";

export default function LoginScreen() {
  const router = useRouter();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async () => {
    setError(null);
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      router.replace("/");
    } catch (e: any) {
      setError(e.message ?? "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        <Text style={styles.header}>LOGIN</Text>

        <TextInput
          style={styles.input}
          placeholder="Email"
          placeholderTextColor="#AAA"
          onChangeText={setEmail}
          value={email}
        />

        <TextInput
          style={styles.input}
          placeholder="Password"
          placeholderTextColor="#AAA"
          secureTextEntry
          onChangeText={setPassword}
          value={password}
        />

        {error && <Text style={styles.error}>{error}</Text>}

        <TouchableOpacity
          style={styles.button}
          onPress={handleLogin}
          disabled={submitting}
        >
          {submitting ? (
            <ActivityIndicator color="#1B263B" />
          ) : (
            <Text style={styles.buttonText}>SIGN IN</Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.registerLink}
          onPress={() => router.push("/register")}
        >
          <Text style={styles.registerText}>Register Here</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#1B263B",
  },
  container: {
    flex: 1,
    padding: 24,
    alignItems: "center",
  },
  header: {
    fontSize: 26,
    color: "#FFA500",
    fontWeight: "bold",
    marginBottom: 40,
  },
  input: {
    backgroundColor: "#333",
    width: "100%",
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 10,
    color: "#FFF",
    marginBottom: 16,
  },
  button: {
    backgroundColor: "#FFA500",
    width: "100%",
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: "center",
    marginTop: 10,
  },
  buttonText: {
    color: "#1B263B",
    fontSize: 16,
    fontWeight: "bold",
  },
  error: {
    color: "#FF6B6B",
    marginBottom: 10,
  },
  registerLink: {
    marginTop: 20,
  },
  registerText: {
    color: "#FFA500",
    fontWeight: "600",
  },
});
