import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { AuthError, fetchCurrentUser, getToken, loginRequest, setToken, type CurrentUser } from 'data';

type AuthState = { status: 'loading' } | { status: 'anonymous' } | { status: 'ready'; user: CurrentUser };

interface AuthContextValue {
  state: AuthState;
  login: (email: string, password: string) => Promise<CurrentUser>;
  logout: () => void;
  setUser: (user: CurrentUser) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Sessão no mesmo token do frontend atual: entrar ou sair num app vale para os dois. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() => (getToken() ? { status: 'loading' } : { status: 'anonymous' }));

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    let cancelled = false;
    fetchCurrentUser(token)
      .then((user) => {
        if (!cancelled) setState({ status: 'ready', user });
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof AuthError) setToken(null);
        setState({ status: 'anonymous' });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const token = await loginRequest(email, password);
    setToken(token);
    const user = await fetchCurrentUser(token);
    setState({ status: 'ready', user });
    return user;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setState({ status: 'anonymous' });
  }, []);

  const setUser = useCallback((user: CurrentUser) => setState({ status: 'ready', user }), []);

  const value = useMemo(() => ({ state, login, logout, setUser }), [state, login, logout, setUser]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth fora do AuthProvider');
  return ctx;
}
