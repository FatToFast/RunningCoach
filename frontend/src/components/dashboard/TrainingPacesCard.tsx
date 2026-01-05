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
  // 대표 거리별 시간 표시 (Interval: 400m, Repetition: 200m)
  targetDistance?: number; // meters
}

// 페이스(초/km)를 특정 거리 시간(초)으로 변환
function paceToDistanceTime(paceSecondsPerKm: number, distanceMeters: number): string {
  const timeSeconds = (paceSecondsPerKm * distanceMeters) / 1000;
  const minutes = Math.floor(timeSeconds / 60);
  const seconds = Math.round(timeSeconds % 60);
  if (minutes > 0) {
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }
  return `${seconds}초`;
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
      color: 'text-positive',
      bgColor: 'bg-positive-soft',
    },
    {
      name: 'Marathon',
      minPace: paces.marathon_min,
      maxPace: paces.marathon_max,
      hrRange: '75 - 84%',
      color: 'text-secondary',
      bgColor: 'bg-secondary',
    },
    {
      name: 'Threshold',
      minPace: paces.threshold_min,
      maxPace: paces.threshold_max,
      hrRange: '88 - 92%',
      color: 'text-warning',
      bgColor: 'bg-warning-soft',
    },
    {
      name: 'Interval',
      minPace: paces.interval_min,
      maxPace: paces.interval_max,
      hrRange: '95 - 100%',
      color: 'text-accent',
      bgColor: 'bg-accent-soft',
      targetDistance: 400, // 400m 시간 표시
    },
    {
      name: 'Repetition',
      minPace: paces.repetition_min,
      maxPace: paces.repetition_max,
      hrRange: '105 - 110%',
      color: 'text-danger',
      bgColor: 'bg-danger-soft',
      targetDistance: 200, // 200m 시간 표시
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
            <div className="flex items-center gap-2">
              {zone.targetDistance && (
                <span className="text-[10px] text-muted font-mono">
                  {zone.targetDistance}m: {paceToDistanceTime(zone.maxPace, zone.targetDistance)}-{paceToDistanceTime(zone.minPace, zone.targetDistance)}
                </span>
              )}
              <span className="font-mono text-xs">
                {formatPace(zone.maxPace)} - {formatPace(zone.minPace)}/km
              </span>
            </div>
          </div>
        ))}
      </div>

      <p className="text-[10px] text-muted mt-2 text-center">
        Daniels Running Formula 기반
      </p>
    </div>
  );
}
