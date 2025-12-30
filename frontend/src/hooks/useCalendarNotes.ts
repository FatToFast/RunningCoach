import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { calendarNotesApi, type CalendarNotesParams } from '../api/calendarNotes';
import type { CalendarNoteCreate } from '../types/api';

// Get note types
export function useNoteTypes() {
  return useQuery({
    queryKey: ['calendar-notes', 'types'],
    queryFn: () => calendarNotesApi.getTypes(),
    staleTime: 1000 * 60 * 60, // 1 hour (types rarely change)
  });
}

// Get all notes for a date range
export function useCalendarNotes(params?: CalendarNotesParams) {
  return useQuery({
    queryKey: ['calendar-notes', params],
    queryFn: () => calendarNotesApi.getNotes(params),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

// Get note by date
export function useCalendarNoteByDate(date: string | null) {
  return useQuery({
    queryKey: ['calendar-notes', 'date', date],
    queryFn: () => date ? calendarNotesApi.getNoteByDate(date) : null,
    enabled: !!date,
    staleTime: 1000 * 60 * 5,
  });
}

// Create or update note mutation
export function useCreateOrUpdateNote() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (note: CalendarNoteCreate) => calendarNotesApi.createOrUpdateNote(note),
    onSuccess: (data) => {
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ['calendar-notes'] });
      queryClient.setQueryData(['calendar-notes', 'date', data.date], data);
    },
  });
}

// Delete note mutation
export function useDeleteNote() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (date: string) => calendarNotesApi.deleteNote(date),
    onSuccess: (_, date) => {
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ['calendar-notes'] });
      queryClient.setQueryData(['calendar-notes', 'date', date], null);
    },
  });
}
