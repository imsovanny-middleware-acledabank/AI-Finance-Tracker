import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getCurrentUser, logoutSession, refreshSession } from "@/services/auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function loadUser() {
      try {
        const data = await getCurrentUser();
        if (mounted) setUser(data);
      } catch {
        if (mounted) setUser(null);
      } finally {
        if (mounted) setLoading(false);
      }
    }

    loadUser();

    const refreshTimer = setInterval(async () => {
      try {
        const data = await refreshSession();
        if (mounted) setUser(data);
      } catch {
        if (mounted) setUser(null);
      }
    }, 1000 * 60 * 10);

    return () => {
      mounted = false;
      clearInterval(refreshTimer);
    };
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      role: user?.role ?? "viewer",
      isAuthenticated: Boolean(user?.id),
      setUser,
      async logout() {
        await logoutSession();
        setUser(null);
      },
    }),
    [user, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
