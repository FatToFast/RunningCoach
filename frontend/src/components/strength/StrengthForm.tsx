import { useState } from 'react';
import {
  X,
  Plus,
  Trash2,
  Search,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import {
  useSessionTypes,
  useExercisePresets,
  useCreateStrengthSession,
  getSessionTypeLabel,
} from '../../hooks/useStrength';
import type { ExerciseSet, ExercisePreset } from '../../types/api';

interface ExerciseData {
  exercise_name: string;
  is_custom: boolean;
  sets: ExerciseSet[];
  notes?: string;
}

interface StrengthFormProps {
  onClose: () => void;
  onSuccess: () => void;
  initialData?: {
    session_date: string;
    session_type: string;
    session_purpose?: string;
    duration_minutes?: number;
    notes?: string;
    rating?: number;
    exercises: ExerciseData[];
  };
}

export function StrengthForm({ onClose, onSuccess, initialData }: StrengthFormProps) {
  const today = new Date().toISOString().split('T')[0];

  const [sessionDate, setSessionDate] = useState(initialData?.session_date || today);
  const [sessionType, setSessionType] = useState(initialData?.session_type || 'lower');
  const [sessionPurpose, setSessionPurpose] = useState(initialData?.session_purpose || '');
  const [durationMinutes, setDurationMinutes] = useState<number | ''>(initialData?.duration_minutes || '');
  const [notes, setNotes] = useState(initialData?.notes || '');
  const [rating, setRating] = useState<number>(initialData?.rating || 0);
  const [exercises, setExercises] = useState<ExerciseData[]>(initialData?.exercises || []);

  const [searchTerm, setSearchTerm] = useState('');
  const [showPresets, setShowPresets] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string | undefined>(undefined);

  const { data: typesData } = useSessionTypes();
  const { data: presetsData } = useExercisePresets(selectedCategory);
  const createSession = useCreateStrengthSession();

  const filteredPresets = presetsData?.exercises.filter(
    (e) =>
      e.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      e.name_en.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  const handleAddExercise = (preset?: ExercisePreset) => {
    const newExercise: ExerciseData = {
      exercise_name: preset?.name || '',
      is_custom: !preset,
      sets: [{ weight_kg: null, reps: 10, rest_seconds: 60 }],
    };
    setExercises([...exercises, newExercise]);
    setShowPresets(false);
    setSearchTerm('');
  };

  const handleAddCustomExercise = () => {
    if (!searchTerm.trim()) return;
    handleAddExercise({ name: searchTerm.trim(), name_en: searchTerm.trim(), category: 'custom' });
  };

  const handleRemoveExercise = (index: number) => {
    setExercises(exercises.filter((_, i) => i !== index));
  };

  const handleExerciseNameChange = (index: number, name: string) => {
    const updated = [...exercises];
    updated[index].exercise_name = name;
    updated[index].is_custom = true;
    setExercises(updated);
  };

  const handleAddSet = (exerciseIndex: number) => {
    const updated = [...exercises];
    const lastSet = updated[exerciseIndex].sets[updated[exerciseIndex].sets.length - 1];
    updated[exerciseIndex].sets.push({
      weight_kg: lastSet?.weight_kg ?? null,
      reps: lastSet?.reps ?? 10,
      rest_seconds: lastSet?.rest_seconds ?? 60,
    });
    setExercises(updated);
  };

  const handleRemoveSet = (exerciseIndex: number, setIndex: number) => {
    const updated = [...exercises];
    updated[exerciseIndex].sets = updated[exerciseIndex].sets.filter((_, i) => i !== setIndex);
    setExercises(updated);
  };

  const handleSetChange = (
    exerciseIndex: number,
    setIndex: number,
    field: keyof ExerciseSet,
    value: number | null
  ) => {
    const updated = [...exercises];
    updated[exerciseIndex].sets[setIndex] = {
      ...updated[exerciseIndex].sets[setIndex],
      [field]: value,
    };
    setExercises(updated);
  };

  const handleSubmit = async () => {
    if (!sessionDate || !sessionType || exercises.length === 0) {
      alert('날짜, 운동 타입, 최소 1개의 운동을 입력해주세요.');
      return;
    }

    try {
      await createSession.mutateAsync({
        session_date: sessionDate,
        session_type: sessionType,
        session_purpose: sessionPurpose || undefined,
        duration_minutes: durationMinutes || undefined,
        notes: notes || undefined,
        rating: rating || undefined,
        exercises: exercises.filter(e => e.exercise_name.trim()).map(e => ({
          exercise_name: e.exercise_name,
          is_custom: e.is_custom,
          sets: e.sets,
          notes: e.notes,
        })),
      });
      onSuccess();
    } catch {
      alert('저장에 실패했습니다.');
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-[var(--color-bg-secondary)] rounded-xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--color-border)]">
          <h2 className="text-lg font-bold">보강운동 기록</h2>
          <button onClick={onClose} className="p-2 hover:bg-[var(--color-bg-tertiary)] rounded-lg transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Date & Type */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-muted mb-1">날짜</label>
              <input
                type="date"
                value={sessionDate}
                onChange={(e) => setSessionDate(e.target.value)}
                className="w-full px-3 py-2 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-purple-500"
              />
            </div>
            <div>
              <label className="block text-sm text-muted mb-1">운동 부위</label>
              <select
                value={sessionType}
                onChange={(e) => setSessionType(e.target.value)}
                className="w-full px-3 py-2 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-purple-500"
              >
                {typesData?.types.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Purpose & Duration */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-muted mb-1">목적 (선택)</label>
              <select
                value={sessionPurpose}
                onChange={(e) => setSessionPurpose(e.target.value)}
                className="w-full px-3 py-2 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-purple-500"
              >
                <option value="">선택 안함</option>
                {typesData?.purposes.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-muted mb-1">운동 시간 (분)</label>
              <input
                type="number"
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(e.target.value ? parseInt(e.target.value) : '')}
                placeholder="예: 45"
                className="w-full px-3 py-2 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>

          {/* Rating */}
          <div>
            <label className="block text-sm text-muted mb-1">만족도</label>
            <div className="flex gap-2">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  onClick={() => setRating(star === rating ? 0 : star)}
                  className={`text-2xl transition-colors ${
                    star <= rating ? 'text-amber' : 'text-muted hover:text-amber/50'
                  }`}
                >
                  {star <= rating ? '★' : '☆'}
                </button>
              ))}
            </div>
          </div>

          {/* Exercises */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-muted">운동 목록</label>
              <button
                onClick={() => setShowPresets(!showPresets)}
                className="text-sm text-purple-400 hover:text-purple-300 flex items-center gap-1"
              >
                <Plus className="w-4 h-4" />
                운동 추가
              </button>
            </div>

            {/* Preset Selector */}
            {showPresets && (
              <div className="card p-3 mb-4 space-y-3">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
                  <input
                    type="text"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder="운동 검색..."
                    className="w-full pl-10 pr-3 py-2 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-purple-500"
                  />
                </div>

                <div className="flex gap-2 flex-wrap">
                  <button
                    onClick={() => setSelectedCategory(undefined)}
                    className={`px-2 py-1 rounded text-xs ${!selectedCategory ? 'bg-purple-500 text-white' : 'bg-[var(--color-bg-tertiary)] text-muted'}`}
                  >
                    전체
                  </button>
                  {['lower', 'core', 'upper', 'full_body'].map((cat) => (
                    <button
                      key={cat}
                      onClick={() => setSelectedCategory(cat)}
                      className={`px-2 py-1 rounded text-xs ${selectedCategory === cat ? 'bg-purple-500 text-white' : 'bg-[var(--color-bg-tertiary)] text-muted'}`}
                    >
                      {getSessionTypeLabel(cat)}
                    </button>
                  ))}
                </div>

                <div className="max-h-48 overflow-y-auto space-y-1">
                  {filteredPresets.map((preset, i) => (
                    <button
                      key={i}
                      onClick={() => handleAddExercise(preset)}
                      className="w-full text-left px-3 py-2 rounded-lg hover:bg-[var(--color-bg-tertiary)] transition-colors"
                    >
                      <span className="font-medium">{preset.name}</span>
                      <span className="text-xs text-muted ml-2">({preset.name_en})</span>
                    </button>
                  ))}
                  {searchTerm && !filteredPresets.some(p => p.name === searchTerm) && (
                    <button
                      onClick={handleAddCustomExercise}
                      className="w-full text-left px-3 py-2 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 transition-colors text-purple-400"
                    >
                      <Plus className="w-4 h-4 inline mr-2" />
                      "{searchTerm}" 커스텀 운동 추가
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Exercise List */}
            <div className="space-y-3">
              {exercises.map((exercise, exIndex) => (
                <ExerciseItem
                  key={exIndex}
                  exercise={exercise}
                  onNameChange={(name) => handleExerciseNameChange(exIndex, name)}
                  onRemove={() => handleRemoveExercise(exIndex)}
                  onAddSet={() => handleAddSet(exIndex)}
                  onRemoveSet={(setIndex) => handleRemoveSet(exIndex, setIndex)}
                  onSetChange={(setIndex, field, value) => handleSetChange(exIndex, setIndex, field, value)}
                />
              ))}
            </div>

            {exercises.length === 0 && (
              <div className="text-center py-8 text-muted">
                <p>위의 "운동 추가" 버튼을 눌러 운동을 추가하세요</p>
              </div>
            )}
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm text-muted mb-1">메모</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="오늘 운동에 대한 메모..."
              rows={2}
              className="w-full px-3 py-2 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-purple-500 resize-none"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex gap-3 p-4 border-t border-[var(--color-border)]">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-[var(--color-bg-tertiary)] rounded-lg hover:bg-[var(--color-border)] transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleSubmit}
            disabled={createSession.isPending || exercises.length === 0}
            className="flex-1 px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {createSession.isPending ? '저장 중...' : '저장'}
          </button>
        </div>
      </div>
    </div>
  );
}

// Exercise Item Component
interface ExerciseItemProps {
  exercise: ExerciseData;
  onNameChange: (name: string) => void;
  onRemove: () => void;
  onAddSet: () => void;
  onRemoveSet: (setIndex: number) => void;
  onSetChange: (setIndex: number, field: keyof ExerciseSet, value: number | null) => void;
}

function ExerciseItem({
  exercise,
  onNameChange,
  onRemove,
  onAddSet,
  onRemoveSet,
  onSetChange,
}: ExerciseItemProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="card p-3">
      <div className="flex items-center gap-2 mb-2">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1 hover:bg-[var(--color-bg-tertiary)] rounded"
        >
          {collapsed ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
        </button>
        <input
          type="text"
          value={exercise.exercise_name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder="운동명"
          className="flex-1 px-2 py-1 bg-transparent border-b border-[var(--color-border)] focus:outline-none focus:border-purple-500"
        />
        <span className="text-sm text-muted">{exercise.sets.length}세트</span>
        <button
          onClick={onRemove}
          className="p-1 text-red-400 hover:bg-red-500/10 rounded"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {!collapsed && (
        <div className="space-y-2 mt-3">
          {/* Sets Header */}
          <div className="grid grid-cols-4 gap-2 text-xs text-muted px-2">
            <span>세트</span>
            <span>무게 (kg)</span>
            <span>횟수</span>
            <span></span>
          </div>

          {/* Sets */}
          {exercise.sets.map((set, setIndex) => (
            <div key={setIndex} className="grid grid-cols-4 gap-2 items-center">
              <span className="text-sm text-muted pl-2">{setIndex + 1}</span>
              <input
                type="number"
                value={set.weight_kg ?? ''}
                onChange={(e) =>
                  onSetChange(setIndex, 'weight_kg', e.target.value ? parseFloat(e.target.value) : null)
                }
                placeholder="맨몸"
                className="px-2 py-1.5 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded text-sm focus:outline-none focus:border-purple-500"
              />
              <input
                type="number"
                value={set.reps}
                onChange={(e) =>
                  onSetChange(setIndex, 'reps', parseInt(e.target.value) || 1)
                }
                min={1}
                className="px-2 py-1.5 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded text-sm focus:outline-none focus:border-purple-500"
              />
              <button
                onClick={() => onRemoveSet(setIndex)}
                disabled={exercise.sets.length === 1}
                className="p-1.5 text-muted hover:text-red-400 hover:bg-red-500/10 rounded disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}

          {/* Add Set Button */}
          <button
            onClick={onAddSet}
            className="w-full py-1.5 text-sm text-purple-400 hover:bg-purple-500/10 rounded-lg transition-colors flex items-center justify-center gap-1"
          >
            <Plus className="w-3 h-3" />
            세트 추가
          </button>
        </div>
      )}
    </div>
  );
}
