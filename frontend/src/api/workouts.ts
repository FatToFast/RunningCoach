import { apiClient } from './client';
import type {
  Workout,
  WorkoutListResponse,
  WorkoutSchedule,
  ScheduleListResponse,
  WorkoutCreate,
  ScheduleCreate,
  WorkoutStep,
  ScheduleStatus,
  GarminWorkoutsListResponse,
  GarminWorkoutImportResponse,
} from '../types/api';

export interface WorkoutListParams {
  page?: number;
  per_page?: number;
  workout_type?: string;
}

export interface ScheduleListParams {
  page?: number;
  per_page?: number;
  start_date?: string;
  end_date?: string;
  status?: ScheduleStatus;
}

export interface WorkoutUpdateData {
  name?: string;
  workout_type?: string;
  structure?: WorkoutStep[];
  target?: Record<string, unknown>;
  notes?: string;
}

export interface ScheduleStatusUpdate {
  status: ScheduleStatus;
  completed_activity_id?: number;
}

export const workoutsApi = {
  // List Workouts
  getList: async (params?: WorkoutListParams): Promise<WorkoutListResponse> => {
    const { data } = await apiClient.get('/workouts', { params });
    return data;
  },

  // Get Workout Detail
  getDetail: async (id: number): Promise<Workout> => {
    const { data } = await apiClient.get(`/workouts/${id}`);
    return data;
  },

  // Create Workout
  create: async (workoutData: WorkoutCreate): Promise<Workout> => {
    const { data } = await apiClient.post('/workouts', workoutData);
    return data;
  },

  // Update Workout
  update: async (id: number, workoutData: WorkoutUpdateData): Promise<Workout> => {
    const { data } = await apiClient.patch(`/workouts/${id}`, workoutData);
    return data;
  },

  // Delete Workout
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/workouts/${id}`);
  },

  // Push to Garmin
  pushToGarmin: async (id: number): Promise<{ success: boolean; garmin_workout_id: number | null; message: string }> => {
    const { data } = await apiClient.post(`/workouts/${id}/push`);
    return data;
  },

  // List Schedules
  getSchedules: async (params?: ScheduleListParams): Promise<ScheduleListResponse> => {
    const { data } = await apiClient.get('/workouts/schedules/list', { params });
    return data;
  },

  // Create Schedule
  createSchedule: async (scheduleData: ScheduleCreate): Promise<WorkoutSchedule> => {
    const { data } = await apiClient.post('/workouts/schedules', scheduleData);
    return data;
  },

  // Update Schedule Status
  updateScheduleStatus: async (id: number, update: ScheduleStatusUpdate): Promise<WorkoutSchedule> => {
    const { data } = await apiClient.patch(`/workouts/schedules/${id}/status`, update);
    return data;
  },

  // Delete Schedule
  deleteSchedule: async (id: number): Promise<void> => {
    await apiClient.delete(`/workouts/schedules/${id}`);
  },

  // Garmin Import
  getGarminWorkouts: async (limit?: number): Promise<GarminWorkoutsListResponse> => {
    const { data } = await apiClient.get('/workouts/garmin/list', { params: { limit } });
    return data;
  },

  importGarminWorkouts: async (garminWorkoutIds: number[]): Promise<GarminWorkoutImportResponse> => {
    const { data } = await apiClient.post('/workouts/garmin/import', {
      garmin_workout_ids: garminWorkoutIds,
    });
    return data;
  },

  // Refresh workout from Garmin
  refreshFromGarmin: async (id: number): Promise<{ success: boolean; message: string; workout: Workout | null }> => {
    const { data } = await apiClient.post(`/workouts/${id}/refresh-garmin`);
    return data;
  },
};
