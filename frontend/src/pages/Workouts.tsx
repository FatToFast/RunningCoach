import { useState, useEffect } from 'react';
import {
  Target,
  Plus,
  ChevronRight,
  Calendar,
  Clock,
  CheckCircle2,
  XCircle,
  SkipForward,
  Upload,
  Filter,
  Play,
  Download,
  Check,
  Loader2,
  Edit3,
  Trash2,
} from 'lucide-react';
import {
  useWorkouts,
  useSchedules,
  useCreateWorkout,
  useUpdateWorkout,
  useDeleteWorkout,
  usePushToGarmin,
  useCreateSchedule,
  useUpdateScheduleStatus,
  useDeleteSchedule,
  useGarminWorkouts,
  useImportGarminWorkouts,
  getWorkoutTypeLabel,
  getWorkoutTypeColor,
  getWorkoutTypeIcon,
  getScheduleStatusLabel,
  getScheduleStatusColor,
  getStepTypeLabel,
} from '../hooks/useWorkouts';
import type { Workout, WorkoutSchedule, ScheduleStatus, WorkoutStep } from '../types/api';

// Format date in Korean
function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const month = date.getMonth() + 1;
  const day = date.getDate();
  const weekdays = ['일', '월', '화', '수', '목', '금', '토'];
  const weekday = weekdays[date.getDay()];
  return `${month}/${day} (${weekday})`;
}

// Format date for input
function formatDateForInput(date: Date): string {
  return date.toISOString().split('T')[0];
}

