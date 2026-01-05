import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { aiApi } from '../api/ai';
import type { ChatRequest, ConversationCreateRequest } from '../api/ai';

export function useConversations(page = 1, perPage = 20) {
  return useQuery({
    queryKey: ['conversations', page, perPage],
    queryFn: () => aiApi.getConversations(page, perPage),
  });
}

export function useConversation(id: number | null) {
  return useQuery({
    queryKey: ['conversation', id],
    queryFn: () => (id ? aiApi.getConversation(id) : null),
    enabled: id !== null,
  });
}

export function useCreateConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request?: ConversationCreateRequest) => aiApi.createConversation(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
    },
  });
}

export function useDeleteConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => aiApi.deleteConversation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
    },
  });
}

export function useSendMessage(conversationId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: ChatRequest) => aiApi.sendMessage(conversationId, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversation', conversationId] });
    },
  });
}

export function useChat() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: ChatRequest) => aiApi.chat(request),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
      queryClient.invalidateQueries({ queryKey: ['conversation', data.conversation_id] });
    },
  });
}

export function useExportSummary() {
  return useMutation({
    mutationFn: (format: 'markdown' | 'json' = 'markdown') => aiApi.exportSummary(format),
  });
}

export function useCoachContext(activityId?: number) {
  return useQuery({
    queryKey: ['ai', 'coach-context', activityId],
    queryFn: () => aiApi.getCoachContext(activityId),
  });
}
