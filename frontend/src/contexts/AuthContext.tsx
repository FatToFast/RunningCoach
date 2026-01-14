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

import { createContext, useContext, useEffect, useState, useCallback, useMemo, type ReactNode } from 'react';
import { useAuth as useClerkAuth, useUser as useClerkUser } from '@clerk/clerk-react';
import { apiClient } from '../api/client';

// Auth mode from environment
const AUTH_MODE = import.meta.env.VITE_AUTH_MODE || 'session';
const CLERK_PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || '';
export const CLERK_ENABLED = !!CLERK_PUBLISHABLE_KEY && (AUTH_MODE === 'clerk' || AUTH_MODE === 'hybrid');

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

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

/**
 * Session-only Auth Provider (no Clerk dependency)
 */
function SessionAuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch user from backend
  const fetchBackendUser = useCallback(async (): Promise<User | null> => {
    try {
      const response = await apiClient.get<User>('/auth/me');
      return response.data;
    } catch {
      console.debug('[Auth] Failed to fetch user from backend');
      return null;
    }
  }, []);

  // Refresh user data
  const refreshUser = useCallback(async () => {
    setIsLoading(true);
    try {
      const backendUser = await fetchBackendUser();
      setUser(backendUser);
    } catch (error) {
      console.error('[Auth] Error refreshing user:', error);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, [fetchBackendUser]);

  // Traditional login (session-based)
  const login = useCallback(async (email: string, password: string) => {
    const response = await apiClient.post<User>('/auth/login', { email, password });
    setUser(response.data);
  }, []);

  // Logout
  const logout = useCallback(async () => {
    try {
      await apiClient.post('/auth/logout');
    } catch (error) {
      console.error('[Auth] Logout error:', error);
    } finally {
      setUser(null);
    }
  }, []);

  // No-op getToken for session mode
  const getToken = useCallback(async (): Promise<string | null> => {
    return null;
  }, []);

  // Effect: Check session on mount
  useEffect(() => {
    const checkSession = async () => {
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
  }, [fetchBackendUser]);

  // Memoized context value
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

/**
 * Clerk-enabled Auth Provider (requires ClerkProvider wrapper)
 * This component is only rendered when CLERK_ENABLED is true
 */
function ClerkAuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Clerk hooks - only called when this component is mounted (CLERK_ENABLED=true)
  const clerkAuth = useClerkAuth();
  const clerkUser = useClerkUser();

  // Get JWT token for API calls
  const getToken = useCallback(async (): Promise<string | null> => {
    if (clerkAuth.isSignedIn) {
      try {
        const token = await clerkAuth.getToken();
        return token;
      } catch (error) {
        console.error('[Auth] Failed to get Clerk token:', error);
      }
    }
    return null;
  }, [clerkAuth]);

  // Fetch user from backend (works with both auth methods)
  const fetchBackendUser = useCallback(async (token?: string | null): Promise<User | null> => {
    try {
      const headers: Record<string, string> = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await apiClient.get<User>('/auth/me', { headers });
      return response.data;
    } catch {
      console.debug('[Auth] Failed to fetch user from backend');
      return null;
    }
  }, []);

  // Refresh user data
  const refreshUser = useCallback(async () => {
    setIsLoading(true);
    try {
      // Try Clerk auth first
      if (clerkAuth.isSignedIn) {
        const token = await getToken();
        const backendUser = await fetchBackendUser(token);
        if (backendUser) {
          setUser(backendUser);
          setIsLoading(false);
          return;
        }
      }

      // Fall back to session auth (hybrid mode)
      if (AUTH_MODE === 'hybrid') {
        const backendUser = await fetchBackendUser();
        setUser(backendUser);
      } else {
        setUser(null);
      }
    } catch (error) {
      console.error('[Auth] Error refreshing user:', error);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, [clerkAuth.isSignedIn, getToken, fetchBackendUser]);

  // Traditional login (session-based) - only for hybrid mode
  const login = useCallback(async (email: string, password: string) => {
    if (AUTH_MODE === 'clerk') {
      throw new Error('Session login not available in Clerk-only mode');
    }

    const response = await apiClient.post<User>('/auth/login', { email, password });
    setUser(response.data);
  }, []);

  // Logout
  const logout = useCallback(async () => {
    try {
      // Logout from Clerk if signed in
      if (clerkAuth.isSignedIn) {
        await clerkAuth.signOut();
      }

      // Logout from session (hybrid mode)
      if (AUTH_MODE === 'hybrid') {
        await apiClient.post('/auth/logout');
      }
    } catch (error) {
      console.error('[Auth] Logout error:', error);
    } finally {
      setUser(null);
    }
  }, [clerkAuth]);

  // Effect: Handle Clerk auth state changes
  useEffect(() => {
    // Wait for Clerk to be ready
    if (clerkAuth.isLoaded === false) {
      return;
    }

    const syncClerkUser = async () => {
      if (clerkAuth.isSignedIn && clerkUser.isLoaded && clerkUser.user) {
        console.debug('[Auth] Clerk user signed in, syncing with backend');
        const token = await getToken();
        const backendUser = await fetchBackendUser(token);
        if (backendUser) {
          setUser(backendUser);
        }
      }
      setIsLoading(false);
    };

    syncClerkUser();
  }, [clerkAuth.isLoaded, clerkAuth.isSignedIn, clerkUser.isLoaded, clerkUser.user, getToken, fetchBackendUser]);

  // Effect: Check session on mount (for hybrid mode)
  useEffect(() => {
    if (AUTH_MODE !== 'hybrid') {
      return;
    }

    const checkSession = async () => {
      try {
        const backendUser = await fetchBackendUser();
        if (backendUser && !user) {
          setUser(backendUser);
        }
      } catch {
        // Session not valid
      }
    };

    checkSession();
  }, [fetchBackendUser]); // eslint-disable-line react-hooks/exhaustive-deps

  // Memoized context value
  const contextValue = useMemo<AuthContextType>(() => ({
    user,
    isLoading: isLoading || !clerkAuth.isLoaded,
    isAuthenticated: !!user,
    authMode: AUTH_MODE as 'clerk' | 'hybrid',
    clerkEnabled: true,
    login,
    logout,
    refreshUser,
    getToken,
  }), [user, isLoading, clerkAuth.isLoaded, login, logout, refreshUser, getToken]);

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}

/**
 * Unified AuthProvider - automatically selects the right provider based on environment
 */
export function AuthProvider({ children }: AuthProviderProps) {
  // Only mount ClerkAuthProvider when Clerk is configured
  // This prevents Clerk hooks from being called when Clerk is not set up
  if (CLERK_ENABLED) {
    return <ClerkAuthProvider>{children}</ClerkAuthProvider>;
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
