import clsx from 'clsx';
import type { FitnessStatus } from '../../types/api';

interface FitnessGaugeProps {
  fitness: FitnessStatus;
}

export function FitnessGauge({ fitness }: FitnessGaugeProps) {
  const { ctl, atl, tsb } = fitness;

  // TSB interpretation
  const getTSBStatus = (tsb: number | null) => {
    if (tsb === null) return { label: 'No Data', color: 'text-muted' };
    if (tsb > 25) return { label: 'Fresh', color: 'text-green' };
    if (tsb > 5) return { label: 'Ready', color: 'text-cyan' };
    if (tsb > -10) return { label: 'Neutral', color: 'text-amber' };
    if (tsb > -25) return { label: 'Tired', color: 'text-amber' };
    return { label: 'Fatigued', color: 'text-red' };
  };

  const tsbStatus = getTSBStatus(tsb);

  return (
    <div className="card">
      <h3 className="font-display text-lg font-semibold mb-6">Fitness Status</h3>

      {/* TSB Main Display */}
      <div className="text-center mb-6">
        <div className={clsx('stat-value text-5xl', tsbStatus.color)}>
          {tsb !== null ? (tsb > 0 ? '+' : '') + tsb.toFixed(0) : '--'}
        </div>
        <div className="text-sm text-muted mt-1">Training Stress Balance</div>
        <div className={clsx('text-sm font-medium mt-2', tsbStatus.color)}>
          {tsbStatus.label}
        </div>
      </div>

      {/* CTL / ATL Bars */}
      <div className="space-y-4">
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted">CTL (Fitness)</span>
            <span className="font-mono text-cyan">{ctl?.toFixed(1) ?? '--'}</span>
          </div>
          <div className="h-2 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
            <div
              className="h-full bg-cyan rounded-full transition-all"
              style={{ width: `${Math.min((ctl ?? 0) / 100 * 100, 100)}%` }}
            />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted">ATL (Fatigue)</span>
            <span className="font-mono text-amber">{atl?.toFixed(1) ?? '--'}</span>
          </div>
          <div className="h-2 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
            <div
              className="h-full bg-amber rounded-full transition-all"
              style={{ width: `${Math.min((atl ?? 0) / 100 * 100, 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Weekly Load */}
      <div className="mt-6 pt-4 border-t border-[var(--color-border)] grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs text-muted mb-1">Weekly TRIMP</div>
          <div className="font-mono text-lg">
            {fitness.weekly_trimp?.toFixed(0) ?? '--'}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted mb-1">Weekly TSS</div>
          <div className="font-mono text-lg">
            {fitness.weekly_tss?.toFixed(0) ?? '--'}
          </div>
        </div>
      </div>
    </div>
  );
}
