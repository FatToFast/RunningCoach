import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Footprints,
  Calendar,
  Activity,
  AlertTriangle,
  Edit2,
  Trash2,
  Archive,
} from 'lucide-react';
import {
  useGearDetail,
  useRetireGear,
  getGearTypeLabel,
  getUsageColor,
  getUsageBarColor,
} from '../hooks/useGear';
import { formatDate } from '../utils/format';

export function GearDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const gearId = parseInt(id || '0', 10);

  const { data: gear, isLoading, error } = useGearDetail(gearId);
  const retireGear = useRetireGear();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-cyan animate-pulse">장비 정보 불러오는 중...</div>
      </div>
    );
  }

  if (error || !gear) {
    return (
      <div className="card text-center py-12">
        <AlertTriangle className="w-12 h-12 text-amber mx-auto mb-4" />
        <p className="text-muted mb-4">장비를 찾을 수 없습니다</p>
        <button onClick={() => navigate('/gear')} className="btn btn-primary">
          목록으로 돌아가기
        </button>
      </div>
    );
  }

  const distanceKm = gear.total_distance_meters / 1000;
  const maxKm = (gear.max_distance_meters || 800000) / 1000;
  const usagePercent = gear.usage_percentage ?? Math.round((distanceKm / maxKm) * 100);
  const isNearRetirement = usagePercent >= 80;

  const handleRetire = async () => {
    if (window.confirm('이 신발을 은퇴시키시겠습니까?')) {
      await retireGear.mutateAsync(gearId);
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header with back button */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/gear')}
          className="p-2 rounded-lg hover:bg-[var(--color-bg-tertiary)] transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-xl sm:text-2xl font-display font-bold">{gear.name}</h1>
          <div className="flex items-center gap-2 text-sm text-muted mt-1">
            {gear.brand && <span>{gear.brand}</span>}
            <span>{getGearTypeLabel(gear.gear_type)}</span>
            {gear.status === 'retired' && (
              <span className="px-2 py-0.5 bg-gray-500/20 text-gray-400 rounded text-xs">
                은퇴
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn btn-secondary p-2">
            <Edit2 className="w-4 h-4" />
          </button>
          {gear.status === 'active' && (
            <button
              className="btn btn-secondary p-2"
              onClick={handleRetire}
              disabled={retireGear.isPending}
            >
              <Archive className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Retirement Warning */}
      {isNearRetirement && gear.status === 'active' && (
        <div className="card p-4 border-amber/30 bg-amber/5">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-medium text-amber">교체 권장</h3>
              <p className="text-sm text-muted mt-1">
                이 신발은 권장 수명의 {usagePercent}%를 사용했습니다. 새 신발로 교체를 고려해보세요.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
        <div className="card p-3 sm:p-4">
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-cyan/10 flex items-center justify-center flex-shrink-0">
              <Footprints className="w-4 h-4 sm:w-5 sm:h-5 text-cyan" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">총 거리</p>
              <p className="text-lg sm:text-xl font-mono font-bold">{distanceKm.toFixed(0)} km</p>
            </div>
          </div>
        </div>

        <div className="card p-3 sm:p-4">
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-green-500/10 flex items-center justify-center flex-shrink-0">
              <Activity className="w-4 h-4 sm:w-5 sm:h-5 text-green-400" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">활동 횟수</p>
              <p className="text-lg sm:text-xl font-mono font-bold">{gear.activity_count}회</p>
            </div>
          </div>
        </div>

        <div className="card p-3 sm:p-4">
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-amber/10 flex items-center justify-center flex-shrink-0">
              <AlertTriangle className="w-4 h-4 sm:w-5 sm:h-5 text-amber" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">남은 거리</p>
              <p className="text-lg sm:text-xl font-mono font-bold">
                {Math.max(0, maxKm - distanceKm).toFixed(0)} km
              </p>
            </div>
          </div>
        </div>

        <div className="card p-3 sm:p-4">
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-purple-500/10 flex items-center justify-center flex-shrink-0">
              <Calendar className="w-4 h-4 sm:w-5 sm:h-5 text-purple-400" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">구매일</p>
              <p className="text-lg sm:text-xl font-mono font-bold">
                {gear.purchase_date ? formatDate(gear.purchase_date) : '-'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Usage Progress */}
      <div className="card p-4 sm:p-6">
        <h3 className="font-medium mb-4">수명 현황</h3>
        <div className="space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-muted">사용량</span>
            <span className={getUsageColor(usagePercent)}>{usagePercent}%</span>
          </div>
          <div className="h-3 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${getUsageBarColor(usagePercent)}`}
              style={{ width: `${Math.min(usagePercent, 100)}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-muted">
            <span>0 km</span>
            <span>{distanceKm.toFixed(0)} / {maxKm.toFixed(0)} km</span>
          </div>
        </div>
      </div>

      {/* Details */}
      <div className="card p-4 sm:p-6">
        <h3 className="font-medium mb-4">상세 정보</h3>
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-muted">브랜드</span>
            <span>{gear.brand || '-'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">모델</span>
            <span>{gear.model || '-'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">종류</span>
            <span>{getGearTypeLabel(gear.gear_type)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">상태</span>
            <span>{gear.status === 'active' ? '사용 중' : '은퇴'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">최대 권장 거리</span>
            <span>{maxKm.toFixed(0)} km</span>
          </div>
          {gear.retired_date && (
            <div className="flex justify-between">
              <span className="text-muted">은퇴일</span>
              <span>{formatDate(gear.retired_date)}</span>
            </div>
          )}
        </div>
      </div>

      {/* Notes */}
      {gear.notes && (
        <div className="card p-4 sm:p-6">
          <h3 className="font-medium mb-4">메모</h3>
          <p className="text-sm text-muted whitespace-pre-wrap">{gear.notes}</p>
        </div>
      )}

      {/* Danger Zone */}
      <div className="card p-4 sm:p-6 border-red-500/30">
        <h3 className="font-medium text-red-400 mb-4">위험 구역</h3>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm">이 장비를 삭제합니다</p>
            <p className="text-xs text-muted mt-1">이 작업은 되돌릴 수 없습니다</p>
          </div>
          <button className="btn bg-red-500/10 text-red-400 hover:bg-red-500/20">
            <Trash2 className="w-4 h-4 mr-2" />
            삭제
          </button>
        </div>
      </div>
    </div>
  );
}
