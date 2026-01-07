import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Send, Trash2, Bot, User, Loader2, Save } from 'lucide-react'
import { trainingApi } from '../api/client'
import type { ChatMessage, Schedule } from '../types'
import clsx from 'clsx'

export default function Training() {
  const [message, setMessage] = useState('')
  const [suggestedSchedule, setSuggestedSchedule] = useState<Partial<Schedule> | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

  const { data: history = [], isLoading } = useQuery({
    queryKey: ['chat-history'],
    queryFn: () => trainingApi.getChatHistory(50),
  })

  const chatMutation = useMutation({
    mutationFn: (msg: string) => trainingApi.chat(msg, true),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['chat-history'] })
      if (data.suggested_schedule) {
        setSuggestedSchedule(data.suggested_schedule)
      }
    },
  })

  const clearMutation = useMutation({
    mutationFn: trainingApi.clearChatHistory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat-history'] })
      setSuggestedSchedule(null)
    },
  })

  const saveScheduleMutation = useMutation({
    mutationFn: (schedule: Partial<Schedule>) => trainingApi.createSchedule(schedule),
    onSuccess: () => {
      setSuggestedSchedule(null)
      queryClient.invalidateQueries({ queryKey: ['schedules'] })
    },
  })

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!message.trim() || chatMutation.isPending) return
    chatMutation.mutate(message)
    setMessage('')
  }

  const quickPrompts = [
    '이번 주 훈련 계획을 추천해줘',
    '하프마라톤 준비 4주 계획',
    '내 훈련 상태를 분석해줘',
    '회복을 위한 조언을 해줘',
  ]

  return (
    <div className="flex flex-col h-[calc(100vh-12rem)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">AI 러닝 코치</h1>
          <p className="text-slate-500">가민 데이터를 기반으로 맞춤 훈련 계획을 제안합니다</p>
        </div>
        <button
          onClick={() => clearMutation.mutate()}
          disabled={clearMutation.isPending}
          className="flex items-center space-x-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
        >
          <Trash2 className="h-4 w-4" />
          <span>대화 초기화</span>
        </button>
      </div>

      {/* Quick Prompts */}
      {history.length === 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {quickPrompts.map((prompt) => (
            <button
              key={prompt}
              onClick={() => {
                setMessage(prompt)
                chatMutation.mutate(prompt)
              }}
              className="px-3 py-2 text-sm bg-primary-50 text-primary-700 rounded-lg hover:bg-primary-100 transition-colors"
            >
              {prompt}
            </button>
          ))}
        </div>
      )}

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 bg-white rounded-xl p-4 border border-slate-100">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-primary-600" />
          </div>
        ) : history.length === 0 ? (
          <div className="text-center py-8 text-slate-400">
            <Bot className="h-12 w-12 mx-auto mb-3 text-slate-300" />
            <p>AI 코치에게 질문해보세요!</p>
          </div>
        ) : (
          history.map((msg, idx) => (
            <ChatBubble key={idx} message={msg} />
          ))
        )}
        {chatMutation.isPending && (
          <div className="flex items-start space-x-3">
            <div className="p-2 rounded-full bg-primary-100">
              <Bot className="h-5 w-5 text-primary-600" />
            </div>
            <div className="flex items-center space-x-2 p-3 bg-slate-100 rounded-lg">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm text-slate-600">생각 중...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Schedule */}
      {suggestedSchedule && (
        <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-xl">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-semibold text-green-800">추천 스케줄</h3>
            <button
              onClick={() => saveScheduleMutation.mutate(suggestedSchedule)}
              disabled={saveScheduleMutation.isPending}
              className="flex items-center space-x-1 px-3 py-1 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm"
            >
              <Save className="h-4 w-4" />
              <span>{saveScheduleMutation.isPending ? '저장 중...' : '저장하기'}</span>
            </button>
          </div>
          <p className="text-sm text-green-700">{suggestedSchedule.title}</p>
          {suggestedSchedule.description && (
            <p className="text-xs text-green-600 mt-1">{suggestedSchedule.description}</p>
          )}
        </div>
      )}

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="flex space-x-2">
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="훈련 계획에 대해 물어보세요..."
          className="flex-1 px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          disabled={chatMutation.isPending}
        />
        <button
          type="submit"
          disabled={!message.trim() || chatMutation.isPending}
          className={clsx(
            'px-4 py-3 rounded-xl transition-colors',
            message.trim() && !chatMutation.isPending
              ? 'bg-primary-600 text-white hover:bg-primary-700'
              : 'bg-slate-100 text-slate-400 cursor-not-allowed'
          )}
        >
          <Send className="h-5 w-5" />
        </button>
      </form>
    </div>
  )
}

function ChatBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'

  return (
    <div className={clsx('flex items-start space-x-3', isUser && 'flex-row-reverse space-x-reverse')}>
      <div className={clsx('p-2 rounded-full', isUser ? 'bg-slate-200' : 'bg-primary-100')}>
        {isUser ? (
          <User className="h-5 w-5 text-slate-600" />
        ) : (
          <Bot className="h-5 w-5 text-primary-600" />
        )}
      </div>
      <div
        className={clsx(
          'max-w-[80%] p-3 rounded-xl',
          isUser ? 'bg-primary-600 text-white' : 'bg-slate-100 text-slate-700'
        )}
      >
        <p className="whitespace-pre-wrap text-sm">{message.content}</p>
      </div>
    </div>
  )
}
