import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

const AuthContext = createContext(null);

const TOKEN_KEY = 'photon_token';
const USER_KEY = 'photon_user';

const readStoredAuth = () => {
  const localToken = localStorage.getItem(TOKEN_KEY);
  const sessionToken = sessionStorage.getItem(TOKEN_KEY);

  const token = localToken || sessionToken || null;
  const userRaw = localToken ? localStorage.getItem(USER_KEY) : sessionStorage.getItem(USER_KEY);

  let user = null;
  if (userRaw) {
    try {
      user = JSON.parse(userRaw);
    } catch {
      user = null;
    }
  }

  return { token, user, remember: Boolean(localToken) };
};

export function AuthProvider({ children }) {
  const initial = readStoredAuth();
  const [token, setToken] = useState(initial.token);
  const [user, setUser] = useState(initial.user);
  const [isHydrating, setIsHydrating] = useState(Boolean(initial.token));

  const login = useCallback(({ token: nextToken, user: nextUser, remember }) => {
    setToken(nextToken);
    setUser(nextUser);

    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);

    const storage = remember ? localStorage : sessionStorage;
    storage.setItem(TOKEN_KEY, nextToken);
    storage.setItem(USER_KEY, JSON.stringify(nextUser));
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const hydrate = async () => {
      if (!token) {
        setIsHydrating(false);
        return;
      }

      try {
        const res = await fetch('/api/auth/me', {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const me = await res.json();
          if (!cancelled) {
            setUser((prev) => prev || me);
          }
          return;
        }
        if (!cancelled) {
          logout();
        }
      } catch {
        if (!cancelled) {
          setIsHydrating(false);
        }
      } finally {
        if (!cancelled) {
          setIsHydrating(false);
        }
      }
    };

    hydrate();

    return () => {
      cancelled = true;
    };
  }, [token, logout]);

  const value = useMemo(
    () => ({
      token,
      user,
      isAuthenticated: Boolean(token),
      isHydrating,
      login,
      logout,
    }),
    [token, user, isHydrating, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
