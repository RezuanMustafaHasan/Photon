import { createContext, useContext } from 'react';

const AuthContext = createContext(null);

export const TOKEN_KEY = 'photon_token';
export const USER_KEY = 'photon_user';

export const readStoredAuth = () => {
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

export default AuthContext;

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
