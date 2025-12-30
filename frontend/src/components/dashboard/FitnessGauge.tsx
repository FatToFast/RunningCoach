import clsx from 'clsx';
import type { FitnessStatus } from '../../types/api';

interface FitnessGaugeProps {
  fitness: FitnessStatus;
}

export function FitnessGauge({ fitness }: FitnessGaugeProps) {
  const { ctl, atl, tsb } = fitness;

  // TSB 상태 해석 (한국어)
  const getTSBStatus = (tsb: number | null) => {
    if (tsb === null) return { label: '데이터 없음', color: 'text-muted' };
    if (tsb > 25) return { label: '상쾌함', color: 'text-green-400' };
    if (tsb > 5) return { label: '준비됨', color: 'text-cyan' };
    if (tsb > -10) return { label: '보통', color: 'text-amber' };
    if (tsb > -25) return { label: '피로', color: 'text-amber' };
    return { label: '과부하', color: 'text-red-400' };
  };

  const tsbStatus = getTSBStatus(tsb);

  return (
    <div className="card p-3 sm:p-4">
      <h3 className="font-display text-base sm:text-lg font-semibold mb-4 sm:mb-6">피트니스 상태</h3>

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
