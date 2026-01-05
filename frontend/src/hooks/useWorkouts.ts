import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  workoutsApi,
  type WorkoutListParams,
  type ScheduleListParams,
  type WorkoutUpdateData,
  type ScheduleStatusUpdate,
} from '../api/workouts';
import type { WorkoutCreate, ScheduleCreate } from '../types/api';

// -------------------------------------------------------------------------
// Query Hooks
// -------------------------------------------------------------------------

export function useWorkouts(params?: WorkoutListParams) {
  return useQuery({
    queryKey: ['workouts', 'list', params],
    queryFn: () => workoutsApi.getList(params),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

export function useWorkout(id: number) {
  return useQuery({
    queryKey: ['workouts', 'detail', id],
    queryFn: () => workoutsApi.getDetail(id),
    staleTime: 1000 * 60 * 10, // 10 minutes
    enabled: !!id,
  });
}

export function useSchedules(params?: ScheduleListParams) {
  return useQuery({
    queryKey: ['workouts', 'schedules', params],
    queryFn: () => workoutsApi.getSchedules(params),
    staleTime: 1000 * 60 * 5,
  });
}

// -------------------------------------------------------------------------
// Mutation Hooks
// -------------------------------------------------------------------------

export function useCreateWorkout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: WorkoutCreate) => workoutsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workouts'] });
    },
  });
}

export function useUpdateWorkout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: WorkoutUpdateData }) =>
      workoutsApi.update(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['workouts'] });
      queryClient.invalidateQueries({ queryKey: ['workouts', 'detail', id] });
    },
  });
}

export function useDeleteWorkout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => workoutsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workouts'] });
    },
  });
}

export function usePushToGarmin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => workoutsApi.pushToGarmin(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['workouts', 'detail', id] });
      queryClient.invalidateQueries({ queryKey: ['workouts', 'list'] });
    },
  });
}

export function useCreateSchedule() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ScheduleCreate) => workoutsApi.createSchedule(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workouts', 'schedules'] });
    },
  });
}

export function useUpdateScheduleStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, update }: { id: number; update: ScheduleStatusUpdate }) =>
      workoutsApi.updateScheduleStatus(id, update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workouts', 'schedules'] });
    },
  });
}

export function useDeleteSchedule() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => workoutsApi.deleteSchedule(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workouts', 'schedules'] });
    },
  });
}

// -------------------------------------------------------------------------
// Garmin Import Hooks
// -------------------------------------------------------------------------

export function useGarminWorkouts(limit?: number) {
  return useQuery({
    queryKey: ['workouts', 'garmin', limit],
    queryFn: () => workoutsApi.getGarminWorkouts(limit),
    staleTime: 1000 * 60 * 2, // 2 minutes
    enabled: false, // Manual fetch only
  });
}

export function useImportGarminWorkouts() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (garminWorkoutIds: number[]) => workoutsApi.importGarminWorkouts(garminWorkoutIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workouts'] });
    },
  });
}

// -------------------------------------------------------------------------
// Utility Functions
// -------------------------------------------------------------------------

export function getWorkoutTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    easy: '이지런',
    long: '장거리',
    tempo: '템포런',
    interval: '인터벌',
    hills: '언덕훈련',
    fartlek: '파틀렉',
    recovery: '회복런',
  };
  return labels[type] || type;
}

export function getWorkoutTypeColor(type: string): string {
  const colors: Record<string, string> = {
    easy: 'bg-green-500',
    long: 'bg-blue-500',
    tempo: 'bg-orange-500',
    interval: 'bg-red-500',
    hills: 'bg-amber-600',
    fartlek: 'bg-purple-500',
    recovery: 'bg-cyan-500',
  };
  return colors[type] || 'bg-gray-500';
}

export function getWorkoutTypeIcon(type: string): string {
  const icons: Record<string, string> = {
    easy: '🏃',
    long: '🛤️',
    tempo: '⏱️',
    interval: '🔥',
    hills: '⛰️',
    fartlek: '🎲',
    recovery: '🧘',
  };
  return icons[type] || '🏃';
}

export function getScheduleStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    scheduled: '예정됨',
    completed: '완료',
    skipped: '건너뜀',
    cancelled: '취소됨',
  };
  return labels[status] || status;
}

export function getScheduleStatusColor(status: string): string {
  const colors: Record<string, string> = {
    scheduled: 'text-cyan bg-cyan/10',
    completed: 'text-green-400 bg-green-500/10',
    skipped: 'text-amber bg-amber/10',
    cancelled: 'text-muted bg-muted/10',
  };
  return colors[status] || 'text-muted bg-muted/10';
}

export function getStepTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    warmup: '웜업',
    main: '메인',
    cooldown: '쿨다운',
    rest: '휴식',
    recovery: '회복',
  };
  return labels[type] || type;
}
