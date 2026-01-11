import { useMemo } from 'react';
import clsx from 'clsx';
import {
  AlertTriangle,
  Shield,
  TrendingUp,
  TrendingDown,
  Info,
  Activity,
  Zap,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  ReferenceLine,
} from 'recharts';
import type { FitnessStatus, HealthStatus } from '../../types/api';
import { getTSBStatus, analyzeInjuryRisks } from '../../constants/fitness';
import { useTrends } from '../../hooks/useDashboard';

interface CompactFitnessProps {
  fitness: FitnessStatus;
  health: HealthStatus;
}

export function CompactFitness({ fitness, health }: CompactFitnessProps) {
  const { tsb, ctl, atl, ctl_percent, atl_percent, workload_ratio } = fitness;
  const { data: trends } = useTrends(6);

  const tsbStatus = useMemo(() => getTSBStatus(tsb), [tsb]);
  const injuryRisks = useMemo(
    () => analyzeInjuryRisks(tsb, workload_ratio),
    [tsb, workload_ratio]
  );
  const hasHighRisk = injuryRisks.length > 0;

  // 차트 데이터 (최근 42일 = 6주)
  const chartData = useMemo(() => {
    if (!trends?.ctl_atl) return [];
    return trends.ctl_atl.slice(-42).map((d) => ({
      date: new Date(d.date).toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric' }),
      ctl: d.ctl_percent,
      atl: d.atl_percent,
      tsb: d.tsb,
    }));
  }, [trends?.ctl_atl]);

  const effectiveVo2max = fitness.effective_vo2max ?? health.vo2max;

  // TSB 해석 가이드
  const getTSBGuide = (value: number | null) => {
    if (value === null) return '';
    if (value > 25) return '과도한 휴식 - 훈련 강도 높여도 됨';
    if (value > 5) return '신선함 - 레이스나 하드 세션에 적합';
    if (value >= -10) return '최적 범위 - 균형 잡힌 훈련 상태';
    if (value >= -25) return '피로 누적 - 회복에 신경 쓸 것';
    return '과훈련 위험 - 휴식 필요';
  };

  return (
    <div
      className={clsx(
        'card p-3',
        hasHighRisk && 'ring-1 ring-[var(--color-danger)]'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <Shield className={clsx('w-4 h-4', hasHighRisk ? 'text-danger' : 'text-accent')} />
          <span className="text-xs font-medium uppercase tracking-wider">피트니스 상태</span>
        </div>
        {hasHighRisk && (
          <span className="flex items-center gap-1 text-[10px] text-danger bg-danger-soft px-1.5 py-0.5 rounded-full">
            <AlertTriangle className="w-2.5 h-2.5" />
            부상 위험
          </span>
        )}
      </div>

      {/* Alert */}
      {hasHighRisk && (
        <div className="mb-3 p-2 bg-danger-soft border border-[var(--color-danger)]/20 rounded text-[11px] text-danger">
          {injuryRisks[0]}
        </div>
      )}

      {/* TSB + CTL/ATL Section */}
      <div className="grid grid-cols-[90px_1fr] gap-3 mb-3">
        {/* TSB Display with Tooltip */}
        <div className="text-center py-1 group relative">
          <div className={clsx('font-mono text-4xl font-bold leading-none cursor-help', tsbStatus.color)}>
            {tsb !== null ? (tsb > 0 ? '+' : '') + tsb.toFixed(0) : '--'}
          </div>
          <div className="text-[9px] text-muted mt-0.5 flex items-center justify-center gap-0.5">
            TSB
            <Info className="w-2.5 h-2.5 opacity-50" />
          </div>
          <div className={clsx('text-[10px] font-medium mt-1', tsbStatus.color)}>
            {tsbStatus.label}
          </div>
          {/* TSB Tooltip */}
          <div className="absolute left-0 top-full mt-2 w-64 p-2.5 bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg shadow-lg text-[10px] opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 text-left">
            <div className="font-semibold mb-1.5">TSB (Training Stress Balance)</div>
            <div className="text-[var(--color-text-secondary)] space-y-1">
              <p><span className="font-medium">공식:</span> CTL - ATL</p>
              <p><span className="font-medium">현재:</span> {getTSBGuide(tsb)}</p>
              <div className="mt-1.5 pt-1.5 border-t border-[var(--color-border)] space-y-0.5">
                <p className="text-positive">+25 이상: 과도한 휴식</p>
                <p className="text-positive">+5 ~ +25: 신선함</p>
                <p className="text-accent">-10 ~ +5: 최적</p>
                <p className="text-warning">-25 ~ -10: 피로</p>
                <p className="text-danger">-25 이하: 위험</p>
              </div>
            </div>
          </div>
        </div>

        {/* CTL/ATL Bars */}
        <div className="space-y-2">
          {/* CTL with Tooltip */}
          <div className="group relative">
            <div className="flex justify-between text-[10px] mb-0.5">
              <span className="text-muted flex items-center gap-0.5 cursor-help">
                <TrendingUp className="w-2.5 h-2.5 text-positive" />
                CTL (체력)
                <Info className="w-2 h-2 opacity-40" />
              </span>
              <span className="font-mono">
                <span className="text-positive font-medium">{ctl?.toFixed(0) ?? '--'}</span>
                <span className="text-muted ml-0.5">({ctl_percent?.toFixed(0) ?? '--'}%)</span>
              </span>
            </div>
            <div className="h-1.5 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
              <div
                className="h-full bg-positive rounded-full transition-all"
                style={{ width: `${Math.min(ctl_percent ?? 0, 100)}%` }}
              />
            </div>
            {/* CTL Tooltip */}
            <div className="absolute left-0 top-full mt-1 w-60 p-2 bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg shadow-lg text-[10px] opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
              <div className="font-semibold mb-1">CTL (Chronic Training Load)</div>
              <div className="text-[var(--color-text-secondary)] space-y-0.5">
                <p>현재값: {fitness.ctl?.toFixed(1)} / 최고값: {fitness.max_ctl?.toFixed(1)}</p>
                <p>42일 EMA로 계산된 장기 훈련 부하</p>
              </div>
            </div>
          </div>

          {/* ATL with Tooltip */}
          <div className="group relative">
            <div className="flex justify-between text-[10px] mb-0.5">
              <span className="text-muted flex items-center gap-0.5 cursor-help">
                <TrendingDown className="w-2.5 h-2.5 text-danger" />
                ATL (피로)
                <Info className="w-2 h-2 opacity-40" />
              </span>
              <span className="font-mono">
                <span className="text-danger font-medium">{atl?.toFixed(0) ?? '--'}</span>
                <span className="text-muted ml-0.5">({atl_percent?.toFixed(0) ?? '--'}%)</span>
              </span>
            </div>
            <div className="h-1.5 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
              <div
                className="h-full bg-danger rounded-full transition-all"
                style={{ width: `${Math.min(atl_percent ?? 0, 100)}%` }}
              />
            </div>
            {/* ATL Tooltip */}
            <div className="absolute left-0 top-full mt-1 w-60 p-2 bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg shadow-lg text-[10px] opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
              <div className="font-semibold mb-1">ATL (Acute Training Load)</div>
              <div className="text-[var(--color-text-secondary)] space-y-0.5">
                <p>현재값: {fitness.atl?.toFixed(1)} / 최고값: {fitness.max_atl?.toFixed(1)}</p>
                <p>7일 EMA로 계산된 단기 피로도</p>
              </div>
            </div>
          </div>

          {/* A:C Ratio with Tooltip */}
          <div className="group relative flex items-center justify-between text-[10px] pt-0.5">
            <span className="text-muted flex items-center gap-0.5 cursor-help">
              A:C Ratio
              <Info className="w-2 h-2 opacity-40" />
            </span>
            <span
              className={clsx(
                'font-mono font-medium px-1.5 py-0.5 rounded text-[9px]',
                workload_ratio != null && workload_ratio >= 0.8 && workload_ratio <= 1.3
                  ? 'text-positive bg-positive-soft'
                  : workload_ratio != null && workload_ratio > 1.5
                    ? 'text-danger bg-danger-soft'
                    : 'text-warning bg-warning-soft'
              )}
            >
              {workload_ratio?.toFixed(2) ?? '--'}
              {workload_ratio != null && (
                <span className="ml-1 opacity-80">
                  {workload_ratio >= 0.8 && workload_ratio <= 1.3
                    ? '안전'
                    : workload_ratio > 1.5
                      ? '위험'
                      : '주의'}
                </span>
              )}
            </span>
            {/* A:C Tooltip */}
            <div className="absolute right-0 top-full mt-1 w-56 p-2 bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg shadow-lg text-[10px] opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
              <div className="font-semibold mb-1">Acute:Chronic Ratio</div>
              <div className="text-[var(--color-text-secondary)] space-y-0.5">
                <p className="text-positive">0.8-1.3: 안전 구간</p>
                <p className="text-warning">1.3-1.5: 주의 필요</p>
                <p className="text-danger">1.5+: 부상 위험 증가</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* CTL/ATL/TSB Chart - Y축 표시, TSB 구분 */}
      {chartData.length > 0 && (
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-muted">6주 추이</span>
            <div className="flex items-center gap-2 text-[9px]">
              <span className="flex items-center gap-1">
                <span className="w-2 h-0.5 bg-positive rounded" />
                CTL
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-0.5 bg-danger rounded" />
                ATL
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-0.5 bg-warning rounded opacity-70" style={{ borderBottom: '1px dashed' }} />
                TSB
              </span>
            </div>
          </div>
          <div className="h-28">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 5, right: 5, left: -15, bottom: 0 }}>
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
                  domain={['auto', 'auto']}
                  tickFormatter={(v) => `${v}`}
                />
                <Tooltip
                  contentStyle={{
                    background: 'var(--color-bg-elevated)',
                    border: '1px solid var(--color-border)',
                    borderRadius: '6px',
                    fontSize: '10px',
                    padding: '4px 8px',
                  }}
                  formatter={(value: number | undefined, name: string | undefined) => {
                    const label = name === 'ctl' ? 'CTL' : name === 'atl' ? 'ATL' : 'TSB';
                    const unit = name === 'tsb' ? '' : '%';
                    return [`${value?.toFixed(0) ?? '--'}${unit}`, label];
                  }}
                />
                <ReferenceLine y={0} stroke="var(--color-border)" strokeDasharray="3 3" />
                <Line
                  type="monotone"
                  dataKey="ctl"
                  stroke="var(--color-success)"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="atl"
                  stroke="var(--color-danger)"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="tsb"
                  stroke="var(--color-warning)"
                  strokeWidth={1.5}
                  strokeDasharray="4 2"
                  dot={false}
                  opacity={0.8}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Key Metrics Grid - 2x2 layout with Tooltips */}
      <div className="grid grid-cols-4 gap-2 pt-2 border-t border-[var(--color-border)]">
        {/* VO2max with Tooltip */}
        <div className="group relative text-center p-1.5 bg-[var(--color-bg-secondary)] rounded cursor-help">
          <div className="flex items-center justify-center gap-0.5 mb-0.5">
            <Activity className="w-3 h-3 text-positive" />
            <span className="text-[9px] text-muted">VO2max</span>
          </div>
          <div className="font-mono text-sm font-semibold text-positive">
            {effectiveVo2max?.toFixed(1) ?? '--'}
          </div>
          {/* VO2max Tooltip */}
          <div className="absolute left-0 bottom-full mb-1 w-52 p-2 bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg shadow-lg text-[10px] opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 text-left">
            <div className="font-semibold mb-1">VO2max (최대산소섭취량)</div>
            <div className="text-[var(--color-text-secondary)]">
              <p>유산소 능력을 나타내는 핵심 지표</p>
              <p className="mt-1">높을수록 심폐 지구력이 좋음</p>
            </div>
          </div>
        </div>

        {/* Marathon Shape with Tooltip */}
        <div className="group relative text-center p-1.5 bg-[var(--color-bg-secondary)] rounded cursor-help">
          <div className="flex items-center justify-center gap-0.5 mb-0.5">
            <Zap className="w-3 h-3 text-accent" />
            <span className="text-[9px] text-muted">Shape</span>
          </div>
          <div className="font-mono text-sm font-semibold text-accent">
            {fitness.marathon_shape != null ? `${fitness.marathon_shape}%` : '--'}
          </div>
          {/* Shape Tooltip */}
          <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 w-52 p-2 bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg shadow-lg text-[10px] opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 text-left">
            <div className="font-semibold mb-1">Marathon Shape</div>
            <div className="text-[var(--color-text-secondary)]">
              <p>현재 마라톤 레이스 컨디션</p>
              <p className="mt-1">100%에 가까울수록 최상의 상태</p>
            </div>
          </div>
        </div>

        {/* TRIMP with Tooltip */}
        <div className="group relative text-center p-1.5 bg-[var(--color-bg-secondary)] rounded cursor-help">
          <div className="flex items-center justify-center gap-0.5 mb-0.5">
            <span className="text-[9px] text-muted">TRIMP</span>
          </div>
          <div className="font-mono text-sm font-semibold">
            {fitness.weekly_trimp?.toFixed(0) ?? '--'}
          </div>
          {/* TRIMP Tooltip */}
          <div className="absolute right-0 bottom-full mb-1 w-52 p-2 bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg shadow-lg text-[10px] opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 text-left">
            <div className="font-semibold mb-1">주간 TRIMP</div>
            <div className="text-[var(--color-text-secondary)] space-y-0.5">
              <p>심박수 기반 훈련 부하</p>
              <p className="text-positive">~300: 가벼운 주간</p>
              <p className="text-accent">300-600: 적정</p>
              <p className="text-warning">600-900: 높음</p>
              <p className="text-danger">900+: 매우 높음</p>
            </div>
          </div>
        </div>

        {/* TSS with Tooltip */}
        <div className="group relative text-center p-1.5 bg-[var(--color-bg-secondary)] rounded cursor-help">
          <div className="flex items-center justify-center gap-0.5 mb-0.5">
            <span className="text-[9px] text-muted">TSS</span>
          </div>
          <div className="font-mono text-sm font-semibold">
            {fitness.weekly_tss?.toFixed(0) ?? '--'}
          </div>
          {/* TSS Tooltip */}
          <div className="absolute right-0 bottom-full mb-1 w-52 p-2 bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg shadow-lg text-[10px] opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 text-left">
            <div className="font-semibold mb-1">주간 TSS</div>
            <div className="text-[var(--color-text-secondary)] space-y-0.5">
              <p>페이스 기반 훈련 부하 (rTSS)</p>
              <p className="text-positive">~150: 가벼운 주간</p>
              <p className="text-accent">150-300: 적정</p>
              <p className="text-warning">300-450: 높음</p>
              <p className="text-danger">450+: 매우 높음</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
