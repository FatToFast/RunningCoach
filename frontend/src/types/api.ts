/**
 * API Response Types
 * Matches backend Pydantic models
 */

// Dashboard Types
export interface WeeklySummary {
  total_distance_km: number;
  total_duration_hours: number;
  total_activities: number;
  avg_pace_per_km: string;
  avg_pace_seconds: number | null; // 페이스를 초 단위로 (formatPace용)
  avg_hr: number | null;
  total_elevation_m: number | null;
  total_calories: number | null;
}

export interface RecentActivity {
  id: number;
  name: string | null;
  activity_type: string;
  start_time: string;
  distance_km: number | null;
  duration_seconds: number | null; // Duration in seconds (hh:mm:ss 포맷용)
  avg_pace_seconds: number | null; // 페이스 (초/km)
  avg_hr: number | null; // 평균 심박수 (bpm)
  avg_hr_percent: number | null; // 최대심박 대비 % (Runalyze: 72%)
  elevation_gain: number | null; // 고도 상승 (m)
  calories: number | null; // 에너지 (kcal)
  trimp: number | null; // TRIMP
  // Runalyze 추가 필드
  vo2max_est: number | null; // 활동별 VO2max 추정치
  avg_cadence: number | null; // 케이던스 (spm)
  avg_ground_time: number | null; // 지면 접촉 시간 (ms)
  avg_vertical_oscillation: number | null; // 수직 진동 (cm)
}

export interface HealthStatus {
  latest_sleep_score: number | null;
  latest_sleep_hours: number | null;
  resting_hr: number | null;
  body_battery: number | null;
  vo2max: number | null;
}

export interface FitnessStatus {
  ctl: number | null;
  atl: number | null;
  tsb: number | null;
  weekly_trimp: number | null;
  weekly_tss: number | null;
  // Extended Runalyze-style metrics
  effective_vo2max: number | null;
  marathon_shape: number | null; // percentage
  workload_ratio: number | null; // Acute:Chronic ratio (A:C)
  rest_days: number | null;
  monotony: number | null; // percentage
  training_strain: number | null;
}

// Daniels Training Paces based on VDOT
export interface TrainingPaces {
  vdot: number;
  easy_min: number; // seconds per km
  easy_max: number;
  marathon_min: number;
  marathon_max: number;
  threshold_min: number;
  threshold_max: number;
  interval_min: number;
  interval_max: number;
  repetition_min: number;
  repetition_max: number;
}

export interface UpcomingWorkout {
  id: number;
  workout_name: string;
  workout_type: string;
  scheduled_date: string;
}

export interface DashboardSummary {
  period_type: 'week' | 'month';
  period_start: string;
  period_end: string;
  summary: WeeklySummary;
  recent_activities: RecentActivity[];
  health_status: HealthStatus;
  fitness_status: FitnessStatus;
  upcoming_workouts: UpcomingWorkout[];
  training_paces: TrainingPaces | null;
}

// Analytics Types
export interface PeriodStats {
  period_start: string;
  period_end: string;
  total_distance_km: number;
  total_duration_hours: number;
  total_activities: number;
  avg_pace_per_km: string;
  avg_hr: number | null;
  total_elevation_m: number | null;
  total_calories: number | null;
  total_trimp: number | null;
  total_tss: number | null;
}

export interface PeriodChange {
  distance_change_pct: number | null;
  duration_change_pct: number | null;
  activities_change: number;
  pace_change_seconds: number | null;
  elevation_change_pct: number | null;
}

export interface CompareResponse {
  current_period: PeriodStats;
  previous_period: PeriodStats;
  change: PeriodChange;
  improvement_summary: string;
}

export interface PersonalRecord {
  category: string;
  value: number;
  unit: string;
  activity_id: number;
  activity_name: string | null;
  achieved_date: string;
  previous_best: number | null;
  improvement_pct: number | null;
}

export interface PersonalRecordsResponse {
  distance_records: PersonalRecord[];
  pace_records: PersonalRecord[];
  endurance_records: PersonalRecord[];
  recent_prs: PersonalRecord[];
}

// Trends Types
export interface TrendPoint {
  date: string;
  value: number;
}

export interface CTLATLPoint {
  date: string;
  ctl: number | null;
  atl: number | null;
  tsb: number | null;
}

export interface TrendsResponse {
  weekly_distance: TrendPoint[];
  weekly_duration: TrendPoint[];
  avg_pace: TrendPoint[];
  resting_hr: TrendPoint[];
  ctl_atl: CTLATLPoint[];
}

// -------------------------------------------------------------------------
// Calendar Types (백엔드: /dashboard/calendar)
// -------------------------------------------------------------------------

// Calendar Day (백엔드: CalendarDay)
export interface CalendarDay {
  date: string;
  activities: RecentActivity[];
  scheduled_workouts: UpcomingWorkout[];
}

// Calendar Response (백엔드: CalendarResponse)
export interface CalendarResponse {
  days: CalendarDay[];
  start_date: string;
  end_date: string;
}

