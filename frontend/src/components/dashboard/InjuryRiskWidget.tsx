import { useMemo } from 'react';
import clsx from 'clsx';
import {
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  TrendingUp,
  TrendingDown,
  Info,
  Activity,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
  Tooltip,
} from 'recharts';
import type { FitnessStatus } from '../../types/api';
import { useTrends } from '../../hooks/useDashboard';
import {
  AC_RATIO_THRESHOLDS,
  TSB_THRESHOLDS,
  analyzeInjuryRisks,
} from '../../constants/fitness';

interface InjuryRiskWidgetProps {
  fitness: FitnessStatus;
}

export function InjuryRiskWidget({ fitness }: InjuryRiskWidgetProps) {
  const { tsb, workload_ratio, ctl, atl } = fitness;
  const { data: trends } = useTrends(4); // 4주 데이터

  // 부상 위험 분석
  const risks = useMemo(
    () => analyzeInjuryRisks(tsb, workload_ratio),
    [tsb, workload_ratio]
  );

  const hasRisk = risks.length > 0;

  // A:C 비율 상태 결정
  const acRatioStatus = useMemo(() => {
    if (workload_ratio === null) {
      return { status: 'unknown', label: '데이터 없음', color: 'text-muted' };
    }
    if (workload_ratio >= AC_RATIO_THRESHOLDS.OPTIMAL_MIN &&
        workload_ratio <= AC_RATIO_THRESHOLDS.OPTIMAL_MAX) {
      return { status: 'optimal', label: '최적', color: 'text-positive' };
    }
    if (workload_ratio > AC_RATIO_THRESHOLDS.INJURY_RISK) {
      return { status: 'danger', label: '위험', color: 'text-danger' };
    }
    if (workload_ratio > AC_RATIO_THRESHOLDS.OPTIMAL_MAX) {
      return { status: 'warning', label: '주의', color: 'text-warning' };
    }
    return { status: 'low', label: '부족', color: 'text-warning' };
  }, [workload_ratio]);

  // A:C 비율 히스토리 (CTL/ATL에서 계산)
  const acRatioHistory = useMemo(() => {
    if (!trends?.ctl_atl) return [];

    // 최근 28일만 사용
    return trends.ctl_atl.slice(-28).map((d) => {
      const ratio = d.ctl && d.ctl > 0 ? (d.atl ?? 0) / d.ctl : null;
      return {
        date: new Date(d.date).toLocaleDateString('ko-KR', {
          month: 'numeric',
          day: 'numeric'
        }),
        ratio: ratio ? parseFloat(ratio.toFixed(2)) : null,
        tsb: d.tsb,
      };
    }).filter((d) => d.ratio !== null);
  }, [trends?.ctl_atl]);

  // TSB 상태에 따른 조언
  const tsbAdvice = useMemo(() => {
    if (tsb === null) return null;
    if (tsb > TSB_THRESHOLDS.FRESH) {
      return { type: 'info', text: '충분히 회복된 상태입니다. 강도 높은 훈련 가능' };
    }
    if (tsb > TSB_THRESHOLDS.READY) {
      return { type: 'info', text: '좋은 컨디션입니다. 레이스나 하드 세션에 적합' };
    }
    if (tsb > TSB_THRESHOLDS.NORMAL) {
      return { type: 'info', text: '균형 잡힌 훈련 상태입니다' };
    }
    if (tsb > TSB_THRESHOLDS.TIRED) {
      return { type: 'warning', text: '피로가 누적되고 있습니다. 회복에 신경 쓰세요' };
    }
    return { type: 'danger', text: '과훈련 위험! 휴식이 필요합니다' };
  }, [tsb]);

  // A:C 비율 게이지 퍼센트 (0.5 ~ 2.0 범위를 0~100%로 변환)
  const gaugePercent = useMemo(() => {
    if (workload_ratio === null) return 50;
    // 0.5 = 0%, 1.0 = 33%, 1.5 = 67%, 2.0 = 100%
    const clamped = Math.min(Math.max(workload_ratio, 0.5), 2.0);
    return ((clamped - 0.5) / 1.5) * 100;
  }, [workload_ratio]);

  return (
    <div
      className={clsx(
        'card p-3',
        hasRisk && 'ring-1 ring-[var(--color-danger)]'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          {hasRisk ? (
            <ShieldAlert className="w-4 h-4 text-danger" />
          ) : (
            <ShieldCheck className="w-4 h-4 text-positive" />
          )}
          <span className="text-xs font-medium uppercase tracking-wider">
            부상 위험 분석
          </span>
        </div>
        <span
          className={clsx(
            'text-[10px] px-1.5 py-0.5 rounded-full font-medium',
            hasRisk ? 'bg-danger-soft text-danger' : 'bg-positive-soft text-positive'
          )}
        >
          {hasRisk ? '주의 필요' : '양호'}
        </span>
      </div>

      {/* Risk Alerts */}
      {hasRisk && (
        <div className="mb-3 space-y-1">
          {risks.map((risk, i) => (
            <div
              key={i}
              className="flex items-start gap-1.5 p-2 bg-danger-soft border border-[var(--color-danger)]/20 rounded text-[11px] text-danger"
            >
              <AlertTriangle className="w-3 h-3 flex-shrink-0 mt-0.5" />
              <span>{risk}</span>
            </div>
          ))}
        </div>
      )}

      {/* A:C Ratio Gauge */}
      <div className="mb-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] text-muted flex items-center gap-1">
            A:C Ratio (급만성 비율)
            <Info className="w-2.5 h-2.5 opacity-50" />
          </span>
          <span className={clsx('text-xs font-mono font-semibold', acRatioStatus.color)}>
            {workload_ratio?.toFixed(2) ?? '--'}
            <span className="ml-1 text-[10px] opacity-80">{acRatioStatus.label}</span>
          </span>
        </div>

        {/* Gauge Bar */}
        <div className="relative h-3 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
          {/* Zone backgrounds */}
          <div className="absolute inset-0 flex">
            {/* Undertrained zone (0.5-0.8) = 0-20% */}
            <div className="w-[20%] bg-warning/20" />
            {/* Optimal zone (0.8-1.3) = 20-53% */}
            <div className="w-[33%] bg-positive/20" />
            {/* Caution zone (1.3-1.5) = 53-67% */}
            <div className="w-[14%] bg-warning/20" />
            {/* Danger zone (1.5-2.0) = 67-100% */}
            <div className="w-[33%] bg-danger/20" />
          </div>

          {/* Current position indicator */}
          <div
            className={clsx(
              'absolute top-0 h-full w-1 rounded-full transition-all',
              acRatioStatus.status === 'optimal' && 'bg-positive',
              acRatioStatus.status === 'danger' && 'bg-danger',
              acRatioStatus.status === 'warning' && 'bg-warning',
              acRatioStatus.status === 'low' && 'bg-warning',
              acRatioStatus.status === 'unknown' && 'bg-muted'
            )}
            style={{ left: `calc(${gaugePercent}% - 2px)` }}
          />
        </div>

        {/* Zone labels */}
        <div className="flex justify-between mt-0.5 text-[8px] text-muted">
          <span>0.5</span>
          <span className="text-positive">0.8</span>
          <span className="text-positive">1.3</span>
          <span className="text-danger">1.5</span>
          <span>2.0</span>
        </div>
      </div>

      {/* A:C Ratio Trend Chart */}
      {acRatioHistory.length > 7 && (
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-muted">28일 추이</span>
            <div className="flex items-center gap-1.5 text-[9px]">
              <span className="flex items-center gap-0.5">
                <span className="w-2 h-0.5 bg-accent rounded" />
                A:C
              </span>
            </div>
          </div>
          <div className="h-20">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={acRatioHistory} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="acRatioGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--color-accent)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="var(--color-accent)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="date"
                  stroke="var(--color-text-muted)"
                  fontSize={8}
                  tickLine={false}
                  axisLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis
                  stroke="var(--color-text-muted)"
                  fontSize={8}
                  tickLine={false}
                  axisLine={false}
                  domain={[0.4, 2]}
                  ticks={[0.8, 1.3, 1.5]}
                />
                <Tooltip
                  contentStyle={{
                    background: 'var(--color-bg-elevated)',
                    border: '1px solid var(--color-border)',
                    borderRadius: '6px',
                    fontSize: '10px',
                    padding: '4px 8px',
                  }}
                  formatter={(value: number | undefined) => [value?.toFixed(2) ?? '--', 'A:C']}
                />
                {/* Safe zone reference */}
                <ReferenceArea
                  y1={0.8}
                  y2={1.3}
                  fill="var(--color-success)"
                  fillOpacity={0.1}
                />
                {/* Danger line */}
                <ReferenceLine
                  y={1.5}
                  stroke="var(--color-danger)"
                  strokeDasharray="3 3"
                  strokeOpacity={0.5}
                />
                <Area
                  type="monotone"
                  dataKey="ratio"
                  stroke="var(--color-accent)"
                  strokeWidth={1.5}
                  fill="url(#acRatioGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Quick Stats */}
      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-[var(--color-border)]">
        {/* CTL */}
        <div className="text-center">
          <div className="text-[9px] text-muted mb-0.5 flex items-center justify-center gap-0.5">
            <TrendingUp className="w-2.5 h-2.5 text-positive" />
            CTL
          </div>
          <div className="font-mono text-sm font-semibold text-positive">
            {ctl?.toFixed(0) ?? '--'}
          </div>
        </div>

        {/* ATL */}
        <div className="text-center">
          <div className="text-[9px] text-muted mb-0.5 flex items-center justify-center gap-0.5">
            <TrendingDown className="w-2.5 h-2.5 text-danger" />
            ATL
          </div>
          <div className="font-mono text-sm font-semibold text-danger">
            {atl?.toFixed(0) ?? '--'}
          </div>
        </div>

        {/* TSB */}
        <div className="text-center">
          <div className="text-[9px] text-muted mb-0.5 flex items-center justify-center gap-0.5">
            <Activity className="w-2.5 h-2.5 text-accent" />
            TSB
          </div>
          <div
            className={clsx(
              'font-mono text-sm font-semibold',
              tsb !== null && tsb > 0 && 'text-positive',
              tsb !== null && tsb < -10 && 'text-danger',
              tsb !== null && tsb >= -10 && tsb <= 0 && 'text-warning'
            )}
          >
            {tsb !== null ? (tsb > 0 ? '+' : '') + tsb.toFixed(0) : '--'}
          </div>
        </div>
      </div>

      {/* TSB Advice */}
      {tsbAdvice && (
        <div
          className={clsx(
            'mt-2 p-2 rounded text-[10px]',
            tsbAdvice.type === 'danger' && 'bg-danger-soft text-danger',
            tsbAdvice.type === 'warning' && 'bg-warning-soft text-warning',
            tsbAdvice.type === 'info' && 'bg-accent-soft text-accent'
          )}
        >
          {tsbAdvice.text}
        </div>
      )}
    </div>
  );
}
