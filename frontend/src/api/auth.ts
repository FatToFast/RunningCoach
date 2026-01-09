import { apiClient } from './client';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface User {
  id: number;
  email: string;
  display_name: string | null;
  timezone: string;
  last_login_at?: string | null;
}

export interface GarminSyncInfo {
  connected: boolean;
  session_valid: boolean;
  last_sync: string | null;
  needs_sync: boolean;
}

export interface LoginResponse {
  success: boolean;
  user: User;
  message: string;
  garmin: GarminSyncInfo | null;
}

export interface GarminConnectRequest {
  email: string;
  password: string;
}

export interface GarminStatus {
  connected: boolean;
  session_valid: boolean;
  last_login: string | null;
  last_sync: string | null;
}

// Response types matching backend Pydantic models
export interface GarminConnectResponse {
  connected: boolean;
  message: string;
  last_login: string | null;
}

export interface GarminRefreshResponse {
  success: boolean;
  message: string;
}

export interface GarminDisconnectResponse {
  success: boolean;
  message: string;
}

export const authApi = {
  login: async (credentials: LoginRequest): Promise<LoginResponse> => {
    const { data } = await apiClient.post('/auth/login', credentials);
    return data;
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/auth/logout');
  },

  getMe: async (): Promise<User> => {
    const { data } = await apiClient.get('/auth/me');
    return data;
  },

  // Garmin
  connectGarmin: async (credentials: GarminConnectRequest): Promise<GarminConnectResponse> => {
    const { data } = await apiClient.post('/auth/garmin/connect', credentials);
    return data;
  },

  getGarminStatus: async (): Promise<GarminStatus> => {
    const { data } = await apiClient.get('/auth/garmin/status');
    return data;
  },

  refreshGarmin: async (): Promise<GarminRefreshResponse> => {
    const { data } = await apiClient.post('/auth/garmin/refresh');
    return data;
  },

  disconnectGarmin: async (): Promise<GarminDisconnectResponse> => {
    const { data } = await apiClient.delete('/auth/garmin/disconnect');
    return data;
  },
};
