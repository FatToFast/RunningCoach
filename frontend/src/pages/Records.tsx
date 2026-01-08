import { useState } from 'react';
import { Trophy, Clock, Route, TrendingUp, Calendar, Zap, Flag, Edit2, X, Check, MapPin, Plus, Download } from 'lucide-react';
import { usePersonalRecords } from '../hooks/useDashboard';
import { useRaces, useUpdateRace, useCreateRace, useGarminEvents, useImportGarminEvents } from '../hooks/useRaces';
import type { Race, RaceUpdate, RaceCreate } from '../api/races';
import type { PersonalRecord } from '../types/api';

function formatTime(seconds: number) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

function formatPace(seconds: number) {
  // 초단위로 반올림
  const totalSec = Math.round(seconds);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${sec.toString().padStart(2, '0')}`;
}

function formatDistance(meters: number) {
  if (meters >= 1000) {
    return `${(meters / 1000).toFixed(2)} km`;
  }
  return `${meters} m`;
}

function formatDate(dateStr: string) {
  const date = new Date(dateStr);
  return date.toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function parseTimeToSeconds(timeStr: string): number | null {
  // Parse formats: "HH:MM:SS", "H:MM:SS", "MM:SS", "M:SS"
  const parts = timeStr.split(':').map((p) => parseInt(p, 10));
  if (parts.some(isNaN)) return null;

  if (parts.length === 3) {
    // HH:MM:SS
    return parts[0] * 3600 + parts[1] * 60 + parts[2];
  } else if (parts.length === 2) {
    // MM:SS
    return parts[0] * 60 + parts[1];
  }
  return null;
}

function getDDayText(daysUntil: number): string {
  if (daysUntil === 0) return 'D-DAY';
  if (daysUntil > 0) return `D-${daysUntil}`;
  return `D+${Math.abs(daysUntil)}`;
}

function getDDayColor(daysUntil: number): string {
  if (daysUntil === 0) return 'text-red';
  if (daysUntil <= 7) return 'text-amber';
  if (daysUntil <= 30) return 'text-cyan';
  return 'text-muted';
}

// Record Edit Modal Component (for Personal Record to Race conversion)
interface RecordEditModalProps {
  record: PersonalRecord;
  existingRace: Race | null;
  onClose: () => void;
  onSave: (raceId: number | null, race: RaceUpdate | RaceCreate) => void;
  isSaving: boolean;
}

function RecordEditModal({ record, existingRace, onClose, onSave, isSaving }: RecordEditModalProps) {
  const [name, setName] = useState(existingRace?.name || record.category || '');
  const [raceDate, setRaceDate] = useState(
    existingRace?.race_date || record.achieved_date || new Date().toISOString().split('T')[0]
  );
  const [resultTime, setResultTime] = useState(
    existingRace?.result_time_seconds ? formatTime(existingRace.result_time_seconds) : formatTime(record.value)
  );
  const [location, setLocation] = useState(existingRace?.location || '');
  const [resultNotes, setResultNotes] = useState(existingRace?.result_notes || '');

  // Get distance from category
  const getDistanceFromCategory = (category: string): { km: number | null; label: string | null } => {
    if (category.includes('5K') || category.includes('5k')) {
      return { km: 5, label: '5K' };
    } else if (category.includes('10K') || category.includes('10k')) {
      return { km: 10, label: '10K' };
    } else if (category.includes('Half') || category.includes('하프')) {
      return { km: 21.0975, label: 'Half Marathon' };
    } else if (category.includes('Marathon') || category.includes('마라톤') || category.includes('풀')) {
      return { km: 42.195, label: 'Marathon' };
    }
    return { km: null, label: null };
  };

  const { km, label } = getDistanceFromCategory(record.category);

  const handleSave = () => {
    const resultSeconds = resultTime ? parseTimeToSeconds(resultTime) : null;
    const distanceInfo = getDistanceFromCategory(record.category);

    if (existingRace) {
      // Update existing race
      onSave(existingRace.id, {
        name,
        race_date: raceDate,
        result_time_seconds: resultSeconds,
        result_notes: resultNotes || null,
        location: location || null,
        is_completed: true,
      });
    } else {
      // Create new race
      onSave(null, {
        name,
        race_date: raceDate,
        distance_km: distanceInfo.km,
        distance_label: distanceInfo.label,
        location: location || null,
        result_time_seconds: resultSeconds,
        result_notes: resultNotes || null,
        is_completed: true,
      });
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="card max-w-md w-full">
        <div className="flex items-center justify-between mb-6">
          <h3 className="font-display text-lg font-semibold">대회 기록 입력/수정</h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-[var(--color-surface-elevated)] rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          {/* Race Name */}
          <div>
            <label className="block text-sm text-muted mb-1">대회명 *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-cyan"
              placeholder="예: 2024 서울마라톤"
            />
          </div>

          {/* Race Date */}
          <div>
            <label className="block text-sm text-muted mb-1">대회 날짜 *</label>
            <input
              type="date"
              value={raceDate}
              onChange={(e) => setRaceDate(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-cyan"
            />
          </div>

          {/* Location */}
          <div>
            <label className="block text-sm text-muted mb-1">장소 (선택)</label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-cyan"
              placeholder="예: 서울시청 앞"
            />
          </div>

          {/* Official Time */}
          <div>
            <label className="block text-sm text-muted mb-1">
              공식 기록 (시:분:초 또는 분:초) *
            </label>
            <input
              type="text"
              value={resultTime}
              onChange={(e) => setResultTime(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-cyan font-mono"
              placeholder="예: 3:45:30 또는 45:30"
            />
            <p className="text-xs text-muted mt-1">
              가민 기록({formatTime(record.value)})과 다를 경우 공식 기록을 입력하세요
            </p>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm text-muted mb-1">메모 (선택)</label>
            <textarea
              value={resultNotes}
              onChange={(e) => setResultNotes(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-cyan resize-none"
              rows={2}
              placeholder="예: PB 달성! 날씨 좋았음"
            />
          </div>

          {/* Distance Info (read-only) */}
          {label && (
            <div className="text-sm text-muted border-t border-[var(--color-border)] pt-4">
              <div className="flex items-center gap-2">
                <Route className="w-4 h-4" />
                <span>{label}</span>
                {km && (
                  <>
                    <span className="text-[var(--color-border)]">•</span>
                    <span>{km} km</span>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-[var(--color-border)] rounded-lg hover:bg-[var(--color-surface-elevated)] transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving || !name.trim() || !raceDate || !resultTime}
            className="flex-1 px-4 py-2 bg-cyan text-black rounded-lg hover:bg-cyan/80 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isSaving ? (
              <span className="animate-pulse">저장 중...</span>
            ) : (
              <>
                <Check className="w-4 h-4" />
                저장
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// Race Edit Modal Component
interface RaceEditModalProps {
  race: Race;
  onClose: () => void;
  onSave: (raceId: number, update: RaceUpdate) => void;
  isSaving: boolean;
}

function RaceEditModal({ race, onClose, onSave, isSaving }: RaceEditModalProps) {
  const [name, setName] = useState(race.name);
  const [resultTime, setResultTime] = useState(
    race.result_time_seconds ? formatTime(race.result_time_seconds) : ''
  );
  const [resultNotes, setResultNotes] = useState(race.result_notes || '');

  const handleSave = () => {
    const resultSeconds = resultTime ? parseTimeToSeconds(resultTime) : null;

    onSave(race.id, {
      name,
      result_time_seconds: resultSeconds,
      result_notes: resultNotes || null,
      is_completed: resultSeconds ? true : race.is_completed,
    });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="card max-w-md w-full">
        <div className="flex items-center justify-between mb-6">
          <h3 className="font-display text-lg font-semibold">대회 기록 수정</h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-[var(--color-surface-elevated)] rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          {/* Race Name */}
          <div>
            <label className="block text-sm text-muted mb-1">대회명</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-cyan"
              placeholder="예: 2024 서울마라톤"
            />
          </div>

          {/* Official Time */}
          <div>
            <label className="block text-sm text-muted mb-1">
              공식 기록 (시:분:초 또는 분:초)
            </label>
            <input
              type="text"
              value={resultTime}
              onChange={(e) => setResultTime(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-cyan font-mono"
              placeholder="예: 3:45:30 또는 45:30"
            />
            <p className="text-xs text-muted mt-1">
              가민 기록과 다를 경우 공식 기록을 입력하세요
            </p>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-sm text-muted mb-1">메모 (선택)</label>
            <textarea
              value={resultNotes}
              onChange={(e) => setResultNotes(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-cyan resize-none"
              rows={2}
              placeholder="예: PB 달성! 날씨 좋았음"
            />
          </div>

          {/* Race Info (read-only) */}
          <div className="text-sm text-muted border-t border-[var(--color-border)] pt-4">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4" />
              <span>{formatDate(race.race_date)}</span>
              {race.distance_label && (
                <>
                  <span className="text-[var(--color-border)]">•</span>
                  <span>{race.distance_label}</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-[var(--color-border)] rounded-lg hover:bg-[var(--color-surface-elevated)] transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving || !name.trim()}
            className="flex-1 px-4 py-2 bg-cyan text-black rounded-lg hover:bg-cyan/80 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isSaving ? (
              <span className="animate-pulse">저장 중...</span>
            ) : (
              <>
                <Check className="w-4 h-4" />
                저장
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// New Race Modal Component (for adding upcoming races)
interface NewRaceModalProps {
  onClose: () => void;
  onSave: (race: RaceCreate) => void;
  isSaving: boolean;
}

function NewRaceModal({ onClose, onSave, isSaving }: NewRaceModalProps) {
  const [name, setName] = useState('');
  const [raceDate, setRaceDate] = useState('');
  const [distanceKm, setDistanceKm] = useState('');
  const [distanceLabel, setDistanceLabel] = useState('');
  const [location, setLocation] = useState('');
  const [goalTime, setGoalTime] = useState('');
  const [isPrimary, setIsPrimary] = useState(false);

  const distancePresets = [
    { label: '5K', km: 5 },
    { label: '10K', km: 10 },
    { label: 'Half Marathon', km: 21.0975 },
    { label: 'Marathon', km: 42.195 },
  ];

  const handlePresetClick = (preset: { label: string; km: number }) => {
    setDistanceLabel(preset.label);
    setDistanceKm(preset.km.toString());
  };

  const handleSave = () => {
    const goalSeconds = goalTime ? parseTimeToSeconds(goalTime) : null;

    onSave({
      name,
      race_date: raceDate,
      distance_km: parseFloat(distanceKm) || null,
      distance_label: distanceLabel || null,
      location: location || null,
      goal_time_seconds: goalSeconds,
      is_primary: isPrimary,
    });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="card max-w-md w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h3 className="font-display text-lg font-semibold">새 대회 추가</h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-[var(--color-surface-elevated)] rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          {/* Race Name */}
          <div>
            <label className="block text-sm text-muted mb-1">대회명 *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-cyan"
              placeholder="예: 2025 서울마라톤"
            />
          </div>

          {/* Race Date */}
          <div>
            <label className="block text-sm text-muted mb-1">대회 날짜 *</label>
            <input
              type="date"
              value={raceDate}
              onChange={(e) => setRaceDate(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-cyan"
            />
          </div>

          {/* Distance Presets */}
          <div>
            <label className="block text-sm text-muted mb-2">거리</label>
            <div className="flex flex-wrap gap-2 mb-2">
              {distancePresets.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => handlePresetClick(preset)}
                  className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                    distanceLabel === preset.label
                      ? 'border-cyan bg-cyan/10 text-cyan'
                      : 'border-[var(--color-border)] hover:border-cyan/50'
                  }`}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                type="number"
                value={distanceKm}
                onChange={(e) => setDistanceKm(e.target.value)}
                className="flex-1 px-3 py-2 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-cyan"
                placeholder="거리 (km)"
                step="0.1"
              />
              <input
                type="text"
                value={distanceLabel}
                onChange={(e) => setDistanceLabel(e.target.value)}
                className="flex-1 px-3 py-2 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-cyan"
                placeholder="라벨 (예: Half)"
              />
            </div>
          </div>

          {/* Location */}
          <div>
            <label className="block text-sm text-muted mb-1">장소 (선택)</label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-cyan"
              placeholder="예: 서울시청 앞"
            />
          </div>

          {/* Goal Time */}
          <div>
            <label className="block text-sm text-muted mb-1">목표 기록 (선택)</label>
            <input
              type="text"
              value={goalTime}
              onChange={(e) => setGoalTime(e.target.value)}
              className="w-full px-3 py-2 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-cyan font-mono"
              placeholder="예: 1:45:00 또는 45:00"
            />
          </div>

          {/* Primary Race Checkbox */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is-primary"
              checked={isPrimary}
              onChange={(e) => setIsPrimary(e.target.checked)}
              className="w-4 h-4 rounded border-[var(--color-border)] text-cyan focus:ring-cyan"
            />
            <label htmlFor="is-primary" className="text-sm">
              주요 대회로 설정 (대시보드에 표시)
            </label>
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-[var(--color-border)] rounded-lg hover:bg-[var(--color-surface-elevated)] transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving || !name.trim() || !raceDate}
            className="flex-1 px-4 py-2 bg-cyan text-black rounded-lg hover:bg-cyan/80 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isSaving ? (
              <span className="animate-pulse">저장 중...</span>
            ) : (
              <>
                <Check className="w-4 h-4" />
                추가
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// Race Card Component for upcoming races
interface RaceCardProps {
  race: Race;
  onEdit: (race: Race) => void;
  variant: 'upcoming' | 'completed';
}

function RaceCard({ race, onEdit, variant }: RaceCardProps) {
  const isUpcoming = variant === 'upcoming';

  return (
    <div
      className={`card group hover:border-[var(--color-accent-cyan)] transition-all ${
        race.is_primary && isUpcoming ? 'border-amber' : ''
      }`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div
            className={`w-10 h-10 rounded-lg flex items-center justify-center ${
              isUpcoming ? 'bg-amber/20' : 'bg-green/20'
            }`}
          >
            <Flag className={`w-5 h-5 ${isUpcoming ? 'text-amber' : 'text-green'}`} />
          </div>
          <div>
            <h3 className="font-display font-semibold">{race.name}</h3>
            <p className="text-muted text-sm">{race.distance_label || `${race.distance_km}km`}</p>
          </div>
        </div>
        <button
          onClick={() => onEdit(race)}
          className="p-2 opacity-0 group-hover:opacity-100 hover:bg-[var(--color-surface-elevated)] rounded transition-all"
          title="수정"
        >
          <Edit2 className="w-4 h-4 text-muted" />
        </button>
      </div>

      {/* D-day or Result Time */}
      <div className="mb-3">
        {isUpcoming ? (
          <div className={`stat-value text-3xl ${getDDayColor(race.days_until)}`}>
            {getDDayText(race.days_until)}
          </div>
        ) : (
          <div className="stat-value text-3xl text-green">
            {race.result_time_seconds ? formatTime(race.result_time_seconds) : '기록 없음'}
          </div>
        )}
      </div>

      {/* Date and Location */}
      <div className="flex items-center gap-4 text-sm text-muted">
        <div className="flex items-center gap-1">
          <Calendar className="w-4 h-4" />
          {formatDate(race.race_date)}
        </div>
        {race.location && (
          <div className="flex items-center gap-1">
            <MapPin className="w-4 h-4" />
            {race.location}
          </div>
        )}
      </div>

      {/* Goal Time for upcoming */}
      {isUpcoming && race.goal_time_seconds && (
        <div className="mt-3 pt-3 border-t border-[var(--color-border)]">
          <div className="text-xs text-muted">
            목표 기록:{' '}
            <span className="font-mono text-cyan">{formatTime(race.goal_time_seconds)}</span>
          </div>
        </div>
      )}

      {/* Result Notes for completed */}
      {!isUpcoming && race.result_notes && (
        <div className="mt-3 pt-3 border-t border-[var(--color-border)]">
          <div className="text-xs text-muted">{race.result_notes}</div>
        </div>
      )}

      {/* Primary badge */}
      {race.is_primary && isUpcoming && (
        <div className="absolute top-2 right-2">
          <span className="px-2 py-0.5 bg-amber/20 text-amber text-xs rounded-full">
            주요 대회
          </span>
        </div>
      )}
    </div>
  );
}

interface RecordCardProps {
  category: string;
  value: number;
  unit: string;
  activityName: string | null;
  achievedDate: string;
  previousBest?: number | null;
  improvementPct?: number | null;
  formatValue?: (value: number) => string;
  icon: React.ElementType;
  accentColor: string;
  onEdit?: () => void;
  showEdit?: boolean;
}

function RecordCard({
  category,
  value,
  unit,
  activityName,
  achievedDate,
  previousBest,
  improvementPct,
  formatValue,
  icon: Icon,
  accentColor,
  onEdit,
  showEdit = false,
}: RecordCardProps) {
  const displayValue = formatValue ? formatValue(value) : value.toString();

  return (
    <div className="card group hover:border-[var(--color-accent-cyan)] transition-all">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: `${accentColor}20` }}
          >
            <Icon className="w-5 h-5" style={{ color: accentColor }} />
          </div>
          <div>
            <h3 className="font-display font-semibold">{category}</h3>
            {activityName && <p className="text-muted text-sm">{activityName}</p>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {showEdit && onEdit && (
            <button
              onClick={onEdit}
              className="p-2 opacity-0 group-hover:opacity-100 hover:bg-[var(--color-surface-elevated)] rounded transition-all"
              title="대회 기록 수정"
            >
              <Edit2 className="w-4 h-4 text-muted" />
            </button>
          )}
          <Trophy className="w-5 h-5 text-amber opacity-80" />
        </div>
      </div>

      <div className="mb-4">
        <div className="stat-value text-3xl" style={{ color: accentColor }}>
          {displayValue}
        </div>
        {unit && <div className="text-muted text-sm mt-1">{unit}</div>}
      </div>

      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-1 text-muted">
          <Calendar className="w-4 h-4" />
          {formatDate(achievedDate)}
        </div>
        {improvementPct != null && improvementPct > 0 && (
          <div className="flex items-center gap-1 text-green">
            <TrendingUp className="w-4 h-4" />
            <span className="font-mono">+{improvementPct.toFixed(1)}%</span>
          </div>
        )}
      </div>

      {previousBest != null && (
        <div className="mt-3 pt-3 border-t border-[var(--color-border)]">
          <div className="text-xs text-muted">
            Previous best:{' '}
            <span className="font-mono text-[var(--color-text-secondary)]">
              {formatValue ? formatValue(previousBest) : previousBest}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

// Garmin Events Import Modal Component
interface GarminEventsImportModalProps {
  onClose: () => void;
}

function GarminEventsImportModal({ onClose }: GarminEventsImportModalProps) {
  const [selectedEvents, setSelectedEvents] = useState<Set<string>>(new Set());
  const importEventsMutation = useImportGarminEvents();

  // Wide date range: 1 year ago to 2 years from now
  // Backend will automatically split into 90-day chunks
  const today = new Date();
  const startDate = new Date(today);
  startDate.setFullYear(startDate.getFullYear() - 1); // 1 year ago
  startDate.setHours(0, 0, 0, 0);
  const endDate = new Date(today);
  endDate.setFullYear(endDate.getFullYear() + 2); // 2 years from now
  endDate.setHours(23, 59, 59, 999);

  const startDateStr = startDate.toISOString().split('T')[0];
  const endDateStr = endDate.toISOString().split('T')[0];

  const { data: eventsResponse, isLoading, error } = useGarminEvents(startDateStr, endDateStr);

  // Use all events (no search filter)
  const filteredEvents = eventsResponse?.events || [];

  const toggleEvent = (eventId: string) => {
    const newSelected = new Set(selectedEvents);
    if (newSelected.has(eventId)) {
      newSelected.delete(eventId);
    } else {
      newSelected.add(eventId);
    }
    setSelectedEvents(newSelected);
  };

  const toggleAll = () => {
    if (selectedEvents.size === filteredEvents.length) {
      setSelectedEvents(new Set());
    } else {
      setSelectedEvents(new Set(filteredEvents.map((e, idx) => `${e.event_date}-${idx}`)));
    }
  };

  const handleImport = async () => {
    if (selectedEvents.size === 0) {
      alert('가져올 이벤트를 선택해주세요.');
      return;
    }

    const selectedIndices = Array.from(selectedEvents).map((id) => {
      const parts = id.split('-');
      return parseInt(parts[parts.length - 1]);
    });

    const eventsToImport = selectedIndices.map((idx) => filteredEvents[idx]);

    try {
      // Create races from selected events
      // We'll need to modify the API to accept specific events
      // For now, we'll use the existing endpoint but filter on the backend
      // TODO: Create a new endpoint that accepts event IDs
      
      const races = await importEventsMutation.mutateAsync({
        startDate: startDateStr,
        endDate: endDateStr,
        filterRacesOnly: false, // We're already filtering by selection
        selectedEventDates: eventsToImport.map((e) => e.event_date),
        selectedEventNames: eventsToImport.map((e) => e.name),
      });

      alert(`${races.length}개의 대회가 가져와졌습니다.`);
      onClose();
    } catch (error) {
      console.error('Failed to import Garmin events:', error);
      alert('Garmin 이벤트 가져오기에 실패했습니다. Garmin 계정이 연결되어 있는지 확인하세요.');
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="card max-w-4xl w-full max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between mb-6">
          <h3 className="font-display text-lg font-semibold">Garmin 이벤트 가져오기</h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-[var(--color-surface-elevated)] rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Events List */}
        <div className="flex-1 overflow-y-auto mb-4">
          {isLoading ? (
            <div className="text-center py-8 text-muted">이벤트를 불러오는 중...</div>
          ) : error ? (
            <div className="text-center py-8 text-red">
              이벤트를 불러오는데 실패했습니다. Garmin 계정이 연결되어 있는지 확인하세요.
              <div className="text-xs mt-2">{(error as Error)?.message || String(error)}</div>
            </div>
          ) : !eventsResponse?.events || eventsResponse.events.length === 0 ? (
            <div className="text-center py-8 text-muted">
              이벤트가 없습니다.
              <div className="text-xs mt-2">
                {startDateStr} ~ {endDateStr} 범위에 등록된 Garmin 이벤트가 없습니다.
              </div>
            </div>
          ) : filteredEvents.length === 0 ? (
            <div className="text-center py-8 text-muted">
              이벤트가 없습니다.
              <div className="text-xs mt-2">
                {startDateStr} ~ {endDateStr} 범위에 등록된 Garmin 이벤트가 없습니다.
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              {/* Select All */}
              <div className="flex items-center gap-2 p-2 border-b border-[var(--color-border)]">
                <input
                  type="checkbox"
                  checked={filteredEvents.length > 0 && selectedEvents.size === filteredEvents.length}
                  onChange={toggleAll}
                  className="w-4 h-4 rounded border-[var(--color-border)] text-cyan focus:ring-cyan"
                />
                <span className="text-sm text-muted">
                  전체 선택 ({selectedEvents.size}/{filteredEvents.length})
                </span>
              </div>

              {/* Event Items */}
              {filteredEvents.map((event, idx) => {
                const eventId = `${event.event_date}-${idx}`;
                const isSelected = selectedEvents.has(eventId);
                const eventDate = new Date(event.event_date);
                const isPast = eventDate < today;

                return (
                  <div
                    key={eventId}
                    className={`p-3 rounded-lg border transition-colors cursor-pointer ${
                      isSelected
                        ? 'border-cyan bg-cyan/10'
                        : 'border-[var(--color-border)] hover:border-cyan/50'
                    }`}
                    onClick={() => toggleEvent(eventId)}
                  >
                    <div className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleEvent(eventId)}
                        onClick={(e) => e.stopPropagation()}
                        className="mt-1 w-4 h-4 rounded border-[var(--color-border)] text-cyan focus:ring-cyan"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-semibold truncate">{event.name}</h4>
                          {isPast && (
                            <span className="px-2 py-0.5 bg-muted/20 text-muted text-xs rounded">
                              과거
                            </span>
                          )}
                        </div>
                        <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
                          {event.event_date && (
                            <div className="flex items-center gap-1">
                              <Calendar className="w-3 h-3" />
                              {formatDate(event.event_date)}
                            </div>
                          )}
                          {event.location && (
                            <div className="flex items-center gap-1">
                              <MapPin className="w-3 h-3" />
                              {event.location}
                            </div>
                          )}
                          {(event.distance_label || event.distance_km) && (
                            <div className="flex items-center gap-1">
                              <Route className="w-3 h-3" />
                              {event.distance_label || `${event.distance_km}km`}
                            </div>
                          )}
                          {event.event_type && (
                            <span className="text-xs">{event.event_type}</span>
                          )}
                        </div>
                        {event.notes && (
                          <p className="text-xs text-muted mt-1 line-clamp-2">{event.notes}</p>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between pt-4 border-t border-[var(--color-border)]">
          <div className="text-sm text-muted">
            {selectedEvents.size > 0 && `${selectedEvents.size}개 선택됨`}
          </div>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 border border-[var(--color-border)] rounded-lg hover:bg-[var(--color-surface-elevated)] transition-colors"
            >
              취소
            </button>
            <button
              onClick={handleImport}
              disabled={importEventsMutation.isPending || selectedEvents.size === 0}
              className="px-4 py-2 bg-cyan text-black rounded-lg hover:bg-cyan/80 transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              {importEventsMutation.isPending ? (
                <span className="animate-pulse">가져오는 중...</span>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  선택한 {selectedEvents.size}개 가져오기
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}


export function Records() {
  const { data: records, isLoading, error } = usePersonalRecords('running');
  const { data: racesData } = useRaces(true); // include completed
  const updateRaceMutation = useUpdateRace();
  const createRaceMutation = useCreateRace();
  const [editingRace, setEditingRace] = useState<Race | null>(null);
  const [editingRecord, setEditingRecord] = useState<{ record: PersonalRecord; existingRace: Race | null } | null>(null);
  const [showNewRaceModal, setShowNewRaceModal] = useState(false);
  const [showAddRaceOptions, setShowAddRaceOptions] = useState(false);
  const [showGarminImport, setShowGarminImport] = useState(false);

  // Separate races into upcoming and completed
  const upcomingRaces =
    racesData?.races.filter((r) => !r.is_completed && r.days_until >= 0) || [];
  const completedRaces = racesData?.races.filter((r) => r.is_completed) || [];

  // Find existing race for a record (by distance and date proximity)
  const findRaceForRecord = (record: PersonalRecord): Race | null => {
    if (!racesData) return null;
    
    const recordDate = new Date(record.achieved_date);
    const category = record.category.toLowerCase();
    
    // Get distance from category
    let targetDistance: number | null = null;
    if (category.includes('5k')) targetDistance = 5;
    else if (category.includes('10k')) targetDistance = 10;
    else if (category.includes('half')) targetDistance = 21.0975;
    else if (category.includes('marathon') || category.includes('풀')) targetDistance = 42.195;

    // Find race with matching distance and date (within 7 days)
    return racesData.races.find((race) => {
      if (!race.is_completed || !race.result_time_seconds) return false;
      if (targetDistance && race.distance_km) {
        const distanceMatch = Math.abs(race.distance_km - targetDistance) < 1; // within 1km
        const raceDate = new Date(race.race_date);
        const dateDiff = Math.abs((raceDate.getTime() - recordDate.getTime()) / (1000 * 60 * 60 * 24));
        return distanceMatch && dateDiff <= 7;
      }
      return false;
    }) || null;
  };

  const handleRaceSave = (raceId: number, update: RaceUpdate) => {
    updateRaceMutation.mutate(
      { raceId, race: update },
      {
        onSuccess: () => {
          setEditingRace(null);
          // Invalidate records query to refresh PRs
          // This will be done automatically by the mutation's onSuccess
        },
      }
    );
  };

  const handleRecordSave = (raceId: number | null, raceData: RaceUpdate | RaceCreate) => {
    if (raceId) {
      // Update existing race
      updateRaceMutation.mutate(
        { raceId, race: raceData as RaceUpdate },
        {
          onSuccess: () => {
            setEditingRecord(null);
          },
        }
      );
    } else {
      // Create new race
      createRaceMutation.mutate(raceData as RaceCreate, {
        onSuccess: () => {
          setEditingRecord(null);
        },
      });
    }
  };

  const handleNewRaceSave = (raceData: RaceCreate) => {
    createRaceMutation.mutate(raceData, {
      onSuccess: () => {
        setShowNewRaceModal(false);
      },
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-cyan animate-pulse">Loading records...</div>
      </div>
    );
  }

  if (error || !records) {
    return (
      <div className="card text-center py-12">
        <p className="text-red mb-2">Failed to load records</p>
        <p className="text-muted text-sm">Please check your connection and try again.</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="font-display text-2xl font-bold flex items-center gap-3">
          <Trophy className="w-7 h-7 text-amber" />
          Personal Records
        </h1>
        <p className="text-muted text-sm mt-1">Your best performances</p>
      </div>

      {/* Distance Records */}
      {records.distance_records.length > 0 && (
        <section>
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <Clock className="w-5 h-5 text-cyan" />
            Race Times
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {records.distance_records.map((record) => {
              const existingRace = findRaceForRecord(record);
              // 연결된 레이스가 있고 공식 기록이 있으면 공식 기록 표시
              const displayValue = existingRace?.result_time_seconds ?? record.value;
              const displayName = existingRace?.name ?? record.activity_name;
              return (
                <RecordCard
                  key={record.category}
                  category={record.category}
                  value={displayValue}
                  unit=""
                  activityName={displayName}
                  achievedDate={record.achieved_date}
                  previousBest={record.previous_best}
                  improvementPct={record.improvement_pct}
                  formatValue={formatTime}
                  icon={Clock}
                  accentColor="#00d4ff"
                  showEdit={true}
                  onEdit={() => setEditingRecord({ record, existingRace })}
                />
              );
            })}
          </div>
        </section>
      )}

      {/* Pace Records */}
      {records.pace_records.length > 0 && (
        <section>
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <Zap className="w-5 h-5 text-amber" />
            Best Paces
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {records.pace_records.map((record) => (
              <RecordCard
                key={record.category}
                category={record.category}
                value={record.value}
                unit="/km"
                activityName={record.activity_name}
                achievedDate={record.achieved_date}
                previousBest={record.previous_best}
                improvementPct={record.improvement_pct}
                formatValue={formatPace}
                icon={Zap}
                accentColor="#ffb800"
              />
            ))}
          </div>
        </section>
      )}

      {/* Endurance Records */}
      {records.endurance_records.length > 0 && (
        <section>
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <Route className="w-5 h-5 text-green" />
            Endurance Records
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {records.endurance_records.map((record) => (
              <RecordCard
                key={record.category}
                category={record.category}
                value={record.value}
                unit={record.unit === 'meters' ? '' : record.unit}
                activityName={record.activity_name}
                achievedDate={record.achieved_date}
                previousBest={record.previous_best}
                improvementPct={record.improvement_pct}
                formatValue={
                  record.unit === 'meters'
                    ? formatDistance
                    : record.unit === 'seconds'
                    ? formatTime
                    : undefined
                }
                icon={Route}
                accentColor="#00ff88"
              />
            ))}
          </div>
        </section>
      )}

      {/* Upcoming Races with D-day */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-lg font-semibold flex items-center gap-2">
            <Flag className="w-5 h-5 text-amber" />
            출전 예정 대회
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowAddRaceOptions(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-amber/10 text-amber rounded-lg hover:bg-amber/20 transition-colors"
            >
              <Plus className="w-4 h-4" />
              대회 추가
            </button>
          </div>
        </div>
        {upcomingRaces.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {upcomingRaces.map((race) => (
              <RaceCard
                key={race.id}
                race={race}
                onEdit={setEditingRace}
                variant="upcoming"
              />
            ))}
          </div>
        ) : (
          <div className="card text-center py-8">
            <Flag className="w-10 h-10 text-muted mx-auto mb-3" />
            <p className="text-muted">등록된 예정 대회가 없습니다</p>
            <p className="text-sm text-muted mt-1">위의 "대회 추가" 버튼을 눌러 출전 예정 대회를 등록하세요</p>
          </div>
        )}
      </section>

      {/* Completed Race Records - 모든 대회 기록 (수동 등록 + Garmin PB) */}
      {(() => {
        // distance_records와 completedRaces를 병합
        // 1. completedRaces는 그대로 표시
        // 2. distance_records 중 completedRaces에 없는 것들을 추가 (Garmin PB만 있는 경우)

        // distance_records를 Race-like 객체로 변환
        const garminOnlyRecords = records.distance_records
          .filter((record) => !findRaceForRecord(record)) // 연결된 레이스가 없는 경우만
          .map((record) => ({
            id: `garmin-${record.category}`, // 임시 ID
            name: record.activity_name || record.category,
            race_date: record.achieved_date,
            distance_km: (() => {
              const cat = record.category.toLowerCase();
              if (cat.includes('5k')) return 5;
              if (cat.includes('10k')) return 10;
              if (cat.includes('half')) return 21.0975;
              if (cat.includes('marathon') || cat.includes('풀')) return 42.195;
              return null;
            })(),
            distance_label: record.category,
            location: null,
            goal_time_seconds: null,
            goal_description: null,
            is_primary: false,
            is_completed: true,
            result_time_seconds: record.value,
            result_notes: 'Garmin 기록 (대회 등록 필요)',
            days_until: 0,
            isGarminOnly: true, // Garmin-only 플래그
            originalRecord: record, // 원본 record 참조
          }));

        // 모든 대회 기록 (completedRaces + garminOnlyRecords)
        const allRaceRecords = [
          ...completedRaces.map(r => ({ ...r, isGarminOnly: false, originalRecord: null as PersonalRecord | null })),
          ...garminOnlyRecords,
        ].sort((a, b) => new Date(b.race_date).getTime() - new Date(a.race_date).getTime());

        if (allRaceRecords.length === 0) return null;

        return (
          <section>
            <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
              <Trophy className="w-5 h-5 text-green" />
              대회 기록
              <span className="text-muted text-sm font-normal ml-2">
                (클릭하여 공식 기록 수정)
              </span>
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {allRaceRecords.map((record) => (
                record.isGarminOnly ? (
                  // Garmin-only 기록: RecordCard 스타일로 표시 + 클릭시 대회 등록 모달
                  <div
                    key={record.id}
                    className="card group hover:border-[var(--color-accent-cyan)] transition-all cursor-pointer"
                    onClick={() => {
                      if (record.originalRecord) {
                        setEditingRecord({ record: record.originalRecord, existingRace: null });
                      }
                    }}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-amber/20">
                          <Flag className="w-5 h-5 text-amber" />
                        </div>
                        <div>
                          <h3 className="font-display font-semibold">{record.distance_label}</h3>
                          <p className="text-muted text-sm">{record.name}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <span className="px-2 py-0.5 bg-amber/20 text-amber text-xs rounded-full">
                          Garmin PB
                        </span>
                        <Edit2 className="w-4 h-4 text-muted opacity-0 group-hover:opacity-100" />
                      </div>
                    </div>

                    <div className="mb-3">
                      <div className="stat-value text-3xl text-cyan">
                        {record.result_time_seconds ? formatTime(record.result_time_seconds) : '기록 없음'}
                      </div>
                    </div>

                    <div className="flex items-center gap-4 text-sm text-muted">
                      <div className="flex items-center gap-1">
                        <Calendar className="w-4 h-4" />
                        {formatDate(record.race_date)}
                      </div>
                    </div>

                    <div className="mt-3 pt-3 border-t border-[var(--color-border)]">
                      <div className="text-xs text-amber">
                        클릭하여 대회로 등록하기
                      </div>
                    </div>
                  </div>
                ) : (
                  // 기존 RaceCard로 표시
                  <RaceCard
                    key={record.id}
                    race={record as Race}
                    onEdit={setEditingRace}
                    variant="completed"
                  />
                )
              ))}
            </div>
          </section>
        );
      })()}

      {/* Recent PRs */}
      {records.recent_prs && records.recent_prs.length > 0 && (
        <section>
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-red" />
            Recent PRs
          </h2>
          <div className="card">
            <div className="space-y-3">
              {records.recent_prs.map((pr, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between py-2 border-b border-[var(--color-border)] last:border-0"
                >
                  <div className="flex items-center gap-3">
                    <Trophy className="w-4 h-4 text-amber" />
                    <div>
                      <div className="font-medium">{pr.category}</div>
                      <div className="text-sm text-muted">{pr.activity_name}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-cyan">{pr.value}</div>
                    <div className="text-xs text-muted">{formatDate(pr.achieved_date)}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Empty State */}
      {records.distance_records.length === 0 &&
        records.pace_records.length === 0 &&
        records.endurance_records.length === 0 && (
          <div className="card text-center py-16">
            <Trophy className="w-12 h-12 text-muted mx-auto mb-4" />
            <h3 className="font-display text-lg font-semibold mb-2">No Records Yet</h3>
            <p className="text-muted">
              Complete some activities to start tracking your personal records!
            </p>
          </div>
        )}

      {/* Race Edit Modal */}
      {editingRace && (
        <RaceEditModal
          race={editingRace}
          onClose={() => setEditingRace(null)}
          onSave={handleRaceSave}
          isSaving={updateRaceMutation.isPending}
        />
      )}

      {/* Record Edit Modal */}
      {editingRecord && (
        <RecordEditModal
          record={editingRecord.record}
          existingRace={editingRecord.existingRace}
          onClose={() => setEditingRecord(null)}
          onSave={handleRecordSave}
          isSaving={updateRaceMutation.isPending || createRaceMutation.isPending}
        />
      )}

      {/* New Race Modal */}
      {/* Add Race Options Modal */}
      {showAddRaceOptions && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="card max-w-md w-full">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-display text-lg font-semibold">대회 추가</h3>
              <button
                onClick={() => setShowAddRaceOptions(false)}
                className="p-1 hover:bg-[var(--color-surface-elevated)] rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3">
              <button
                onClick={() => {
                  setShowAddRaceOptions(false);
                  setShowNewRaceModal(true);
                }}
                className="w-full px-4 py-3 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg hover:border-cyan transition-colors text-left flex items-center gap-3"
              >
                <Plus className="w-5 h-5 text-cyan" />
                <div>
                  <div className="font-semibold">수동으로 추가</div>
                  <div className="text-sm text-muted">대회 정보를 직접 입력합니다</div>
                </div>
              </button>

              <button
                onClick={() => {
                  setShowAddRaceOptions(false);
                  setShowGarminImport(true);
                }}
                className="w-full px-4 py-3 bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-lg hover:border-cyan transition-colors text-left flex items-center gap-3"
              >
                <Download className="w-5 h-5 text-cyan" />
                <div>
                  <div className="font-semibold">Garmin에서 가져오기</div>
                  <div className="text-sm text-muted">Garmin Connect 이벤트 대시보드에서 대회를 가져옵니다</div>
                </div>
              </button>
            </div>

            <div className="mt-6">
              <button
                onClick={() => setShowAddRaceOptions(false)}
                className="w-full px-4 py-2 border border-[var(--color-border)] rounded-lg hover:bg-[var(--color-surface-elevated)] transition-colors"
              >
                취소
              </button>
            </div>
          </div>
        </div>
      )}

      {showNewRaceModal && (
        <NewRaceModal
          onClose={() => setShowNewRaceModal(false)}
          onSave={handleNewRaceSave}
          isSaving={createRaceMutation.isPending}
        />
      )}

      {showGarminImport && (
        <GarminEventsImportModal onClose={() => setShowGarminImport(false)} />
      )}
    </div>
  );
}
