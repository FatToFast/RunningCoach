import { HelpCircle } from 'lucide-react';
import { useState } from 'react';

interface MetricTooltipProps {
  description: string;
  className?: string;
}

export function MetricTooltip({ description, className = '' }: MetricTooltipProps) {
  const [isVisible, setIsVisible] = useState(false);

  return (
    <div className={`absolute top-1 left-1 ${className}`}>
      <button
        type="button"
        className="text-muted hover:text-cyan transition-colors"
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
        onFocus={() => setIsVisible(true)}
        onBlur={() => setIsVisible(false)}
        aria-label="지표 설명"
      >
        <HelpCircle className="w-3 h-3" />
      </button>
      {isVisible && (
        <div className="absolute left-0 top-5 z-50 w-48 sm:w-56 p-2 text-[10px] sm:text-xs text-left bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg shadow-lg">
          {description}
        </div>
      )}
    </div>
  );
}

// Re-export for backward compatibility
// eslint-disable-next-line react-refresh/only-export-components
export { metricDescriptions } from './metricDescriptions';
