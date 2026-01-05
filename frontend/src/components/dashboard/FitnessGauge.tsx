import { useMemo } from 'react';
import clsx from 'clsx';
import { AlertTriangle, Shield, Info } from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  ReferenceLine,
} from 'recharts';
import type { FitnessStatus } from '../../types/api';
import { getTSBStatus, analyzeInjuryRisks } from '../../constants/fitness';
import { useTrends } from '../../hooks/useDashboard';

interface FitnessGaugeProps {
  fitness: FitnessStatus;
}

export function FitnessGauge({ fitness }: FitnessGaugeProps) {
  const { tsb, ctl_percent, atl_percent, workload_ratio } = fitness;
  const { data: trends } = useTrends(4); // 4주 데이터

  // Memoize TSB status and injury risks to avoid recalculation on every render
  const tsbStatus = useMemo(() => getTSBStatus(tsb), [tsb]);
  const injuryRisks = useMemo(
    () => analyzeInjuryRisks(tsb, workload_ratio),
    [tsb, workload_ratio]
  );
  const hasHighRisk = injuryRisks.length > 0;

  // CTL/ATL 차트 데이터 (최근 28일) - 퍼센트 값 사용
  const chartData = useMemo(() => {
    if (!trends?.ctl_atl) return [];
    // 최근 28일만 표시, CTL/ATL은 퍼센트로 표시
    return trends.ctl_atl.slice(-28).map((d) => ({
      date: new Date(d.date).toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric' }),
      ctl: d.ctl_percent,
      atl: d.atl_percent,
      tsb: d.tsb,
    }));
  }, [trends?.ctl_atl]);

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
    <div className={clsx(
      'card p-3 sm:p-4',
      hasHighRisk && 'ring-2 ring-[var(--color-danger)]'
    )}>
      <div className="flex items-center justify-between mb-4 sm:mb-5">
        <div className="flex items-center gap-2">
          <Shield className={clsx('w-4 h-4 sm:w-5 sm:h-5', hasHighRisk ? 'text-danger' : 'text-accent')} />
          <h3 className="font-display text-base sm:text-lg font-semibold">피트니스 상태</h3>
        </div>
        {hasHighRisk && (
          <span className="flex items-center gap-1 text-[10px] sm:text-xs text-danger bg-danger-soft px-2 py-1 rounded-full">
            <AlertTriangle className="w-3 h-3" />
            주의
          </span>
        )}
      </div>

      {/* 부상 위험 경고 */}
      {hasHighRisk && (
        <div className="mb-4 p-2.5 sm:p-3 bg-danger-soft border border-[var(--color-danger)]/30 rounded-lg">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-danger flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              {injuryRisks.map((risk, i) => (
                <p key={i} className="text-xs sm:text-sm text-danger">{risk}</p>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TSB Main Display with Tooltip */}
      <div className="text-center mb-4 sm:mb-6 relative group">
        <div className={clsx('font-mono text-4xl sm:text-5xl font-bold cursor-help', tsbStatus.color)}>
          {tsb !== null ? (tsb > 0 ? '+' : '') + tsb.toFixed(0) : '--'}
        </div>
        <div className="text-xs sm:text-sm text-muted mt-1 flex items-center justify-center gap-1">
          훈련 스트레스 균형 (TSB)
          <Info className="w-3 h-3 opacity-50" />
        </div>
        <div className={clsx('text-xs sm:text-sm font-medium mt-2', tsbStatus.color)}>
          {tsbStatus.label}
        </div>
        {/* TSB Tooltip */}
        <div className="absolute left-1/2 -translate-x-1/2 top-full mt-2 w-72 p-3 bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg shadow-lg text-xs opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
          <div className="font-semibold mb-2">TSB (Training Stress Balance)</div>
          <div className="text-[var(--color-text-secondary)] space-y-1.5">
            <p><span className="font-medium">공식:</span> CTL - ATL (체력 - 피로도)</p>
            <p><span className="font-medium">현재:</span> {getTSBGuide(tsb)}</p>
            <div className="mt-2 pt-2 border-t border-[var(--color-border)]">
              <p className="text-positive">+25 이상: 과도한 휴식</p>
              <p className="text-positive">+5 ~ +25: 신선함 (레이스 적합)</p>
              <p className="text-accent">-10 ~ +5: 최적 훈련 상태</p>
              <p className="text-warning">-25 ~ -10: 피로 누적</p>
              <p className="text-danger">-25 이하: 과훈련 위험</p>
            </div>
          </div>
        </div>
      </div>

      {/* CTL / ATL / TSB Chart */}
      {chartData.length > 0 && (
        <div className="mb-4">
          <div className="h-32 sm:h-40">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                <XAxis
                  dataKey="date"
                  tick={{ fill: 'var(--color-text-muted)', fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fill: 'var(--color-text-muted)', fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                  domain={['auto', 'auto']}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--color-bg-card)',
                    border: '1px solid var(--color-border)',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  labelStyle={{ color: 'var(--color-text-secondary)' }}
                  formatter={(value, name) => {
                    const label = name === 'ctl' ? 'CTL' : name === 'atl' ? 'ATL' : 'TSB';
                    const unit = name === 'tsb' ? '' : '%';
                    const numValue = typeof value === 'number' ? value.toFixed(1) : '--';
                    return [`${numValue}${unit}`, label];
                  }}
                />
                <ReferenceLine y={0} stroke="var(--color-border)" strokeDasharray="3 3" />
                <Line
                  type="monotone"
                  dataKey="ctl"
                  name="CTL"
                  stroke="var(--color-success)"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="atl"
                  name="ATL"
                  stroke="var(--color-danger)"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="tsb"
                  name="TSB"
                  stroke="var(--color-warning)"
                  strokeWidth={1.5}
                  strokeDasharray="4 2"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="flex justify-center gap-4 mt-2 text-[10px] sm:text-xs">
            <span className="flex items-center gap-1">
              <span className="w-3 h-0.5 bg-positive rounded"></span>
              <span className="text-muted">CTL</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-0.5 bg-danger rounded"></span>
              <span className="text-muted">ATL</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-0.5 bg-warning rounded" style={{ borderStyle: 'dashed' }}></span>
              <span className="text-muted">TSB</span>
            </span>
          </div>
        </div>
      )}

      {/* CTL / ATL Bars - Using percentage of all-time max (Runalyze-style) */}
      <div className="space-y-3 sm:space-y-4">
        {/* CTL Bar with Tooltip */}
        <div className="group relative">
          <div className="flex justify-between text-[10px] sm:text-xs mb-1">
            <span className="text-muted flex items-center gap-1 cursor-help">
              CTL (체력)
              <Info className="w-3 h-3 opacity-50" />
            </span>
            <span className="font-mono text-positive">{ctl_percent?.toFixed(0) ?? '--'}%</span>
          </div>
          <div className="h-1.5 sm:h-2 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
            <div
              className="h-full bg-positive rounded-full transition-all"
              style={{ width: `${Math.min(ctl_percent ?? 0, 100)}%` }}
            />
          </div>
          {/* CTL Tooltip */}
          <div className="absolute left-0 top-full mt-1 w-72 p-3 bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg shadow-lg text-xs opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
            <div className="font-semibold mb-2">CTL (Chronic Training Load) - 체력</div>
            <div className="text-[var(--color-text-secondary)] space-y-1.5">
              <p><span className="font-medium">현재값:</span> {fitness.ctl?.toFixed(1) ?? '--'}</p>
              <p><span className="font-medium">최고값:</span> {fitness.max_ctl?.toFixed(1) ?? '--'}</p>
              <p><span className="font-medium">퍼센트:</span> {ctl_percent?.toFixed(1) ?? '--'}% (최고 대비)</p>
              <div className="mt-2 pt-2 border-t border-[var(--color-border)]">
                <p>42일 지수이동평균(EMA)으로 계산된 장기 훈련 부하입니다.</p>
                <p className="mt-1">높을수록 체력이 좋고, 꾸준한 훈련으로 상승합니다.</p>
              </div>
            </div>
          </div>
        </div>

        {/* ATL Bar with Tooltip */}
        <div className="group relative">
          <div className="flex justify-between text-[10px] sm:text-xs mb-1">
            <span className="text-muted flex items-center gap-1 cursor-help">
              ATL (피로도)
              <Info className="w-3 h-3 opacity-50" />
            </span>
            <span className="font-mono text-warning">{atl_percent?.toFixed(0) ?? '--'}%</span>
          </div>
          <div className="h-1.5 sm:h-2 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
            <div
              className="h-full bg-warning rounded-full transition-all"
              style={{ width: `${Math.min(atl_percent ?? 0, 100)}%` }}
            />
          </div>
          {/* ATL Tooltip */}
          <div className="absolute left-0 top-full mt-1 w-72 p-3 bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg shadow-lg text-xs opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
            <div className="font-semibold mb-2">ATL (Acute Training Load) - 피로도</div>
            <div className="text-[var(--color-text-secondary)] space-y-1.5">
              <p><span className="font-medium">현재값:</span> {fitness.atl?.toFixed(1) ?? '--'}</p>
              <p><span className="font-medium">최고값:</span> {fitness.max_atl?.toFixed(1) ?? '--'}</p>
              <p><span className="font-medium">퍼센트:</span> {atl_percent?.toFixed(1) ?? '--'}% (최고 대비)</p>
              <div className="mt-2 pt-2 border-t border-[var(--color-border)]">
                <p>7일 지수이동평균(EMA)으로 계산된 단기 피로도입니다.</p>
                <p className="mt-1">최근 훈련 강도를 반영하며, 휴식 시 빠르게 감소합니다.</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Weekly Load with Tooltips */}
      <div className="mt-4 sm:mt-6 pt-3 sm:pt-4 border-t border-[var(--color-border)] grid grid-cols-3 gap-3 sm:gap-4">
        {/* TRIMP with Tooltip */}
        <div className="group relative">
          <div className="text-[10px] sm:text-xs text-muted mb-1 flex items-center gap-1 cursor-help">
            주간 TRIMP
            <Info className="w-3 h-3 opacity-50" />
          </div>
          <div className="font-mono text-base sm:text-lg">
            {fitness.weekly_trimp?.toFixed(0) ?? '--'}
          </div>
          {/* TRIMP Tooltip */}
          <div className="absolute left-0 bottom-full mb-1 w-64 p-3 bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg shadow-lg text-xs opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
            <div className="font-semibold mb-2">TRIMP (Training Impulse)</div>
            <div className="text-[var(--color-text-secondary)] space-y-1.5">
              <p>심박수 기반 훈련 부하 지표입니다.</p>
              <p><span className="font-medium">공식:</span> 시간 × 심박 강도 × 지수 가중치</p>
              <div className="mt-2 pt-2 border-t border-[var(--color-border)]">
                <p className="text-positive">~300: 가벼운 주간</p>
                <p className="text-accent">300-600: 적정 훈련량</p>
                <p className="text-warning">600-900: 높은 훈련량</p>
                <p className="text-danger">900+: 매우 높은 부하</p>
              </div>
            </div>
          </div>
        </div>

        {/* TSS with Tooltip */}
        <div className="group relative">
          <div className="text-[10px] sm:text-xs text-muted mb-1 flex items-center gap-1 cursor-help">
            주간 TSS
            <Info className="w-3 h-3 opacity-50" />
          </div>
          <div className="font-mono text-base sm:text-lg">
            {fitness.weekly_tss?.toFixed(0) ?? '--'}
          </div>
          {/* TSS Tooltip */}
          <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 w-64 p-3 bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg shadow-lg text-xs opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
            <div className="font-semibold mb-2">TSS (Training Stress Score)</div>
            <div className="text-[var(--color-text-secondary)] space-y-1.5">
              <p>페이스 기반 러닝 훈련 부하 (rTSS)입니다.</p>
              <p><span className="font-medium">공식:</span> 시간 × 강도계수² × 100</p>
              <div className="mt-2 pt-2 border-t border-[var(--color-border)]">
                <p className="text-positive">~150: 가벼운 주간</p>
                <p className="text-accent">150-300: 적정 훈련량</p>
                <p className="text-warning">300-450: 높은 훈련량</p>
                <p className="text-danger">450+: 매우 높은 부하</p>
              </div>
            </div>
          </div>
        </div>

        {/* A:C Ratio (ACWR) with Tooltip */}
        <div className="group relative">
          <div className="text-[10px] sm:text-xs text-muted mb-1 flex items-center gap-1 cursor-help">
            A:C Ratio
            <Info className="w-3 h-3 opacity-50" />
          </div>
          <div className={clsx(
            'font-mono text-base sm:text-lg',
            workload_ratio !== null && workload_ratio !== undefined && (
              workload_ratio < 0.8 ? 'text-warning' :
              workload_ratio > 1.5 ? 'text-danger' :
              workload_ratio > 1.3 ? 'text-warning' :
              'text-positive'
            )
          )}>
            {workload_ratio?.toFixed(2) ?? '--'}
          </div>
          {/* ACWR Tooltip */}
          <div className="absolute right-0 bottom-full mb-1 w-64 p-3 bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg shadow-lg text-xs opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
            <div className="font-semibold mb-2">ACWR (Acute:Chronic Workload Ratio)</div>
            <div className="text-[var(--color-text-secondary)] space-y-1.5">
              <p>급성/만성 훈련 부하 비율입니다.</p>
              <p><span className="font-medium">공식:</span> ATL ÷ CTL</p>
              <div className="mt-2 pt-2 border-t border-[var(--color-border)]">
                <p className="text-warning">&lt; 0.8: 훈련 부족 (체력 감소 위험)</p>
                <p className="text-positive">0.8 - 1.3: 적정 범위 (최적)</p>
                <p className="text-warning">1.3 - 1.5: 주의 (부상 위험 증가)</p>
                <p className="text-danger">&gt; 1.5: 위험 (부상 고위험)</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
