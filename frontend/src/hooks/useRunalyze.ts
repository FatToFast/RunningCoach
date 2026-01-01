import { useQuery } from '@tanstack/react-query';
import { runalyzeApi, type RunalyzeDataParams } from '../api/runalyze';
import type {
  RunalyzeConnectionStatus,
  RunalyzeHRVResponse,
  RunalyzeSleepResponse,
  RunalyzeSummary,
  RunalyzeCalculations,
  RunalyzeTrainingPaces,
} from '../types/api';

// Use environment variable for mock data (default: false in production)
const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === 'true';

// -------------------------------------------------------------------------
// Mock Data (for development/testing only)
// -------------------------------------------------------------------------

const mockStatus: RunalyzeConnectionStatus = {
  connected: true,
  message: 'Runalyze 연결됨',
};

const mockHRVResponse: RunalyzeHRVResponse = {
  data: [
    { id: 1, date_time: '2024-12-29T06:30:00Z', hrv: 52, rmssd: 52.3, metric: 'rmssd', measurement_type: 'sleep' },
    { id: 2, date_time: '2024-12-28T06:15:00Z', hrv: 48, rmssd: 48.1, metric: 'rmssd', measurement_type: 'sleep' },
    { id: 3, date_time: '2024-12-27T06:45:00Z', hrv: 55, rmssd: 55.2, metric: 'rmssd', measurement_type: 'sleep' },
    { id: 4, date_time: '2024-12-26T06:20:00Z', hrv: 51, rmssd: 51.0, metric: 'rmssd', measurement_type: 'sleep' },
    { id: 5, date_time: '2024-12-25T06:30:00Z', hrv: 49, rmssd: 49.5, metric: 'rmssd', measurement_type: 'sleep' },
    { id: 6, date_time: '2024-12-24T06:10:00Z', hrv: 53, rmssd: 53.8, metric: 'rmssd', measurement_type: 'sleep' },
    { id: 7, date_time: '2024-12-23T06:35:00Z', hrv: 50, rmssd: 50.2, metric: 'rmssd', measurement_type: 'sleep' },
  ],
  count: 7,
};

const mockSleepResponse: RunalyzeSleepResponse = {
  data: [
    { id: 1, date_time: '2024-12-29T06:30:00Z', duration: 450, rem_duration: 90, light_sleep_duration: 210, deep_sleep_duration: 120, awake_duration: 30, quality: 8, source: 'garmin' },
    { id: 2, date_time: '2024-12-28T06:15:00Z', duration: 420, rem_duration: 80, light_sleep_duration: 200, deep_sleep_duration: 110, awake_duration: 30, quality: 7, source: 'garmin' },
    { id: 3, date_time: '2024-12-27T06:45:00Z', duration: 480, rem_duration: 100, light_sleep_duration: 220, deep_sleep_duration: 130, awake_duration: 30, quality: 9, source: 'garmin' },
    { id: 4, date_time: '2024-12-26T06:20:00Z', duration: 390, rem_duration: 70, light_sleep_duration: 190, deep_sleep_duration: 100, awake_duration: 30, quality: 6, source: 'garmin' },
    { id: 5, date_time: '2024-12-25T06:30:00Z', duration: 435, rem_duration: 85, light_sleep_duration: 205, deep_sleep_duration: 115, awake_duration: 30, quality: 7, source: 'garmin' },
    { id: 6, date_time: '2024-12-24T06:10:00Z', duration: 465, rem_duration: 95, light_sleep_duration: 215, deep_sleep_duration: 125, awake_duration: 30, quality: 8, source: 'garmin' },
    { id: 7, date_time: '2024-12-23T06:35:00Z', duration: 405, rem_duration: 75, light_sleep_duration: 195, deep_sleep_duration: 105, awake_duration: 30, quality: 7, source: 'garmin' },
  ],
  count: 7,
};

const mockSummary: RunalyzeSummary = {
  latest_hrv: 52,
  latest_hrv_date: '2024-12-29T06:30:00Z',
  avg_hrv_7d: 51.1,
  latest_sleep_quality: 8,
  latest_sleep_duration: 450,
  latest_sleep_date: '2024-12-29T06:30:00Z',
  avg_sleep_quality_7d: 7.4,
  hrv_error: null,
  sleep_error: null,
};