// Workout Form Modal
function WorkoutForm({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [name, setName] = useState('');
  const [workoutType, setWorkoutType] = useState('easy');
  const [notes, setNotes] = useState('');
  const createWorkout = useCreateWorkout();

  const workoutTypes = ['easy', 'long', 'tempo', 'interval', 'hills', 'fartlek', 'recovery'];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    try {
      await createWorkout.mutateAsync({
        name: name.trim(),
        workout_type: workoutType,
        notes: notes.trim() || undefined,
      });
      onSuccess();
    } catch (error) {
      console.error('Failed to create workout:', error);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-md p-6">
        <h2 className="text-lg font-bold mb-4">새 워크아웃</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-muted mb-1">이름</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input w-full"
              placeholder="예: 5km 템포런"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-muted mb-1">유형</label>
            <div className="grid grid-cols-4 gap-2">
              {workoutTypes.map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setWorkoutType(type)}
                  className={`px-2 py-2 rounded-lg text-xs transition-colors ${
                    workoutType === type
                      ? `${getWorkoutTypeColor(type)} text-white`
                      : 'bg-[var(--color-bg-tertiary)] text-muted hover:text-white'
                  }`}
                >
                  {getWorkoutTypeIcon(type)} {getWorkoutTypeLabel(type)}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm text-muted mb-1">메모</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="input w-full h-20"
              placeholder="워크아웃 설명..."
            />
          </div>
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn btn-secondary flex-1">
              취소
            </button>
            <button
              type="submit"
              className="btn btn-primary flex-1"
              disabled={createWorkout.isPending}
            >
              {createWorkout.isPending ? '저장 중...' : '저장'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Garmin Import Modal
function GarminImportModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const { data, isLoading, refetch } = useGarminWorkouts(50);
  const importMutation = useImportGarminWorkouts();

  // Fetch when modal opens
  useEffect(() => {
    refetch();
  }, [refetch]);

  const handleToggle = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleSelectAll = () => {
    if (!data?.items) return;
    const availableIds = data.items
      .filter((w) => !w.already_imported)
      .map((w) => w.garmin_workout_id);

    if (selectedIds.size === availableIds.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(availableIds));
    }
  };

  const handleImport = async () => {
    if (selectedIds.size === 0) return;
    try {
      const result = await importMutation.mutateAsync(Array.from(selectedIds));
      alert(`${result.imported}개 워크아웃을 가져왔습니다.${result.skipped > 0 ? ` (${result.skipped}개 건너뜀)` : ''}`);
      onSuccess();
    } catch (error) {
      console.error('Failed to import workouts:', error);
      alert('워크아웃 가져오기에 실패했습니다.');
    }
  };

  const formatDuration = (seconds: number | null): string => {
    if (!seconds) return '-';
    const mins = Math.floor(seconds / 60);
    if (mins < 60) return `${mins}분`;
    const hours = Math.floor(mins / 60);
    const remainMins = mins % 60;
    return `${hours}시간 ${remainMins}분`;
  };

  const availableCount = data?.items?.filter((w) => !w.already_imported).length || 0;

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-2xl p-6 max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <Download className="w-5 h-5 text-cyan" />
            Garmin에서 워크아웃 가져오기
          </h2>
          <button
            onClick={() => refetch()}
            className="p-2 hover:bg-[var(--color-bg-tertiary)] rounded-lg transition-colors"
            disabled={isLoading}
          >
            <Loader2 className={`w-4 h-4 text-muted ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {isLoading ? (
          <div className="flex-1 flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-cyan animate-spin" />
          </div>
        ) : !data?.items || data.items.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center py-12">
            <Target className="w-12 h-12 text-muted mb-4" />
            <p className="text-muted">Garmin Connect에 워크아웃이 없습니다</p>
          </div>
        ) : (
          <>
            {/* Select All */}
            {availableCount > 0 && (
              <div className="flex items-center justify-between mb-3 pb-3 border-b border-[var(--color-border)]">
                <button
                  onClick={handleSelectAll}
                  className="text-sm text-cyan hover:text-cyan/80 transition-colors"
                >
                  {selectedIds.size === availableCount ? '전체 해제' : '전체 선택'}
                </button>
                <span className="text-sm text-muted">
                  {selectedIds.size}개 선택됨 / {availableCount}개 가져오기 가능
                </span>
              </div>
            )}

            {/* Workout List */}
            <div className="flex-1 overflow-y-auto space-y-2 mb-4">
              {data.items.map((workout) => (
                <div
                  key={workout.garmin_workout_id}
                  onClick={() => !workout.already_imported && handleToggle(workout.garmin_workout_id)}
                  className={`p-3 rounded-lg border transition-all ${
                    workout.already_imported
                      ? 'border-[var(--color-border)] bg-[var(--color-bg-tertiary)]/50 opacity-50 cursor-not-allowed'
                      : selectedIds.has(workout.garmin_workout_id)
                      ? 'border-cyan bg-cyan/10 cursor-pointer'
                      : 'border-[var(--color-border)] hover:border-cyan/30 cursor-pointer'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    {/* Checkbox */}
                    <div className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 ${
                      workout.already_imported
                        ? 'border-green-500 bg-green-500'
                        : selectedIds.has(workout.garmin_workout_id)
                        ? 'border-cyan bg-cyan'
                        : 'border-[var(--color-border)]'
                    }`}>
                      {(workout.already_imported || selectedIds.has(workout.garmin_workout_id)) && (
                        <Check className="w-3 h-3 text-white" />
                      )}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium truncate">{workout.name}</span>
                        {workout.already_imported && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400 flex-shrink-0">
                            가져옴
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-muted">
                        <span className="capitalize">{workout.workout_type}</span>
                        {workout.step_count > 0 && (
                          <span>{workout.step_count}개 단계</span>
                        )}
                        {workout.estimated_duration_seconds && (
                          <span>{formatDuration(workout.estimated_duration_seconds)}</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {/* Actions */}
        <div className="flex gap-2 pt-3 border-t border-[var(--color-border)]">
          <button onClick={onClose} className="btn btn-secondary flex-1">
            닫기
          </button>
          <button
            onClick={handleImport}
            className="btn btn-primary flex-1 flex items-center justify-center gap-2"
            disabled={selectedIds.size === 0 || importMutation.isPending}
          >
            {importMutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                가져오는 중...
              </>
            ) : (
              <>
                <Download className="w-4 h-4" />
                {selectedIds.size}개 가져오기
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// Step type colors
function getStepTypeColor(type: string): string {
  const colors: Record<string, string> = {
    warmup: 'bg-amber-500',
    main: 'bg-cyan',
    cooldown: 'bg-blue-500',
    rest: 'bg-gray-500',
    recovery: 'bg-green-500',
  };
  return colors[type] || 'bg-gray-500';
}

// Workout Edit Modal with Steps Editor
function WorkoutEditModal({
  workout,
  onClose,
  onSuccess,
}: {
  workout: Workout;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [name, setName] = useState(workout.name);
  const [workoutType, setWorkoutType] = useState(workout.workout_type);
  const [notes, setNotes] = useState(workout.notes || '');
  const [steps, setSteps] = useState<WorkoutStep[]>(workout.structure || []);
  const updateWorkout = useUpdateWorkout();

  const workoutTypes = ['easy', 'long', 'tempo', 'interval', 'hills', 'fartlek', 'recovery'];
  const stepTypes = ['warmup', 'main', 'cooldown', 'rest', 'recovery'];

  const handleAddStep = () => {
    setSteps([
      ...steps,
      {
        type: 'main',
        duration_minutes: null,
        distance_km: null,
        target_pace: null,
        target_hr_zone: null,
        description: null,
      },
    ]);
  };

  const handleUpdateStep = (index: number, field: keyof WorkoutStep, value: string | number | null) => {
    const newSteps = [...steps];
    newSteps[index] = { ...newSteps[index], [field]: value };
    setSteps(newSteps);
  };

  const handleDeleteStep = (index: number) => {
    setSteps(steps.filter((_, i) => i !== index));
  };

  const handleMoveStep = (index: number, direction: 'up' | 'down') => {
    if (direction === 'up' && index === 0) return;
    if (direction === 'down' && index === steps.length - 1) return;

    const newSteps = [...steps];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    [newSteps[index], newSteps[targetIndex]] = [newSteps[targetIndex], newSteps[index]];
    setSteps(newSteps);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    try {
      await updateWorkout.mutateAsync({
        id: workout.id,
        data: {
          name: name.trim(),
          workout_type: workoutType,
          notes: notes.trim() || undefined,
          structure: steps.length > 0 ? steps : undefined,
        },
      });
      onSuccess();
    } catch (error) {
      console.error('Failed to update workout:', error);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-2xl p-6 max-h-[90vh] flex flex-col">
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
          <Edit3 className="w-5 h-5 text-cyan" />
          워크아웃 편집
        </h2>
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto space-y-4">
          {/* Basic Info */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-muted mb-1">이름</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="input w-full"
                placeholder="예: 5km 템포런"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-muted mb-1">유형</label>
              <select
                value={workoutType}
                onChange={(e) => setWorkoutType(e.target.value)}
                className="input w-full"
              >
                {workoutTypes.map((type) => (
                  <option key={type} value={type}>
                    {getWorkoutTypeIcon(type)} {getWorkoutTypeLabel(type)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm text-muted mb-1">메모</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="input w-full h-16"
              placeholder="워크아웃 설명..."
            />
          </div>

          {/* Steps Editor */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-muted">워크아웃 단계</label>
              <button
                type="button"
                onClick={handleAddStep}
                className="text-xs text-cyan hover:text-cyan/80 flex items-center gap-1"
              >
                <Plus className="w-3 h-3" />
                단계 추가
              </button>
            </div>

            {steps.length === 0 ? (
              <div className="border border-dashed border-[var(--color-border)] rounded-lg p-4 text-center text-muted text-sm">
                워크아웃 단계가 없습니다. 단계를 추가하여 구조화된 훈련을 만들어보세요.
              </div>
            ) : (
              <div className="space-y-2">
                {steps.map((step, index) => (
                  <div
                    key={index}
                    className="border border-[var(--color-border)] rounded-lg p-3 bg-[var(--color-bg-tertiary)]/30"
                  >
                    <div className="flex items-start gap-2">
                      {/* Drag Handle & Order */}
                      <div className="flex flex-col items-center gap-1 pt-1">
                        <button
                          type="button"
                          onClick={() => handleMoveStep(index, 'up')}
                          disabled={index === 0}
                          className="p-0.5 hover:bg-[var(--color-bg-tertiary)] rounded disabled:opacity-30"
                        >
                          <ChevronRight className="w-3 h-3 -rotate-90" />
                        </button>
                        <span className="text-[10px] text-muted font-mono">{index + 1}</span>
                        <button
                          type="button"
                          onClick={() => handleMoveStep(index, 'down')}
                          disabled={index === steps.length - 1}
                          className="p-0.5 hover:bg-[var(--color-bg-tertiary)] rounded disabled:opacity-30"
                        >
                          <ChevronRight className="w-3 h-3 rotate-90" />
                        </button>
                      </div>

                      {/* Step Content */}
                      <div className="flex-1 grid grid-cols-2 sm:grid-cols-4 gap-2">
                        <div>
                          <label className="text-[10px] text-muted">유형</label>
                          <select
                            value={step.type}
                            onChange={(e) => handleUpdateStep(index, 'type', e.target.value)}
                            className="input w-full text-xs py-1"
                          >
                            {stepTypes.map((type) => (
                              <option key={type} value={type}>
                                {getStepTypeLabel(type)}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="text-[10px] text-muted">시간 (분)</label>
                          <input
                            type="number"
                            value={step.duration_minutes || ''}
                            onChange={(e) =>
                              handleUpdateStep(index, 'duration_minutes', e.target.value ? Number(e.target.value) : null)
                            }
                            className="input w-full text-xs py-1"
                            placeholder="-"
                            min="0"
                            step="0.5"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-muted">거리 (km)</label>
                          <input
                            type="number"
                            value={step.distance_km || ''}
                            onChange={(e) =>
                              handleUpdateStep(index, 'distance_km', e.target.value ? Number(e.target.value) : null)
                            }
                            className="input w-full text-xs py-1"
                            placeholder="-"
                            min="0"
                            step="0.1"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-muted">목표 페이스</label>
                          <input
                            type="text"
                            value={step.target_pace || ''}
                            onChange={(e) =>
                              handleUpdateStep(index, 'target_pace', e.target.value || null)
                            }
                            className="input w-full text-xs py-1"
                            placeholder="예: 5:00"
                          />
                        </div>
                        <div className="col-span-2 sm:col-span-3">
                          <label className="text-[10px] text-muted">설명</label>
                          <input
                            type="text"
                            value={step.description || ''}
                            onChange={(e) =>
                              handleUpdateStep(index, 'description', e.target.value || null)
                            }
                            className="input w-full text-xs py-1"
                            placeholder="단계 설명..."
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-muted">HR Zone</label>
                          <select
                            value={step.target_hr_zone || ''}
                            onChange={(e) =>
                              handleUpdateStep(index, 'target_hr_zone', e.target.value ? Number(e.target.value) : null)
                            }
                            className="input w-full text-xs py-1"
                          >
                            <option value="">-</option>
                            {[1, 2, 3, 4, 5].map((zone) => (
                              <option key={zone} value={zone}>
                                Zone {zone}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>

                      {/* Delete Button */}
                      <button
                        type="button"
                        onClick={() => handleDeleteStep(index)}
                        className="p-1 text-red-400 hover:bg-red-500/10 rounded"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>

                    {/* Step Type Indicator */}
                    <div className="mt-2 flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${getStepTypeColor(step.type)}`} />
                      <span className="text-[10px] text-muted">
                        {getStepTypeLabel(step.type)}
                        {step.duration_minutes && ` · ${step.duration_minutes}분`}
                        {step.distance_km && ` · ${step.distance_km}km`}
                        {step.target_pace && ` @ ${step.target_pace}/km`}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Garmin Info */}
          {workout.garmin_workout_id && (
            <div className="text-xs text-muted bg-[var(--color-bg-tertiary)] p-3 rounded-lg flex items-center gap-2">
              <Check className="w-4 h-4 text-green-500" />
              Garmin Connect에서 가져온 워크아웃입니다. (ID: {workout.garmin_workout_id})
            </div>
          )}
        </form>

        {/* Actions */}
        <div className="flex gap-2 pt-4 border-t border-[var(--color-border)] mt-4">
          <button type="button" onClick={onClose} className="btn btn-secondary flex-1">
            취소
          </button>
          <button
            onClick={handleSubmit}
            className="btn btn-primary flex-1"
            disabled={updateWorkout.isPending}
          >
            {updateWorkout.isPending ? '저장 중...' : '저장'}
          </button>
        </div>
      </div>
    </div>
  );
}

// Schedule Form Modal
function ScheduleForm({
  workouts,
  onClose,
  onSuccess,
}: {
  workouts: Workout[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [workoutId, setWorkoutId] = useState<number | null>(workouts[0]?.id || null);
  const [scheduledDate, setScheduledDate] = useState(formatDateForInput(new Date()));
  const createSchedule = useCreateSchedule();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!workoutId) return;

    try {
      await createSchedule.mutateAsync({
        workout_id: workoutId,
        scheduled_date: scheduledDate,
      });
      onSuccess();
    } catch (error) {
      console.error('Failed to create schedule:', error);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-md p-6">
        <h2 className="text-lg font-bold mb-4">워크아웃 예약</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-muted mb-1">워크아웃</label>
            <select
              value={workoutId || ''}
              onChange={(e) => setWorkoutId(Number(e.target.value))}
              className="input w-full"
              required
            >
              <option value="">선택하세요</option>
              {workouts.map((workout) => (
                <option key={workout.id} value={workout.id}>
                  {getWorkoutTypeIcon(workout.workout_type)} {workout.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-muted mb-1">날짜</label>
            <input
              type="date"
              value={scheduledDate}
              onChange={(e) => setScheduledDate(e.target.value)}
              className="input w-full"
              required
            />
          </div>
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn btn-secondary flex-1">
              취소
            </button>
            <button
              type="submit"
              className="btn btn-primary flex-1"
              disabled={createSchedule.isPending || !workoutId}
            >
              {createSchedule.isPending ? '저장 중...' : '예약'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Workout Item Component
function WorkoutItem({
  workout,
  onEdit,
  onDelete,
  onPushToGarmin,
}: {
  workout: Workout;
  onEdit: () => void;
  onDelete: () => void;
  onPushToGarmin: () => void;
}) {
  const [showMenu, setShowMenu] = useState(false);
  const stepCount = workout.structure?.length || 0;

  return (
    <div
      className="card p-3 sm:p-4 hover:border-cyan/30 transition-all cursor-pointer"
      onClick={onEdit}
    >
      <div className="flex items-center gap-3 sm:gap-4">
        {/* Type Badge */}
        <div className={`w-10 h-10 sm:w-12 sm:h-12 rounded-xl ${getWorkoutTypeColor(workout.workout_type)} bg-opacity-20 flex items-center justify-center flex-shrink-0`}>
          <span className="text-xl">{getWorkoutTypeIcon(workout.workout_type)}</span>
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium truncate">{workout.name}</span>
            {workout.garmin_workout_id && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/20 text-green-400">
                Garmin
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1 text-xs text-muted">
            <span className={`px-1.5 py-0.5 rounded ${getWorkoutTypeColor(workout.workout_type)} text-white text-[10px]`}>
              {getWorkoutTypeLabel(workout.workout_type)}
            </span>
            {stepCount > 0 && (
              <span className="text-[10px]">{stepCount}개 단계</span>
            )}
            {workout.notes && (
              <span className="truncate">{workout.notes}</span>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="relative" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => setShowMenu(!showMenu)}
            className="p-2 hover:bg-[var(--color-bg-tertiary)] rounded-lg transition-colors"
          >
            <ChevronRight className={`w-4 h-4 text-muted transition-transform ${showMenu ? 'rotate-90' : ''}`} />
          </button>
          {showMenu && (
            <div className="absolute right-0 top-full mt-1 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg shadow-lg z-10 py-1 min-w-[140px]">
              <button
                onClick={() => {
                  onEdit();
                  setShowMenu(false);
                }}
                className="w-full px-3 py-2 text-left text-sm hover:bg-[var(--color-bg-tertiary)] flex items-center gap-2"
              >
                <Edit3 className="w-4 h-4" />
                편집
              </button>
              {!workout.garmin_workout_id && (
                <button
                  onClick={() => {
                    onPushToGarmin();
                    setShowMenu(false);
                  }}
                  className="w-full px-3 py-2 text-left text-sm hover:bg-[var(--color-bg-tertiary)] flex items-center gap-2"
                >
                  <Upload className="w-4 h-4" />
                  Garmin 전송
                </button>
              )}
              <button
                onClick={() => {
                  onDelete();
                  setShowMenu(false);
                }}
                className="w-full px-3 py-2 text-left text-sm hover:bg-[var(--color-bg-tertiary)] text-red-400 flex items-center gap-2"
              >
                <XCircle className="w-4 h-4" />
                삭제
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Schedule Item Component
function ScheduleItem({
  schedule,
  onStatusUpdate,
  onDelete,
}: {
  schedule: WorkoutSchedule;
  onStatusUpdate: (status: ScheduleStatus) => void;
  onDelete: () => void;
}) {
  const [showMenu, setShowMenu] = useState(false);
  const workout = schedule.workout;

  return (
    <div className="card p-3 sm:p-4 hover:border-cyan/30 transition-all">
      <div className="flex items-center gap-3 sm:gap-4">
        {/* Date */}
        <div className="w-12 text-center flex-shrink-0">
          <div className="text-sm font-mono font-bold">{formatDate(schedule.scheduled_date).split(' ')[0]}</div>
          <div className="text-[10px] text-muted">{formatDate(schedule.scheduled_date).match(/\((.)\)/)?.[1]}</div>
        </div>

        {/* Type Badge */}
        {workout && (
          <div className={`w-8 h-8 sm:w-10 sm:h-10 rounded-lg ${getWorkoutTypeColor(workout.workout_type)} bg-opacity-20 flex items-center justify-center flex-shrink-0`}>
            <span className="text-lg">{getWorkoutTypeIcon(workout.workout_type)}</span>
          </div>
        )}

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="font-medium truncate">{workout?.name || '알 수 없는 워크아웃'}</div>
          <div className="flex items-center gap-2 mt-1">
            <span className={`text-[10px] px-1.5 py-0.5 rounded ${getScheduleStatusColor(schedule.status)}`}>
              {getScheduleStatusLabel(schedule.status)}
            </span>
            {workout && (
              <span className="text-[10px] text-muted">{getWorkoutTypeLabel(workout.workout_type)}</span>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="relative">
          <button
            onClick={() => setShowMenu(!showMenu)}
            className="p-2 hover:bg-[var(--color-bg-tertiary)] rounded-lg transition-colors"
          >
            <ChevronRight className={`w-4 h-4 text-muted transition-transform ${showMenu ? 'rotate-90' : ''}`} />
          </button>
          {showMenu && (
            <div className="absolute right-0 top-full mt-1 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg shadow-lg z-10 py-1 min-w-[140px]">
              {schedule.status === 'scheduled' && (
                <>
                  <button
                    onClick={() => {
                      onStatusUpdate('completed');
                      setShowMenu(false);
                    }}
                    className="w-full px-3 py-2 text-left text-sm hover:bg-[var(--color-bg-tertiary)] flex items-center gap-2 text-green-400"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    완료
                  </button>
                  <button
                    onClick={() => {
                      onStatusUpdate('skipped');
                      setShowMenu(false);
                    }}
                    className="w-full px-3 py-2 text-left text-sm hover:bg-[var(--color-bg-tertiary)] flex items-center gap-2 text-amber"
                  >
                    <SkipForward className="w-4 h-4" />
                    건너뛰기
                  </button>
                </>
              )}
              <button
                onClick={() => {
                  onDelete();
                  setShowMenu(false);
                }}
                className="w-full px-3 py-2 text-left text-sm hover:bg-[var(--color-bg-tertiary)] text-red-400 flex items-center gap-2"
              >
                <XCircle className="w-4 h-4" />
                삭제
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function Workouts() {
  const [showWorkoutForm, setShowWorkoutForm] = useState(false);
  const [showScheduleForm, setShowScheduleForm] = useState(false);
  const [showGarminImport, setShowGarminImport] = useState(false);
  const [editingWorkout, setEditingWorkout] = useState<Workout | null>(null);
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [activeTab, setActiveTab] = useState<'templates' | 'scheduled'>('scheduled');

  const { data: workoutsData, isLoading: workoutsLoading, refetch: refetchWorkouts } = useWorkouts({
    workout_type: typeFilter !== 'all' ? typeFilter : undefined,
  });

  const { data: schedulesData, isLoading: schedulesLoading, refetch: refetchSchedules } = useSchedules({
    status: activeTab === 'scheduled' ? 'scheduled' : undefined,
  });

  const deleteWorkout = useDeleteWorkout();
  const pushToGarmin = usePushToGarmin();
  const updateScheduleStatus = useUpdateScheduleStatus();
  const deleteSchedule = useDeleteSchedule();

  const handleWorkoutFormSuccess = () => {
    setShowWorkoutForm(false);
    refetchWorkouts();
  };

  const handleScheduleFormSuccess = () => {
    setShowScheduleForm(false);
    refetchSchedules();
  };

  const handleGarminImportSuccess = () => {
    setShowGarminImport(false);
    refetchWorkouts();
  };

  const handleEditWorkoutSuccess = () => {
    setEditingWorkout(null);
    refetchWorkouts();
  };

  const handleDeleteWorkout = async (id: number) => {
    if (!confirm('이 워크아웃을 삭제하시겠습니까?')) return;
    try {
      await deleteWorkout.mutateAsync(id);
    } catch (error) {
      console.error('Failed to delete workout:', error);
    }
  };

  const handlePushToGarmin = async (id: number) => {
    try {
      const result = await pushToGarmin.mutateAsync(id);
      alert(result.message);
    } catch (error) {
      console.error('Failed to push to Garmin:', error);
      alert('Garmin 전송에 실패했습니다.');
    }
  };

  const handleUpdateScheduleStatus = async (id: number, status: ScheduleStatus) => {
    try {
      await updateScheduleStatus.mutateAsync({ id, update: { status } });
    } catch (error) {
      console.error('Failed to update schedule status:', error);
    }
  };

  const handleDeleteSchedule = async (id: number) => {
    if (!confirm('이 예약을 삭제하시겠습니까?')) return;
    try {
      await deleteSchedule.mutateAsync(id);
    } catch (error) {
      console.error('Failed to delete schedule:', error);
    }
  };

  const isLoading = workoutsLoading || schedulesLoading;
  const workouts = workoutsData?.items || [];
  const schedules = schedulesData?.items || [];

  // Filter schedules to show upcoming ones first
  const sortedSchedules = [...schedules].sort((a, b) =>
    new Date(a.scheduled_date).getTime() - new Date(b.scheduled_date).getTime()
  );

  // Stats
  const scheduledCount = schedules.filter(s => s.status === 'scheduled').length;
  const completedCount = schedules.filter(s => s.status === 'completed').length;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-cyan animate-pulse">워크아웃 불러오는 중...</div>
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-display font-bold">워크아웃</h1>
          <p className="text-muted text-sm mt-1">
            훈련 계획 및 스케줄 관리
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowGarminImport(true)}
            className="btn btn-secondary flex items-center gap-2"
            title="Garmin에서 워크아웃 가져오기"
          >
            <Download className="w-4 h-4" />
            <span className="hidden sm:inline">Garmin</span>
          </button>
          <button
            onClick={() => setShowScheduleForm(true)}
            className="btn btn-secondary flex items-center gap-2"
            disabled={workouts.length === 0}
          >
            <Calendar className="w-4 h-4" />
            <span className="hidden sm:inline">예약</span>
          </button>
          <button
            onClick={() => setShowWorkoutForm(true)}
            className="btn btn-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">새 워크아웃</span>
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
        <div className="card p-3 sm:p-4">
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-cyan/10 flex items-center justify-center flex-shrink-0">
              <Target className="w-4 h-4 sm:w-5 sm:h-5 text-cyan" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">템플릿</p>
              <p className="text-lg sm:text-xl font-mono font-bold">{workoutsData?.total || 0}</p>
            </div>
          </div>
        </div>

        <div className="card p-3 sm:p-4">
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-blue-500/10 flex items-center justify-center flex-shrink-0">
              <Calendar className="w-4 h-4 sm:w-5 sm:h-5 text-blue-400" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">예정됨</p>
              <p className="text-lg sm:text-xl font-mono font-bold">{scheduledCount}</p>
            </div>
          </div>
        </div>

        <div className="card p-3 sm:p-4">
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-green-500/10 flex items-center justify-center flex-shrink-0">
              <CheckCircle2 className="w-4 h-4 sm:w-5 sm:h-5 text-green-400" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">완료</p>
              <p className="text-lg sm:text-xl font-mono font-bold">{completedCount}</p>
            </div>
          </div>
        </div>

        <div className="card p-3 sm:p-4">
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-amber/10 flex items-center justify-center flex-shrink-0">
              <Clock className="w-4 h-4 sm:w-5 sm:h-5 text-amber" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">이번 주</p>
              <p className="text-lg sm:text-xl font-mono font-bold">
                {schedules.filter(s => {
                  const scheduleDate = new Date(s.scheduled_date);
                  const now = new Date();
                  const weekStart = new Date(now);
                  weekStart.setDate(now.getDate() - now.getDay());
                  const weekEnd = new Date(weekStart);
                  weekEnd.setDate(weekStart.getDate() + 6);
                  return scheduleDate >= weekStart && scheduleDate <= weekEnd;
                }).length}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-[var(--color-border)]">
        <button
          onClick={() => setActiveTab('scheduled')}
          className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
            activeTab === 'scheduled'
              ? 'border-cyan text-cyan'
              : 'border-transparent text-muted hover:text-white'
          }`}
        >
          <Play className="w-4 h-4 inline-block mr-1.5" />
          예약된 워크아웃
        </button>
        <button
          onClick={() => setActiveTab('templates')}
          className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
            activeTab === 'templates'
              ? 'border-cyan text-cyan'
              : 'border-transparent text-muted hover:text-white'
          }`}
        >
          <Target className="w-4 h-4 inline-block mr-1.5" />
          워크아웃 템플릿
        </button>
      </div>

      {/* Scheduled Workouts Tab */}
      {activeTab === 'scheduled' && (
        <div className="space-y-3">
          {sortedSchedules.length === 0 ? (
            <div className="card text-center py-12">
              <Calendar className="w-12 h-12 text-muted mx-auto mb-4" />
              <p className="text-muted">예약된 워크아웃이 없습니다</p>
              <button
                onClick={() => setShowScheduleForm(true)}
                className="btn btn-primary mt-4"
                disabled={workouts.length === 0}
              >
                <Plus className="w-4 h-4 mr-2" />
                워크아웃 예약하기
              </button>
              {workouts.length === 0 && (
                <p className="text-xs text-muted mt-2">먼저 워크아웃 템플릿을 생성하세요</p>
              )}
            </div>
          ) : (
            sortedSchedules.map((schedule) => (
              <ScheduleItem
                key={schedule.id}
                schedule={schedule}
                onStatusUpdate={(status) => handleUpdateScheduleStatus(schedule.id, status)}
                onDelete={() => handleDeleteSchedule(schedule.id)}
              />
            ))
          )}
        </div>
      )}

      {/* Workout Templates Tab */}
      {activeTab === 'templates' && (
        <>
          {/* Filter */}
          <div className="card p-3 sm:p-4">
            <div className="flex items-center gap-2 flex-wrap">
              <Filter className="w-4 h-4 text-muted" />
              <span className="text-sm text-muted">필터:</span>
              {['all', 'easy', 'long', 'tempo', 'interval', 'hills', 'fartlek', 'recovery'].map((type) => (
                <button
                  key={type}
                  onClick={() => setTypeFilter(type)}
                  className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${
                    typeFilter === type
                      ? 'bg-cyan text-white'
                      : 'bg-[var(--color-bg-tertiary)] text-muted hover:text-white'
                  }`}
                >
                  {type === 'all' ? '전체' : `${getWorkoutTypeIcon(type)} ${getWorkoutTypeLabel(type)}`}
                </button>
              ))}
            </div>
          </div>

          {/* Workouts List */}
          <div className="space-y-3">
            {workouts.length === 0 ? (
              <div className="card text-center py-12">
                <Target className="w-12 h-12 text-muted mx-auto mb-4" />
                <p className="text-muted">워크아웃 템플릿이 없습니다</p>
                <button
                  onClick={() => setShowWorkoutForm(true)}
                  className="btn btn-primary mt-4"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  첫 번째 워크아웃 만들기
                </button>
              </div>
            ) : (
              workouts.map((workout) => (
                <WorkoutItem
                  key={workout.id}
                  workout={workout}
                  onEdit={() => setEditingWorkout(workout)}
                  onDelete={() => handleDeleteWorkout(workout.id)}
                  onPushToGarmin={() => handlePushToGarmin(workout.id)}
                />
              ))
            )}
          </div>
        </>
      )}

      {/* Workout Form Modal */}
      {showWorkoutForm && (
        <WorkoutForm
          onClose={() => setShowWorkoutForm(false)}
          onSuccess={handleWorkoutFormSuccess}
        />
      )}

      {/* Schedule Form Modal */}
      {showScheduleForm && workouts.length > 0 && (
        <ScheduleForm
          workouts={workouts}
          onClose={() => setShowScheduleForm(false)}
          onSuccess={handleScheduleFormSuccess}
        />
      )}

      {/* Garmin Import Modal */}
      {showGarminImport && (
        <GarminImportModal
          onClose={() => setShowGarminImport(false)}
          onSuccess={handleGarminImportSuccess}
        />
      )}

      {/* Workout Edit Modal */}
      {editingWorkout && (
        <WorkoutEditModal
          workout={editingWorkout}
          onClose={() => setEditingWorkout(null)}
          onSuccess={handleEditWorkoutSuccess}
        />
      )}
    </div>
  );
}
