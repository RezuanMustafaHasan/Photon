import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  clearStoredRateLimitNotice,
  createRateLimitNotice,
  getRateLimitRemainingSeconds,
  persistRateLimitNotice,
  registerPageLoadRateLimit,
  readStoredRateLimitNotice,
} from '../utils/rateLimit.js';

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
  const [rateLimitNotice, setRateLimitNotice] = useState(() => {
    const storedNotice = readStoredRateLimitNotice();
    if (storedNotice) {
      return storedNotice;
    }

    const pageLoadNotice = registerPageLoadRateLimit({
      pathname: typeof window !== 'undefined' ? window.location.pathname : '/',
    });

    if (pageLoadNotice) {
      persistRateLimitNotice(pageLoadNotice);
      return pageLoadNotice;
    }

    return null;
  });

  const login = useCallback(({ token: nextToken, user: nextUser, remember }) => {
    setToken(nextToken);
    setUser(nextUser);
    setRateLimitNotice(null);
    clearStoredRateLimitNotice();

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
    setRateLimitNotice(null);
    clearStoredRateLimitNotice();
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }, []);

  const showRateLimitNotice = useCallback((notice) => {
    setRateLimitNotice(notice);
    persistRateLimitNotice(notice);
  }, []);

  const clearRateLimitNotice = useCallback(() => {
    setRateLimitNotice(null);
    clearStoredRateLimitNotice();
  }, []);

  useEffect(() => {
    if (!rateLimitNotice) {
      return undefined;
    }

    const remainingSeconds = getRateLimitRemainingSeconds(rateLimitNotice);
    if (remainingSeconds <= 0) {
      setRateLimitNotice(null);
      clearStoredRateLimitNotice();
      return undefined;
    }

    const timeoutId = setTimeout(() => {
      setRateLimitNotice(null);
      clearStoredRateLimitNotice();
    }, remainingSeconds * 1000);

    return () => {
      clearTimeout(timeoutId);
    };
  }, [rateLimitNotice]);

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
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
          const me = data;
          if (!cancelled) {
            setUser((prev) => prev || me);
          }
          return;
        }
        if (res.status === 429) {
          if (!cancelled) {
            const notice = createRateLimitNotice(
              data,
              res.headers,
              'Too many requests right now. Please wait before trying again.',
            );
            setRateLimitNotice(notice);
            persistRateLimitNotice(notice);
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
      rateLimitNotice,
      login,
      logout,
      showRateLimitNotice,
      clearRateLimitNotice,
    }),
    [token, user, isHydrating, rateLimitNotice, login, logout, showRateLimitNotice, clearRateLimitNotice],
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
