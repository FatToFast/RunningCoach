import { apiClient } from './client';
import type {
  RunalyzeConnectionStatus,
  RunalyzeHRVResponse,
  RunalyzeSleepResponse,
  RunalyzeSummary,
} from '../types/api';

export interface RunalyzeDataParams {
  limit?: number;
}

export const runalyzeApi = {
  /**
   * Check Runalyze connection status.
   */
  getStatus: async (): Promise<RunalyzeConnectionStatus> => {
    const { data } = await apiClient.get('/runalyze/status');
    return data;
  },

  /**
   * Get HRV (Heart Rate Variability) data from Runalyze.
   * @param limit - Maximum number of records to return (default: 30)
   */
  getHRV: async (params?: RunalyzeDataParams): Promise<RunalyzeHRVResponse> => {
    const { data } = await apiClient.get('/runalyze/hrv', {
      params: { limit: params?.limit ?? 30 },
    });
    return data;
  },

  /**
   * Get sleep data from Runalyze.
   * @param limit - Maximum number of records to return (default: 30)
   */
  getSleep: async (params?: RunalyzeDataParams): Promise<RunalyzeSleepResponse> => {
    const { data } = await apiClient.get('/runalyze/sleep', {
      params: { limit: params?.limit ?? 30 },
    });
    return data;
  },

  /**
   * Get combined health metrics summary from Runalyze.
   * Includes latest HRV, sleep quality, and 7-day averages.
   */
  getSummary: async (): Promise<RunalyzeSummary> => {
    const { data } = await apiClient.get('/runalyze/summary');
    return data;
  },
};
