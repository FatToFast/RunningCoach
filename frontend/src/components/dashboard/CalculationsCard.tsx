import { Activity, TrendingUp, TrendingDown, Battery, Zap, Calendar, BarChart3 } from 'lucide-react';
import type { FitnessStatus, HealthStatus } from '../../types/api';

interface CalculationsCardProps {
  fitness: FitnessStatus;
  health: HealthStatus;
}

// TSB 상태에 따른 색상
function getTsbColor(tsb: number | null): string {
  if (tsb === null) return 'text-muted';
  if (tsb > 10) return 'text-positive'; // Fresh
  if (tsb > -10) return 'text-accent'; // Optimal
  if (tsb > -25) return 'text-warning'; // Tired
  return 'text-danger'; // Overreached
}

// Workload Ratio 상태에 따른 색상
function getWorkloadColor(ratio: number | null): string {
  if (ratio === null) return 'text-muted';
  if (ratio >= 0.8 && ratio <= 1.3) return 'text-positive'; // Sweet spot
  if (ratio > 1.5) return 'text-danger'; // Injury risk
  return 'text-warning'; // Caution
}

export function CalculationsCard({ fitness, health }: CalculationsCardProps) {
  const effectiveVo2max = fitness.effective_vo2max ?? health.vo2max;

  return (
    <div className="card p-3 sm:p-4">
      <h3 className="font-display text-sm font-semibold text-muted uppercase tracking-wider mb-3">
        Calculations
      </h3>

      <div className="space-y-2">
        {/* Effective VO2max */}
        <div className="flex items-center justify-between py-1">
          <div className="flex items-center gap-2">
          <Zap className="w-3.5 h-3.5 text-positive" />
            <span className="text-xs text-muted">Effective VO2max</span>
          </div>
          <span className="font-mono text-sm font-semibold text-positive">
            {effectiveVo2max?.toFixed(2) ?? '--'}
          </span>
        </div>

        {/* Marathon Shape */}
        <div className="flex items-center justify-between py-1">
          <div className="flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-accent" />
          <span className="text-xs text-muted">Marathon Shape</span>
        </div>
        <span className="font-mono text-sm font-semibold text-accent">
          {fitness.marathon_shape != null ? `${fitness.marathon_shape}%` : '--'}
        </span>
      </div>

        {/* Fatigue (ATL) */}
        <div className="flex items-center justify-between py-1">
          <div className="flex items-center gap-2">
          <TrendingUp className="w-3.5 h-3.5 text-danger" />
          <span className="text-xs text-muted">Fatigue (ATL)</span>
        </div>
        <span className="font-mono text-sm font-semibold">
          {fitness.atl != null ? `${Math.round(fitness.atl)}%` : '--'}
        </span>
        </div>

        {/* Fitness (CTL) */}
        <div className="flex items-center justify-between py-1">
          <div className="flex items-center gap-2">
          <TrendingUp className="w-3.5 h-3.5 text-positive" />
          <span className="text-xs text-muted">Fitness (CTL)</span>
        </div>
        <span className="font-mono text-sm font-semibold">
          {fitness.ctl != null ? `${Math.round(fitness.ctl)}%` : '--'}
        </span>
        </div>

        {/* Stress Balance (TSB) */}
        <div className="flex items-center justify-between py-1">
          <div className="flex items-center gap-2">
          <Battery className="w-3.5 h-3.5 text-warning" />
          <span className="text-xs text-muted">Stress Balance (TSB)</span>
        </div>
        <span className={`font-mono text-sm font-semibold ${getTsbColor(fitness.tsb)}`}>
          {fitness.tsb != null ? fitness.tsb : '--'}
        </span>
        </div>

        {/* Workload Ratio (A:C) */}
        <div className="flex items-center justify-between py-1">
          <div className="flex items-center gap-2">
          <BarChart3 className="w-3.5 h-3.5 text-warning" />
          <span className="text-xs text-muted">Workload Ratio (A:C)</span>
        </div>
        <span className={`font-mono text-sm font-semibold ${getWorkloadColor(fitness.workload_ratio)}`}>
          {fitness.workload_ratio?.toFixed(2) ?? '--'}
        </span>
        </div>

        {/* Rest days */}
        <div className="flex items-center justify-between py-1">
          <div className="flex items-center gap-2">
            <Calendar className="w-3.5 h-3.5 text-muted" />
            <span className="text-xs text-muted">Rest days</span>
          </div>
          <span className="font-mono text-sm font-semibold">
            {fitness.rest_days?.toFixed(1) ?? '--'}
          </span>
        </div>

        {/* Monotony */}
        <div className="flex items-center justify-between py-1">
          <div className="flex items-center gap-2">
            <TrendingDown className="w-3.5 h-3.5 text-muted" />
            <span className="text-xs text-muted">Monotony</span>
          </div>
          <span className="font-mono text-sm font-semibold">
            {fitness.monotony != null ? `${fitness.monotony}%` : '--'}
          </span>
        </div>

        {/* Training strain */}
        <div className="flex items-center justify-between py-1">
          <div className="flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-accent-strong" />
          <span className="text-xs text-muted">Training strain</span>
        </div>
          <span className="font-mono text-sm font-semibold">
            {fitness.training_strain ?? '--'}
          </span>
        </div>
      </div>
    </div>
  );
}
