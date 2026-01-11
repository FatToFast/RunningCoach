import { useMemo } from 'react';
import clsx from 'clsx';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  GitCompare,
  Activity,
  Timer,
  Mountain,
  Gauge,
} from 'lucide-react';
import type { CompareResponse } from '../../types/api';

interface CompactComparisonProps {
  data: CompareResponse | undefined;
  isLoading: boolean;
  period: 'week' | 'month';
}

interface ChangeIndicatorProps {
  value: number | null;
  unit?: string;
  inverse?: boolean; // true면 감소가 좋은 것 (예: 페이스)
}

function ChangeIndicator({ value, unit = '%', inverse = false }: ChangeIndicatorProps) {
  if (value === null || value === undefined) {
    return <span className="text-muted">--</span>;
  }

  const isPositive = inverse ? value < 0 : value > 0;
  const isNegative = inverse ? value > 0 : value < 0;
  const absValue = Math.abs(value);

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-0.5 font-mono text-xs font-medium',
        isPositive && 'text-positive',
        isNegative && 'text-danger',
        !isPositive && !isNegative && 'text-muted'
      )}
    >
      {isPositive && <TrendingUp className="w-3 h-3" />}
      {isNegative && <TrendingDown className="w-3 h-3" />}
      {!isPositive && !isNegative && <Minus className="w-3 h-3" />}
      {absValue.toFixed(1)}{unit}
    </span>
  );
}

export function CompactComparison({ data, isLoading, period }: CompactComparisonProps) {
  const periodLabel = period === 'week' ? '주' : '월';
  const prevLabel = period === 'week' ? '지난주' : '지난달';
  const currLabel = period === 'week' ? '이번주' : '이번달';

  // 페이스 변화 (초 → 가독성 텍스트)
  const paceChangeText = useMemo(() => {
    if (!data?.change.pace_change_seconds) return null;
    const seconds = data.change.pace_change_seconds;
    const absSeconds = Math.abs(seconds);
    const isFaster = seconds < 0;

    if (absSeconds < 1) return null;

    const mins = Math.floor(absSeconds / 60);
    const secs = Math.round(absSeconds % 60);

    let text = '';
    if (mins > 0) {
      text = `${mins}분 ${secs}초`;
    } else {
      text = `${secs}초`;
    }

    return { text, isFaster };
  }, [data?.change.pace_change_seconds]);

  if (isLoading) {
    return (
      <div className="card p-3 animate-pulse">
        <div className="flex items-center gap-1.5 mb-3">
          <div className="w-4 h-4 bg-[var(--color-bg-tertiary)] rounded" />
          <div className="w-24 h-4 bg-[var(--color-bg-tertiary)] rounded" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-16 bg-[var(--color-bg-tertiary)] rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="card p-3 text-center text-muted text-xs">
        비교 데이터를 불러올 수 없습니다
      </div>
    );
  }

  const { current_period, previous_period, change } = data;

  return (
    <div className="card p-3">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1.5">
          <GitCompare className="w-4 h-4 text-accent" />
          <span className="text-xs font-medium uppercase tracking-wider">
            {periodLabel}간 비교
          </span>
        </div>
        <span className="text-[10px] text-muted">
          {prevLabel} → {currLabel}
        </span>
      </div>

      {/* Comparison Grid */}
      <div className="grid grid-cols-2 gap-2">
        {/* 거리 */}
        <div className="p-2 bg-[var(--color-bg-secondary)] rounded">
          <div className="flex items-center gap-1 mb-1">
            <Activity className="w-3 h-3 text-accent" />
            <span className="text-[10px] text-muted">거리</span>
          </div>
          <div className="flex items-baseline justify-between">
            <span className="font-mono text-lg font-semibold">
              {current_period.total_distance_km.toFixed(1)}
              <span className="text-[10px] text-muted ml-0.5">km</span>
            </span>
            <ChangeIndicator value={change.distance_change_pct} />
          </div>
          <div className="text-[9px] text-muted mt-0.5">
            {prevLabel}: {previous_period.total_distance_km.toFixed(1)}km
          </div>
        </div>

        {/* 시간 */}
        <div className="p-2 bg-[var(--color-bg-secondary)] rounded">
          <div className="flex items-center gap-1 mb-1">
            <Timer className="w-3 h-3 text-accent" />
            <span className="text-[10px] text-muted">시간</span>
          </div>
          <div className="flex items-baseline justify-between">
            <span className="font-mono text-lg font-semibold">
              {current_period.total_duration_hours.toFixed(1)}
              <span className="text-[10px] text-muted ml-0.5">h</span>
            </span>
            <ChangeIndicator value={change.duration_change_pct} />
          </div>
          <div className="text-[9px] text-muted mt-0.5">
            {prevLabel}: {previous_period.total_duration_hours.toFixed(1)}h
          </div>
        </div>

        {/* 페이스 */}
        <div className="p-2 bg-[var(--color-bg-secondary)] rounded">
          <div className="flex items-center gap-1 mb-1">
            <Gauge className="w-3 h-3 text-accent" />
            <span className="text-[10px] text-muted">평균 페이스</span>
          </div>
          <div className="flex items-baseline justify-between">
            <span className="font-mono text-lg font-semibold">
              {current_period.avg_pace_per_km}
            </span>
            {paceChangeText && (
              <span
                className={clsx(
                  'text-[10px] font-medium',
                  paceChangeText.isFaster ? 'text-positive' : 'text-danger'
                )}
              >
                {paceChangeText.isFaster ? '↓' : '↑'} {paceChangeText.text}
              </span>
            )}
          </div>
          <div className="text-[9px] text-muted mt-0.5">
            {prevLabel}: {previous_period.avg_pace_per_km}
          </div>
        </div>

        {/* 고도 */}
        <div className="p-2 bg-[var(--color-bg-secondary)] rounded">
          <div className="flex items-center gap-1 mb-1">
            <Mountain className="w-3 h-3 text-accent" />
            <span className="text-[10px] text-muted">고도</span>
          </div>
          <div className="flex items-baseline justify-between">
            <span className="font-mono text-lg font-semibold">
              {current_period.total_elevation_m?.toFixed(0) ?? '--'}
              <span className="text-[10px] text-muted ml-0.5">m</span>
            </span>
            <ChangeIndicator value={change.elevation_change_pct} />
          </div>
          <div className="text-[9px] text-muted mt-0.5">
            {prevLabel}: {previous_period.total_elevation_m?.toFixed(0) ?? '--'}m
          </div>
        </div>
      </div>

      {/* Activity Count */}
      <div className="mt-2 pt-2 border-t border-[var(--color-border)] flex items-center justify-between text-[10px]">
        <span className="text-muted">활동 수</span>
        <div className="flex items-center gap-2">
          <span className="font-mono">
            {previous_period.total_activities} → {current_period.total_activities}
          </span>
          <span
            className={clsx(
              'font-medium',
              change.activities_change > 0 && 'text-positive',
              change.activities_change < 0 && 'text-danger',
              change.activities_change === 0 && 'text-muted'
            )}
          >
            ({change.activities_change > 0 ? '+' : ''}{change.activities_change})
          </span>
        </div>
      </div>

      {/* Improvement Summary */}
      {data.improvement_summary && (
        <div className="mt-2 p-2 bg-accent-soft rounded text-[10px] text-accent">
          {data.improvement_summary}
        </div>
      )}
    </div>
  );
}
