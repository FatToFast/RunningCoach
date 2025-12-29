import { useState } from 'react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { TrendingUp, TrendingDown, Activity, Heart } from 'lucide-react';
import { useTrends } from '../hooks/useDashboard';

type MetricType = 'distance' | 'duration' | 'pace' | 'hr' | 'fitness';

const metricConfig = {
  distance: {
    label: 'Weekly Distance',
    unit: 'km',
    color: '#00d4ff',
    dataKey: 'weekly_distance',
  },
  duration: {
    label: 'Weekly Duration',
    unit: 'hours',
    color: '#00ff88',
    dataKey: 'weekly_duration',
  },
  pace: {
    label: 'Average Pace',
    unit: 'sec/km',
    color: '#ffb800',
    dataKey: 'avg_pace',
  },
  hr: {
    label: 'Resting Heart Rate',
    unit: 'bpm',
    color: '#ff4757',
    dataKey: 'resting_hr',
  },
  fitness: {
    label: 'Fitness (CTL/ATL/TSB)',
    unit: '',
    color: '#00d4ff',
    dataKey: 'ctl_atl',
  },
};

function formatDate(dateStr: string) {
  const date = new Date(dateStr);
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

function formatPace(seconds: number) {
  const min = Math.floor(seconds / 60);
  const sec = seconds % 60;
  return `${min}:${sec.toString().padStart(2, '0')}`;
}

export function Trends() {
  const [selectedMetric, setSelectedMetric] = useState<MetricType>('distance');
  const { data: trends, isLoading, error } = useTrends(12);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-cyan animate-pulse">Loading trends...</div>
      </div>
    );
  }

  if (error || !trends) {
    return (
      <div className="card text-center py-12">
        <p className="text-red mb-2">Failed to load trends</p>
        <p className="text-muted text-sm">Please check your connection and try again.</p>
      </div>
    );
  }

  const getChartData = () => {
    switch (selectedMetric) {
      case 'distance':
        return trends.weekly_distance.map((d) => ({
          date: formatDate(d.date),
          value: d.value,
        }));
      case 'duration':
        return trends.weekly_duration.map((d) => ({
          date: formatDate(d.date),
          value: d.value,
        }));
      case 'pace':
        return trends.avg_pace.map((d) => ({
          date: formatDate(d.date),
          value: d.value,
          displayValue: formatPace(d.value),
        }));
      case 'hr':
        return trends.resting_hr.map((d) => ({
          date: formatDate(d.date),
          value: d.value,
        }));
      case 'fitness':
        return trends.ctl_atl.map((d) => ({
          date: formatDate(d.date),
          ctl: d.ctl,
          atl: d.atl,
          tsb: d.tsb,
        }));
      default:
        return [];
    }
  };

  const chartData = getChartData();
  const config = metricConfig[selectedMetric];

  // Calculate trend
  const calculateTrend = () => {
    if (selectedMetric === 'fitness') {
      const first = trends.ctl_atl[0]?.ctl ?? 0;
      const last = trends.ctl_atl[trends.ctl_atl.length - 1]?.ctl ?? 0;
      return ((last - first) / first) * 100;
    }

    const dataArray =
      selectedMetric === 'distance'
        ? trends.weekly_distance
        : selectedMetric === 'duration'
        ? trends.weekly_duration
        : selectedMetric === 'pace'
        ? trends.avg_pace
        : trends.resting_hr;

    const first = dataArray[0]?.value ?? 0;
    const last = dataArray[dataArray.length - 1]?.value ?? 0;
    return ((last - first) / first) * 100;
  };

  const trend = calculateTrend();
  // For pace and HR, lower is better
  const isPositiveTrend =
    selectedMetric === 'pace' || selectedMetric === 'hr' ? trend < 0 : trend > 0;

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg p-3 shadow-lg">
          <p className="text-sm text-muted mb-1">{label}</p>
          {payload.map((entry: any, index: number) => (
            <p key={index} className="text-sm font-mono" style={{ color: entry.color }}>
              {entry.name}: {selectedMetric === 'pace' ? formatPace(entry.value) : entry.value}
              {config.unit && ` ${config.unit}`}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold">Trends</h1>
          <p className="text-muted text-sm mt-1">Track your progress over time</p>
        </div>
      </div>

      {/* Metric Selector */}
      <div className="flex flex-wrap gap-2">
        {(Object.keys(metricConfig) as MetricType[]).map((metric) => (
          <button
            key={metric}
            onClick={() => setSelectedMetric(metric)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              selectedMetric === metric
                ? 'bg-cyan text-[var(--color-bg-primary)]'
                : 'bg-[var(--color-bg-card)] text-muted hover:text-[var(--color-text-primary)] border border-[var(--color-border)]'
            }`}
          >
            {metricConfig[metric].label}
          </button>
        ))}
      </div>

      {/* Trend Summary */}
      <div className="card">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="font-display text-lg font-semibold">{config.label}</h2>
            <p className="text-muted text-sm">Last 12 weeks</p>
          </div>
          <div className="flex items-center gap-2">
            {isPositiveTrend ? (
              <TrendingUp className="w-5 h-5 text-green" />
            ) : (
              <TrendingDown className="w-5 h-5 text-red" />
            )}
            <span
              className={`font-mono text-lg font-bold ${
                isPositiveTrend ? 'text-green' : 'text-red'
              }`}
            >
              {trend > 0 ? '+' : ''}
              {trend.toFixed(1)}%
            </span>
          </div>
        </div>

        {/* Chart */}
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            {selectedMetric === 'fitness' ? (
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis
                  dataKey="date"
                  stroke="var(--color-text-muted)"
                  tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }}
                />
                <YAxis
                  stroke="var(--color-text-muted)"
                  tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="ctl"
                  name="CTL (Fitness)"
                  stroke="#00d4ff"
                  strokeWidth={2}
                  dot={{ fill: '#00d4ff', strokeWidth: 0, r: 4 }}
                  activeDot={{ r: 6, strokeWidth: 0 }}
                />
                <Line
                  type="monotone"
                  dataKey="atl"
                  name="ATL (Fatigue)"
                  stroke="#ff4757"
                  strokeWidth={2}
                  dot={{ fill: '#ff4757', strokeWidth: 0, r: 4 }}
                  activeDot={{ r: 6, strokeWidth: 0 }}
                />
                <Line
                  type="monotone"
                  dataKey="tsb"
                  name="TSB (Form)"
                  stroke="#ffb800"
                  strokeWidth={2}
                  dot={{ fill: '#ffb800', strokeWidth: 0, r: 4 }}
                  activeDot={{ r: 6, strokeWidth: 0 }}
                />
              </LineChart>
            ) : (
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id={`gradient-${selectedMetric}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={config.color} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={config.color} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis
                  dataKey="date"
                  stroke="var(--color-text-muted)"
                  tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }}
                />
                <YAxis
                  stroke="var(--color-text-muted)"
                  tick={{ fill: 'var(--color-text-secondary)', fontSize: 12 }}
                  tickFormatter={selectedMetric === 'pace' ? formatPace : undefined}
                />
                <Tooltip content={<CustomTooltip />} />
                <Area
                  type="monotone"
                  dataKey="value"
                  name={config.label}
                  stroke={config.color}
                  strokeWidth={2}
                  fill={`url(#gradient-${selectedMetric})`}
                  dot={{ fill: config.color, strokeWidth: 0, r: 4 }}
                  activeDot={{ r: 6, strokeWidth: 0 }}
                />
              </AreaChart>
            )}
          </ResponsiveContainer>
        </div>
      </div>

      {/* Quick Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-cyan" />
            <span className="stat-label">Avg Distance</span>
          </div>
          <div className="stat-value text-xl">
            {(
              trends.weekly_distance.reduce((sum, d) => sum + d.value, 0) /
              trends.weekly_distance.length
            ).toFixed(1)}
          </div>
          <div className="text-muted text-sm">km/week</div>
        </div>

        <div className="card">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-green" />
            <span className="stat-label">Avg Duration</span>
          </div>
          <div className="stat-value text-xl !text-green">
            {(
              trends.weekly_duration.reduce((sum, d) => sum + d.value, 0) /
              trends.weekly_duration.length
            ).toFixed(1)}
          </div>
          <div className="text-muted text-sm">hours/week</div>
        </div>

        <div className="card">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-amber" />
            <span className="stat-label">Best Pace</span>
          </div>
          <div className="stat-value text-xl !text-amber">
            {formatPace(Math.min(...trends.avg_pace.map((d) => d.value)))}
          </div>
          <div className="text-muted text-sm">/km</div>
        </div>

        <div className="card">
          <div className="flex items-center gap-2 mb-2">
            <Heart className="w-4 h-4 text-red" />
            <span className="stat-label">Lowest RHR</span>
          </div>
          <div className="stat-value text-xl !text-red">
            {Math.min(...trends.resting_hr.map((d) => d.value))}
          </div>
          <div className="text-muted text-sm">bpm</div>
        </div>
      </div>
    </div>
  );
}
