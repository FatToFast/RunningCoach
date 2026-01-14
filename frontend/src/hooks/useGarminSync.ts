import { useEffect, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { garminApi } from '../api/garmin';
import type { IngestRunRequest, IngestStatusResponse } from '../api/garmin';

// -------------------------------------------------------------------------
// Constants
// -------------------------------------------------------------------------

const MAX_POLL_TIME_MS = 5 * 60 * 1000; // 5분 타임아웃
const POLL_INTERVAL_MS = 3000; // 3초마다 폴링

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

export interface SyncStatusCallbacks {
  onSyncComplete?: () => void;
  onSyncError?: (error: string) => void;
  onSyncTimeout?: () => void;
}

/**
 * Hook to get Garmin sync/ingest status (/ingest/status).
 * Polls every 3 seconds while sync is running, with 5-minute timeout.
 *
 * Note: This is different from useGarminStatus in useAuth.ts which uses /auth/garmin/status
 */
export function useGarminSyncStatus(
  options?: { enabled?: boolean },
  callbacks?: SyncStatusCallbacks
) {
  const pollStartTime = useRef<number | null>(null);
  const wasRunning = useRef<boolean>(false);
  const callbacksRef = useRef(callbacks);
  callbacksRef.current = callbacks;

  const query = useQuery({
    queryKey: garminSyncKeys.status(),
    queryFn: garminApi.getStatus,
    staleTime: 0, // Always fresh when refetched
    refetchInterval: (q) => {
      const data = q.state.data as IngestStatusResponse | undefined;
      if (!data?.running) {
        // 동기화 완료 또는 미실행
        if (wasRunning.current && pollStartTime.current) {
          // 동기화가 완료됨
          wasRunning.current = false;
          pollStartTime.current = null;
          // 에러 체크 후 콜백
          if (data?.last_error) {
            callbacksRef.current?.onSyncError?.(data.last_error);
          } else {
            callbacksRef.current?.onSyncComplete?.();
          }
        }
        return false;
      }

      // 동기화 진행 중
      if (!wasRunning.current) {
        wasRunning.current = true;
        pollStartTime.current = Date.now();
      }

      // 타임아웃 체크
      const elapsed = Date.now() - (pollStartTime.current || Date.now());
      if (elapsed > MAX_POLL_TIME_MS) {
        // 타임아웃 - 폴링 중단
        wasRunning.current = false;
        pollStartTime.current = null;
        callbacksRef.current?.onSyncTimeout?.();
        return false;
      }

      return POLL_INTERVAL_MS;
    },
    ...options,
  });

  // 폴링 시작 시간 리셋 (쿼리가 비활성화될 때)
  useEffect(() => {
    if (!options?.enabled) {
      pollStartTime.current = null;
      wasRunning.current = false;
    }
  }, [options?.enabled]);

  return query;
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
