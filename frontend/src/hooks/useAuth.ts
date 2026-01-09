import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { authApi } from '../api/auth';
import { garminApi } from '../api/garmin';
import type { LoginRequest, User } from '../api/auth';
import { garminSyncKeys } from './useGarminSync';

export function useUser() {
  return useQuery<User, Error>({
    queryKey: ['user'],
    queryFn: authApi.getMe,
    retry: false,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useLogin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (credentials: LoginRequest) => authApi.login(credentials),
    onSuccess: async (data) => {
      queryClient.setQueryData(['user'], data.user);

      // Auto-sync if Garmin is connected and needs sync
      if (data.garmin?.needs_sync && data.garmin.session_valid) {
        try {
          // Calculate start_date: 7 days ago from today
          const endDate = new Date();
          const startDate = new Date();
          startDate.setDate(startDate.getDate() - 7);

          const formatDate = (d: Date) => d.toISOString().split('T')[0];

          console.log(
            `[Auto-sync] Starting auto-sync for last 7 days (${formatDate(startDate)} to ${formatDate(endDate)})`
          );

          await garminApi.runSync({
            start_date: formatDate(startDate),
            end_date: formatDate(endDate),
          });

          // Invalidate queries to refresh data after sync starts
          queryClient.invalidateQueries({ queryKey: garminSyncKeys.all });
          queryClient.invalidateQueries({ queryKey: ['dashboard'] });
          queryClient.invalidateQueries({ queryKey: ['activities'] });
        } catch (error) {
          console.error('[Auto-sync] Failed to start auto-sync:', error);
          // Don't throw - login succeeded, just sync failed
        }
      }
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ['user'] });
      queryClient.clear();
    },
  });
}

export function useGarminStatus() {
  return useQuery({
    queryKey: ['garmin-status'],
    queryFn: authApi.getGarminStatus,
    retry: false,
  });
}

export function useConnectGarmin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: authApi.connectGarmin,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['garmin-status'] });
      queryClient.invalidateQueries({ queryKey: garminSyncKeys.all });
    },
  });
}

export function useDisconnectGarmin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: authApi.disconnectGarmin,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['garmin-status'] });
      queryClient.invalidateQueries({ queryKey: garminSyncKeys.all });
    },
  });
}
