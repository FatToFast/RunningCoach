import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Dumbbell,
  Plus,
  ChevronRight,
  Calendar,
  Star,
  Filter,
} from 'lucide-react';
import {
  useStrengthSessions,
  getSessionTypeLabel,
  getSessionTypeColor,
  getSessionPurposeLabel,
  getSessionPurposeIcon,
  getRatingStars,
} from '../hooks/useStrength';
import { StrengthForm } from '../components/strength/StrengthForm';
import type { StrengthSessionSummary } from '../types/api';

// Format date in Korean
function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const month = date.getMonth() + 1;
  const day = date.getDate();
  const weekdays = ['일', '월', '화', '수', '목', '금', '토'];
  const weekday = weekdays[date.getDay()];
  return `${month}/${day} (${weekday})`;
}

export function Strength() {
  const [showForm, setShowForm] = useState(false);
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [editingSession, setEditingSession] = useState<StrengthSessionSummary | null>(null);

  const { data: sessions, isLoading, refetch } = useStrengthSessions({
    session_type: typeFilter !== 'all' ? typeFilter : undefined,
    limit: 50,
  });

  const handleFormSuccess = () => {
    setShowForm(false);
    setEditingSession(null);
    refetch();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-cyan animate-pulse">보강운동 불러오는 중...</div>
      </div>
    );
  }

  const items = sessions?.items || [];

  // Group by date for better display
  const groupedByDate = items.reduce((acc, session) => {
    const date = session.session_date;
    if (!acc[date]) {
      acc[date] = [];
    }
    acc[date].push(session);
    return acc;
  }, {} as Record<string, StrengthSessionSummary[]>);

  const sortedDates = Object.keys(groupedByDate).sort((a, b) => b.localeCompare(a));

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-display font-bold">보강운동</h1>
          <p className="text-muted text-sm mt-1">
            근력 운동 기록 및 추적
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="btn btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">운동 추가</span>
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
        <div className="card p-3 sm:p-4">
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-purple-500/10 flex items-center justify-center flex-shrink-0">
              <Dumbbell className="w-4 h-4 sm:w-5 sm:h-5 text-purple-400" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">총 세션</p>
              <p className="text-lg sm:text-xl font-mono font-bold">{sessions?.total || 0}</p>
            </div>
          </div>
        </div>

        <div className="card p-3 sm:p-4">
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-green-500/10 flex items-center justify-center flex-shrink-0">
              <Calendar className="w-4 h-4 sm:w-5 sm:h-5 text-green-400" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">이번 주</p>
              <p className="text-lg sm:text-xl font-mono font-bold">
                {items.filter(s => {
                  const sessionDate = new Date(s.session_date);
                  const now = new Date();
                  const weekStart = new Date(now);
                  weekStart.setDate(now.getDate() - now.getDay());
                  return sessionDate >= weekStart;
                }).length}
              </p>
            </div>
          </div>
        </div>

        <div className="card p-3 sm:p-4">
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-blue-500/10 flex items-center justify-center flex-shrink-0">
              <Star className="w-4 h-4 sm:w-5 sm:h-5 text-blue-400" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">총 세트</p>
              <p className="text-lg sm:text-xl font-mono font-bold">
                {items.reduce((sum, s) => sum + s.total_sets, 0)}
              </p>
            </div>
          </div>
        </div>

        <div className="card p-3 sm:p-4">
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-orange-500/10 flex items-center justify-center flex-shrink-0">
              <Filter className="w-4 h-4 sm:w-5 sm:h-5 text-orange-400" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] sm:text-xs text-muted uppercase tracking-wider">총 종목</p>
              <p className="text-lg sm:text-xl font-mono font-bold">
                {items.reduce((sum, s) => sum + s.exercise_count, 0)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Filter */}
      <div className="card p-3 sm:p-4">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm text-muted">필터:</span>
          {['all', 'upper', 'lower', 'core', 'full_body'].map((type) => (
            <button
              key={type}
              onClick={() => setTypeFilter(type)}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                typeFilter === type
                  ? 'bg-purple-500 text-white'
                  : 'bg-[var(--color-bg-tertiary)] text-muted hover:text-white'
              }`}
            >
              {type === 'all' ? '전체' : getSessionTypeLabel(type)}
            </button>
          ))}
        </div>
      </div>

      {/* Sessions List */}
      <div className="space-y-4">
        {sortedDates.map((date) => (
          <div key={date}>
            <h2 className="text-sm font-medium text-muted mb-2">{formatDate(date)}</h2>
            <div className="space-y-2">
              {groupedByDate[date].map((session) => (
                <Link
                  key={session.id}
                  to={`/strength/${session.id}`}
                  className="card p-3 sm:p-4 hover:border-purple-500/30 focus:border-purple-500 focus:ring-1 focus:ring-purple-500/50 focus:outline-none transition-all cursor-pointer group block"
                >
                  <div className="flex items-center gap-3 sm:gap-4">
                    {/* Type Badge */}
                    <div className={`w-10 h-10 sm:w-12 sm:h-12 rounded-xl ${getSessionTypeColor(session.session_type)} bg-opacity-20 flex items-center justify-center flex-shrink-0`}>
                      <Dumbbell className="w-5 h-5 sm:w-6 sm:h-6 text-white" />
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-0.5 rounded ${getSessionTypeColor(session.session_type)} text-white`}>
                          {getSessionTypeLabel(session.session_type)}
                        </span>
                        {session.session_purpose && (
                          <span className="text-xs text-muted">
                            {getSessionPurposeIcon(session.session_purpose)} {getSessionPurposeLabel(session.session_purpose)}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 sm:gap-4 mt-1.5 text-xs sm:text-sm text-muted">
                        <span>{session.exercise_count}종목</span>
                        <span>{session.total_sets}세트</span>
                        {session.duration_minutes && (
                          <span>{session.duration_minutes}분</span>
                        )}
                      </div>
                    </div>

                    {/* Rating */}
                    <div className="text-right flex-shrink-0">
                      {session.rating && (
                        <div className="text-amber text-sm">
                          {getRatingStars(session.rating)}
                        </div>
                      )}
                    </div>

                    {/* Arrow */}
                    <ChevronRight className="w-4 h-4 sm:w-5 sm:h-5 text-muted group-hover:text-purple-400 transition-colors flex-shrink-0" />
                  </div>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Empty State */}
      {items.length === 0 && (
        <div className="card text-center py-12">
          <Dumbbell className="w-12 h-12 text-muted mx-auto mb-4" />
          <p className="text-muted">기록된 보강운동이 없습니다</p>
          <button
            onClick={() => setShowForm(true)}
            className="btn btn-primary mt-4"
          >
            <Plus className="w-4 h-4 mr-2" />
            첫 번째 운동 기록하기
          </button>
        </div>
      )}

      {/* Form Modal */}
      {showForm && (
        <StrengthForm
          onClose={() => setShowForm(false)}
          onSuccess={handleFormSuccess}
        />
      )}
    </div>
  );
}
