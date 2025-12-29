import { apiClient } from './client';
import type {
  DashboardSummary,
  TrendsResponse,
  CompareResponse,
  PersonalRecordsResponse,
} from '../types/api';

export interface DashboardParams {
  target_date?: string;
  period?: 'week' | 'month';
}

export interface CompareParams {
  period?: 'week' | 'month';
  current_end?: string;
}

export const dashboardApi = {
  getSummary: async (params?: DashboardParams): Promise<DashboardSummary> => {
    const { data } = await apiClient.get('/dashboard/summary', { params });
    return data;
  },

  getTrends: async (weeks = 12): Promise<TrendsResponse> => {
    const { data } = await apiClient.get('/dashboard/trends', {
      params: { weeks },
    });
    return data;
  },

  compare: async (params?: CompareParams): Promise<CompareResponse> => {
    const { data } = await apiClient.get('/analytics/compare', { params });
    return data;
  },

  getPersonalRecords: async (
    activityType = 'running'
  ): Promise<PersonalRecordsResponse> => {
    const { data } = await apiClient.get('/analytics/personal-records', {
      params: { activity_type: activityType },
    });
    return data;
  },
};
