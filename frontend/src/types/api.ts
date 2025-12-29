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
  duration_minutes: number | null;
  avg_hr: number | null;
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

// Activity Types
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

// Connection Status
export interface ConnectionStatus {
  garmin_connected: boolean;
  strava_connected: boolean;
  last_sync: string | null;
}
