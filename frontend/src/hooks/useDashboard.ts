import { useQuery } from '@tanstack/react-query';
import { dashboardApi, type DashboardParams, type CompareParams } from '../api/dashboard';
import {
  mockDashboardSummary,
  mockCompareResponse,
  mockTrendsResponse,
  mockPersonalRecords,
} from '../api/mockData';

// Set to true to use mock data (when backend is not running)
const USE_MOCK_DATA = true;

export function useDashboardSummary(params?: DashboardParams) {
  return useQuery({
    queryKey: ['dashboard', 'summary', params],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        // Simulate network delay
        await new Promise((resolve) => setTimeout(resolve, 300));
        return mockDashboardSummary;
      }
      return dashboardApi.getSummary(params);
    },
    staleTime: 1000 * 60 * 5,
    refetchInterval: 1000 * 60 * 5,
  });
}

export function useTrends(weeks = 12) {
  return useQuery({
    queryKey: ['dashboard', 'trends', weeks],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 200));
        return mockTrendsResponse;
      }
      return dashboardApi.getTrends(weeks);
    },
    staleTime: 1000 * 60 * 30,
  });
}

export function useCompare(params?: CompareParams) {
  return useQuery({
    queryKey: ['analytics', 'compare', params],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 200));
        return mockCompareResponse;
      }
      return dashboardApi.compare(params);
    },
    staleTime: 1000 * 60 * 15,
  });
}

export function usePersonalRecords(activityType = 'running') {
  return useQuery({
    queryKey: ['analytics', 'personal-records', activityType],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 200));
        return mockPersonalRecords;
      }
      return dashboardApi.getPersonalRecords(activityType);
    },
    staleTime: 1000 * 60 * 60,
  });
}
