import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  Clock,
  MapPin,
  Heart,
  Flame,
  ChevronRight,
  ChevronLeft,
  Filter,
  Search,
  ArrowUp,
  ArrowDown,
} from 'lucide-react';
import { useActivitiesList } from '../hooks/useActivities';
import {
  formatPace,
  formatDate,
  formatTime,
  formatDurationCompact,
  formatCalories,
  getPaceZone,
  getActivityTypeColor,
} from '../utils/format';
import type { ActivitiesParams } from '../api/activities';

type SortField = 'start_time' | 'distance' | 'duration';
type SortOrder = 'asc' | 'desc';

export function Activities() {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<SortField>('start_time');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  const params: ActivitiesParams = useMemo(() => ({
    page,
    per_page: 20,
    activity_type: selectedType === 'all' ? undefined : selectedType,
    sort_by: sortBy,
    sort_order: sortOrder,
  }), [page, selectedType, sortBy, sortOrder]);

  const { data, isLoading, error } = useActivitiesList(params);

  const handleSort = (field: SortField) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
    setPage(1); // Reset to first page on sort change
  };

  const handleTypeChange = (type: string) => {
    setSelectedType(type);
    setPage(1); // Reset to first page on filter change
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-cyan animate-pulse">활동 불러오는 중...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="card text-center py-12">
        <p className="text-red-400 mb-2">활동을 불러오지 못했습니다</p>
        <p className="text-muted text-sm">연결 상태를 확인하고 다시 시도해주세요.</p>
      </div>
    );
  }

  const activities = data.items;

  const filteredActivities = activities.filter((activity) => {
    const matchesSearch = (activity.name || '').toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch;
  });

  // Calculate summary stats
  const totalDistance = filteredActivities.reduce((sum, a) => sum + (a.distance_meters || 0), 0) / 1000;
  const totalDuration = filteredActivities.reduce((sum, a) => sum + (a.duration_seconds || 0), 0);
  const totalCalories = filteredActivities.reduce((sum, a) => sum + (a.calories || 0), 0);

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-display font-bold">활동 기록</h1>
          <p className="text-muted text-sm mt-1">
            {filteredActivities.length}개의 활동
          </p>
        </div>
      </div>

      {/* Summary Cards - 2x2 on mobile, 4 columns on desktop */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
        <div className="card p-3 sm:p-4">
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-cyan/10 flex items-center justify-center flex-shrink-0">
              <MapPin className="w-4 h-4 sm:w-5 sm:h-5 text-cyan" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">총 거리</p>
              <p className="text-lg sm:text-xl font-mono font-bold truncate">{totalDistance.toFixed(1)} km</p>
            </div>
          </div>
        </div>

        <div className="card p-3 sm:p-4">
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-amber/10 flex items-center justify-center flex-shrink-0">
              <Clock className="w-4 h-4 sm:w-5 sm:h-5 text-amber" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">총 시간</p>
              <p className="text-lg sm:text-xl font-mono font-bold truncate">{formatDurationCompact(totalDuration)}</p>
            </div>
          </div>
        </div>

        <div className="card p-3 sm:p-4">
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-red-500/10 flex items-center justify-center flex-shrink-0">
              <Flame className="w-4 h-4 sm:w-5 sm:h-5 text-red-400" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">칼로리</p>
              <p className="text-lg sm:text-xl font-mono font-bold truncate">{formatCalories(totalCalories)}</p>
            </div>
          </div>
        </div>

        <div className="card p-3 sm:p-4">
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-green-500/10 flex items-center justify-center flex-shrink-0">
              <Activity className="w-4 h-4 sm:w-5 sm:h-5 text-green-400" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">활동 수</p>
              <p className="text-lg sm:text-xl font-mono font-bold">{filteredActivities.length}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="card p-3 sm:p-4">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 sm:gap-4">
          {/* Search */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
            <input
              type="text"
              placeholder="활동 검색..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-cyan focus:ring-1 focus:ring-cyan/50 transition-colors"
            />
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            {/* Type Filter */}
            <div className="flex items-center gap-2 flex-1 sm:flex-none">
              <Filter className="w-4 h-4 text-muted hidden sm:block" />
              <select
                value={selectedType}
                onChange={(e) => handleTypeChange(e.target.value)}
                className="flex-1 sm:flex-none px-3 py-2 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-cyan focus:ring-1 focus:ring-cyan/50 transition-colors"
              >
                <option value="all">전체</option>
                <option value="running">러닝</option>
                <option value="cycling">사이클</option>
                <option value="swimming">수영</option>
              </select>
            </div>

            {/* Sort */}
            <div className="flex items-center gap-2">
              <select
                value={sortBy}
                onChange={(e) => handleSort(e.target.value as SortField)}
                className="px-3 py-2 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-cyan focus:ring-1 focus:ring-cyan/50 transition-colors"
              >
                <option value="start_time">날짜순</option>
                <option value="distance">거리순</option>
                <option value="duration">시간순</option>
              </select>
              <button
                onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
                className="p-2 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg hover:border-cyan/50 focus:outline-none focus:border-cyan focus:ring-1 focus:ring-cyan/50 transition-colors"
                title={sortOrder === 'asc' ? '오름차순' : '내림차순'}
              >
                {sortOrder === 'asc' ? (
                  <ArrowUp className="w-4 h-4" />
                ) : (
                  <ArrowDown className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Activity List */}
      <div className="space-y-2 sm:space-y-3">
        {filteredActivities.map((activity) => {
          const paceZone = getPaceZone(activity.avg_pace_seconds);
          const distanceKm = (activity.distance_meters || 0) / 1000;

          return (
            <div
              key={activity.id}
              onClick={() => navigate(`/activities/${activity.id}`)}
              onKeyDown={(e) => e.key === 'Enter' && navigate(`/activities/${activity.id}`)}
              role="button"
              tabIndex={0}
              className="card p-3 sm:p-4 hover:border-cyan/30 focus:border-cyan focus:ring-1 focus:ring-cyan/50 focus:outline-none transition-all cursor-pointer group"
            >
              <div className="flex items-center gap-3 sm:gap-4 lg:gap-6">
                {/* Activity Icon */}
                <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl bg-[var(--color-bg-tertiary)] flex items-center justify-center flex-shrink-0">
                  <Activity className={`w-5 h-5 sm:w-6 sm:h-6 ${getActivityTypeColor(activity.activity_type)}`} />
                </div>

                {/* Main Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 sm:gap-3">
                    <h3 className="font-medium truncate text-sm sm:text-base">{activity.name || '활동'}</h3>
                    <span className={`text-[10px] sm:text-xs font-medium px-1.5 sm:px-2 py-0.5 rounded ${paceZone.color} bg-current/10 hidden sm:inline`}>
                      {paceZone.labelKo}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 sm:gap-4 mt-0.5 sm:mt-1 text-xs sm:text-sm text-muted">
                    <span>{formatDate(activity.start_time)}</span>
                    <span className="hidden sm:inline">{formatTime(activity.start_time)}</span>
                  </div>
                </div>

                {/* Stats - Hidden on mobile/tablet, visible on desktop */}
                <div className="hidden xl:grid grid-cols-5 gap-6 text-center">
                  <div>
                    <p className="text-[10px] text-muted uppercase tracking-wider mb-1">거리</p>
                    <p className="font-mono font-bold text-sm">{distanceKm.toFixed(1)} km</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-muted uppercase tracking-wider mb-1">시간</p>
                    <p className="font-mono font-bold text-sm">{formatDurationCompact(activity.duration_seconds)}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-muted uppercase tracking-wider mb-1">페이스</p>
                    <p className="font-mono font-bold text-sm text-cyan">{formatPace(activity.avg_pace_seconds)}/km</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-muted uppercase tracking-wider mb-1">심박</p>
                    <p className="font-mono font-bold text-sm flex items-center justify-center gap-1">
                      <Heart className="w-3 h-3 text-red-400" />
                      {activity.avg_hr ?? '--'}
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] text-muted uppercase tracking-wider mb-1">칼로리</p>
                    <p className="font-mono font-bold text-sm flex items-center justify-center gap-1">
                      <Flame className="w-3 h-3 text-amber" />
                      {activity.calories ?? '--'}
                    </p>
                  </div>
                </div>

                {/* Tablet Stats - Show distance, pace on md screens */}
                <div className="hidden md:flex xl:hidden items-center gap-4 text-center">
                  <div>
                    <p className="font-mono font-bold text-cyan">{distanceKm.toFixed(1)} km</p>
                  </div>
                  <div>
                    <p className="font-mono font-bold">{formatPace(activity.avg_pace_seconds)}/km</p>
                  </div>
                  <div>
                    <p className="font-mono text-sm text-muted">{formatDurationCompact(activity.duration_seconds)}</p>
                  </div>
                </div>

                {/* Mobile Stats */}
                <div className="md:hidden text-right flex-shrink-0">
                  <p className="font-mono font-bold text-cyan text-sm">{distanceKm.toFixed(1)} km</p>
                  <p className="text-xs text-muted">{formatPace(activity.avg_pace_seconds)}/km</p>
                </div>

                {/* Arrow */}
                <ChevronRight className="w-4 h-4 sm:w-5 sm:h-5 text-muted group-hover:text-cyan group-focus:text-cyan transition-colors flex-shrink-0" />
              </div>
            </div>
          );
        })}
      </div>

      {/* Empty State */}
      {filteredActivities.length === 0 && (
        <div className="card text-center py-12">
          <Activity className="w-12 h-12 text-muted mx-auto mb-4" />
          <p className="text-muted">활동이 없습니다</p>
          <p className="text-sm text-muted mt-1">필터를 조정해 보세요</p>
        </div>
      )}

      {/* Pagination */}
      {filteredActivities.length > 0 && data.total > data.per_page && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="btn btn-secondary px-3 sm:px-4 py-2 text-sm focus:ring-2 focus:ring-cyan/50 flex items-center gap-1"
            disabled={page <= 1}
          >
            <ChevronLeft className="w-4 h-4" />
            <span className="hidden sm:inline">이전</span>
          </button>
          <span className="text-sm text-muted px-2 sm:px-4">
            {page} / {Math.ceil(data.total / data.per_page)}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(Math.ceil(data.total / data.per_page), p + 1))}
            className="btn btn-secondary px-3 sm:px-4 py-2 text-sm focus:ring-2 focus:ring-cyan/50 flex items-center gap-1"
            disabled={page >= Math.ceil(data.total / data.per_page)}
          >
            <span className="hidden sm:inline">다음</span>
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}
