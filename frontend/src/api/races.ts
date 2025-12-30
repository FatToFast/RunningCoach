import { apiClient } from './client';

export interface Race {
  id: number;
  name: string;
  race_date: string;
  distance_km: number | null;
  distance_label: string | null;
  location: string | null;
  goal_time_seconds: number | null;
  goal_description: string | null;
  is_primary: boolean;
  is_completed: boolean;
  result_time_seconds: number | null;
  result_notes: string | null;
  days_until: number;
}

export interface RaceCreate {
  name: string;
  race_date: string;
  distance_km?: number | null;
  distance_label?: string | null;
  location?: string | null;
  goal_time_seconds?: number | null;
  goal_description?: string | null;
  is_primary?: boolean;
}

export interface RaceUpdate {
  name?: string;
  race_date?: string;
  distance_km?: number | null;
  distance_label?: string | null;
  location?: string | null;
  goal_time_seconds?: number | null;
  goal_description?: string | null;
  is_primary?: boolean;
  is_completed?: boolean;
  result_time_seconds?: number | null;
  result_notes?: string | null;
}

export interface RacesListResponse {
  races: Race[];
  primary_race: Race | null;
}

export interface GarminRacePrediction {
  distance: string; // "5K", "10K", "Half Marathon", "Marathon"
  distance_km: number;
  predicted_time_seconds: number;
  predicted_time_formatted: string;
  pace_per_km: string;
}

export interface GarminRacePredictionsResponse {
  predictions: GarminRacePrediction[];
  vo2_max: number | null;
  last_updated: string | null;
}

export interface GarminRaceImport {
  distance: string;
  race_date: string;
  name: string;
  location?: string | null;
  is_primary?: boolean;
}

export const racesApi = {
  // Get all races
  getRaces: async (includeCompleted = false): Promise<RacesListResponse> => {
    const { data } = await apiClient.get('/races', {
      params: { include_completed: includeCompleted },
    });
    return data;
  },

  // Get upcoming race for D-day display
  getUpcomingRace: async (): Promise<Race | null> => {
    const { data } = await apiClient.get('/races/upcoming');
    return data;
  },

  // Get single race
  getRace: async (raceId: number): Promise<Race> => {
    const { data } = await apiClient.get(`/races/${raceId}`);
    return data;
  },

  // Create race
  createRace: async (race: RaceCreate): Promise<Race> => {
    const { data } = await apiClient.post('/races', race);
    return data;
  },

  // Update race
  updateRace: async (raceId: number, race: RaceUpdate): Promise<Race> => {
    const { data } = await apiClient.patch(`/races/${raceId}`, race);
    return data;
  },

  // Delete race
  deleteRace: async (raceId: number): Promise<void> => {
    await apiClient.delete(`/races/${raceId}`);
  },

  // Set primary race
  setPrimaryRace: async (raceId: number): Promise<Race> => {
    const { data } = await apiClient.post(`/races/${raceId}/set-primary`);
    return data;
  },

  // Get Garmin race predictions (VO2Max based)
  getGarminPredictions: async (): Promise<GarminRacePredictionsResponse> => {
    const { data } = await apiClient.get('/races/garmin/predictions');
    return data;
  },

  // Import race from Garmin with predicted goal time
  importFromGarmin: async (raceData: GarminRaceImport): Promise<Race> => {
    const { data } = await apiClient.post('/races/garmin/import', null, {
      params: raceData,
    });
    return data;
  },
};
