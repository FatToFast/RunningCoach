import { apiClient } from './client';
import type {
  DashboardSummary,
  TrendsResponse,
  CompareResponse,
  PersonalRecordsResponse,
  CalendarResponse,
} from '../types/api';

export interface DashboardParams {
  target_date?: string;
  period?: 'week' | 'month';
}

export interface CompareParams {
  period?: 'week' | 'month';
  current_end?: string;
}

export interface CalendarParams {
  start_date: string; // YYYY-MM-DD
  end_date: string; // YYYY-MM-DD
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

  /**
   * Get calendar view with activities and scheduled workouts.
   */
  getCalendar: async (params: CalendarParams): Promise<CalendarResponse> => {
    const { data } = await apiClient.get('/dashboard/calendar', { params });
    return data;
  },
};
