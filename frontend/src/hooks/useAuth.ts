import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { authApi } from '../api/auth';
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
    onSuccess: (data) => {
      queryClient.setQueryData(['user'], data.user);
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
