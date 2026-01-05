import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { RecentActivity } from '../../types/api';
import {
  formatDateRunalyze,
  formatDuration,
  formatPace,
  getActivityTypeShort,
} from '../../utils/format';

interface RecentActivitiesProps {
  activities: RecentActivity[];
}

export function RecentActivities({ activities }: RecentActivitiesProps) {
  if (!activities.length) {
    return (
      <div className="card p-3 sm:p-4">
        <h3 className="font-display text-base sm:text-lg font-semibold mb-3 sm:mb-4">최근 활동</h3>
        <p className="text-muted text-sm">최근 활동이 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="card p-3 sm:p-4">
      <div className="flex items-center justify-between mb-3 sm:mb-4">
        <h3 className="font-display text-base sm:text-lg font-semibold">최근 활동</h3>
        <Link
          to="/activities"
          className="text-accent text-xs sm:text-sm hover:underline flex items-center gap-1 focus:outline-none focus:ring-2 focus:ring-[var(--color-border-accent)] rounded px-1"
        >
          전체보기 <ArrowRight className="w-3 h-3 sm:w-4 sm:h-4" />
        </Link>
      </div>

      {/* Compact Table - No horizontal scroll */}
      <div className="hidden sm:block">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[var(--color-border)] text-[10px] text-muted uppercase tracking-wider">
              <th className="text-left py-2 font-medium">날짜</th>
              <th className="text-left py-2 font-medium">제목</th>
              <th className="text-right py-2 font-medium">거리</th>
              <th className="text-right py-2 font-medium">시간</th>
              <th className="text-right py-2 font-medium">페이스</th>
              <th className="text-right py-2 font-medium">심박</th>
              <th className="text-right py-2 font-medium">TRIMP</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {activities.map((activity) => (
              <tr
                key={activity.id}
                className="hover:bg-[var(--color-bg-secondary)] transition-colors cursor-pointer"
                onClick={() => window.location.href = `/activities/${activity.id}`}
              >
                <td className="py-2 font-mono text-muted whitespace-nowrap">
                  {formatDateRunalyze(activity.start_time)}
                </td>
                <td className="py-2 truncate max-w-[160px]" title={activity.name || ''}>
                  {activity.name || '--'}
                </td>
                <td className="py-2 text-right font-mono">
                  {activity.distance_km != null ? `${activity.distance_km.toFixed(1)}` : '--'}
                  <span className="text-muted text-[10px] ml-0.5">km</span>
                </td>
                <td className="py-2 text-right font-mono text-muted">
                  {formatDuration(activity.duration_seconds)}
                </td>
                <td className="py-2 text-right font-mono">
                  {activity.avg_pace_seconds != null ? formatPace(activity.avg_pace_seconds) : '--'}
                </td>
                <td className="py-2 text-right font-mono text-danger whitespace-nowrap">
                  {activity.avg_hr != null ? (
                    <>
                      {activity.avg_hr}
                      {activity.avg_hr_percent != null && (
                        <span className="text-muted text-[10px] ml-0.5">({activity.avg_hr_percent}%)</span>
                      )}
                    </>
                  ) : '--'}
                </td>
                <td className="py-2 text-right font-mono text-warning">
                  {activity.trimp != null ? Math.round(activity.trimp) : '--'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile List */}
      <div className="sm:hidden space-y-2">
        {activities.map((activity) => (
          <Link
            key={activity.id}
            to={`/activities/${activity.id}`}
            className="block p-2.5 bg-[var(--color-bg-secondary)] rounded-lg hover:bg-[var(--color-bg-tertiary)] transition-colors"
          >
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <span className="font-mono text-muted text-[11px]">
                  {formatDateRunalyze(activity.start_time)}
                </span>
                <span className="bg-accent-soft text-accent px-1 py-0.5 rounded text-[10px] font-medium">
                  {getActivityTypeShort(activity.activity_type, activity.name)}
                </span>
              </div>
              {activity.trimp != null && (
                <span className="text-warning font-mono text-[11px]">{Math.round(activity.trimp)}</span>
              )}
            </div>
            <div className="flex items-center justify-between text-[11px] font-mono">
              <span>{activity.distance_km?.toFixed(1) ?? '--'} km</span>
              <span className="text-muted">{formatDuration(activity.duration_seconds)}</span>
              <span>{formatPace(activity.avg_pace_seconds)}</span>
              <span className="text-danger">
                {activity.avg_hr ?? '--'}
                {activity.avg_hr_percent != null && (
                  <span className="text-muted">({activity.avg_hr_percent}%)</span>
                )}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
