import { apiClient } from './client';
import type {
  StrengthSession,
  StrengthSessionListResponse,
  StrengthSessionSummary,
  SessionTypesResponse,
  ExercisePresetsResponse,
  ExerciseSet,
} from '../types/api';

export interface StrengthListParams {
  start_date?: string;
  end_date?: string;
  session_type?: string;
  limit?: number;
  offset?: number;
}

export interface ExerciseCreateData {
  exercise_name: string;
  is_custom?: boolean;
  sets: ExerciseSet[];
  notes?: string;
}

export interface StrengthSessionCreateData {
  session_date: string;
  session_type: string;
  session_purpose?: string;
  duration_minutes?: number;
  notes?: string;
  rating?: number;
  exercises: ExerciseCreateData[];
}

export interface StrengthSessionUpdateData {
  session_date?: string;
  session_type?: string;
  session_purpose?: string | null;
  duration_minutes?: number | null;
  notes?: string | null;
  rating?: number | null;
  exercises?: ExerciseCreateData[];
}

export const strengthApi = {
  // Session Types and Purposes
  getTypes: async (): Promise<SessionTypesResponse> => {
    const { data } = await apiClient.get('/strength/types');
    return data;
  },

  // Preset Exercises
  getExercisePresets: async (category?: string): Promise<ExercisePresetsResponse> => {
    const { data } = await apiClient.get('/strength/exercises/presets', {
      params: category ? { category } : undefined,
    });
    return data;
  },

  // List Sessions
  getList: async (params?: StrengthListParams): Promise<StrengthSessionListResponse> => {
    const { data } = await apiClient.get('/strength', { params });
    return data;
  },

  // Get Session Detail
  getDetail: async (id: number): Promise<StrengthSession> => {
    const { data } = await apiClient.get(`/strength/${id}`);
    return data;
  },

  // Create Session
  create: async (sessionData: StrengthSessionCreateData): Promise<StrengthSession> => {
    const { data } = await apiClient.post('/strength', sessionData);
    return data;
  },

  // Update Session
  update: async (id: number, sessionData: StrengthSessionUpdateData): Promise<StrengthSession> => {
    const { data } = await apiClient.patch(`/strength/${id}`, sessionData);
    return data;
  },

  // Delete Session
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/strength/${id}`);
  },

  // Calendar View (get sessions for a specific month)
  getCalendarSessions: async (year: number, month: number): Promise<StrengthSessionSummary[]> => {
    const { data } = await apiClient.get(`/strength/calendar/${year}/${month}`);
    return data;
  },

  // Add Exercise to Session
  addExercise: async (sessionId: number, exercise: ExerciseCreateData): Promise<void> => {
    await apiClient.post(`/strength/${sessionId}/exercises`, exercise);
  },

  // Remove Exercise from Session
  removeExercise: async (sessionId: number, exerciseId: number): Promise<void> => {
    await apiClient.delete(`/strength/${sessionId}/exercises/${exerciseId}`);
  },
};
