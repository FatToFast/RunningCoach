import type { TrainingPaces } from '../../types/api';
import { formatPace } from '../../utils/format';

interface TrainingPacesCardProps {
  paces: TrainingPaces | null;
}

interface PaceZone {
  name: string;
  minPace: number;
  maxPace: number;
  hrRange: string;
  color: string;
  bgColor: string;
}

export function TrainingPacesCard({ paces }: TrainingPacesCardProps) {
  if (!paces) {
    return (
      <div className="card p-3 sm:p-4">
        <h3 className="font-display text-sm font-semibold text-muted uppercase tracking-wider mb-3">
          Training Paces
        </h3>
        <p className="text-muted text-xs">페이스 데이터가 없습니다</p>
      </div>
    );
  }

  const zones: PaceZone[] = [
    {
      name: 'Easy',
      minPace: paces.easy_min,
      maxPace: paces.easy_max,
      hrRange: '59 - 74%',
      color: 'text-green-400',
      bgColor: 'bg-green-400/10',
    },
    {
      name: 'Marathon',
      minPace: paces.marathon_min,
      maxPace: paces.marathon_max,
      hrRange: '75 - 84%',
      color: 'text-blue-400',
      bgColor: 'bg-blue-400/10',
    },
    {
      name: 'Threshold',
      minPace: paces.threshold_min,
      maxPace: paces.threshold_max,
      hrRange: '88 - 92%',
      color: 'text-amber-400',
      bgColor: 'bg-amber-400/10',
    },
    {
      name: 'Interval',
      minPace: paces.interval_min,
      maxPace: paces.interval_max,
      hrRange: '95 - 100%',
      color: 'text-orange-400',
      bgColor: 'bg-orange-400/10',
    },
    {
      name: 'Repetition',
      minPace: paces.repetition_min,
      maxPace: paces.repetition_max,
      hrRange: '105 - 110%',
      color: 'text-red-400',
      bgColor: 'bg-red-400/10',
    },
  ];

  return (
    <div className="card p-3 sm:p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-display text-sm font-semibold text-muted uppercase tracking-wider">
          Training Paces
        </h3>
        <span className="text-[10px] text-muted bg-[var(--color-bg-tertiary)] px-1.5 py-0.5 rounded">
          VDOT {paces.vdot}
        </span>
      </div>

      <div className="space-y-1.5">
        {zones.map((zone) => (
          <div
            key={zone.name}
            className={`flex items-center justify-between py-1.5 px-2 rounded ${zone.bgColor}`}
          >
            <div className="flex items-center gap-2">
              <span className={`text-xs font-medium ${zone.color}`}>{zone.name}</span>
              <span className="text-[10px] text-muted">({zone.hrRange})</span>
            </div>
            <span className="font-mono text-xs">
              {formatPace(zone.minPace)} - {formatPace(zone.maxPace)}/km
            </span>
          </div>
        ))}
      </div>

      <p className="text-[10px] text-muted mt-2 text-center">
        Daniels Running Formula 기반
      </p>
    </div>
  );
}
