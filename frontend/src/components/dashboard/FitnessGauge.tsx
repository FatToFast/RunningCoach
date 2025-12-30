import { useMemo } from 'react';
import clsx from 'clsx';
import { AlertTriangle, Shield } from 'lucide-react';
import type { FitnessStatus } from '../../types/api';
import { getTSBStatus, analyzeInjuryRisks } from '../../constants/fitness';

interface FitnessGaugeProps {
  fitness: FitnessStatus;
}

export function FitnessGauge({ fitness }: FitnessGaugeProps) {
  const { ctl, atl, tsb, workload_ratio } = fitness;

  // Memoize TSB status and injury risks to avoid recalculation on every render
  const tsbStatus = useMemo(() => getTSBStatus(tsb), [tsb]);
  const injuryRisks = useMemo(
    () => analyzeInjuryRisks(tsb, workload_ratio),
    [tsb, workload_ratio]
  );
  const hasHighRisk = injuryRisks.length > 0;

  return (
    <div className={clsx(
      'card p-3 sm:p-4',
      hasHighRisk && 'ring-2 ring-red-400/50'
    )}>
      <div className="flex items-center justify-between mb-4 sm:mb-5">
        <div className="flex items-center gap-2">
          <Shield className={clsx('w-4 h-4 sm:w-5 sm:h-5', hasHighRisk ? 'text-red-400' : 'text-cyan')} />
          <h3 className="font-display text-base sm:text-lg font-semibold">피트니스 상태</h3>
        </div>
        {hasHighRisk && (
          <span className="flex items-center gap-1 text-[10px] sm:text-xs text-red-400 bg-red-400/10 px-2 py-1 rounded-full">
            <AlertTriangle className="w-3 h-3" />
            주의
          </span>
        )}
      </div>

      {/* 부상 위험 경고 */}
      {hasHighRisk && (
        <div className="mb-4 p-2.5 sm:p-3 bg-red-400/10 border border-red-400/30 rounded-lg">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              {injuryRisks.map((risk, i) => (
                <p key={i} className="text-xs sm:text-sm text-red-400">{risk}</p>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TSB Main Display */}
      <div className="text-center mb-4 sm:mb-6">
        <div className={clsx('font-mono text-4xl sm:text-5xl font-bold', tsbStatus.color)}>
          {tsb !== null ? (tsb > 0 ? '+' : '') + tsb.toFixed(0) : '--'}
        </div>
        <div className="text-xs sm:text-sm text-muted mt-1">훈련 스트레스 균형 (TSB)</div>
        <div className={clsx('text-xs sm:text-sm font-medium mt-2', tsbStatus.color)}>
          {tsbStatus.label}
        </div>
      </div>

      {/* CTL / ATL Bars */}
      <div className="space-y-3 sm:space-y-4">
        <div>
          <div className="flex justify-between text-[10px] sm:text-xs mb-1">
            <span className="text-muted">CTL (체력)</span>
            <span className="font-mono text-cyan">{ctl?.toFixed(1) ?? '--'}</span>
          </div>
          <div className="h-1.5 sm:h-2 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
            <div
              className="h-full bg-cyan rounded-full transition-all"
              style={{ width: `${Math.min((ctl ?? 0) / 100 * 100, 100)}%` }}
            />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-[10px] sm:text-xs mb-1">
            <span className="text-muted">ATL (피로도)</span>
            <span className="font-mono text-amber">{atl?.toFixed(1) ?? '--'}</span>
          </div>
          <div className="h-1.5 sm:h-2 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
            <div
              className="h-full bg-amber rounded-full transition-all"
              style={{ width: `${Math.min((atl ?? 0) / 100 * 100, 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Weekly Load */}
      <div className="mt-4 sm:mt-6 pt-3 sm:pt-4 border-t border-[var(--color-border)] grid grid-cols-2 gap-3 sm:gap-4">
        <div>
          <div className="text-[10px] sm:text-xs text-muted mb-1">주간 TRIMP</div>
          <div className="font-mono text-base sm:text-lg">
            {fitness.weekly_trimp?.toFixed(0) ?? '--'}
          </div>
        </div>
        <div>
          <div className="text-[10px] sm:text-xs text-muted mb-1">주간 TSS</div>
          <div className="font-mono text-base sm:text-lg">
            {fitness.weekly_tss?.toFixed(0) ?? '--'}
          </div>
        </div>
      </div>
    </div>
  );
}
