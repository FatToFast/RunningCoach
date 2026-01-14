/**
 * Clerk-specific AuthProvider
 *
 * This component is only imported when CLERK_ENABLED is true,
 * which means ClerkProvider is available in the component tree.
 */

import { useEffect, useState, useCallback, useMemo, type ReactNode } from 'react';
import { useAuth as useClerkAuth, useUser as useClerkUser } from '@clerk/clerk-react';
import { apiClient } from '../api/client';

// Auth mode from environment
const AUTH_MODE = import.meta.env.VITE_AUTH_MODE || 'session';

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
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  getToken: () => Promise<string | null>;
}


interface ClerkAuthProviderProps {
  children: ReactNode;
  AuthContext: React.Context<AuthContextType | undefined>;
}

// Fetch user from backend
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
 * Clerk AuthProvider - uses Clerk hooks (must be inside ClerkProvider)
 */
export function ClerkAuthProvider({ children, AuthContext }: ClerkAuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const clerkAuth = useClerkAuth();
  const clerkUser = useClerkUser();

  console.log('[Auth] ClerkAuthProvider state:', {
    isLoaded: clerkAuth.isLoaded,
    isSignedIn: clerkAuth.isSignedIn,
    userLoaded: clerkUser.isLoaded,
    hasUser: !!clerkUser.user
  });

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

  // Refresh user data
  const refreshUser = useCallback(async () => {
    setIsLoading(true);
    try {
      if (clerkAuth.isSignedIn) {
        const token = await clerkAuth.getToken();
        const backendUser = await fetchBackendUser(token);
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
  }, [clerkAuth]);

  // Traditional login (not available in Clerk mode)
  const login = useCallback(async () => {
    throw new Error('Session login not available in Clerk mode. Use Clerk sign-in.');
  }, []);

  // Logout
  const logout = useCallback(async () => {
    try {
      if (clerkAuth.isSignedIn) {
        await clerkAuth.signOut();
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
    if (!clerkAuth.isLoaded) {
      console.log('[Auth] Waiting for Clerk to load...');
      return;
    }

    const syncClerkUser = async () => {
      console.log('[Auth] syncClerkUser called:', {
        isSignedIn: clerkAuth.isSignedIn,
        userLoaded: clerkUser.isLoaded,
        hasUser: !!clerkUser.user
      });

      if (clerkAuth.isSignedIn && clerkUser.isLoaded && clerkUser.user) {
        console.log('[Auth] Clerk user signed in, syncing with backend');
        try {
          const token = await clerkAuth.getToken();
          console.log('[Auth] Got token:', !!token);
          const backendUser = await fetchBackendUser(token);
          console.log('[Auth] Backend user:', backendUser);
          setUser(backendUser);
        } catch (error) {
          console.error('[Auth] Failed to sync user:', error);
        }
      } else {
        console.log('[Auth] Clerk not signed in, clearing user');
        setUser(null);
      }
      setIsLoading(false);
    };

    syncClerkUser();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clerkAuth.isLoaded, clerkAuth.isSignedIn, clerkUser.isLoaded, clerkUser.user?.id]);

  // Memoized context value
  const contextValue = useMemo<AuthContextType>(() => ({
    user,
    isLoading: isLoading || !clerkAuth.isLoaded,
    isAuthenticated: !!user,
    authMode: AUTH_MODE as 'clerk' | 'session' | 'hybrid',
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
