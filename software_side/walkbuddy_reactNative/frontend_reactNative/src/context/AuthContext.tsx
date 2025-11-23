// src/context/AuthContext.tsx
import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from "react";
import {
  User,
  onAuthStateChanged,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
} from "firebase/auth";
import { doc, getDoc, setDoc } from "firebase/firestore";
import { auth, db } from "../utils/firebase";

type LanguageOption = "english" | "spanish" | "mandarin" | "punjabi";
type RoleOption = "admin" | "user";

export type UserProfile = {
  uid: string;
  email: string;
  firstName: string;
  age: number;
  language: LanguageOption;
  role: RoleOption;
};

type RegisterParams = {
  email: string;
  password: string;
  firstName: string;
  age: number;
  language: LanguageOption;
  role: RoleOption;
};

type AuthContextValue = {
  user: User | null;
  profile: UserProfile | null;
  loading: boolean;
  register: (params: RegisterParams) => Promise<UserProfile>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  // ---------------------------------------------------------
  // Load Firebase auth state and load the profile safely
  // ---------------------------------------------------------
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      setUser(firebaseUser);

      try {
        if (firebaseUser) {
          const ref = doc(db, "users", firebaseUser.uid);
          const snap = await getDoc(ref);

          if (snap.exists()) {
            setProfile(snap.data() as UserProfile);
          } else {
            setProfile(null);
          }
        } else {
          setProfile(null);
        }
      } catch (err) {
        console.error(
          "AuthContext onAuthStateChanged: error loading Firestore profile",
          err
        );
        // Do not break the auth state if Firestore is offline
      } finally {
        setLoading(false);
      }
    });

    return () => unsubscribe();
  }, []);

  // ---------------------------------------------------------
  // REGISTER — create Firebase user + Firestore profile
  // ---------------------------------------------------------
  const register = async ({
    email,
    password,
    firstName,
    age,
    language,
    role,
  }: RegisterParams): Promise<UserProfile> => {
    try {
      console.log("AuthContext.register: creating user", { email });

      const cred = await createUserWithEmailAndPassword(auth, email, password);
      const uid = cred.user.uid;

      const profileData: UserProfile = {
        uid,
        email,
        firstName,
        age,
        language,
        role,
      };

      console.log("AuthContext.register: writing Firestore profile doc");
      await setDoc(doc(db, "users", uid), profileData);

      // Update local profile immediately
      setProfile(profileData);

      console.log("AuthContext.register: completed successfully");

      return profileData;
    } catch (err) {
      console.error("AuthContext.register: ERROR", err);
      throw err;
    }
  };

  // ---------------------------------------------------------
  // LOGIN — loads profile via onAuthStateChanged
  // ---------------------------------------------------------
  const login = async (email: string, password: string) => {
    await signInWithEmailAndPassword(auth, email, password);
  };

  // ---------------------------------------------------------
  // LOGOUT
  // ---------------------------------------------------------
  const logout = async () => {
    await signOut(auth);
  };

  const value: AuthContextValue = {
    user,
    profile,
    loading,
    register,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return ctx;
}
