import { apiClient } from './client';
import type {
  ActivityListResponse,
  ActivityDetail,
  ActivitySamplesResponse,
  HRZonesResponse,
  LapsResponse,
} from '../types/api';

export interface ActivitiesParams {
  page?: number;
  per_page?: number;
  activity_type?: string;
  start_date?: string;
  end_date?: string;
  sort_by?: 'start_time' | 'distance' | 'duration';
  sort_order?: 'asc' | 'desc';
}

export interface SamplesParams {
  limit?: number;
  offset?: number;
  downsample?: number;
  fields?: string; // 'hr,pace,cadence,power,gps,altitude'
}

export interface HRZonesParams {
  max_hr?: number; // User's max HR (100-250)
}

export interface LapsParams {
  split_distance?: number; // Distance per lap in meters (default: 1000)
}

export const activitiesApi = {
  getList: async (params?: ActivitiesParams): Promise<ActivityListResponse> => {
    const { data } = await apiClient.get('/activities', { params });
    return data;
  },

  getDetail: async (id: number): Promise<ActivityDetail> => {
    const { data } = await apiClient.get(`/activities/${id}`);
    return data;
  },

  getSamples: async (id: number, params?: SamplesParams): Promise<ActivitySamplesResponse> => {
    const { data } = await apiClient.get(`/activities/${id}/samples`, { params });
    return data;
  },

  /**
   * Get HR zone distribution for an activity.
   *
   * Zones are calculated based on percentage of max HR:
   * - Zone 1 (Recovery): 50-60%
   * - Zone 2 (Aerobic): 60-70%
   * - Zone 3 (Tempo): 70-80%
   * - Zone 4 (Threshold): 80-90%
   * - Zone 5 (VO2max): 90-100%
   */
  getHRZones: async (id: number, params?: HRZonesParams): Promise<HRZonesResponse> => {
    const { data } = await apiClient.get(`/activities/${id}/hr-zones`, { params });
    return data;
  },

  /**
   * Get lap/split data for an activity.
   *
   * Splits activity into laps based on distance (default: 1km).
   * For activities without GPS, uses time-based splits (5 min).
   */
  getLaps: async (id: number, params?: LapsParams): Promise<LapsResponse> => {
    const { data } = await apiClient.get(`/activities/${id}/laps`, { params });
    return data;
  },

  downloadFit: async (id: number): Promise<Blob> => {
    const response = await apiClient.get(`/activities/${id}/fit`, {
      responseType: 'blob',
    });
    return response.data;
  },

  getTypes: async (): Promise<string[]> => {
    const { data } = await apiClient.get('/activities/types/list');
    return data;
  },
};
