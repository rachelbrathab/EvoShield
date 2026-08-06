"use client";

/**
 * Client-side session state.
 *
 * The session itself lives in an httpOnly cookie set by the backend — the
 * browser can't read it, so authentication state is derived from the API:
 * `fetchCurrentUser()` on mount, and the AuthResponse returned by
 * register/login. All mutations go through the backend, never the store.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  fetchCurrentUser,
  login as apiLogin,
  logout as apiLogout,
  registerAccount,
  type UserProfile,
} from "@/lib/api";

type AuthContextValue = {
  user: UserProfile | null;
  /** True until the initial session check has completed. */
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, fullName?: string) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<UserProfile | null>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  // Hydrate the session once on mount: the cookie may already be valid
  // (page reload, OAuth redirect back), so we ask the backend who we are.
  useEffect(() => {
    let cancelled = false;
    fetchCurrentUser()
      .then((profile) => {
        if (!cancelled) setUser(profile);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const result = await apiLogin({ email, password });
    setUser(result.user);
  }, []);

  const signUp = useCallback(
    async (email: string, password: string, fullName?: string) => {
      const result = await registerAccount({
        email,
        password,
        full_name: fullName ?? null,
      });
      setUser(result.user);
    },
    [],
  );

  const signOut = useCallback(async () => {
    try {
      await apiLogout();
    } finally {
      // Clear local state even if the backend call fails — the cookie is
      // cleared server-side, and the app must not keep a stale session.
      setUser(null);
    }
  }, []);

  const refresh = useCallback(async () => {
    const profile = await fetchCurrentUser();
    setUser(profile);
    return profile;
  }, []);

  const value = useMemo(
    () => ({ user, loading, signIn, signUp, signOut, refresh }),
    [user, loading, signIn, signUp, signOut, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an <AuthProvider>");
  }
  return ctx;
}
