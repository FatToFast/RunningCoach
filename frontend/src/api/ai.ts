import { apiClient } from './client';

export interface Message {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  tokens: number | null;
  created_at: string;
}

export interface Conversation {
  id: number;
  title: string | null;
  language: string;
  model: string;
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
}

export interface ChatResponse {
  conversation_id: number;
  message: Message;
  reply: Message;
}

export interface ConversationCreateRequest {
  title?: string;
  language?: string;
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
  sendMessage: async (conversationId: number, message: string): Promise<ChatResponse> => {
    const { data } = await apiClient.post(`/ai/conversations/${conversationId}/chat`, {
      message,
    });
    return data;
  },

  // 빠른 채팅 (새 대화 생성 + 메시지)
  chat: async (request: ChatRequest): Promise<ChatResponse> => {
    const { data } = await apiClient.post('/ai/chat', request);
    return data;
  },

  // 훈련 요약 내보내기
  exportSummary: async (format: 'markdown' | 'json' = 'markdown'): Promise<string> => {
    const { data } = await apiClient.get('/ai/export', {
      params: { format },
    });
    return data;
  },
};
