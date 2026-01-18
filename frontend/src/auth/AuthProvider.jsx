import React, { useCallback, useMemo, useState } from 'react';
import AuthContext, { readStoredAuth, TOKEN_KEY, USER_KEY } from './AuthContext.jsx';

const clearStorage = () => {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
};

const AuthProvider = ({ children }) => {
  const initial = readStoredAuth();
  const [token, setToken] = useState(initial.token);
  const [user, setUser] = useState(initial.user);

  const login = useCallback(({ token: nextToken, user: nextUser, remember }) => {
    setToken(nextToken);
    setUser(nextUser);
    clearStorage();
    const storage = remember ? localStorage : sessionStorage;
    storage.setItem(TOKEN_KEY, nextToken);
    storage.setItem(USER_KEY, JSON.stringify(nextUser));
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    clearStorage();
  }, []);

  const value = useMemo(
    () => ({
      token,
      user,
      isAuthenticated: Boolean(token),
      login,
      logout,
    }),
    [token, user, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export default AuthProvider;

