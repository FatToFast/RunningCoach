import { useState, useRef, useEffect } from 'react';
import {
  MessageSquare,
  Send,
  Plus,
  Trash2,
  Bot,
  User,
  Loader2,
  Copy,
  Check,
  Download
} from 'lucide-react';
import {
  useConversations,
  useConversation,
  useCreateConversation,
  useDeleteConversation,
  useSendMessage,
  useChat,
  useExportSummary
} from '../hooks/useAI';
import type { Message } from '../api/ai';

export function Coach() {
  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(null);
  const [inputMessage, setInputMessage] = useState('');
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { data: conversationsData, isLoading: conversationsLoading } = useConversations();
  const { data: conversationDetail, isLoading: detailLoading } = useConversation(selectedConversationId);

  const createConversation = useCreateConversation();
  const deleteConversation = useDeleteConversation();
  const chat = useChat();
  const sendMessage = useSendMessage(selectedConversationId || 0);
  const exportSummary = useExportSummary();

  // 메시지 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversationDetail?.messages]);

  const handleNewConversation = async () => {
    try {
      const conversation = await createConversation.mutateAsync({ title: '새 대화' });
      setSelectedConversationId(conversation.id);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleDeleteConversation = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('이 대화를 삭제하시겠습니까?')) return;

    try {
      await deleteConversation.mutateAsync(id);
      if (selectedConversationId === id) {
        setSelectedConversationId(null);
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim()) return;

    const message = inputMessage.trim();
    setInputMessage('');

    try {
      if (selectedConversationId) {
        await sendMessage.mutateAsync(message);
      } else {
        const response = await chat.mutateAsync({ message });
        setSelectedConversationId(response.conversation_id);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  };

  const handleCopyMessage = (message: Message) => {
    navigator.clipboard.writeText(message.content);
    setCopiedId(message.id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleExportSummary = async () => {
    try {
      const summary = await exportSummary.mutateAsync('markdown');
      navigator.clipboard.writeText(typeof summary === 'string' ? summary : JSON.stringify(summary, null, 2));
      alert('훈련 요약이 클립보드에 복사되었습니다.');
    } catch (error) {
      console.error('Failed to export summary:', error);
    }
  };

  const formatTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('ko-KR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const isLoading = chat.isPending || sendMessage.isPending;

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* 사이드바 - 대화 목록 */}
      <div className="w-72 flex-shrink-0 card flex flex-col">
        <div className="p-4 border-b border-[var(--color-border)]">
          <button
            onClick={handleNewConversation}
            disabled={createConversation.isPending}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-cyan text-[var(--color-bg-primary)] font-semibold rounded-lg hover:bg-cyan/90 transition-colors disabled:opacity-50"
          >
            <Plus className="w-4 h-4" />
            새 대화
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {conversationsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-muted" />
            </div>
          ) : conversationsData?.items.length === 0 ? (
            <div className="text-center py-8 text-muted text-sm">
              대화가 없습니다
            </div>
          ) : (
            <div className="space-y-1">
              {conversationsData?.items.map((conv) => (
                <div
                  key={conv.id}
                  onClick={() => setSelectedConversationId(conv.id)}
                  className={`group flex items-center gap-2 p-3 rounded-lg cursor-pointer transition-colors ${
                    selectedConversationId === conv.id
                      ? 'bg-cyan/10 text-cyan'
                      : 'hover:bg-[var(--color-bg-tertiary)]'
                  }`}
                >
                  <MessageSquare className="w-4 h-4 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">
                      {conv.title || '새 대화'}
                    </p>
                    <p className="text-xs text-muted truncate">
                      {formatTime(conv.updated_at)}
                    </p>
                  </div>
                  <button
                    onClick={(e) => handleDeleteConversation(conv.id, e)}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 rounded transition-all"
                  >
                    <Trash2 className="w-3.5 h-3.5 text-red-400" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Export 버튼 */}
        <div className="p-4 border-t border-[var(--color-border)]">
          <button
            onClick={handleExportSummary}
            disabled={exportSummary.isPending}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm text-muted hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-tertiary)] rounded-lg transition-colors"
          >
            <Download className="w-4 h-4" />
            훈련 요약 복사
          </button>
        </div>
      </div>

      {/* 메인 채팅 영역 */}
      <div className="flex-1 card flex flex-col">
        {/* 헤더 */}
        <div className="p-4 border-b border-[var(--color-border)] flex items-center gap-3">
          <div className="p-2 bg-cyan/10 rounded-lg">
            <Bot className="w-5 h-5 text-cyan" />
          </div>
          <div>
            <h1 className="font-display font-semibold">AI 코치</h1>
            <p className="text-xs text-muted">훈련 계획 생성 및 조언</p>
          </div>
        </div>

        {/* 메시지 영역 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {detailLoading ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="w-6 h-6 animate-spin text-muted" />
            </div>
          ) : conversationDetail?.messages.length === 0 || !selectedConversationId ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <Bot className="w-16 h-16 text-muted mb-4" />
              <h2 className="text-lg font-semibold mb-2">AI 러닝 코치</h2>
              <p className="text-muted text-sm max-w-md">
                훈련 계획, 페이스 조언, 회복 전략 등
                러닝에 관한 모든 질문을 해보세요.
              </p>
              <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                <button
                  onClick={() => setInputMessage('이번 주 훈련 계획을 세워줘')}
                  className="px-4 py-2 bg-[var(--color-bg-tertiary)] rounded-lg hover:bg-cyan/10 transition-colors text-left"
                >
                  이번 주 훈련 계획을 세워줘
                </button>
                <button
                  onClick={() => setInputMessage('10km 대회 준비 어떻게 해야 할까?')}
                  className="px-4 py-2 bg-[var(--color-bg-tertiary)] rounded-lg hover:bg-cyan/10 transition-colors text-left"
                >
                  10km 대회 준비 어떻게 해야 할까?
                </button>
                <button
                  onClick={() => setInputMessage('오늘 컨디션이 안좋은데 쉬어야 할까?')}
                  className="px-4 py-2 bg-[var(--color-bg-tertiary)] rounded-lg hover:bg-cyan/10 transition-colors text-left"
                >
                  오늘 컨디션이 안좋은데 쉬어야 할까?
                </button>
                <button
                  onClick={() => setInputMessage('최근 훈련 데이터를 분석해줘')}
                  className="px-4 py-2 bg-[var(--color-bg-tertiary)] rounded-lg hover:bg-cyan/10 transition-colors text-left"
                >
                  최근 훈련 데이터를 분석해줘
                </button>
              </div>
            </div>
          ) : (
            <>
              {conversationDetail?.messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : ''}`}
                >
                  {message.role === 'assistant' && (
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-cyan/10 flex items-center justify-center">
                      <Bot className="w-4 h-4 text-cyan" />
                    </div>
                  )}
                  <div
                    className={`group relative max-w-[80%] px-4 py-3 rounded-2xl ${
                      message.role === 'user'
                        ? 'bg-cyan text-[var(--color-bg-primary)]'
                        : 'bg-[var(--color-bg-tertiary)]'
                    }`}
                  >
                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                    <p className={`text-xs mt-1 ${
                      message.role === 'user' ? 'text-cyan-100' : 'text-muted'
                    }`}>
                      {formatTime(message.created_at)}
                    </p>
                    <button
                      onClick={() => handleCopyMessage(message)}
                      className={`absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1 rounded transition-all ${
                        message.role === 'user'
                          ? 'hover:bg-white/20'
                          : 'hover:bg-[var(--color-bg-secondary)]'
                      }`}
                    >
                      {copiedId === message.id ? (
                        <Check className="w-3.5 h-3.5" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                  {message.role === 'user' && (
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[var(--color-bg-tertiary)] flex items-center justify-center">
                      <User className="w-4 h-4" />
                    </div>
                  )}
                </div>
              ))}
              {isLoading && (
                <div className="flex gap-3">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-cyan/10 flex items-center justify-center">
                    <Bot className="w-4 h-4 text-cyan" />
                  </div>
                  <div className="bg-[var(--color-bg-tertiary)] px-4 py-3 rounded-2xl">
                    <Loader2 className="w-5 h-5 animate-spin text-muted" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* 입력 영역 */}
        <form onSubmit={handleSendMessage} className="p-4 border-t border-[var(--color-border)]">
          <div className="flex gap-3">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder="메시지를 입력하세요..."
              disabled={isLoading}
              className="flex-1 px-4 py-3 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-xl text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:ring-2 focus:ring-cyan/50 focus:border-cyan transition-colors disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!inputMessage.trim() || isLoading}
              className="px-4 py-3 bg-cyan text-[var(--color-bg-primary)] rounded-xl hover:bg-cyan/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
