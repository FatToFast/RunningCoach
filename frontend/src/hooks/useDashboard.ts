import { useQuery } from '@tanstack/react-query';
import { dashboardApi, type DashboardParams, type CompareParams, type CalendarParams } from '../api/dashboard';
import {
  mockDashboardSummary,
  mockCompareResponse,
  mockTrendsResponse,
  mockPersonalRecords,
  mockCalendarResponse,
} from '../api/mockData';

// Use mock data when VITE_USE_MOCK_DATA env var is 'true'
const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === 'true';

// Default extended fitness metrics (Runalyze-style)
const defaultExtendedFitness = {
  effective_vo2max: null,
  marathon_shape: null,
  workload_ratio: null,
  rest_days: null,
  monotony: null,
  training_strain: null,
};

// Default training paces (calculated from VO2max if available)
const defaultTrainingPaces = null;

export function useDashboardSummary(params?: DashboardParams) {
  return useQuery({
    queryKey: ['dashboard', 'summary', params],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        // Simulate network delay
        await new Promise((resolve) => setTimeout(resolve, 300));
        return mockDashboardSummary;
      }
      const data = await dashboardApi.getSummary(params);

      // Merge with default extended fields if not present from backend
      return {
        ...data,
        fitness_status: {
          ...defaultExtendedFitness,
          ...data.fitness_status,
        },
        training_paces: data.training_paces ?? defaultTrainingPaces,
      };
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

export function useCalendar(params: CalendarParams) {
  return useQuery({
    queryKey: ['dashboard', 'calendar', params],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 200));
        // Mock: 요청된 월에 맞게 날짜를 필터링
        const startDate = new Date(params.start_date);
        const endDate = new Date(params.end_date);

        const filteredDays = mockCalendarResponse.days.filter(day => {
          const d = new Date(day.date);
          return d >= startDate && d <= endDate;
        });

        return {
          ...mockCalendarResponse,
          start_date: params.start_date,
          end_date: params.end_date,
          days: filteredDays,
        };
      }
      return dashboardApi.getCalendar(params);
    },
    staleTime: 1000 * 60 * 5,
  });
}