// -------------------------------------------------------------------------
// Activity Types (백엔드 Pydantic 모델과 일치)
// -------------------------------------------------------------------------

export interface ActivitySummary {
  id: number;
  garmin_id: number;
  activity_type: string;
  name: string | null;
  start_time: string;
  duration_seconds: number | null;
  distance_meters: number | null;
  avg_hr: number | null;
  avg_pace_seconds: number | null;
  calories: number | null;
}

export interface ActivityListResponse {
  items: ActivitySummary[];
  total: number;
  page: number;
  per_page: number;
}

// Activity Metrics (백엔드: ActivityMetricResponse)
export interface ActivityMetrics {
  // From ActivityMetric table
  trimp: number | null;
  tss: number | null;
  training_effect: number | null;
  vo2max_est: number | null;
  efficiency_factor: number | null;
  // Power Metrics (from Activity table / FIT session)
  avg_power: number | null;
  max_power: number | null;
  normalized_power: number | null;
  intensity_factor: number | null; // IF (NP/FTP)
  // Running Dynamics (from FIT records)
  ground_time: number | null; // GCT in ms
  vertical_oscillation: number | null; // in cm
  stride_length: number | null; // in m
  leg_spring_stiffness: number | null; // in kN/m (calculated)
  form_power: number | null; // from Stryd
  // Calculated metrics
  power_to_hr: number | null; // Pa:Hr ratio (W/bpm)
  running_effectiveness: number | null; // m/kJ
}

// 활동에 사용된 센서/장비 정보
export interface ActivitySensors {
  has_power_meter: boolean; // Stryd 등 파워미터
  has_hr_monitor: boolean; // 외장 심박계 (Garmin HRM, Polar 등)
  has_footpod: boolean; // 풋팟
  power_meter_name: string | null; // 'Stryd', 'Garmin RD Pod' 등
  hr_monitor_name: string | null; // 'HRM-Pro', 'Polar H10' 등
}

// Activity Detail (백엔드: ActivityDetailResponse)
export interface ActivityDetail {
  id: number;
  garmin_id: number;
  activity_type: string;
  name: string | null;
  start_time: string;
  // Duration and distance
  duration_seconds: number | null;
  elapsed_seconds: number | null; // Total elapsed time including pauses
  distance_meters: number | null;
  calories: number | null;
  // Heart rate
  avg_hr: number | null;
  max_hr: number | null;
  // Pace
  avg_pace_seconds: number | null;
  best_pace_seconds: number | null; // Fastest pace during activity
  // Elevation
  elevation_gain: number | null;
  elevation_loss: number | null;
  // Cadence
  avg_cadence: number | null;
  max_cadence: number | null;
  // Training effect & VO2Max (from Garmin)
  training_effect_aerobic: number | null;
  training_effect_anaerobic: number | null;
  vo2max: number | null;
  // Extended data
  metrics: ActivityMetrics | null;
  sensors: ActivitySensors | null;
  has_fit_file: boolean;
  has_samples: boolean;
  created_at: string;
  updated_at: string;
}

// Activity Sample (백엔드: SampleResponse)
export interface ActivitySample {
  timestamp: string;
  hr: number | null;
  pace_seconds: number | null;
  cadence: number | null;
  power: number | null;
  latitude: number | null;
  longitude: number | null;
  altitude: number | null;
}

// Activity Samples Response (백엔드: SamplesListResponse)
export interface ActivitySamplesResponse {
  activity_id: number;
  samples: ActivitySample[];
  total: number;
  is_downsampled: boolean;
  original_count: number | null;
}

// -------------------------------------------------------------------------
// HR Zones API (백엔드: /activities/{id}/hr-zones)
// -------------------------------------------------------------------------

// HR Zone (백엔드: HRZoneResponse)
export interface HRZone {
  zone: number;
  name: string;
  min_hr: number;
  max_hr: number;
  time_seconds: number;
  percentage: number;
}

// HR Zones Response (백엔드: HRZonesResponse)
export interface HRZonesResponse {
  activity_id: number;
  max_hr: number;
  zones: HRZone[];
  total_time_in_zones: number;
}

// -------------------------------------------------------------------------
// Laps API (백엔드: /activities/{id}/laps)
// -------------------------------------------------------------------------

// Activity Lap (백엔드: LapResponse)
export interface ActivityLap {
  lap_number: number;
  start_time: string;
  end_time: string;
  duration_seconds: number;
  distance_meters: number | null;
  avg_hr: number | null;
  max_hr: number | null;
  avg_pace_seconds: number | null;
  elevation_gain: number | null;
  avg_cadence: number | null;
}

// Laps Response (백엔드: LapsResponse)
export interface LapsResponse {
  activity_id: number;
  laps: ActivityLap[];
  total_laps: number;
}

// -------------------------------------------------------------------------
// Gear (신발/장비) Types
// -------------------------------------------------------------------------

export type GearType = 'running_shoes' | 'cycling_shoes' | 'bike' | 'other';
export type GearStatus = 'active' | 'retired';

