import { apiClient } from './client';

// -------------------------------------------------------------------------
// Types
// -------------------------------------------------------------------------

export interface IngestRunRequest {
  endpoints?: string[];
  full_backfill?: boolean;
  start_date?: string;
  end_date?: string;
}

export interface IngestRunResponse {
  started: boolean;
  message: string;
  endpoints: string[];
  sync_id?: string;
}

export interface SyncStateResponse {
  endpoint: string;
  last_sync_at: string | null;
  last_success_at: string | null;
  cursor: string | null;
}

export interface SyncProgress {
  current_endpoint: string;
  current_index: number;
  total_endpoints: number;
  items_synced: number;
}

export interface IngestStatusResponse {
  connected: boolean;
  running: boolean;
  sync_states: SyncStateResponse[];
  last_error?: string | null;
  last_sync_started_at?: string | null;
  progress?: SyncProgress | null;
}

export interface SyncHistoryItem {
  id: number;
  endpoint: string;
  fetched_at: string;
  record_count: number;
}

export interface SyncHistoryResponse {
  items: SyncHistoryItem[];
  total: number;
}

// -------------------------------------------------------------------------
// API Functions
// -------------------------------------------------------------------------

export const garminApi = {
  /**
   * Trigger manual Garmin data sync (background job).
   */
  runSync: async (request?: IngestRunRequest): Promise<IngestRunResponse> => {
    const { data } = await apiClient.post('/ingest/run', request ?? {});
    return data;
  },

  /**
   * Get current sync status.
   */
  getStatus: async (): Promise<IngestStatusResponse> => {
    const { data } = await apiClient.get('/ingest/status');
    return data;
  },

  /**
   * Get sync history.
   */
  getHistory: async (params?: {
    endpoint?: string;
    page?: number;
    per_page?: number;
  }): Promise<SyncHistoryResponse> => {
    const { data } = await apiClient.get('/ingest/history', { params });
    return data;
  },
};
