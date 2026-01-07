import { useState } from 'react';
import { Trophy, Clock, Route, TrendingUp, Calendar, Zap, Flag, Edit2, X, Check, MapPin } from 'lucide-react';
import { usePersonalRecords } from '../hooks/useDashboard';
import { useRaces, useUpdateRace } from '../hooks/useRaces';
import type { Race, RaceUpdate } from '../api/races';

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
  const min = Math.floor(seconds / 60);
  const sec = seconds % 60;
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
        <Trophy className="w-5 h-5 text-amber opacity-80" />
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

export function Records() {
  const { data: records, isLoading, error } = usePersonalRecords('running');
  const { data: racesData, isLoading: racesLoading } = useRaces(true); // include completed
  const updateRaceMutation = useUpdateRace();
  const [editingRace, setEditingRace] = useState<Race | null>(null);

  // Separate races into upcoming and completed
  const upcomingRaces =
    racesData?.races.filter((r) => !r.is_completed && r.days_until >= 0) || [];
  const completedRaces = racesData?.races.filter((r) => r.is_completed) || [];

  const handleRaceSave = (raceId: number, update: RaceUpdate) => {
    updateRaceMutation.mutate(
      { raceId, race: update },
      {
        onSuccess: () => setEditingRace(null),
      }
    );
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
            {records.distance_records.map((record) => (
              <RecordCard
                key={record.category}
                category={record.category}
                value={record.value}
                unit=""
                activityName={record.activity_name}
                achievedDate={record.achieved_date}
                previousBest={record.previous_best}
                improvementPct={record.improvement_pct}
                formatValue={formatTime}
                icon={Clock}
                accentColor="#00d4ff"
              />
            ))}
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
      {upcomingRaces.length > 0 && (
        <section>
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <Flag className="w-5 h-5 text-amber" />
            출전 예정 대회
          </h2>
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
        </section>
      )}

      {/* Completed Race Records */}
      {completedRaces.length > 0 && (
        <section>
          <h2 className="font-display text-lg font-semibold mb-4 flex items-center gap-2">
            <Trophy className="w-5 h-5 text-green" />
            대회 기록
            <span className="text-muted text-sm font-normal ml-2">
              (클릭하여 공식 기록 수정)
            </span>
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {completedRaces.map((race) => (
              <RaceCard
                key={race.id}
                race={race}
                onEdit={setEditingRace}
                variant="completed"
              />
            ))}
          </div>
        </section>
      )}

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
    </div>
  );
}
