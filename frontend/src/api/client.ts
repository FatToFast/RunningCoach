import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true, // HTTP-only cookies
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || '';
      // Don't redirect for:
      // - Garmin auth errors (external auth failures)
      // - Login attempts (show error message instead)
      // - Strava auth errors
      if (url.includes('/garmin/') || url.includes('/auth/login') || url.includes('/strava/')) {
        return Promise.reject(error);
      }
      // Redirect to login on session expiry
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
