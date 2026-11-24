import React, { createContext, useContext, useEffect, useState } from "react";
import { apiRequest, getStoredToken, setStoredToken } from "../api/client";
import type { User } from "../types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  canWrite: boolean;
  isSeniorOrAdmin: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      setLoading(false);
      return;
    }
    apiRequest<User>("/auth/me")
      .then((u) => setUser(u))
      .catch(() => {
        setStoredToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const data = await apiRequest<{ access_token: string; user: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setStoredToken(data.access_token);
    setUser(data.user);
  };

  const logout = () => {
    setStoredToken(null);
    setUser(null);
  };

  const canWrite = Boolean(user && ["analyst", "senior_analyst", "admin"].includes(user.role));
  const isSeniorOrAdmin = Boolean(user && ["senior_analyst", "admin"].includes(user.role));

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, canWrite, isSeniorOrAdmin }}>
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
