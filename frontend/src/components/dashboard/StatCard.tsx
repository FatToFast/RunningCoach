import { type LucideIcon } from 'lucide-react';
import clsx from 'clsx';

interface StatCardProps {
  label: string;
  value: string | number;
  unit?: string;
  icon?: LucideIcon;
  change?: number | null;
  changeLabel?: string;
  variant?: 'default' | 'accent' | 'warning';
}

export function StatCard({
  label,
  value,
  unit,
  icon: Icon,
  change,
  changeLabel,
  variant = 'default',
}: StatCardProps) {
  const isPositive = change && change > 0;
  const isNegative = change && change < 0;

  return (
    <div className="card">
      <div className="flex items-start justify-between mb-4">
        <span className="stat-label">{label}</span>
        {Icon && (
          <Icon
            className={clsx(
              'w-5 h-5',
              variant === 'accent' && 'text-cyan',
              variant === 'warning' && 'text-amber',
              variant === 'default' && 'text-muted'
            )}
          />
        )}
      </div>

      <div className="flex items-baseline gap-2">
        <span
          className={clsx(
            'stat-value',
            variant === 'warning' && '!text-amber'
          )}
        >
          {value}
        </span>
        {unit && <span className="text-muted text-sm">{unit}</span>}
      </div>

      {change !== undefined && change !== null && (
        <div className="mt-3 flex items-center gap-2">
          <span
            className={clsx(
              'text-xs font-medium',
              isPositive && 'text-green',
              isNegative && 'text-red',
              !isPositive && !isNegative && 'text-muted'
            )}
          >
            {isPositive && '+'}
            {change.toFixed(1)}%
          </span>
          {changeLabel && (
            <span className="text-xs text-muted">{changeLabel}</span>
          )}
        </div>
      )}
    </div>
  );
}
