/**
 * API Client with hybrid authentication support
 *
 * Supports both:
 * - Clerk JWT tokens (Bearer auth)
 * - Session cookies (withCredentials)
 */

import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === 'true';
const AUTH_MODE = import.meta.env.VITE_AUTH_MODE || 'session';

// Token getter function - set by AuthProvider
let tokenGetter: (() => Promise<string | null>) | null = null;

/**
 * Set the token getter function (called by AuthProvider)
 */
export function setTokenGetter(getter: () => Promise<string | null>) {
  tokenGetter = getter;
}

/**
 * Create Axios client with interceptors
 */
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true, // Always send cookies (for session auth)
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second timeout
});

/**
 * Request interceptor - adds JWT token if available
 */
apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    // Skip token for mock mode
    if (USE_MOCK_DATA) {
      return config;
    }

    // Add Bearer token if available (Clerk or hybrid mode)
    if (AUTH_MODE !== 'session' && tokenGetter) {
      try {
        const token = await tokenGetter();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      } catch (error) {
        console.debug('[API] Failed to get auth token:', error);
      }
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Response interceptor - handles auth errors
 */
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Skip redirect in mock mode
    if (USE_MOCK_DATA) {
      return Promise.reject(error);
    }

    const status = error.response?.status;
    const url = error.config?.url || '';

    // Handle 401 Unauthorized
    if (status === 401) {
      // Don't redirect for these endpoints
      const skipRedirectPaths = [
        '/garmin/',
        '/auth/login',
        '/strava/',
        '/webhooks/',
      ];

      const shouldSkipRedirect = skipRedirectPaths.some(path => url.includes(path));

      if (!shouldSkipRedirect) {
        // In Clerk mode, don't redirect - let Clerk handle it
        if (AUTH_MODE === 'clerk') {
          console.debug('[API] 401 in Clerk mode - not redirecting');
        } else {
          // Session mode - redirect to login
          console.debug('[API] 401 - redirecting to login');
          window.location.href = '/login';
        }
      }
    }

    // Log error details for debugging
    if (import.meta.env.DEV) {
      console.error('[API Error]', {
        url,
        status,
        message: error.message,
        response: error.response?.data,
      });
    }

    return Promise.reject(error);
  }
);

/**
 * Helper to check if API is reachable
 */
export async function checkApiHealth(): Promise<boolean> {
  try {
    await apiClient.get('/health', { timeout: 5000 });
    return true;
  } catch {
    return false;
  }
}

/**
 * Export base URL for debugging
 */
export const getApiBaseUrl = () => API_BASE_URL;
