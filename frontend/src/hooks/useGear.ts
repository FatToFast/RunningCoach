import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { gearApi, type GearParams, type CreateGearData, type UpdateGearData } from '../api/gear';
import type { Gear, GearListResponse, GearStats } from '../types/api';

// Mock 데이터 사용 여부
const USE_MOCK_DATA = true;

// Mock 데이터
const mockGearList: GearListResponse = {
  items: [
    {
      id: 1,
      name: 'Nike Vaporfly 3',
      brand: 'Nike',
      gear_type: 'running_shoes',
      status: 'active',
      total_distance_meters: 245000,
      max_distance_meters: 500000,
      activity_count: 32,
      usage_percentage: 49,
    },
    {
      id: 2,
      name: 'ASICS Gel-Kayano 30',
      brand: 'ASICS',
      gear_type: 'running_shoes',
      status: 'active',
      total_distance_meters: 680000,
      max_distance_meters: 800000,
      activity_count: 85,
      usage_percentage: 85,
    },
    {
      id: 3,
      name: 'Nike Pegasus 40',
      brand: 'Nike',
      gear_type: 'running_shoes',
      status: 'active',
      total_distance_meters: 120000,
      max_distance_meters: 800000,
      activity_count: 18,
      usage_percentage: 15,
    },
    {
      id: 4,
      name: 'Hoka Clifton 9',
      brand: 'Hoka',
      gear_type: 'running_shoes',
      status: 'retired',
      total_distance_meters: 820000,
      max_distance_meters: 800000,
      activity_count: 105,
      usage_percentage: 102,
    },
  ],
  total: 4,
};

const mockGearDetail: Gear = {
  id: 1,
  garmin_uuid: 'abc-123-def',
  name: 'Nike Vaporfly 3',
  brand: 'Nike',
  model: 'Vaporfly 3',
  gear_type: 'running_shoes',
  status: 'active',
  purchase_date: '2024-06-15',
  initial_distance_meters: 0,
  total_distance_meters: 245000,
  max_distance_meters: 500000,
  activity_count: 32,
  notes: '레이스용 신발. 5K, 10K, 하프마라톤에 사용.',
  image_url: null,
  created_at: '2024-06-15T10:00:00Z',
  updated_at: '2024-12-29T08:00:00Z',
};

const mockGearStats: GearStats = {
  total_gears: 4,
  active_gears: 3,
  retired_gears: 1,
  gears_near_retirement: [
    {
      id: 2,
      name: 'ASICS Gel-Kayano 30',
      brand: 'ASICS',
      gear_type: 'running_shoes',
      status: 'active',
      total_distance_meters: 680000,
      max_distance_meters: 800000,
      activity_count: 85,
      usage_percentage: 85,
    },
  ],
};

export function useGearList(params?: GearParams) {
  return useQuery({
    queryKey: ['gear', 'list', params],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 200));

        let items = [...mockGearList.items];

        // Filter by status
        if (params?.status && params.status !== 'all') {
          items = items.filter((item) => item.status === params.status);
        }

        // Filter by gear type
        if (params?.gear_type) {
          items = items.filter((item) => item.gear_type === params.gear_type);
        }

        return { items, total: items.length };
      }
      return gearApi.getList(params);
    },
    staleTime: 1000 * 60 * 5,
  });
}

export function useGearDetail(id: number) {
  return useQuery({
    queryKey: ['gear', 'detail', id],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 200));
        return { ...mockGearDetail, id };
      }
      return gearApi.getDetail(id);
    },
    staleTime: 1000 * 60 * 10,
    enabled: !!id,
  });
}

export function useGearStats() {
  return useQuery({
    queryKey: ['gear', 'stats'],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 150));
        return mockGearStats;
      }
      return gearApi.getStats();
    },
    staleTime: 1000 * 60 * 5,
  });
}

export function useActivityGear(activityId: number) {
  return useQuery({
    queryKey: ['activities', activityId, 'gear'],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 100));
        // 활동 1에 Nike Vaporfly 3 연결
        if (activityId === 1) {
          return [mockGearList.items[0]];
        }
        return [];
      }
      return gearApi.getActivityGear(activityId);
    },
    staleTime: 1000 * 60 * 10,
    enabled: !!activityId,
  });
}

export function useCreateGear() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateGearData) => gearApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gear'] });
    },
  });
}

export function useUpdateGear() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateGearData }) => gearApi.update(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['gear'] });
      queryClient.invalidateQueries({ queryKey: ['gear', 'detail', id] });
    },
  });
}

export function useRetireGear() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => gearApi.retire(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gear'] });
    },
  });
}

export function useDeleteGear() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => gearApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gear'] });
    },
  });
}

export function useSyncGearFromGarmin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => gearApi.syncFromGarmin(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gear'] });
    },
  });
}

// 유틸리티 함수
export function getGearTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    running_shoes: '러닝화',
    cycling_shoes: '사이클화',
    bike: '자전거',
    other: '기타',
  };
  return labels[type] || type;
}

export function getGearStatusLabel(status: string): string {
  return status === 'active' ? '사용 중' : '은퇴';
}

export function getUsageColor(percentage: number | null): string {
  if (percentage === null) return 'text-muted';
  if (percentage >= 100) return 'text-red-400';
  if (percentage >= 80) return 'text-amber';
  if (percentage >= 50) return 'text-yellow-400';
  return 'text-green-400';
}

export function getUsageBarColor(percentage: number | null): string {
  if (percentage === null) return 'bg-gray-500';
  if (percentage >= 100) return 'bg-red-500';
  if (percentage >= 80) return 'bg-amber';
  if (percentage >= 50) return 'bg-yellow-500';
  return 'bg-green-500';
}
