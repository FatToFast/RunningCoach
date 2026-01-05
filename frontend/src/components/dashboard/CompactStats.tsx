import { Route as RouteIcon, Clock, TrendingUp, Zap, Heart, Flame } from 'lucide-react';
import clsx from 'clsx';
import { formatPace } from '../../utils/format';

interface CompactStatsProps {
  summary: {
    total_distance_km: number;
    total_duration_hours: number;
    total_activities: number;
    avg_pace_seconds: number | null;
    avg_hr: number | null;
    total_calories: number | null;
  };
  variant?: 'default' | 'minimal' | 'monthly';
}

export function CompactStats({ summary, variant = 'default' }: CompactStatsProps) {
  const stats = [
    {
      label: '거리',
      value: summary.total_distance_km.toFixed(1),
      unit: 'km',
      icon: RouteIcon,
      color: 'text-accent',
    },
    {
      label: '시간',
      value: summary.total_duration_hours.toFixed(1),
      unit: 'h',
      icon: Clock,
      color: 'text-secondary',
    },
    {
      label: '활동',
      value: summary.total_activities,
      unit: '회',
      icon: TrendingUp,
      color: 'text-secondary',
    },
    {
      label: '페이스',
      value: formatPace(summary.avg_pace_seconds),
      unit: '/km',
      icon: Zap,
      color: 'text-secondary',
    },
    ...(summary.avg_hr
      ? [
          {
            label: '심박',
            value: summary.avg_hr,
            unit: 'bpm',
            icon: Heart,
            color: 'text-danger',
          },
        ]
      : []),
    ...(summary.total_calories
      ? [
          {
            label: '칼로리',
            value: Math.round(summary.total_calories),
            unit: 'kcal',
            icon: Flame,
            color: 'text-warning',
          },
        ]
      : []),
  ];

  if (variant === 'minimal') {
    return (
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {stats.slice(0, 4).map((stat) => (
          <div key={stat.label} className="flex items-baseline gap-1">
            <span className={clsx('font-mono text-lg font-semibold', stat.color)}>
              {stat.value}
            </span>
            <span className="text-[10px] text-muted">{stat.unit}</span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="bg-[var(--color-bg-secondary)] rounded-lg p-2 text-center"
        >
          <div className="flex items-center justify-center gap-1 mb-0.5">
            <stat.icon className={clsx('w-3 h-3', stat.color)} />
            <span className="text-[10px] text-muted uppercase">{stat.label}</span>
          </div>
          <div className="flex items-baseline justify-center gap-0.5">
            <span className={clsx('font-mono text-base sm:text-lg font-semibold', stat.color)}>
              {stat.value}
            </span>
            <span className="text-[9px] text-muted">{stat.unit}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