export interface Gear {
  id: number;
  garmin_uuid: string | null;
  name: string;
  brand: string | null;
  model: string | null;
  gear_type: GearType;
  status: GearStatus;
  purchase_date: string | null;
  initial_distance_meters: number; // 등록 전 기존 거리
  total_distance_meters: number; // 총 누적 거리
  max_distance_meters: number | null; // 권장 최대 거리 (신발 수명)
  activity_count: number;
  notes: string | null;
  image_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface GearSummary {
  id: number;
  name: string;
  brand: string | null;
  gear_type: GearType;
  status: GearStatus;
  total_distance_meters: number;
  max_distance_meters: number | null;
  activity_count: number;
  usage_percentage: number | null; // 수명 대비 사용률
}

export interface GearListResponse {
  items: GearSummary[];
  total: number;
}

export interface GearStats {
  total_gears: number;
  active_gears: number;
  retired_gears: number;
  gears_near_retirement: GearSummary[]; // 80% 이상 사용
}

// 활동-장비 연결
export interface ActivityGear {
  activity_id: number;
  gear_id: number;
  gear_name: string;
  gear_type: GearType;
}

// -------------------------------------------------------------------------
// Connection Status
// -------------------------------------------------------------------------

export interface GarminConnectionStatus {
  connected: boolean;
  last_sync: string | null;
}

export interface StravaConnectionStatus {
  connected: boolean;
  last_sync: string | null;
}

// 통합 상태 (프론트엔드에서 조합하여 사용)
export interface ConnectionStatus {
  garmin: GarminConnectionStatus;
  strava: StravaConnectionStatus;
  runalyze?: RunalyzeConnectionStatus;
}

// -------------------------------------------------------------------------
// Runalyze Integration Types (HRV, Sleep)
// -------------------------------------------------------------------------

export interface RunalyzeConnectionStatus {
  connected: boolean;
  message: string;
}

export interface RunalyzeHRVDataPoint {
  id: number;
  date_time: string;
  hrv: number;
  rmssd: number;
  metric: string;
  measurement_type: string;
}

export interface RunalyzeHRVResponse {
  data: RunalyzeHRVDataPoint[];
  count: number;
}

export interface RunalyzeSleepDataPoint {
  id: number;
  date_time: string;
  duration: number; // minutes
  rem_duration: number | null;
  light_sleep_duration: number | null;
  deep_sleep_duration: number | null;
  awake_duration: number | null;
  quality: number | null; // 1-10
  source: string | null;
}

export interface RunalyzeSleepResponse {
  data: RunalyzeSleepDataPoint[];
  count: number;
}

export interface RunalyzeSummary {
  latest_hrv: number | null;
  latest_hrv_date: string | null;
  avg_hrv_7d: number | null;
  latest_sleep_quality: number | null;
  latest_sleep_duration: number | null;
  latest_sleep_date: string | null;
  avg_sleep_quality_7d: number | null;
}

// -------------------------------------------------------------------------
// Strength Training Types (보강운동)
// -------------------------------------------------------------------------

export type SessionType = 'upper' | 'lower' | 'core' | 'full_body';
export type SessionPurpose = 'strength' | 'flexibility' | 'balance' | 'injury_prevention';

export interface ExerciseSet {
  weight_kg: number | null;
  reps: number;
  rest_seconds: number | null;
}

export interface StrengthExercise {
  id: number;
  exercise_name: string;
  is_custom: boolean;
  order: number;
  sets: ExerciseSet[];
  notes: string | null;
}

export interface StrengthSession {
  id: number;
  session_date: string;
  session_type: SessionType;
  session_purpose: SessionPurpose | null;
  duration_minutes: number | null;
  notes: string | null;
  rating: number | null;
  exercises: StrengthExercise[];
  total_sets: number;
  total_exercises: number;
  created_at: string;
  updated_at: string;
}

export interface StrengthSessionSummary {
  id: number;
  session_date: string;
  session_type: SessionType;
  session_purpose: SessionPurpose | null;
  duration_minutes: number | null;
  rating: number | null;
  exercise_count: number;
  total_sets: number;
}

export interface StrengthSessionListResponse {
  items: StrengthSessionSummary[];
  total: number;
}

export interface SessionTypeInfo {
  value: string;
  label: string;
  label_en: string;
}

export interface SessionTypesResponse {
  types: SessionTypeInfo[];
  purposes: SessionTypeInfo[];
}

export interface ExercisePreset {
  name: string;
  name_en: string;
  category: string;
}

export interface ExercisePresetsResponse {
  exercises: ExercisePreset[];
}

// Calendar Notes (메모)
export interface CalendarNote {
  id: number;
  date: string;
  note_type: string;
  content: string;
  icon: string | null;
}

export interface CalendarNoteCreate {
  date: string;
  note_type: string;
  content: string;
  icon?: string | null;
}

export interface CalendarNotesResponse {
  notes: CalendarNote[];
}

export interface NoteTypeInfo {
  value: string;
  label: string;
  icon: string;
}

export interface NoteTypesResponse {
  types: NoteTypeInfo[];
}
