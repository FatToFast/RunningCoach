import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { racesApi, type Race, type RaceCreate, type RaceUpdate, type GarminRaceImport } from '../api/races';

// Get all races
export function useRaces(includeCompleted = false) {
  return useQuery({
    queryKey: ['races', { includeCompleted }],
    queryFn: () => racesApi.getRaces(includeCompleted),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

// Get upcoming race for D-day display
export function useUpcomingRace() {
  return useQuery({
    queryKey: ['races', 'upcoming'],
    queryFn: () => racesApi.getUpcomingRace(),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

// Get single race
export function useRace(raceId: number | null) {
  return useQuery({
    queryKey: ['races', raceId],
    queryFn: () => (raceId ? racesApi.getRace(raceId) : null),
    enabled: !!raceId,
    staleTime: 1000 * 60 * 5,
  });
}

// Create race mutation
export function useCreateRace() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (race: RaceCreate) => racesApi.createRace(race),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['races'] });
    },
  });
}

// Update race mutation
export function useUpdateRace() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ raceId, race }: { raceId: number; race: RaceUpdate }) =>
      racesApi.updateRace(raceId, race),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['races'] });
    },
  });
}

// Delete race mutation
export function useDeleteRace() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (raceId: number) => racesApi.deleteRace(raceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['races'] });
    },
  });
}

// Set primary race mutation
export function useSetPrimaryRace() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (raceId: number) => racesApi.setPrimaryRace(raceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['races'] });
    },
  });
}

// Get Garmin race predictions (VO2Max based)
export function useGarminPredictions() {
  return useQuery({
    queryKey: ['races', 'garmin-predictions'],
    queryFn: () => racesApi.getGarminPredictions(),
    staleTime: 1000 * 60 * 30, // 30 minutes (predictions don't change often)
    retry: false, // Don't retry if Garmin not connected
  });
}

// Import race from Garmin mutation
export function useImportFromGarmin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (raceData: GarminRaceImport) => racesApi.importFromGarmin(raceData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['races'] });
    },
  });
}

// Garmin event type for import modal
export interface GarminEvent {
  name: string;
  event_date: string;
  event_type?: string;
  distance_km?: number | null;
  distance_label?: string | null;
  location?: string | null;
  notes?: string | null;
}

export interface GarminEventsResponse {
  events: GarminEvent[];
}

// Stub: Fetch Garmin events (not yet implemented on backend)
export function useGarminEvents(_startDate: string, _endDate: string) {
  return useQuery<GarminEventsResponse, Error>({
    queryKey: ['garmin-events', _startDate, _endDate],
    queryFn: async () => {
      // Backend API not yet implemented - return empty events
      return { events: [] };
    },
    enabled: false, // Disabled until backend is ready
  });
}

// Stub: Import multiple Garmin events (not yet implemented on backend)
export interface GarminEventsImportParams {
  startDate: string;
  endDate: string;
  filterRacesOnly: boolean;
  selectedEventDates: string[];
  selectedEventNames: string[];
}

export function useImportGarminEvents() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (_params: GarminEventsImportParams): Promise<Race[]> => {
      // Backend API not yet implemented - return empty array
      console.warn('Garmin events import not yet implemented');
      return [];
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['races'] });
    },
  });
}
