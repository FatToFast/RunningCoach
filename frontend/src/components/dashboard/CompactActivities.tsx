import { Link } from 'react-router-dom';
import { Activity as ActivityIcon, ChevronRight } from 'lucide-react';
import clsx from 'clsx';
import type { RecentActivity } from '../../types/api';
import { formatPace, formatDuration } from '../../utils/format';

interface CompactActivitiesProps {
  activities: RecentActivity[];
  maxItems?: number;
}

const activityTypeLabels: Record<string, string> = {
  running: '러닝',
  trail_running: '트레일',
  treadmill_running: '트레드밀',
  track_running: '트랙',
  cycling: '사이클',
  swimming: '수영',
  strength_training: '근력',
  walking: '걷기',
};

const activityTypeColors: Record<string, string> = {
  running: 'bg-accent',
  trail_running: 'bg-positive',
  treadmill_running: 'bg-secondary',
  track_running: 'bg-warning',
  cycling: 'bg-info',
  swimming: 'bg-info',
  strength_training: 'bg-danger',
  walking: 'bg-muted',
};

export function CompactActivities({ activities, maxItems = 5 }: CompactActivitiesProps) {
  const displayActivities = activities.slice(0, maxItems);

  if (displayActivities.length === 0) {
    return (
      <div className="card p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-muted uppercase tracking-wider">
            최근 활동
          </span>
        </div>
        <div className="py-4 text-center text-muted text-xs">
          아직 활동 기록이 없습니다
        </div>
      </div>
    );
  }

  return (
    <div className="card p-3">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <ActivityIcon className="w-3.5 h-3.5 text-accent" />
          <span className="text-xs font-medium text-muted uppercase tracking-wider">
            최근 활동
          </span>
        </div>
        <Link
          to="/activities"
          className="text-[10px] text-accent hover:text-accent-hover flex items-center gap-0.5"
        >
          전체보기
          <ChevronRight className="w-3 h-3" />
        </Link>
      </div>

      {/* Activity List */}
      <div className="space-y-1">
        {displayActivities.map((activity) => {
          const typeLabel = activityTypeLabels[activity.activity_type] || activity.activity_type;
          const typeColor = activityTypeColors[activity.activity_type] || 'bg-muted';
          const date = new Date(activity.start_time);

          return (
            <Link
              key={activity.id}
              to={`/activities/${activity.id}`}
              className="flex items-center gap-2 p-1.5 -mx-1.5 rounded hover:bg-[var(--color-bg-tertiary)] transition-colors group"
            >
              {/* Type indicator */}
              <div className={clsx('w-1 h-8 rounded-full', typeColor)} />

              {/* Date */}
              <div className="w-10 text-center">
                <div className="text-[10px] text-muted">
                  {date.toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric' })}
                </div>
                <div className="text-[9px] text-muted opacity-60">
                  {date.toLocaleDateString('ko-KR', { weekday: 'short' })}
                </div>
              </div>

              {/* Name & Type */}
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium truncate group-hover:text-accent transition-colors">
                  {activity.name || typeLabel}
                </div>
                <div className="text-[10px] text-muted">{typeLabel}</div>
              </div>

              {/* Stats */}
              <div className="text-right">
                <div className="font-mono text-xs font-medium">
                  {activity.distance_km?.toFixed(1) ?? '--'}
                  <span className="text-[9px] text-muted ml-0.5">km</span>
                </div>
                <div className="font-mono text-[10px] text-muted">
                  {formatPace(activity.avg_pace_seconds)}
                </div>
              </div>

              {/* Duration */}
              <div className="w-12 text-right">
                <div className="font-mono text-[10px] text-secondary">
                  {formatDuration(activity.duration_seconds)}
                </div>
              </div>
            </Link>
          );
        })}
      </div>

      {/* More indicator */}
      {activities.length > maxItems && (
        <div className="mt-2 pt-2 border-t border-[var(--color-border)] text-center">
          <Link
            to="/activities"
            className="text-[10px] text-muted hover:text-accent transition-colors"
          >
            +{activities.length - maxItems}개 더 보기
          </Link>
        </div>
      )}
    </div>
  );
}
