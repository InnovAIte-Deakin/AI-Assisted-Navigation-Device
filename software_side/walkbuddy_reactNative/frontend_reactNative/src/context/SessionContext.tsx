// app/SessionContext.tsx
import React, { createContext, useContext, useMemo, useState } from "react";

export type ProfileRecord = {
  email: string;
  displayName: string;
  photoString: string;
};

export type AuthState =
  | { status: "loggedOut" }
  | { status: "loggedInNoProfile"; email: string }
  | { status: "loggedInWithProfile"; profile: ProfileRecord };

type SessionContextValue = {
  auth: AuthState;
  setAuth: React.Dispatch<React.SetStateAction<AuthState>>;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [auth, setAuth] = useState<AuthState>({ status: "loggedOut" });

  const value = useMemo(() => {
    return { auth, setAuth };
  }, [auth]);

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error("useSession must be used within a SessionProvider");
  }
  return ctx;
}
