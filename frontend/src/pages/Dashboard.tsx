import { useState, useMemo } from 'react';
import { CompactStats } from '../components/dashboard/CompactStats';
import { CompactFitness } from '../components/dashboard/CompactFitness';
import { CompactMileage } from '../components/dashboard/CompactMileage';
import { CompactActivities } from '../components/dashboard/CompactActivities';
import { TrainingPacesCard } from '../components/dashboard/TrainingPacesCard';
import { CompactComparison } from '../components/dashboard/CompactComparison';
import { InjuryRiskWidget } from '../components/dashboard/InjuryRiskWidget';
import { useDashboardSummary, useTrends, useCompare } from '../hooks/useDashboard';

export function Dashboard() {
  const [period, setPeriod] = useState<'week' | 'month'>('week');
  const { data: dashboard, isLoading, error } = useDashboardSummary({ period });
  // Trends API에서 실제 주간 거리 데이터 가져오기 (8주 = 주간, 26주 = 월간 집계용)
  const { data: trends } = useTrends(period === 'week' ? 8 : 26);
  // 기간 비교 데이터
  const { data: compareData, isLoading: compareLoading } = useCompare({ period });

  // 마일리지 차트 데이터 생성 - Trends API의 weekly_distance 사용
  const mileageData = useMemo(() => {
    if (!trends?.weekly_distance || trends.weekly_distance.length === 0) return [];

    if (period === 'week') {
      // Trends API의 weekly_distance를 직접 사용 (최근 8주)
      const weeklyData = trends.weekly_distance.slice(-8);
      return weeklyData.map((d, index) => {
        const weeksAgo = weeklyData.length - 1 - index;
        return {
          label: weeksAgo === 0 ? '이번주' : weeksAgo === 1 ? '저번주' : `${weeksAgo}주전`,
          distance: d.value,
          isCurrent: weeksAgo === 0,
        };
      });
    } else {
      // 월간: 주간 데이터를 월별로 집계
      const monthlyMap = new Map<string, number>();

      for (const week of trends.weekly_distance) {
        const weekDate = new Date(week.date);
        const monthKey = `${weekDate.getFullYear()}-${String(weekDate.getMonth() + 1).padStart(2, '0')}`;
        monthlyMap.set(monthKey, (monthlyMap.get(monthKey) || 0) + week.value);
      }

      // 최근 6개월만 가져오기
      const sortedMonths = Array.from(monthlyMap.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .slice(-6);

      const now = new Date();
      const currentMonthKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;

      return sortedMonths.map(([monthKey, distance]) => {
        const [year, month] = monthKey.split('-');
        const monthDate = new Date(parseInt(year), parseInt(month) - 1, 1);
        return {
          label: monthDate.toLocaleDateString('ko-KR', { month: 'short' }),
          distance,
          isCurrent: monthKey === currentMonthKey,
        };
      });
    }
  }, [trends?.weekly_distance, period]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-accent animate-pulse">대시보드 불러오는 중...</div>
      </div>
    );
  }

  if (error || !dashboard) {
    return (
      <div className="card text-center py-12">
        <p className="text-danger mb-2">대시보드를 불러오지 못했습니다</p>
        <p className="text-muted text-sm">연결 상태를 확인하고 다시 시도해주세요.</p>
      </div>
    );
  }

  const { summary, recent_activities, health_status, fitness_status, training_paces } = dashboard;

  // 기간 포맷
  const formatPeriodDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' });
  };

  return (
    <div className="space-y-4 page-reveal">
      {/* Header - 더 컴팩트하게 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-xl font-semibold text-ink">대시보드</h1>
          <p className="text-muted text-xs">
            {formatPeriodDate(dashboard.period_start)} - {formatPeriodDate(dashboard.period_end)}
          </p>
        </div>

        {/* Period Toggle */}
        <div className="segmented text-xs">
          <button
            onClick={() => setPeriod('week')}
            className={`segmented-item px-3 py-1 ${period === 'week' ? 'active' : ''}`}
          >
            주간
          </button>
          <button
            onClick={() => setPeriod('month')}
            className={`segmented-item px-3 py-1 ${period === 'month' ? 'active' : ''}`}
          >
            월간
          </button>
        </div>
      </div>

      {/* Primary Stats - 컴팩트 6열 그리드 */}
      <CompactStats summary={summary} variant={period === 'month' ? 'monthly' : 'default'} />

      {/* Main Content - Runalyze 스타일 2열 레이아웃 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left Column - 비교 + 마일리지 + 피트니스 */}
        <div className="space-y-4">
          {/* 기간 비교 */}
          <CompactComparison
            data={compareData}
            isLoading={compareLoading}
            period={period}
          />

          {/* 마일리지 차트 */}
          <CompactMileage data={mileageData} period={period} />

          {/* 피트니스 상태 (TSB, CTL/ATL) - 핵심 정보 */}
          <CompactFitness fitness={fitness_status} health={health_status} />
        </div>

        {/* Right Column - 활동 + 부상위험 + 페이스 */}
        <div className="space-y-4">
          {/* 최근 활동 */}
          <CompactActivities activities={recent_activities} maxItems={5} />

          {/* 부상 위험 분석 */}
          <InjuryRiskWidget fitness={fitness_status} />

          {/* Training Paces */}
          <TrainingPacesCard paces={training_paces} />
        </div>
      </div>
    </div>
  );
}
