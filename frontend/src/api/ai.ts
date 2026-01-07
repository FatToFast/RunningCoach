import { apiClient } from './client';
import type { ExportSummaryResponse } from '../types/api';

export interface Message {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  token_count: number | null;  // Backend uses 'token_count', not 'tokens'
  created_at: string;
}

export interface Conversation {
  id: number;
  title: string | null;
  context_type: string | null;  // Backend: context_type (e.g., "chat", "plan")
  context_data: Record<string, any> | null;  // Backend: context_data (contains language, model, etc.)
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface ConversationListResponse {
  items: Conversation[];
  total: number;
}

export interface ChatRequest {
  message: string;
  context?: Record<string, unknown>;
  mode?: 'chat' | 'plan';
  save_mode?: 'draft' | 'approved' | 'active';
}

export interface ChatResponse {
  conversation_id: number;
  message: Message;
  reply: Message;
  plan_id?: number | null;
  import_id?: number | null;
  plan_status?: 'draft' | 'approved' | 'active' | null;
  missing_fields?: string[] | null;
}

export interface ConversationCreateRequest {
  title?: string;
  language?: string;
}

export interface CoachRaceSummary {
  id: number;
  name: string;
  race_date: string;
  days_until: number;
  distance_km: number | null;
  distance_label: string | null;
  location: string | null;
  goal_time_seconds: number | null;
  goal_description: string | null;
  is_primary: boolean;
}

export interface CoachActivitySummary {
  activity_id: number;
  activity_type: string;
  name: string | null;
  start_time: string;
  distance_km: number | null;
  duration_min: number | null;
  avg_pace_seconds: number | null;
  avg_hr: number | null;
  max_hr: number | null;
  avg_cadence: number | null;
  training_effect: number | null;
  trimp: number | null;
  tss: number | null;
  efficiency_factor: number | null;
  sample_count: number;
  pace_std_seconds: number | null;
  hr_std: number | null;
  cadence_std: number | null;
}

export interface CoachContextResponse {
  snapshot: Record<string, unknown>;
  primary_race: CoachRaceSummary | null;
  activity: CoachActivitySummary | null;
}

export const aiApi = {
  // 대화 목록 조회
  getConversations: async (page = 1, perPage = 20): Promise<ConversationListResponse> => {
    const { data } = await apiClient.get('/ai/conversations', {
      params: { page, per_page: perPage },
    });
    return data;
  },

  // 대화 생성
  createConversation: async (request?: ConversationCreateRequest): Promise<Conversation> => {
    const { data } = await apiClient.post('/ai/conversations', request || {});
    return data;
  },

  // 대화 상세 조회
  getConversation: async (id: number): Promise<ConversationDetail> => {
    const { data } = await apiClient.get(`/ai/conversations/${id}`);
    return data;
  },

  // 대화 삭제
  deleteConversation: async (id: number): Promise<void> => {
    await apiClient.delete(`/ai/conversations/${id}`);
  },

  // 메시지 전송 (기존 대화)
  sendMessage: async (conversationId: number, request: ChatRequest): Promise<ChatResponse> => {
    const { data } = await apiClient.post(`/ai/conversations/${conversationId}/chat`, request);
    return data;
  },

  // 빠른 채팅 (새 대화 생성 + 메시지)
  chat: async (request: ChatRequest): Promise<ChatResponse> => {
    const { data } = await apiClient.post('/ai/chat', request);
    return data;
  },

  // 훈련 요약 내보내기
  exportSummary: async (format: 'markdown' | 'json' = 'markdown'): Promise<ExportSummaryResponse> => {
    const { data } = await apiClient.get<ExportSummaryResponse>('/ai/export', {
      params: { format },
    });
    return data;
  },

  // AI 코치 컨텍스트
  getCoachContext: async (activityId?: number): Promise<CoachContextResponse> => {
    const { data } = await apiClient.get('/ai/coach/context', {
      params: activityId ? { activity_id: activityId } : undefined,
    });
    return data;
  },
};

// Token Usage Tracking
export interface TokenUsageStats {
  period_days: number;
  total_tokens: number;
  message_count: number;
  avg_tokens_per_message: number;
}

export interface TokenUsageResponse {
  recent_6_weeks: TokenUsageStats;
  recent_12_weeks: TokenUsageStats;
  all_time: TokenUsageStats;
  budget_usd?: number | null;
  estimated_cost_usd?: number | null;
}

// Add getTokenUsage to API client
export const getTokenUsage = async (): Promise<TokenUsageResponse> => {
  const response = await apiClient.get<TokenUsageResponse>('/ai/usage/tokens');
  return response.data;
};
