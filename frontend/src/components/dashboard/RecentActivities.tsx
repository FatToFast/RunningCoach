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
          className="text-cyan text-xs sm:text-sm hover:underline flex items-center gap-1 focus:outline-none focus:ring-2 focus:ring-cyan/50 rounded px-1"
        >
          전체보기 <ArrowRight className="w-3 h-3 sm:w-4 sm:h-4" />
        </Link>
      </div>

      {/* Runalyze-style Table */}
      <div className="overflow-x-auto -mx-3 sm:-mx-4">
        <table className="w-full text-xs sm:text-sm min-w-[800px]">
          {/* Table Header */}
          <thead>
            <tr className="border-b border-[var(--color-border)] text-[10px] sm:text-xs text-muted uppercase tracking-wider">
              <th className="text-left px-2 py-2 font-medium">날짜</th>
              <th className="text-left px-2 py-2 font-medium">Type</th>
              <th className="text-right px-2 py-2 font-medium">Distance</th>
              <th className="text-right px-2 py-2 font-medium">Duration</th>
              <th className="text-right px-2 py-2 font-medium">Pace</th>
              <th className="text-right px-2 py-2 font-medium">avg. HR</th>
              <th className="text-right px-2 py-2 font-medium">Elev.</th>
              <th className="text-right px-2 py-2 font-medium">Energy</th>
              <th className="text-left px-2 py-2 font-medium">Title</th>
              <th className="text-right px-2 py-2 font-medium">TRIMP</th>
              <th className="text-right px-2 py-2 font-medium">VO2max</th>
              <th className="text-right px-2 py-2 font-medium">Ground</th>
              <th className="text-right px-2 py-2 font-medium">Vert.</th>
            </tr>
          </thead>

          {/* Table Body */}
          <tbody className="divide-y divide-[var(--color-border)]">
            {activities.map((activity) => (
              <tr
                key={activity.id}
                className="hover:bg-[var(--color-bg-tertiary)] transition-colors cursor-pointer"
                onClick={() => window.location.href = `/activities/${activity.id}`}
              >
                {/* 날짜 (29.12 월) */}
                <td className="px-2 py-2.5 font-mono text-muted whitespace-nowrap">
                  {formatDateRunalyze(activity.start_time)}
                </td>

                {/* Type (ER, TT, LR 등) */}
                <td className="px-2 py-2.5">
                  <span className="inline-block bg-cyan/20 text-cyan px-1.5 py-0.5 rounded text-[10px] font-medium">
                    {getActivityTypeShort(activity.activity_type, activity.name)}
                  </span>
                </td>

                {/* Distance */}
                <td className="px-2 py-2.5 text-right font-mono">
                  {activity.distance_km != null ? (
                    <>
                      {activity.distance_km.toFixed(1)}{' '}
                      <span className="text-muted text-[10px]">km</span>
                    </>
                  ) : (
                    '--'
                  )}
                </td>

                {/* Duration (hh:mm:ss) */}
                <td className="px-2 py-2.5 text-right font-mono text-muted">
                  {formatDuration(activity.duration_seconds)}
                </td>

                {/* Pace */}
                <td className="px-2 py-2.5 text-right font-mono">
                  {activity.avg_pace_seconds != null ? (
                    <>
                      {formatPace(activity.avg_pace_seconds)}
                      <span className="text-muted text-[10px]">/km</span>
                    </>
                  ) : (
                    '--'
                  )}
                </td>

                {/* avg. HR (% only - Runalyze style: "72 %") */}
                <td className="px-2 py-2.5 text-right font-mono">
                  {activity.avg_hr_percent != null ? (
                    <span className="text-red-400">
                      {activity.avg_hr_percent}{' '}
                      <span className="text-[10px]">%</span>
                    </span>
                  ) : (
                    '--'
                  )}
                </td>

                {/* Elevation */}
                <td className="px-2 py-2.5 text-right font-mono text-muted">
                  {activity.elevation_gain != null ? (
                    <>
                      {Math.round(activity.elevation_gain)}
                      <span className="text-[10px]">m</span>
                    </>
                  ) : (
                    ''
                  )}
                </td>

                {/* Energy (calories) */}
                <td className="px-2 py-2.5 text-right font-mono">
                  {activity.calories != null ? (
                    <>
                      {activity.calories.toLocaleString()}{' '}
                      <span className="text-muted text-[10px]">kcal</span>
                    </>
                  ) : (
                    '--'
                  )}
                </td>

                {/* Title */}
                <td className="px-2 py-2.5 truncate max-w-[120px]" title={activity.name || ''}>
                  {activity.name || '--'}
                </td>

                {/* TRIMP */}
                <td className="px-2 py-2.5 text-right font-mono">
                  {activity.trimp != null ? (
                    <span className="text-amber-400">{Math.round(activity.trimp)}</span>
                  ) : (
                    '--'
                  )}
                </td>

                {/* VO2max */}
                <td className="px-2 py-2.5 text-right font-mono text-muted">
                  {activity.vo2max_est != null ? activity.vo2max_est.toFixed(1) : ''}
                </td>

                {/* Ground Contact (ms) */}
                <td className="px-2 py-2.5 text-right font-mono text-muted">
                  {activity.avg_ground_time != null ? (
                    <>
                      {activity.avg_ground_time}
                      <span className="text-[10px]">ms</span>
                    </>
                  ) : (
                    ''
                  )}
                </td>

                {/* Vertical Oscillation (cm) */}
                <td className="px-2 py-2.5 text-right font-mono text-muted">
                  {activity.avg_vertical_oscillation != null ? (
                    <>
                      {activity.avg_vertical_oscillation.toFixed(1)}
                      <span className="text-[10px]">cm</span>
                    </>
                  ) : (
                    ''
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile Card Layout (for screens < 800px) */}
      <div className="lg:hidden mt-4 space-y-3">
        {activities.map((activity) => (
          <Link
            key={activity.id}
            to={`/activities/${activity.id}`}
            className="block p-3 bg-[var(--color-bg-tertiary)] rounded-lg hover:bg-[var(--color-bg-tertiary)]/80 transition-colors"
          >
            {/* Header Row */}
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="font-mono text-muted text-xs">
                  {formatDateRunalyze(activity.start_time)}
                </span>
                <span className="inline-block bg-cyan/20 text-cyan px-1.5 py-0.5 rounded text-[10px] font-medium">
                  {getActivityTypeShort(activity.activity_type, activity.name)}
                </span>
              </div>
              {activity.trimp != null && (
                <span className="text-amber-400 font-mono text-xs">
                  TRIMP {Math.round(activity.trimp)}
                </span>
              )}
            </div>

            {/* Title */}
            <div className="font-medium text-sm mb-2 truncate">
              {activity.name || '활동'}
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-4 gap-2 text-xs">
              <div>
                <div className="text-muted text-[10px]">거리</div>
                <div className="font-mono">
                  {activity.distance_km?.toFixed(1) ?? '--'} km
                </div>
              </div>
              <div>
                <div className="text-muted text-[10px]">시간</div>
                <div className="font-mono">
                  {formatDuration(activity.duration_seconds)}
                </div>
              </div>
              <div>
                <div className="text-muted text-[10px]">페이스</div>
                <div className="font-mono">
                  {formatPace(activity.avg_pace_seconds)}/km
                </div>
              </div>
              <div>
                <div className="text-muted text-[10px]">심박</div>
                <div className="font-mono text-red-400">
                  {activity.avg_hr_percent != null ? `${activity.avg_hr_percent} %` : '--'}
                </div>
              </div>
            </div>

            {/* Secondary Stats */}
            <div className="flex items-center gap-3 mt-2 text-[10px] text-muted">
              {activity.elevation_gain != null && (
                <span>↑{Math.round(activity.elevation_gain)}m</span>
              )}
              {activity.calories != null && (
                <span>{activity.calories.toLocaleString()} kcal</span>
              )}
              {activity.vo2max_est != null && (
                <span>VO2max {activity.vo2max_est.toFixed(1)}</span>
              )}
              {activity.avg_ground_time != null && (
                <span>GC {activity.avg_ground_time}ms</span>
              )}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
