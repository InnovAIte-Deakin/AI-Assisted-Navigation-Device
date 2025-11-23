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
import { Picker } from "@react-native-picker/picker";
import { useAuth } from "../src/context/AuthContext";

export default function RegisterScreen() {
  const router = useRouter();
  const { register } = useAuth();

  const [firstName, setFirstName] = useState("");
  const [age, setAge] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [language, setLanguage] = useState<"english" | "spanish" | "mandarin" | "punjabi">(
    "english"
  );
  const [role, setRole] = useState<"admin" | "user">("user");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRegister = async () => {
  setError(null);

  if (!email.trim() || !password || !firstName.trim()) {
    setError("Please fill in at least name, email and password.");
    return;
  }

  console.log("Register: starting", { email, firstName, age, language, role });

  setSubmitting(true);
  try {
    await register({
      email: email.trim(),
      password,
      firstName: firstName.trim(),
      age: Number(age) || 0,
      language,
      role,
    });
    console.log("Register: success, navigating home");
    router.replace("/");
  } catch (e: any) {
    console.error("Register: ERROR", e);
    setError(`Firebase: ${e?.message ?? "Registration failed"}`);
  } finally {
    console.log("Register: finished (finally)");
    setSubmitting(false);
  }
};


  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        <Text style={styles.header}>CREATE ACCOUNT</Text>

        <TextInput
          style={styles.input}
          placeholder="First name"
          placeholderTextColor="#AAA"
          value={firstName}
          onChangeText={setFirstName}
        />

        <TextInput
          style={styles.input}
          placeholder="Age"
          placeholderTextColor="#AAA"
          value={age}
          onChangeText={setAge}
          keyboardType="numeric"
        />

        <TextInput
          style={styles.input}
          placeholder="Email"
          placeholderTextColor="#AAA"
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          keyboardType="email-address"
        />

        <TextInput
          style={styles.input}
          placeholder="Password"
          placeholderTextColor="#AAA"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
        />

        <Text style={styles.label}>Language preference</Text>
        <View style={styles.pickerWrapper}>
          <Picker
            selectedValue={language}
            onValueChange={(value) =>
              setLanguage(value as "english" | "spanish" | "mandarin" | "punjabi")
            }
            dropdownIconColor="#FFA500"
          >
            <Picker.Item label="English" value="english" />
            <Picker.Item label="Spanish" value="spanish" />
            <Picker.Item label="Mandarin" value="mandarin" />
            <Picker.Item label="Punjabi" value="punjabi" />
          </Picker>
        </View>

        <Text style={styles.label}>Role</Text>
        <View style={styles.pickerWrapper}>
          <Picker
            selectedValue={role}
            onValueChange={(value) => setRole(value as "admin" | "user")}
            dropdownIconColor="#FFA500"
          >
            <Picker.Item label="User" value="user" />
            <Picker.Item label="Admin" value="admin" />
          </Picker>
        </View>

        {error && <Text style={styles.error}>{error}</Text>}

        <TouchableOpacity
          style={styles.button}
          onPress={handleRegister}
          disabled={submitting}
        >
          {submitting ? (
            <ActivityIndicator color="#1B263B" />
          ) : (
            <Text style={styles.buttonText}>SIGN UP</Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.loginLink}
          onPress={() => router.push("/login")}
        >
          <Text style={styles.loginText}>Back to login</Text>
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
    fontSize: 24,
    color: "#FFA500",
    fontWeight: "bold",
    marginBottom: 30,
  },
  input: {
    backgroundColor: "#333",
    width: "100%",
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: 10,
    color: "#FFF",
    marginBottom: 14,
  },
  label: {
    color: "#FFA500",
    alignSelf: "flex-start",
    marginTop: 4,
    marginBottom: 4,
    fontWeight: "600",
  },
  pickerWrapper: {
    backgroundColor: "#333",
    borderRadius: 10,
    width: "100%",
    marginBottom: 14,
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
    alignSelf: "flex-start",
    marginBottom: 8,
  },
  loginLink: {
    marginTop: 18,
  },
  loginText: {
    color: "#FFA500",
    fontWeight: "600",
  },
});
