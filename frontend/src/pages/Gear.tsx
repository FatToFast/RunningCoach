import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Footprints,
  Plus,
  AlertTriangle,
  CheckCircle,
  Archive,
  RefreshCw,
  ChevronRight,
} from 'lucide-react';
import {
  useGearList,
  useGearStats,
  useSyncGearFromGarmin,
  getGearTypeLabel,
  getUsageColor,
  getUsageBarColor,
} from '../hooks/useGear';

export function Gear() {
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'retired'>('active');

  const { data: gearList, isLoading } = useGearList({ status: statusFilter });
  const { data: stats } = useGearStats();
  const syncGarmin = useSyncGearFromGarmin();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-cyan animate-pulse">장비 불러오는 중...</div>
      </div>
    );
  }

  const items = gearList?.items || [];

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-display font-bold">신발 관리</h1>
          <p className="text-muted text-sm mt-1">
            러닝화 수명 및 거리 추적
          </p>
        </div>
        <button className="btn btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">신발 추가</span>
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
          <div className="card p-3 sm:p-4">
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-cyan/10 flex items-center justify-center flex-shrink-0">
                <Footprints className="w-4 h-4 sm:w-5 sm:h-5 text-cyan" />
              </div>
              <div className="min-w-0">
                <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">전체</p>
                <p className="text-lg sm:text-xl font-mono font-bold">{stats.total_gears}</p>
              </div>
            </div>
          </div>

          <div className="card p-3 sm:p-4">
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-green-500/10 flex items-center justify-center flex-shrink-0">
                <CheckCircle className="w-4 h-4 sm:w-5 sm:h-5 text-green-400" />
              </div>
              <div className="min-w-0">
                <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">사용 중</p>
                <p className="text-lg sm:text-xl font-mono font-bold">{stats.active_gears}</p>
              </div>
            </div>
          </div>

          <div className="card p-3 sm:p-4">
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-gray-500/10 flex items-center justify-center flex-shrink-0">
                <Archive className="w-4 h-4 sm:w-5 sm:h-5 text-gray-400" />
              </div>
              <div className="min-w-0">
                <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">은퇴</p>
                <p className="text-lg sm:text-xl font-mono font-bold">{stats.retired_gears}</p>
              </div>
            </div>
          </div>

          <div className="card p-3 sm:p-4">
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-amber/10 flex items-center justify-center flex-shrink-0">
                <AlertTriangle className="w-4 h-4 sm:w-5 sm:h-5 text-amber" />
              </div>
              <div className="min-w-0">
                <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">교체 권장</p>
                <p className="text-lg sm:text-xl font-mono font-bold">{stats.gears_near_retirement.length}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Retirement Alert */}
      {stats && stats.gears_near_retirement.length > 0 && (
        <div className="card p-4 border-amber/30 bg-amber/5">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-medium text-amber">교체 권장 신발</h3>
              <p className="text-sm text-muted mt-1">
                다음 신발들이 권장 수명의 80% 이상 사용되었습니다:
              </p>
              <ul className="mt-2 space-y-1">
                {stats.gears_near_retirement.map((gear) => (
                  <li key={gear.id} className="text-sm flex items-center gap-2">
                    <span className="font-medium">{gear.name}</span>
                    <span className="text-muted">
                      ({(gear.total_distance_meters / 1000).toFixed(0)}km / {((gear.max_distance_meters || 800000) / 1000).toFixed(0)}km)
                    </span>
                    <span className={getUsageColor(gear.usage_percentage)}>
                      {gear.usage_percentage}%
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Filter & Sync */}
      <div className="card p-3 sm:p-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as 'all' | 'active' | 'retired')}
              className="px-3 py-2 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-cyan focus:ring-1 focus:ring-cyan/50 transition-colors"
            >
              <option value="all">전체</option>
              <option value="active">사용 중</option>
              <option value="retired">은퇴</option>
            </select>
          </div>

          <button
            className="btn btn-secondary flex items-center gap-2"
            onClick={() => syncGarmin.mutate()}
            disabled={syncGarmin.isPending}
          >
            <RefreshCw className={`w-4 h-4 ${syncGarmin.isPending ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">{syncGarmin.isPending ? '동기화 중...' : 'Garmin 동기화'}</span>
          </button>
        </div>
      </div>

      {/* Gear List */}
      <div className="space-y-2 sm:space-y-3">
        {items.map((gear) => {
          const distanceKm = gear.total_distance_meters / 1000;
          const maxKm = (gear.max_distance_meters || 800000) / 1000;
          const usagePercent = gear.usage_percentage ?? Math.round((distanceKm / maxKm) * 100);

          return (
            <Link
              key={gear.id}
              to={`/gear/${gear.id}`}
              className="card p-3 sm:p-4 hover:border-cyan/30 focus:border-cyan focus:ring-1 focus:ring-cyan/50 focus:outline-none transition-all cursor-pointer group block"
            >
              <div className="flex items-center gap-3 sm:gap-4">
                {/* Icon */}
                <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl bg-[var(--color-bg-tertiary)] flex items-center justify-center flex-shrink-0">
                  <Footprints className={`w-5 h-5 sm:w-6 sm:h-6 ${gear.status === 'active' ? 'text-cyan' : 'text-muted'}`} />
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-medium truncate text-sm sm:text-base">{gear.name}</h3>
                    {gear.status === 'retired' && (
                      <span className="text-[10px] sm:text-xs text-muted bg-[var(--color-bg-tertiary)] px-1.5 py-0.5 rounded">
                        은퇴
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 sm:gap-4 mt-0.5 text-xs sm:text-sm text-muted">
                    {gear.brand && <span>{gear.brand}</span>}
                    <span>{getGearTypeLabel(gear.gear_type)}</span>
                    <span>{gear.activity_count}회 사용</span>
                  </div>
                </div>

                {/* Distance & Progress */}
                <div className="text-right flex-shrink-0 w-28 sm:w-36">
                  <div className="flex items-baseline justify-end gap-1">
                    <span className="font-mono font-bold text-sm sm:text-base">{distanceKm.toFixed(0)}</span>
                    <span className="text-xs text-muted">/ {maxKm.toFixed(0)} km</span>
                  </div>
                  <div className="mt-1.5 h-1.5 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${getUsageBarColor(usagePercent)}`}
                      style={{ width: `${Math.min(usagePercent, 100)}%` }}
                    />
                  </div>
                  <div className={`text-[10px] sm:text-xs mt-1 ${getUsageColor(usagePercent)}`}>
                    {usagePercent}% 사용
                  </div>
                </div>

                {/* Arrow */}
                <ChevronRight className="w-4 h-4 sm:w-5 sm:h-5 text-muted group-hover:text-cyan transition-colors flex-shrink-0" />
              </div>
            </Link>
          );
        })}
      </div>

      {/* Empty State */}
      {items.length === 0 && (
        <div className="card text-center py-12">
          <Footprints className="w-12 h-12 text-muted mx-auto mb-4" />
          <p className="text-muted">등록된 신발이 없습니다</p>
          <button className="btn btn-primary mt-4">
            <Plus className="w-4 h-4 mr-2" />
            첫 번째 신발 추가
          </button>
        </div>
      )}
    </div>
  );
}
