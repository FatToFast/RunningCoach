import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  strengthApi,
  type StrengthListParams,
  type StrengthSessionCreateData,
  type StrengthSessionUpdateData,
} from '../api/strength';

// -------------------------------------------------------------------------
// Query Hooks
// -------------------------------------------------------------------------

export function useSessionTypes() {
  return useQuery({
    queryKey: ['strength', 'types'],
    queryFn: () => strengthApi.getTypes(),
    staleTime: 1000 * 60 * 60, // 1 hour - types rarely change
  });
}

export function useExercisePresets(category?: string) {
  return useQuery({
    queryKey: ['strength', 'presets', category],
    queryFn: () => strengthApi.getExercisePresets(category),
    staleTime: 1000 * 60 * 60, // 1 hour
  });
}

export function useStrengthSessions(params?: StrengthListParams) {
  return useQuery({
    queryKey: ['strength', 'list', params],
    queryFn: () => strengthApi.getList(params),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

export function useStrengthSession(id: number) {
  return useQuery({
    queryKey: ['strength', 'detail', id],
    queryFn: () => strengthApi.getDetail(id),
    staleTime: 1000 * 60 * 10, // 10 minutes
    enabled: !!id,
  });
}

export function useStrengthCalendar(year: number, month: number) {
  return useQuery({
    queryKey: ['strength', 'calendar', year, month],
    queryFn: () => strengthApi.getCalendarSessions(year, month),
    staleTime: 1000 * 60 * 5,
    enabled: !!year && !!month,
  });
}

// -------------------------------------------------------------------------
// Mutation Hooks
// -------------------------------------------------------------------------

export function useCreateStrengthSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: StrengthSessionCreateData) => strengthApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strength'] });
    },
  });
}

export function useUpdateStrengthSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: StrengthSessionUpdateData }) =>
      strengthApi.update(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['strength'] });
      queryClient.invalidateQueries({ queryKey: ['strength', 'detail', id] });
    },
  });
}

export function useDeleteStrengthSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => strengthApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strength'] });
    },
  });
}

// -------------------------------------------------------------------------
// Utility Functions
// -------------------------------------------------------------------------

export function getSessionTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    upper: '상체',
    lower: '하체',
    core: '코어',
    full_body: '전신',
  };
  return labels[type] || type;
}

export function getSessionTypeColor(type: string): string {
  const colors: Record<string, string> = {
    upper: 'bg-blue-500',
    lower: 'bg-green-500',
    core: 'bg-orange-500',
    full_body: 'bg-purple-500',
  };
  return colors[type] || 'bg-gray-500';
}

export function getSessionPurposeLabel(purpose: string | null): string {
  if (!purpose) return '';
  const labels: Record<string, string> = {
    strength: '근력',
    flexibility: '유연성',
    balance: '밸런스',
    injury_prevention: '부상예방',
  };
  return labels[purpose] || purpose;
}

export function getSessionPurposeIcon(purpose: string | null): string {
  if (!purpose) return '';
  const icons: Record<string, string> = {
    strength: '💪',
    flexibility: '🧘',
    balance: '⚖️',
    injury_prevention: '🛡️',
  };
  return icons[purpose] || '';
}

export function getRatingStars(rating: number | null): string {
  if (!rating) return '';
  return '★'.repeat(rating) + '☆'.repeat(5 - rating);
}

export function formatSets(sets: { weight_kg: number | null; reps: number }[]): string {
  if (!sets || sets.length === 0) return '-';

  // Group identical sets
  const grouped: { weight: number | null; reps: number; count: number }[] = [];

  for (const set of sets) {
    const existing = grouped.find(g => g.weight === set.weight_kg && g.reps === set.reps);
    if (existing) {
      existing.count++;
    } else {
      grouped.push({ weight: set.weight_kg, reps: set.reps, count: 1 });
    }
  }

  return grouped
    .map(g => {
      const weightStr = g.weight !== null ? `${g.weight}kg` : '맨몸';
      if (g.count > 1) {
        return `${weightStr} × ${g.reps}회 × ${g.count}세트`;
      }
      return `${weightStr} × ${g.reps}회`;
    })
    .join(', ');
}
