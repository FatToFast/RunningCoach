import { apiClient } from './client';
import type {
  CalendarNote,
  CalendarNoteCreate,
  CalendarNotesResponse,
  NoteTypesResponse,
} from '../types/api';

export interface CalendarNotesParams {
  start_date?: string;
  end_date?: string;
  note_type?: string;
}

export const calendarNotesApi = {
  // Get note types
  getTypes: async (): Promise<NoteTypesResponse> => {
    const { data } = await apiClient.get('/calendar-notes/types');
    return data;
  },

  // Get all notes (with optional filters)
  getNotes: async (params?: CalendarNotesParams): Promise<CalendarNotesResponse> => {
    const { data } = await apiClient.get('/calendar-notes', { params });
    return data;
  },

  // Get note by date
  getNoteByDate: async (date: string): Promise<CalendarNote | null> => {
    try {
      const { data } = await apiClient.get(`/calendar-notes/${date}`);
      return data;
    } catch {
      return null;
    }
  },

  // Create or update note (upsert)
  createOrUpdateNote: async (note: CalendarNoteCreate): Promise<CalendarNote> => {
    const { data } = await apiClient.post('/calendar-notes', note);
    return data;
  },

  // Update note
  updateNote: async (date: string, note: Partial<CalendarNoteCreate>): Promise<CalendarNote> => {
    const { data } = await apiClient.patch(`/calendar-notes/${date}`, note);
    return data;
  },

  // Delete note
  deleteNote: async (date: string): Promise<void> => {
    await apiClient.delete(`/calendar-notes/${date}`);
  },
};
