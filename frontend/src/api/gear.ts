import { apiClient } from './client';
import type { Gear, GearListResponse, GearStats, GearSummary } from '../types/api';

export interface GearParams {
  status?: 'active' | 'retired' | 'all';
  gear_type?: string;
}

export interface CreateGearData {
  name: string;
  brand?: string;
  model?: string;
  gear_type: string;
  purchase_date?: string;
  initial_distance_meters?: number;
  max_distance_meters?: number;
  notes?: string;
}

export interface UpdateGearData extends Partial<CreateGearData> {
  status?: 'active' | 'retired';
}

export const gearApi = {
  getList: async (params?: GearParams): Promise<GearListResponse> => {
    const { data } = await apiClient.get('/gear', { params });
    return data;
  },

  getDetail: async (id: number): Promise<Gear> => {
    const { data } = await apiClient.get(`/gear/${id}`);
    return data;
  },

  getStats: async (): Promise<GearStats> => {
    const { data } = await apiClient.get('/gear/stats');
    return data;
  },

  create: async (gearData: CreateGearData): Promise<Gear> => {
    const { data } = await apiClient.post('/gear', gearData);
    return data;
  },

  update: async (id: number, gearData: UpdateGearData): Promise<Gear> => {
    const { data } = await apiClient.patch(`/gear/${id}`, gearData);
    return data;
  },

  retire: async (id: number): Promise<Gear> => {
    const { data } = await apiClient.post(`/gear/${id}/retire`);
    return data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/gear/${id}`);
  },

  // 활동에 장비 연결
  linkToActivity: async (gearId: number, activityId: number): Promise<void> => {
    await apiClient.post(`/gear/${gearId}/activities/${activityId}`);
  },

  unlinkFromActivity: async (gearId: number, activityId: number): Promise<void> => {
    await apiClient.delete(`/gear/${gearId}/activities/${activityId}`);
  },

  // 활동에 연결된 장비 조회
  getActivityGear: async (activityId: number): Promise<GearSummary[]> => {
    const { data } = await apiClient.get(`/activities/${activityId}/gear`);
    // API returns { activity_id, gears: [...], total }
    return data.gears || [];
  },

  // Garmin에서 장비 동기화
  syncFromGarmin: async (): Promise<{ synced: number; updated: number }> => {
    const { data } = await apiClient.post('/gear/sync/garmin');
    return data;
  },
};
