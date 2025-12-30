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
}

export interface LoginResponse {
  user: User;
  message: string;
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
  connectGarmin: async (credentials: GarminConnectRequest): Promise<{ message: string }> => {
    const { data } = await apiClient.post('/auth/garmin/connect', credentials);
    return data;
  },

  getGarminStatus: async (): Promise<GarminStatus> => {
    const { data } = await apiClient.get('/auth/garmin/status');
    return data;
  },

  refreshGarmin: async (): Promise<{ message: string }> => {
    const { data } = await apiClient.post('/auth/garmin/refresh');
    return data;
  },

  disconnectGarmin: async (): Promise<{ message: string }> => {
    const { data } = await apiClient.delete('/auth/garmin/disconnect');
    return data;
  },
};
