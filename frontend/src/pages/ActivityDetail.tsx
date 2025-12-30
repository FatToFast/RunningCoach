import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Calendar,
  Clock,
  MapPin,
  Heart,
  TrendingUp,
  Zap,
  ChevronDown,
  ChevronUp,
  Download,
  FileCheck,
  Activity,
  Footprints,
  Gauge,
  Radio,
} from 'lucide-react';
import { useState, lazy, Suspense } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Area,
  ComposedChart,
} from 'recharts';
import {
  useActivityDetail,
  useActivitySamples,
  useActivityHRZones,
  useActivityLaps,
} from '../hooks/useActivities';
import { useActivityGear, getUsageColor } from '../hooks/useGear';
import {
  formatPace,
  formatDuration,
  formatDateFull,
  formatTime,
  formatPaceFromDecimal,
  formatCalories,
} from '../utils/format';
import { KmPaceChart } from '../components/activity/KmPaceChart';
import { MetricTooltip, metricDescriptions } from '../components/common/MetricTooltip';

// Lazy load map component for better performance
const ActivityMap = lazy(() =>
  import('../components/activity/ActivityMap').then((m) => ({ default: m.ActivityMap }))
);

function getHRZoneColor(zone: number): string {
  const colors = ['#00d4ff', '#00ff88', '#ffb800', '#ff6b35', '#ff4757'];
  return colors[zone - 1] || colors[0];
}

function getHRZoneName(zone: number): string {
  const names = ['회복', '유산소', '템포', '역치', '최대'];
  return names[zone - 1] || '';
}

