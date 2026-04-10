import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import type { ReactNode } from 'react';
import api from '../api/client.ts';
import type { JwtPayload, TokenResponse } from '../types/api.ts';

interface AuthState {
  isAuthenticated: boolean;
  pharmacyId: number | null;
  username: string | null;
  role: string | null;
}

interface AuthContextValue extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function decodeJwt(token: string): JwtPayload | null {
  try {
    const base64 = token.split('.')[1];
    const json = atob(base64);
    return JSON.parse(json) as JwtPayload;
  } catch {
    return null;
  }
}

function loadInitialState(): AuthState {
  const token = localStorage.getItem('access_token');
  const refreshToken = localStorage.getItem('refresh_token');

  // Valid access token → authenticated with full payload
  if (token) {
    const payload = decodeJwt(token);
    if (payload && payload.exp * 1000 > Date.now()) {
      return { isAuthenticated: true, pharmacyId: payload.pharmacy_id, username: null, role: payload.role };
    }
  }

  // Access expired but refresh exists → optimistic auth (interceptor handles 401→refresh)
  if (refreshToken) {
    return { isAuthenticated: true, pharmacyId: null, username: null, role: null };
  }

  return { isAuthenticated: false, pharmacyId: null, username: null, role: null };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(loadInitialState);

  // Try refresh on mount if we have a refresh_token but access expired
  useEffect(() => {
    const accessToken = localStorage.getItem('access_token');
    const refreshToken = localStorage.getItem('refresh_token');
    if (!accessToken && refreshToken) {
      api.post('/auth/refresh', { refresh_token: refreshToken })
        .then(({ data }) => {
          localStorage.setItem('access_token', data.access_token);
          const payload = decodeJwt(data.access_token);
          if (payload) {
            setState({
              isAuthenticated: true,
              pharmacyId: payload.pharmacy_id,
              username: null,
              role: payload.role,
            });
          }
        })
        .catch(() => {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
        });
    }
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const { data } = await api.post<TokenResponse>('/auth/login', {
      username,
      password,
    });

    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);

    const payload = decodeJwt(data.access_token);
    setState({
      isAuthenticated: true,
      pharmacyId: payload?.pharmacy_id ?? null,
      username,
      role: payload?.role ?? null,
    });
  }, []);

  const logout = useCallback(async () => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (refreshToken) {
      try {
        await api.post('/auth/logout', { refresh_token: refreshToken });
      } catch {
        // ignore logout errors
      }
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setState({ isAuthenticated: false, pharmacyId: null, username: null, role: null });
  }, []);

  const value = useMemo(
    () => ({ ...state, login, logout }),
    [state, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
