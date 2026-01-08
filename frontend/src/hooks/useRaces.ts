import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  racesApi,
  type RaceCreate,
  type RaceUpdate,
  type GarminRaceImport,
  type GarminEventsResponse,
} from '../api/races';

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
      // Also invalidate personal records as new race may affect records view
      queryClient.invalidateQueries({ queryKey: ['personal-records'] });
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
      // Also invalidate personal records as race times may be updated
      queryClient.invalidateQueries({ queryKey: ['personal-records'] });
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

// Get Garmin events from Event Dashboard
export function useGarminEvents(startDate: string, endDate: string) {
  return useQuery({
    queryKey: ['races', 'garmin-events', startDate, endDate],
    queryFn: () => racesApi.getGarminEvents(startDate, endDate),
    enabled: !!startDate && !!endDate,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

// Import Garmin events as races mutation
export function useImportGarminEvents() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: {
      startDate: string;
      endDate: string;
      selectedEventDates?: string[];
      selectedEventNames?: string[];
      filterRacesOnly?: boolean;
    }) => racesApi.importGarminEvents(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['races'] });
      queryClient.invalidateQueries({ queryKey: ['personal-records'] });
      queryClient.invalidateQueries({ queryKey: ['races', 'garmin-events'] });
    },
  });
}