export function ActivityDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [showAllLaps, setShowAllLaps] = useState(false);

  const activityId = Number(id);
  const { data: activity, isLoading, error } = useActivityDetail(activityId);
  // 차트 성능을 위해 200개로 다운샘플링
  const { data: samplesData } = useActivitySamples(activityId, 200);
  // 별도 훅으로 HR zones와 laps 조회 (mock 데이터)
  const { data: hrZones } = useActivityHRZones(activityId);
  const { data: laps } = useActivityLaps(activityId);
  // 활동에 연결된 장비 (신발)
  const { data: activityGear } = useActivityGear(activityId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-cyan animate-pulse">활동 불러오는 중...</div>
      </div>
    );
  }

  if (error || !activity) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(-1)}
            className="btn btn-secondary p-2 focus:ring-2 focus:ring-cyan/50"
            title="뒤로 가기"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="font-display text-2xl font-bold">활동을 찾을 수 없습니다</h1>
        </div>
        <div className="card text-center py-12">
          <p className="text-red-400 mb-2">활동 상세 정보를 불러오지 못했습니다</p>
          <p className="text-muted text-sm">연결 상태를 확인하고 다시 시도해주세요.</p>
        </div>
      </div>
    );
  }

  const distanceKm = (activity.distance_meters || 0) / 1000;
  const displayedLaps = showAllLaps ? (laps || []) : (laps || []).slice(0, 5);

  // Convert samples for charts (백엔드 응답 구조에 맞춤)
  const chartSamples =
    samplesData?.samples.map((s, index) => ({
      time: index * 10, // 타임스탬프 대신 인덱스 기반
      hr: s.hr,
      pace: s.pace_seconds ? s.pace_seconds / 60 : null,
      elevation: s.altitude,
      cadence: s.cadence,
    })) || [];

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header with back button */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
        <button
          onClick={() => navigate(-1)}
          className="btn btn-secondary p-2 w-fit focus:ring-2 focus:ring-cyan/50"
          title="뒤로 가기"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="font-display text-xl sm:text-2xl font-bold truncate">
            {activity.name || '활동'}
          </h1>
          <div className="flex flex-wrap items-center gap-2 sm:gap-4 text-xs sm:text-sm text-muted mt-1">
            <span className="flex items-center gap-1">
              <Calendar className="w-3 h-3 sm:w-4 sm:h-4" />
              {formatDateFull(activity.start_time)}
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3 sm:w-4 sm:h-4" />
              {formatTime(activity.start_time)}
            </span>
            {/* Gear (Shoes) */}
            {activityGear && activityGear.length > 0 && (
              <span className="flex items-center gap-1 text-amber">
                <Footprints className="w-3 h-3 sm:w-4 sm:h-4" />
                <span className="truncate max-w-[120px] sm:max-w-none">
                  {activityGear[0].name}
                </span>
                <span className={`font-mono ${getUsageColor(activityGear[0].usage_percentage)}`}>
                  ({((activityGear[0].total_distance_meters || 0) / 1000).toFixed(0)}km)
                </span>
              </span>
            )}
            {/* Sensors (Stryd, HR Monitor) */}
            {activity.sensors?.has_power_meter && (
              <span className="flex items-center gap-1 text-purple-400" title={activity.sensors.power_meter_name || 'Power Meter'}>
                <Gauge className="w-3 h-3 sm:w-4 sm:h-4" />
                <span className="hidden sm:inline">{activity.sensors.power_meter_name || 'PWR'}</span>
              </span>
            )}
            {activity.sensors?.has_hr_monitor && (
              <span className="flex items-center gap-1 text-red-400" title={activity.sensors.hr_monitor_name || 'HR Monitor'}>
                <Radio className="w-3 h-3 sm:w-4 sm:h-4" />
                <span className="hidden sm:inline">{activity.sensors.hr_monitor_name || 'HRM'}</span>
              </span>
            )}
            {/* Status indicators */}
            {activity.has_fit_file && (
              <span className="flex items-center gap-1 text-green-400">
                <FileCheck className="w-3 h-3" />
                <span className="hidden sm:inline">FIT</span>
              </span>
            )}
            {activity.has_samples && (
              <span className="flex items-center gap-1 text-cyan">
                <Activity className="w-3 h-3" />
                <span className="hidden sm:inline">샘플</span>
              </span>
            )}
          </div>
        </div>
        <button className="btn btn-secondary flex items-center gap-2 w-fit focus:ring-2 focus:ring-cyan/50">
          <Download className="w-4 h-4" />
          <span className="hidden sm:inline">내보내기</span>
        </button>
      </div>

      {/* Primary Stats - Compact Layout */}
      <div className="grid grid-cols-4 gap-2 sm:gap-3">
        <div className="card-accent p-2 sm:p-3">
          <div className="flex items-center gap-1.5 mb-0.5 sm:mb-1">
            <MapPin className="w-3 h-3 text-cyan" />
            <span className="text-[9px] sm:text-[10px] text-muted uppercase tracking-wider">거리</span>
          </div>
          <div className="font-mono text-base sm:text-lg font-bold">{distanceKm.toFixed(2)} km</div>
        </div>

        <div className="card p-2 sm:p-3">
          <div className="flex items-center gap-1.5 mb-0.5 sm:mb-1">
            <Clock className="w-3 h-3 text-muted" />
            <span className="text-[9px] sm:text-[10px] text-muted uppercase tracking-wider">시간</span>
          </div>
          <div className="font-mono text-base sm:text-lg font-bold">
            {formatDuration(activity.duration_seconds)}
          </div>
        </div>

        <div className="card p-2 sm:p-3">
          <div className="flex items-center gap-1.5 mb-0.5 sm:mb-1">
            <Zap className="w-3 h-3 text-amber" />
            <span className="text-[9px] sm:text-[10px] text-muted uppercase tracking-wider">페이스</span>
          </div>
          <div className="font-mono text-base sm:text-lg font-bold text-cyan">
            {formatPace(activity.avg_pace_seconds)}/km
          </div>
        </div>

        <div className="card p-2 sm:p-3">
          <div className="flex items-center gap-1.5 mb-0.5 sm:mb-1">
            <Heart className="w-3 h-3 text-red-400" />
            <span className="text-[9px] sm:text-[10px] text-muted uppercase tracking-wider">심박</span>
          </div>
          <div className="font-mono text-base sm:text-lg font-bold">
            {activity.avg_hr ?? '--'}
            {activity.max_hr && <span className="text-muted text-xs font-normal"> / {activity.max_hr}</span>}
          </div>
        </div>
      </div>

      {/* GPS Map and Km Pace Chart */}
      {samplesData?.samples && samplesData.samples.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 sm:gap-4">
          {/* GPS Map */}
          <Suspense
            fallback={
              <div className="card h-[280px] flex items-center justify-center">
                <div className="text-cyan animate-pulse">지도 불러오는 중...</div>
              </div>
            }
          >
            <div className="h-[280px] lg:h-auto lg:min-h-[280px]">
              <ActivityMap samples={samplesData.samples} />
            </div>
          </Suspense>

          {/* 1km Pace Chart */}
          {laps && laps.length > 0 && <KmPaceChart laps={laps} />}
        </div>
      )}

      {/* Training Metrics - 훈련 지표 */}
      <div className="card p-3 sm:p-4">
        <div className="flex items-center gap-2 mb-3 sm:mb-4">
          <Activity className="w-4 h-4 sm:w-5 sm:h-5 text-cyan" />
          <h3 className="font-display font-semibold text-sm sm:text-base">훈련 지표</h3>
        </div>
        <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-7 gap-2 sm:gap-3">
          {/* Calories */}
          <div className="relative text-center p-2 bg-[var(--color-bg-tertiary)] rounded-lg">
            <MetricTooltip description={metricDescriptions.calories} />
            <div className="font-mono text-lg sm:text-xl font-bold text-amber">
              {formatCalories(activity.calories)}
            </div>
            <div className="text-[10px] sm:text-xs text-muted">칼로리</div>
          </div>

          {/* Elevation Gain */}
          <div className="relative text-center p-2 bg-[var(--color-bg-tertiary)] rounded-lg">
            <MetricTooltip description={metricDescriptions.elevation_gain} />
            <div className="font-mono text-lg sm:text-xl font-bold text-green-400">
              +{activity.elevation_gain?.toFixed(0) ?? '--'}m
            </div>
            <div className="text-[10px] sm:text-xs text-muted">고도 상승</div>
          </div>

          {/* Elevation Loss */}
          <div className="relative text-center p-2 bg-[var(--color-bg-tertiary)] rounded-lg">
            <MetricTooltip description={metricDescriptions.elevation_loss} />
            <div className="font-mono text-lg sm:text-xl font-bold text-red-400">
              -{activity.elevation_loss?.toFixed(0) ?? '--'}m
            </div>
            <div className="text-[10px] sm:text-xs text-muted">고도 하강</div>
          </div>

          {/* Training Effect */}
          {activity.metrics?.training_effect && (
            <div className="relative text-center p-2 bg-[var(--color-bg-tertiary)] rounded-lg">
              <MetricTooltip description={metricDescriptions.training_effect} />
              <div className="font-mono text-lg sm:text-xl font-bold text-cyan">
                {activity.metrics.training_effect.toFixed(1)}
              </div>
              <div className="text-[10px] sm:text-xs text-muted">유산소 TE</div>
            </div>
          )}

          {/* TRIMP */}
          {activity.metrics?.trimp && (
            <div className="relative text-center p-2 bg-[var(--color-bg-tertiary)] rounded-lg">
              <MetricTooltip description={metricDescriptions.trimp} />
              <div className="font-mono text-lg sm:text-xl font-bold text-amber">
                {activity.metrics.trimp.toFixed(0)}
              </div>
              <div className="text-[10px] sm:text-xs text-muted">TRIMP</div>
            </div>
          )}

          {/* TSS */}
          {activity.metrics?.tss && (
            <div className="relative text-center p-2 bg-[var(--color-bg-tertiary)] rounded-lg">
              <MetricTooltip description={metricDescriptions.tss} />
              <div className="font-mono text-lg sm:text-xl font-bold text-green-400">
                {activity.metrics.tss.toFixed(0)}
              </div>
              <div className="text-[10px] sm:text-xs text-muted">TSS</div>
            </div>
          )}

          {/* Intensity Factor */}
          {activity.metrics?.intensity_factor && (
            <div className="relative text-center p-2 bg-[var(--color-bg-tertiary)] rounded-lg">
              <MetricTooltip description={metricDescriptions.intensity_factor} />
              <div className="font-mono text-lg sm:text-xl font-bold text-purple-400">
                {activity.metrics.intensity_factor.toFixed(2)}
              </div>
              <div className="text-[10px] sm:text-xs text-muted">IF</div>
            </div>
          )}
        </div>
      </div>

      {/* Power & Efficiency - 파워 & 효율 (파워미터가 있을 때만 표시) */}
      {activity.sensors?.has_power_meter && activity.metrics?.avg_power && (
        <div className="card p-3 sm:p-4">
          <div className="flex items-center gap-2 mb-3 sm:mb-4">
            <Gauge className="w-4 h-4 sm:w-5 sm:h-5 text-purple-400" />
            <h3 className="font-display font-semibold text-sm sm:text-base">파워 & 효율</h3>
            <span className="text-[10px] sm:text-xs text-purple-400 bg-purple-400/10 px-2 py-0.5 rounded">
              {activity.sensors.power_meter_name || 'Power Meter'}
            </span>
          </div>
          <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 sm:gap-3">
            {/* Avg Power */}
            <div className="relative text-center p-2 bg-[var(--color-bg-tertiary)] rounded-lg">
              <MetricTooltip description={metricDescriptions.avg_power} />
              <div className="font-mono text-lg sm:text-xl font-bold text-purple-400">
                {activity.metrics.avg_power}
              </div>
              <div className="text-[10px] sm:text-xs text-muted">평균 파워 (W)</div>
            </div>

            {/* Normalized Power */}
            {activity.metrics.normalized_power && (
              <div className="relative text-center p-2 bg-[var(--color-bg-tertiary)] rounded-lg">
                <MetricTooltip description={metricDescriptions.normalized_power} />
                <div className="font-mono text-lg sm:text-xl font-bold">
                  {activity.metrics.normalized_power}
                </div>
                <div className="text-[10px] sm:text-xs text-muted">NP (W)</div>
              </div>
            )}

            {/* Power-to-HR (Pa:Hr) */}
            {activity.metrics.power_to_hr && (
              <div className="relative text-center p-2 bg-[var(--color-bg-tertiary)] rounded-lg">
                <MetricTooltip description={metricDescriptions.power_to_hr} />
                <div className="font-mono text-lg sm:text-xl font-bold text-cyan">
                  {activity.metrics.power_to_hr.toFixed(2)}
                </div>
                <div className="text-[10px] sm:text-xs text-muted">Pa:Hr (W/bpm)</div>
              </div>
            )}

            {/* Effective VO2max */}
            {activity.metrics.vo2max_est && (
              <div className="relative text-center p-2 bg-[var(--color-bg-tertiary)] rounded-lg">
                <MetricTooltip description={metricDescriptions.vo2max} />
                <div className="font-mono text-lg sm:text-xl font-bold text-green-400">
                  {activity.metrics.vo2max_est.toFixed(1)}
                </div>
                <div className="text-[10px] sm:text-xs text-muted">VO2max</div>
              </div>
            )}

            {/* Running Effectiveness */}
            {activity.metrics.running_effectiveness && (
              <div className="relative text-center p-2 bg-[var(--color-bg-tertiary)] rounded-lg">
                <MetricTooltip description={metricDescriptions.running_effectiveness} />
                <div className="font-mono text-lg sm:text-xl font-bold text-amber">
                  {activity.metrics.running_effectiveness.toFixed(2)}
                </div>
                <div className="text-[10px] sm:text-xs text-muted">RE (m/kJ)</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Running Form - 러닝 폼 (파워미터가 있을 때만 표시) */}
      {activity.sensors?.has_power_meter && (activity.avg_cadence || activity.metrics?.ground_time) && (
        <div className="card p-3 sm:p-4">
          <div className="flex items-center gap-2 mb-3 sm:mb-4">
            <Footprints className="w-4 h-4 sm:w-5 sm:h-5 text-amber" />
            <h3 className="font-display font-semibold text-sm sm:text-base">러닝 폼</h3>
          </div>
          <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 sm:gap-3">
            {/* Cadence */}
            <div className="relative text-center p-2 bg-[var(--color-bg-tertiary)] rounded-lg">
              <MetricTooltip description={metricDescriptions.cadence} />
              <div className="font-mono text-lg sm:text-xl font-bold text-cyan">
                {activity.avg_cadence ?? '--'}
              </div>
              <div className="text-[10px] sm:text-xs text-muted">케이던스 (spm)</div>
            </div>

            {/* Ground Contact Time */}
            {activity.metrics?.ground_time && (
              <div className="relative text-center p-2 bg-[var(--color-bg-tertiary)] rounded-lg">
                <MetricTooltip description={metricDescriptions.ground_time} />
                <div className="font-mono text-lg sm:text-xl font-bold">
                  {activity.metrics.ground_time}
                </div>
                <div className="text-[10px] sm:text-xs text-muted">GCT (ms)</div>
              </div>
            )}

            {/* Vertical Oscillation */}
            {activity.metrics?.vertical_oscillation && (
              <div className="relative text-center p-2 bg-[var(--color-bg-tertiary)] rounded-lg">
                <MetricTooltip description={metricDescriptions.vertical_oscillation} />
                <div className="font-mono text-lg sm:text-xl font-bold text-green-400">
                  {activity.metrics.vertical_oscillation.toFixed(1)}
                </div>
                <div className="text-[10px] sm:text-xs text-muted">VO (cm)</div>
              </div>
            )}

            {/* Leg Spring Stiffness */}
            {activity.metrics?.leg_spring_stiffness && (
              <div className="relative text-center p-2 bg-[var(--color-bg-tertiary)] rounded-lg">
                <MetricTooltip description={metricDescriptions.leg_spring_stiffness} />
                <div className="font-mono text-lg sm:text-xl font-bold text-purple-400">
                  {activity.metrics.leg_spring_stiffness.toFixed(1)}
                </div>
                <div className="text-[10px] sm:text-xs text-muted">LSS (kN/m)</div>
              </div>
            )}

            {/* Form Power */}
            {activity.metrics?.form_power && (
              <div className="relative text-center p-2 bg-[var(--color-bg-tertiary)] rounded-lg">
                <MetricTooltip description={metricDescriptions.form_power} />
                <div className="font-mono text-lg sm:text-xl font-bold text-amber">
                  {activity.metrics.form_power}
                </div>
                <div className="text-[10px] sm:text-xs text-muted">Form Power (W)</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Charts Section */}
      {chartSamples.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
          {/* Heart Rate Chart */}
          <div className="card p-3 sm:p-4">
            <h3 className="font-display font-semibold mb-3 sm:mb-4 text-sm sm:text-base">심박수</h3>
            <div className="h-40 sm:h-48">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartSamples}>
                  <defs>
                    <linearGradient id="hrGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#ff4757" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#ff4757" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="time"
                    tickFormatter={(v) => `${Math.floor(v / 60)}분`}
                    stroke="#484f58"
                    fontSize={10}
                  />
                  <YAxis domain={['dataMin - 10', 'dataMax + 10']} stroke="#484f58" fontSize={10} />
                  <Tooltip
                    contentStyle={{
                      background: '#1c2128',
                      border: '1px solid #30363d',
                      borderRadius: '8px',
                    }}
                    formatter={(value) => [`${value} bpm`, '심박']}
                    labelFormatter={(label) => `${Math.floor(Number(label) / 60)}분`}
                  />
                  <Area
                    type="monotone"
                    dataKey="hr"
                    stroke="#ff4757"
                    fill="url(#hrGradient)"
                    strokeWidth={2}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Pace Chart */}
          <div className="card p-3 sm:p-4">
            <h3 className="font-display font-semibold mb-3 sm:mb-4 text-sm sm:text-base">페이스</h3>
            <div className="h-40 sm:h-48">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartSamples}>
                  <XAxis
                    dataKey="time"
                    tickFormatter={(v) => `${Math.floor(v / 60)}분`}
                    stroke="#484f58"
                    fontSize={10}
                  />
                  <YAxis
                    domain={['dataMin - 0.5', 'dataMax + 0.5']}
                    tickFormatter={(v) => formatPaceFromDecimal(v)}
                    stroke="#484f58"
                    fontSize={10}
                    reversed
                  />
                  <Tooltip
                    contentStyle={{
                      background: '#1c2128',
                      border: '1px solid #30363d',
                      borderRadius: '8px',
                    }}
                    formatter={(value) => [formatPaceFromDecimal(Number(value)) + '/km', '페이스']}
                    labelFormatter={(label) => `${Math.floor(Number(label) / 60)}분`}
                  />
                  <Line type="monotone" dataKey="pace" stroke="#00d4ff" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* HR Zones */}
      {hrZones && hrZones.length > 0 && (
        <div className="card p-3 sm:p-4">
          <h3 className="font-display font-semibold mb-3 sm:mb-4 text-sm sm:text-base">심박 존</h3>
          <div className="space-y-2 sm:space-y-3">
            {hrZones.map((zone) => (
              <div key={zone.zone} className="flex items-center gap-2 sm:gap-4">
                <div className="w-16 sm:w-24 text-xs sm:text-sm flex-shrink-0">
                  <span className="font-semibold">Z{zone.zone}</span>
                  <span className="text-muted ml-1 sm:ml-2">{getHRZoneName(zone.zone)}</span>
                </div>
                <div className="flex-1 h-4 sm:h-6 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${zone.percentage}%`,
                      backgroundColor: getHRZoneColor(zone.zone),
                    }}
                  />
                </div>
                <div className="w-20 sm:w-24 text-right flex-shrink-0">
                  <span className="font-mono text-xs sm:text-sm">
                    {formatDuration(zone.time_seconds)}
                  </span>
                  <span className="text-muted text-[10px] sm:text-xs ml-1">
                    ({zone.percentage.toFixed(0)}%)
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Laps Table */}
      {laps && laps.length > 0 && (
        <div className="card p-3 sm:p-4">
          <h3 className="font-display font-semibold mb-3 sm:mb-4 text-sm sm:text-base">랩</h3>
          <div className="overflow-x-auto -mx-3 sm:mx-0">
            <table className="table w-full text-xs sm:text-sm">
              <thead>
                <tr>
                  <th className="px-2 sm:px-4">랩</th>
                  <th className="px-2 sm:px-4">거리</th>
                  <th className="px-2 sm:px-4">시간</th>
                  <th className="px-2 sm:px-4">페이스</th>
                  <th className="px-2 sm:px-4">심박</th>
                  <th className="px-2 sm:px-4">고도</th>
                </tr>
              </thead>
              <tbody>
                {displayedLaps.map((lap) => (
                  <tr key={lap.lap_number}>
                    <td className="font-mono px-2 sm:px-4">{lap.lap_number}</td>
                    <td className="font-mono px-2 sm:px-4">
                      {((lap.distance_meters || 0) / 1000).toFixed(2)} km
                    </td>
                    <td className="font-mono px-2 sm:px-4">{formatDuration(lap.duration_seconds)}</td>
                    <td className="font-mono text-cyan px-2 sm:px-4">
                      {formatPace(lap.avg_pace_seconds)}/km
                    </td>
                    <td className="font-mono px-2 sm:px-4">
                      <span className="flex items-center gap-1">
                        <Heart className="w-3 h-3 text-red-400" />
                        {lap.avg_hr ?? '--'}
                      </span>
                    </td>
                    <td className="font-mono px-2 sm:px-4">
                      <span className="flex items-center gap-1">
                        <TrendingUp className="w-3 h-3 text-green-400" />
                        {lap.elevation_gain ?? '--'}m
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(laps?.length || 0) > 5 && (
            <button
              onClick={() => setShowAllLaps(!showAllLaps)}
              className="mt-3 sm:mt-4 text-xs sm:text-sm text-cyan flex items-center gap-1 hover:underline focus:outline-none focus:ring-2 focus:ring-cyan/50 rounded"
            >
              {showAllLaps ? (
                <>
                  <ChevronUp className="w-4 h-4" />
                  접기
                </>
              ) : (
                <>
                  <ChevronDown className="w-4 h-4" />
                  전체 {laps?.length}개 랩 보기
                </>
              )}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
