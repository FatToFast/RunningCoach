import { useState, useMemo } from 'react';
import { Route as RouteIcon, Clock, TrendingUp, Zap } from 'lucide-react';
import { StatCard } from '../components/dashboard/StatCard';
import { RecentActivities } from '../components/dashboard/RecentActivities';
import { FitnessGauge } from '../components/dashboard/FitnessGauge';
import { MileageChart } from '../components/dashboard/MileageChart';
import { CalculationsCard } from '../components/dashboard/CalculationsCard';
import { TrainingPacesCard } from '../components/dashboard/TrainingPacesCard';
import { useDashboardSummary } from '../hooks/useDashboard';
import { formatPace } from '../utils/format';

export function Dashboard() {
  const [period, setPeriod] = useState<'week' | 'month'>('week');
  const { data: dashboard, isLoading, error } = useDashboardSummary({ period });

  // 마일리지 차트 데이터 생성 - Hook은 조건문보다 먼저 호출해야 함
  const mileageData = useMemo(() => {
    const activities = dashboard?.recent_activities;
    if (!activities) return [];

    if (period === 'week') {
      // 최근 8주 데이터 (월요일~일요일 기준, 백엔드와 일치)
      const weeks: { label: string; distance: number; isCurrent: boolean }[] = [];
      const now = new Date();

      for (let i = 7; i >= 0; i--) {
        const weekStart = new Date(now);
        // getDay(): 일요일=0, 월요일=1, ... 토요일=6
        // 월요일 기준으로 변환: (getDay() + 6) % 7 → 월요일=0, 일요일=6
        const daysSinceMonday = (now.getDay() + 6) % 7;
        weekStart.setDate(now.getDate() - daysSinceMonday - i * 7);
        const weekEnd = new Date(weekStart);
        weekEnd.setDate(weekStart.getDate() + 6);

        const weekDistance = activities
          .filter((a) => {
            const actDate = new Date(a.start_time);
            return actDate >= weekStart && actDate <= weekEnd;
          })
          .reduce((sum, a) => sum + (a.distance_km || 0), 0);

        weeks.push({
          label: i === 0 ? '이번주' : i === 1 ? '지난주' : `${i}주전`,
          distance: weekDistance,
          isCurrent: i === 0,
        });
      }
      return weeks;
    } else {
      // 최근 6개월 데이터
      const months: { label: string; distance: number; isCurrent: boolean }[] = [];
      const now = new Date();

      for (let i = 5; i >= 0; i--) {
        const monthDate = new Date(now.getFullYear(), now.getMonth() - i, 1);
        const monthEnd = new Date(now.getFullYear(), now.getMonth() - i + 1, 0);

        const monthDistance = activities
          .filter((a) => {
            const actDate = new Date(a.start_time);
            return actDate >= monthDate && actDate <= monthEnd;
          })
          .reduce((sum, a) => sum + (a.distance_km || 0), 0);

        months.push({
          label: monthDate.toLocaleDateString('ko-KR', { month: 'short' }),
          distance: monthDistance,
          isCurrent: i === 0,
        });
      }
      return months;
    }
  }, [dashboard?.recent_activities, period]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-cyan animate-pulse">대시보드 불러오는 중...</div>
      </div>
    );
  }

  if (error || !dashboard) {
    return (
      <div className="card text-center py-12">
        <p className="text-red-400 mb-2">대시보드를 불러오지 못했습니다</p>
        <p className="text-muted text-sm">연결 상태를 확인하고 다시 시도해주세요.</p>
      </div>
    );
  }

  const { summary, recent_activities, health_status, fitness_status, training_paces } = dashboard;

  // 기간 포맷 (한국어)
  const formatPeriodDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' });
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4">
        <div>
          <h1 className="font-display text-xl sm:text-2xl font-bold">대시보드</h1>
          <p className="text-muted text-sm mt-1">
            {formatPeriodDate(dashboard.period_start)} - {formatPeriodDate(dashboard.period_end)}
          </p>
        </div>

        {/* Period Toggle */}
        <div className="flex items-center gap-1 bg-[var(--color-bg-tertiary)] rounded-lg p-1">
          <button
            onClick={() => setPeriod('week')}
            className={`px-3 sm:px-4 py-2 rounded-md text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-cyan/50 ${
              period === 'week'
                ? 'bg-cyan text-[var(--color-bg-primary)]'
                : 'text-muted hover:text-[var(--color-text-primary)]'
            }`}
          >
            주간
          </button>
          <button
            onClick={() => setPeriod('month')}
            className={`px-3 sm:px-4 py-2 rounded-md text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-cyan/50 ${
              period === 'month'
                ? 'bg-cyan text-[var(--color-bg-primary)]'
                : 'text-muted hover:text-[var(--color-text-primary)]'
            }`}
          >
            월간
          </button>
        </div>
      </div>

      {/* Primary Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-3 lg:gap-4">
        <StatCard
          label="총 거리"
          value={summary.total_distance_km.toFixed(1)}
          unit="km"
          icon={RouteIcon}
          variant="accent"
        />
        <StatCard
          label="운동 시간"
          value={summary.total_duration_hours.toFixed(1)}
          unit="시간"
          icon={Clock}
        />
        <StatCard
          label="활동 수"
          value={summary.total_activities}
          unit="회"
          icon={TrendingUp}
        />
        <StatCard
          label="평균 페이스"
          value={formatPace(summary.avg_pace_seconds)}
          unit="/km"
          icon={Zap}
        />
      </div>

      {/* Main Content - 2 column layout on desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        {/* Left Column - Chart & Activities */}
        <div className="lg:col-span-2 space-y-4 sm:space-y-6">
          {/* Mileage Chart */}
          <MileageChart data={mileageData} period={period} />

          {/* Recent Activities */}
          <RecentActivities activities={recent_activities} />
        </div>

        {/* Right Column - Fitness (부상방지 우선), Calculations, Training Paces */}
        <div className="space-y-3 sm:space-y-4">
          {/* Fitness Gauge - 부상방지를 위해 가장 상단에 배치 */}
          <FitnessGauge fitness={fitness_status} />

          {/* Calculations (Runalyze style) */}
          <CalculationsCard fitness={fitness_status} health={health_status} />

          {/* Training Paces (Daniels) */}
          <TrainingPacesCard paces={training_paces} />
        </div>
      </div>
    </div>
  );
}
