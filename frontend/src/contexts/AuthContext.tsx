/**
 * Authentication Context for hybrid auth (Clerk + Session)
 *
 * This context provides unified authentication state that works with:
 * 1. Clerk OAuth authentication (cloud deployment)
 * 2. Traditional session-based authentication (local development)
 *
 * The auth method is determined by the VITE_AUTH_MODE environment variable:
 * - "clerk": Use Clerk for authentication
 * - "session": Use traditional session cookies (default)
 * - "hybrid": Try Clerk first, fall back to session
 */

import { createContext, useContext, useEffect, useState, useCallback, useMemo, lazy, Suspense, type ReactNode } from 'react';
import { apiClient } from '../api/client';

// Auth mode from environment
const AUTH_MODE = import.meta.env.VITE_AUTH_MODE || 'session';
const CLERK_PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || '';
// Only enable Clerk if both key is present AND mode requires it
export const CLERK_ENABLED = !!CLERK_PUBLISHABLE_KEY && (AUTH_MODE === 'clerk' || AUTH_MODE === 'hybrid');

console.log('[Auth] Config:', { AUTH_MODE, CLERK_ENABLED, hasKey: !!CLERK_PUBLISHABLE_KEY });

// User type matching backend
interface User {
  id: number;
  email: string;
  display_name: string | null;
  timezone: string;
  clerk_user_id?: string | null;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  authMode: 'clerk' | 'session' | 'hybrid';
  clerkEnabled: boolean;
  // Actions
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  // Clerk-specific
  getToken: () => Promise<string | null>;
}

// Export context for ClerkAuthProvider to use
export const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

// Fetch user from backend (works with both auth methods)
async function fetchBackendUser(token?: string | null): Promise<User | null> {
  try {
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    console.log('[Auth] Fetching user from backend, hasToken:', !!token);
    const response = await apiClient.get<User>('/auth/me', { headers });
    console.log('[Auth] Backend user response:', response.data);
    return response.data;
  } catch (error) {
    console.debug('[Auth] Failed to fetch user from backend:', error);
    return null;
  }
}

/**
 * Session-only AuthProvider (no Clerk dependency)
 */
function SessionAuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check session on mount
  useEffect(() => {
    const checkSession = async () => {
      console.log('[Auth] SessionAuthProvider: checking session');
      try {
        const backendUser = await fetchBackendUser();
        setUser(backendUser);
      } catch {
        // Session not valid
      } finally {
        setIsLoading(false);
      }
    };

    checkSession();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await apiClient.post<User>('/auth/login', { email, password });
    setUser(response.data);
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiClient.post('/auth/logout');
    } catch (error) {
      console.error('[Auth] Logout error:', error);
    } finally {
      setUser(null);
    }
  }, []);

  const refreshUser = useCallback(async () => {
    setIsLoading(true);
    try {
      const backendUser = await fetchBackendUser();
      setUser(backendUser);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const getToken = useCallback(async () => null, []);

  const contextValue = useMemo<AuthContextType>(() => ({
    user,
    isLoading,
    isAuthenticated: !!user,
    authMode: 'session',
    clerkEnabled: false,
    login,
    logout,
    refreshUser,
    getToken,
  }), [user, isLoading, login, logout, refreshUser, getToken]);

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}

// Lazy load ClerkAuthProvider only when needed
const LazyClerkAuthProvider = lazy(() =>
  import('./ClerkAuthProvider').then(module => ({
    default: ({ children }: { children: ReactNode }) => (
      <module.ClerkAuthProvider AuthContext={AuthContext}>
        {children}
      </module.ClerkAuthProvider>
    )
  }))
);

// Loading fallback for Clerk provider
const AuthLoadingFallback = () => (
  <div className="min-h-screen flex items-center justify-center">
    <div className="text-accent animate-pulse">인증 로딩중...</div>
  </div>
);

/**
 * Main AuthProvider - selects appropriate provider based on configuration
 */
export function AuthProvider({ children }: AuthProviderProps) {
  console.log('[Auth] AuthProvider: CLERK_ENABLED =', CLERK_ENABLED);

  if (CLERK_ENABLED) {
    return (
      <Suspense fallback={<AuthLoadingFallback />}>
        <LazyClerkAuthProvider>{children}</LazyClerkAuthProvider>
      </Suspense>
    );
  }

  return <SessionAuthProvider>{children}</SessionAuthProvider>;
}

/**
 * Hook to access authentication context
 */
export function useAuthContext() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuthContext must be used within AuthProvider');
  }
  return context;
}

/**
 * Hook to get the current user
 */
export function useCurrentUser() {
  const { user, isLoading, isAuthenticated } = useAuthContext();
  return { user, isLoading, isAuthenticated };
}

/**
 * Hook to get auth token for API calls
 */
export function useAuthToken() {
  const { getToken } = useAuthContext();
  return getToken;
}
