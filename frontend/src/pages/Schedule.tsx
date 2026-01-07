import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Calendar, Trash2, Upload, ChevronDown, ChevronUp, CheckCircle } from 'lucide-react'
import { trainingApi } from '../api/client'
import type { Schedule, Workout } from '../types'
import { useState } from 'react'
import clsx from 'clsx'

const WORKOUT_TYPE_LABELS: Record<string, { label: string; color: string }> = {
  easy: { label: '이지런', color: 'bg-green-100 text-green-700' },
  tempo: { label: '템포런', color: 'bg-orange-100 text-orange-700' },
  interval: { label: '인터벌', color: 'bg-red-100 text-red-700' },
  long_run: { label: '장거리', color: 'bg-blue-100 text-blue-700' },
  recovery: { label: '회복', color: 'bg-teal-100 text-teal-700' },
  rest: { label: '휴식', color: 'bg-slate-100 text-slate-500' },
}

export default function SchedulePage() {
  const queryClient = useQueryClient()
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const { data: schedules = [], isLoading } = useQuery({
    queryKey: ['schedules'],
    queryFn: trainingApi.getSchedules,
  })

  const deleteMutation = useMutation({
    mutationFn: trainingApi.deleteSchedule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedules'] })
    },
  })

  const syncMutation = useMutation({
    mutationFn: trainingApi.syncToGarmin,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedules'] })
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">훈련 스케줄</h1>
          <p className="text-slate-500">AI가 생성한 훈련 계획을 관리하세요</p>
        </div>
      </div>

      {schedules.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-xl border border-slate-100">
          <Calendar className="h-16 w-16 text-slate-300 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-slate-700 mb-2">저장된 스케줄이 없습니다</h2>
          <p className="text-slate-500 mb-4">AI 코치에게 훈련 계획을 요청해보세요</p>
          <a href="/training" className="text-primary-600 hover:underline">AI 코치로 이동 →</a>
        </div>
      ) : (
        <div className="space-y-4">
          {schedules.map((schedule) => (
            <ScheduleCard
              key={schedule.id}
              schedule={schedule}
              isExpanded={expandedId === schedule.id}
              onToggle={() => setExpandedId(expandedId === schedule.id ? null : schedule.id)}
              onDelete={() => deleteMutation.mutate(schedule.id)}
              onSync={() => syncMutation.mutate(schedule.id)}
              isDeleting={deleteMutation.isPending}
              isSyncing={syncMutation.isPending}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function ScheduleCard({
  schedule,
  isExpanded,
  onToggle,
  onDelete,
  onSync,
  isDeleting,
  isSyncing,
}: {
  schedule: Schedule
  isExpanded: boolean
  onToggle: () => void
  onDelete: () => void
  onSync: () => void
  isDeleting: boolean
  isSyncing: boolean
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-100 overflow-hidden">
      {/* Header */}
      <div
        className="p-4 cursor-pointer hover:bg-slate-50 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <Calendar className="h-5 w-5 text-primary-600" />
            <div>
              <h3 className="font-semibold text-slate-900">{schedule.title}</h3>
              <p className="text-sm text-slate-500">
                {new Date(schedule.start_date).toLocaleDateString('ko-KR')}
                {schedule.end_date && ` ~ ${new Date(schedule.end_date).toLocaleDateString('ko-KR')}`}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            {schedule.is_synced_to_garmin && (
              <span className="flex items-center space-x-1 px-2 py-1 bg-green-100 text-green-700 rounded text-xs">
                <CheckCircle className="h-3 w-3" />
                <span>동기화됨</span>
              </span>
            )}
            {isExpanded ? (
              <ChevronUp className="h-5 w-5 text-slate-400" />
            ) : (
              <ChevronDown className="h-5 w-5 text-slate-400" />
            )}
          </div>
        </div>
        {schedule.goal && (
          <p className="text-sm text-slate-600 mt-2">목표: {schedule.goal}</p>
        )}
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t border-slate-100">
          {/* Workouts */}
          <div className="p-4 space-y-2">
            {schedule.workouts.length > 0 ? (
              schedule.workouts.map((workout) => (
                <WorkoutItem key={workout.id} workout={workout} />
              ))
            ) : (
              <p className="text-sm text-slate-400 text-center py-4">워크아웃이 없습니다</p>
            )}
          </div>

          {/* Actions */}
          <div className="p-4 bg-slate-50 border-t border-slate-100 flex justify-end space-x-2">
            <button
              onClick={(e) => {
                e.stopPropagation()
                onDelete()
              }}
              disabled={isDeleting}
              className="flex items-center space-x-1 px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            >
              <Trash2 className="h-4 w-4" />
              <span>{isDeleting ? '삭제 중...' : '삭제'}</span>
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation()
                onSync()
              }}
              disabled={isSyncing || schedule.is_synced_to_garmin}
              className={clsx(
                'flex items-center space-x-1 px-3 py-2 text-sm rounded-lg transition-colors',
                schedule.is_synced_to_garmin
                  ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                  : 'bg-primary-600 text-white hover:bg-primary-700'
              )}
            >
              <Upload className="h-4 w-4" />
              <span>{isSyncing ? '전송 중...' : '가민으로 전송'}</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function WorkoutItem({ workout }: { workout: Workout }) {
  const typeInfo = WORKOUT_TYPE_LABELS[workout.workout_type] || {
    label: workout.workout_type,
    color: 'bg-slate-100 text-slate-600',
  }

  return (
    <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
      <div className="flex items-center space-x-3">
        <span className={clsx('px-2 py-1 rounded text-xs font-medium', typeInfo.color)}>
          {typeInfo.label}
        </span>
        <div>
          <p className="font-medium text-slate-700">{workout.title}</p>
          <p className="text-sm text-slate-500">
            {new Date(workout.date).toLocaleDateString('ko-KR', {
              weekday: 'short',
              month: 'short',
              day: 'numeric',
            })}
          </p>
        </div>
      </div>
      <div className="text-right text-sm text-slate-500">
        {workout.target_distance_meters && (
          <p>{(workout.target_distance_meters / 1000).toFixed(1)} km</p>
        )}
        {workout.target_pace && <p>{workout.target_pace} /km</p>}
      </div>
    </div>
  )
}
