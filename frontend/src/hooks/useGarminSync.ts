import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { garminApi } from '../api/garmin';
import type { IngestRunRequest } from '../api/garmin';

// -------------------------------------------------------------------------
// Query Keys
// -------------------------------------------------------------------------

export const garminSyncKeys = {
  all: ['garmin-sync'] as const,
  status: () => [...garminSyncKeys.all, 'status'] as const,
  history: (params?: { endpoint?: string; page?: number }) =>
    [...garminSyncKeys.all, 'history', params] as const,
};

// -------------------------------------------------------------------------
// Hooks
// -------------------------------------------------------------------------

/**
 * Hook to get Garmin sync/ingest status (/ingest/status).
 * Polls every 3 seconds while sync is running, otherwise no auto-refetch.
 *
 * Note: This is different from useGarminStatus in useAuth.ts which uses /auth/garmin/status
 */
export function useGarminSyncStatus(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: garminSyncKeys.status(),
    queryFn: garminApi.getStatus,
    staleTime: 0, // Always fresh when refetched
    refetchInterval: (query) => {
      // Poll every 3 seconds while sync is running
      return query.state.data?.running ? 3000 : false;
    },
    ...options,
  });
}

/**
 * Hook to trigger Garmin sync.
 * Refreshes status and dashboard data after sync completes.
 */
export function useGarminSync() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request?: IngestRunRequest) => garminApi.runSync(request),
    onSettled: () => {
      // Refresh status and related data after sync request
      queryClient.invalidateQueries({ queryKey: garminSyncKeys.status() });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['activities'] });
    },
  });
}

/**
 * Hook to get sync history.
 */
export function useSyncHistory(params?: {
  endpoint?: string;
  page?: number;
  per_page?: number;
}) {
  return useQuery({
    queryKey: garminSyncKeys.history(params),
    queryFn: () => garminApi.getHistory(params),
    staleTime: 30_000, // 30 seconds
  });
}