const mockCalculations: RunalyzeCalculations = {
  effective_vo2max: 52.5,
  marathon_shape: 78.5,
  atl: 45.2,
  ctl: 62.8,
  tsb: 17.6,
  workload_ratio: 0.72,
  rest_days: 2,
  monotony: 1.2,
  training_strain: 285,
};

const mockTrainingPaces: RunalyzeTrainingPaces = {
  vdot: 52,
  easy_min: 330, // 5:30/km
  easy_max: 360, // 6:00/km
  marathon_min: 285, // 4:45/km
  marathon_max: 300, // 5:00/km
  threshold_min: 255, // 4:15/km
  threshold_max: 270, // 4:30/km
  interval_min: 225, // 3:45/km
  interval_max: 240, // 4:00/km
  repetition_min: 195, // 3:15/km
  repetition_max: 210, // 3:30/km
};

// -------------------------------------------------------------------------
// Hooks
// -------------------------------------------------------------------------

/**
 * Hook to check Runalyze connection status.
 */
export function useRunalyzeStatus() {
  return useQuery({
    queryKey: ['runalyze', 'status'],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 200));
        return mockStatus;
      }
      return runalyzeApi.getStatus();
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 1,
  });
}

/**
 * Hook to fetch HRV data from Runalyze.
 * Only fetches when Runalyze is connected.
 * @param params.limit - Maximum number of records (default: 30)
 */
export function useRunalyzeHRV(params?: RunalyzeDataParams) {
  const { data: status } = useRunalyzeStatus();
  const isConnected = status?.connected ?? false;

  return useQuery({
    queryKey: ['runalyze', 'hrv', params?.limit],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 300));
        return mockHRVResponse;
      }
      return runalyzeApi.getHRV(params);
    },
    staleTime: 1000 * 60 * 15, // 15 minutes
    enabled: USE_MOCK_DATA || isConnected, // Only fetch when connected
  });
}

/**
 * Hook to fetch sleep data from Runalyze.
 * Only fetches when Runalyze is connected.
 * @param params.limit - Maximum number of records (default: 30)
 */
export function useRunalyzeSleep(params?: RunalyzeDataParams) {
  const { data: status } = useRunalyzeStatus();
  const isConnected = status?.connected ?? false;

  return useQuery({
    queryKey: ['runalyze', 'sleep', params?.limit],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 300));
        return mockSleepResponse;
      }
      return runalyzeApi.getSleep(params);
    },
    staleTime: 1000 * 60 * 15, // 15 minutes
    enabled: USE_MOCK_DATA || isConnected, // Only fetch when connected
  });
}

/**
 * Hook to fetch combined health metrics summary from Runalyze.
 * Only fetches when Runalyze is connected.
 * Most useful for dashboard display.
 */
export function useRunalyzeSummary() {
  const { data: status } = useRunalyzeStatus();
  const isConnected = status?.connected ?? false;

  return useQuery({
    queryKey: ['runalyze', 'summary'],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 250));
        return mockSummary;
      }
      return runalyzeApi.getSummary();
    },
    staleTime: 1000 * 60 * 10, // 10 minutes
    enabled: USE_MOCK_DATA || isConnected, // Only fetch when connected
  });
}

/**
 * Hook to fetch training calculations from Runalyze.
 * Only fetches when Runalyze is connected.
 * Includes VO2max, ATL, CTL, TSB, and other metrics.
 */
export function useRunalyzeCalculations() {
  const { data: status } = useRunalyzeStatus();
  const isConnected = status?.connected ?? false;

  return useQuery({
    queryKey: ['runalyze', 'calculations'],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 300));
        return mockCalculations;
      }
      return runalyzeApi.getCalculations();
    },
    staleTime: 1000 * 60 * 15, // 15 minutes
    enabled: USE_MOCK_DATA || isConnected, // Only fetch when connected
  });
}

/**
 * Hook to fetch Daniels-based training paces from Runalyze.
 * Only fetches when Runalyze is connected.
 * Returns paces in seconds per km for different training zones.
 */
export function useRunalyzeTrainingPaces() {
  const { data: status } = useRunalyzeStatus();
  const isConnected = status?.connected ?? false;

  return useQuery({
    queryKey: ['runalyze', 'training-paces'],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 300));
        return mockTrainingPaces;
      }
      return runalyzeApi.getTrainingPaces();
    },
    staleTime: 1000 * 60 * 30, // 30 minutes (paces don't change often)
    enabled: USE_MOCK_DATA || isConnected, // Only fetch when connected
  });
}
