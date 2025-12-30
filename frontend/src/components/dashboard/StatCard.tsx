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
    <div className="card p-3 sm:p-4">
      <div className="flex items-start justify-between mb-2 sm:mb-4">
        <span className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">{label}</span>
        {Icon && (
          <Icon
            className={clsx(
              'w-4 h-4 sm:w-5 sm:h-5',
              variant === 'accent' && 'text-cyan',
              variant === 'warning' && 'text-amber',
              variant === 'default' && 'text-muted'
            )}
          />
        )}
      </div>

      <div className="flex items-baseline gap-1 sm:gap-2">
        <span
          className={clsx(
            'font-mono text-xl sm:text-2xl lg:text-3xl font-bold',
            variant === 'accent' && 'text-cyan',
            variant === 'warning' && 'text-amber'
          )}
        >
          {value}
        </span>
        {unit && <span className="text-muted text-xs sm:text-sm">{unit}</span>}
      </div>

      {change !== undefined && change !== null && (
        <div className="mt-2 sm:mt-3 flex items-center gap-1 sm:gap-2">
          <span
            className={clsx(
              'text-[10px] sm:text-xs font-medium',
              isPositive && 'text-green-400',
              isNegative && 'text-red-400',
              !isPositive && !isNegative && 'text-muted'
            )}
          >
            {isPositive && '+'}
            {change.toFixed(1)}%
          </span>
          {changeLabel && (
            <span className="text-[10px] sm:text-xs text-muted">{changeLabel}</span>
          )}
        </div>
      )}
    </div>
  );
}
