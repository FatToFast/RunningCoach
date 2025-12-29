import { Trophy, Clock, Route, TrendingUp, Calendar, Zap } from 'lucide-react';
import { usePersonalRecords } from '../hooks/useDashboard';

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
    </div>
  );
}
