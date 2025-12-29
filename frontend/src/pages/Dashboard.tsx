import { useState } from 'react';
import {
  Route as RouteIcon,
  Clock,
  Flame,
  TrendingUp,
  Heart,
  Moon,
  Zap,
} from 'lucide-react';
import { StatCard } from '../components/dashboard/StatCard';
import { RecentActivities } from '../components/dashboard/RecentActivities';
import { FitnessGauge } from '../components/dashboard/FitnessGauge';
import { useDashboardSummary, useCompare } from '../hooks/useDashboard';

export function Dashboard() {
  const [period, setPeriod] = useState<'week' | 'month'>('week');
  const { data: dashboard, isLoading, error } = useDashboardSummary({ period });
  const { data: compare } = useCompare({ period });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-cyan animate-pulse">Loading dashboard...</div>
      </div>
    );
  }

  if (error || !dashboard) {
    return (
      <div className="card text-center py-12">
        <p className="text-red mb-2">Failed to load dashboard</p>
        <p className="text-muted text-sm">Please check your connection and try again.</p>
      </div>
    );
  }

  const { summary, recent_activities, health_status, fitness_status } = dashboard;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold">Dashboard</h1>
          <p className="text-muted text-sm mt-1">
            {dashboard.period_start} - {dashboard.period_end}
          </p>
        </div>

        {/* Period Toggle */}
        <div className="flex items-center gap-2 bg-[var(--color-bg-card)] rounded-lg p-1">
          <button
            onClick={() => setPeriod('week')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              period === 'week'
                ? 'bg-cyan text-[var(--color-bg-primary)]'
                : 'text-muted hover:text-[var(--color-text-primary)]'
            }`}
          >
            Week
          </button>
          <button
            onClick={() => setPeriod('month')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              period === 'month'
                ? 'bg-cyan text-[var(--color-bg-primary)]'
                : 'text-muted hover:text-[var(--color-text-primary)]'
            }`}
          >
            Month
          </button>
        </div>
      </div>

      {/* Main Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Distance"
          value={summary.total_distance_km.toFixed(1)}
          unit="km"
          icon={RouteIcon}
          variant="accent"
          change={compare?.change.distance_change_pct}
          changeLabel="vs last period"
        />
        <StatCard
          label="Duration"
          value={summary.total_duration_hours.toFixed(1)}
          unit="hours"
          icon={Clock}
          change={compare?.change.duration_change_pct}
          changeLabel="vs last period"
        />
        <StatCard
          label="Activities"
          value={summary.total_activities}
          icon={TrendingUp}
          change={
            compare
              ? (compare.change.activities_change /
                  (compare.previous_period.total_activities || 1)) *
                100
              : null
          }
          changeLabel="vs last period"
        />
        <StatCard
          label="Avg Pace"
          value={summary.avg_pace_per_km}
          icon={Zap}
        />
      </div>

      {/* Secondary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          label="Avg Heart Rate"
          value={summary.avg_hr ?? '--'}
          unit="bpm"
          icon={Heart}
        />
        <StatCard
          label="Total Calories"
          value={summary.total_calories?.toLocaleString() ?? '--'}
          unit="kcal"
          icon={Flame}
          variant="warning"
        />
        <StatCard
          label="Elevation Gain"
          value={summary.total_elevation_m?.toFixed(0) ?? '--'}
          unit="m"
          icon={TrendingUp}
        />
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Activities */}
        <div className="lg:col-span-2">
          <RecentActivities activities={recent_activities} />
        </div>

        {/* Fitness Status */}
        <div>
          <FitnessGauge fitness={fitness_status} />
        </div>
      </div>

      {/* Health Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <div className="flex items-center gap-3 mb-2">
            <Moon className="w-5 h-5 text-cyan" />
            <span className="stat-label">Sleep Score</span>
          </div>
          <div className="stat-value">
            {health_status.latest_sleep_score ?? '--'}
          </div>
          {health_status.latest_sleep_hours && (
            <div className="text-sm text-muted mt-2">
              {health_status.latest_sleep_hours.toFixed(1)} hours
            </div>
          )}
        </div>

        <div className="card">
          <div className="flex items-center gap-3 mb-2">
            <Heart className="w-5 h-5 text-red" />
            <span className="stat-label">Resting HR</span>
          </div>
          <div className="stat-value !text-red">
            {health_status.resting_hr ?? '--'}
          </div>
          <div className="text-sm text-muted mt-2">bpm</div>
        </div>

        <div className="card">
          <div className="flex items-center gap-3 mb-2">
            <Zap className="w-5 h-5 text-green" />
            <span className="stat-label">VO2max</span>
          </div>
          <div className="stat-value !text-green">
            {health_status.vo2max?.toFixed(1) ?? '--'}
          </div>
          <div className="text-sm text-muted mt-2">ml/kg/min</div>
        </div>
      </div>

      {/* Compare Summary */}
      {compare && (
        <div className="card">
          <h3 className="font-display text-lg font-semibold mb-4">
            Period Comparison
          </h3>
          <p className="text-cyan font-medium">{compare.improvement_summary}</p>
        </div>
      )}
    </div>
  );
}
