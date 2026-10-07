import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { api, setTokens, type Tokens } from "../api/client";

export type User = { id: string; typ: "staff" | "patron"; role: string; permissions: string[] };

type AuthState = {
  user: User | null;
  permissions: Set<string>;
  login: (username: string, password: string) => Promise<void>;
  loginWithTokens: (t: Tokens) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  const loginWithTokens = useCallback(async (t: Tokens) => {
    setTokens(t);
    setUser(await api<User>("/auth/me"));
  }, []);

  const login = useCallback(
    async (username: string, password: string) => {
      const t = await api<Tokens>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
      await loginWithTokens(t);
    },
    [loginWithTokens],
  );

  const logout = useCallback(async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    setTokens(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, permissions: new Set(user?.permissions ?? []), login, loginWithTokens, logout }),
    [user, login, loginWithTokens, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

export function RequirePermission({ perm, children }: { perm: string; children: ReactNode }) {
  const { permissions } = useAuth();
  return permissions.has(perm) ? <>{children}</> : null;
}
