export interface Activity {
  id: number
  garmin_activity_id: string
  activity_type: string
  start_time: string
  duration_seconds: number
  distance_meters: number
  avg_heart_rate: number | null
  max_heart_rate: number | null
  avg_pace_seconds: number | null
  calories: number | null
  elevation_gain: number | null
  avg_cadence: number | null
  training_effect_aerobic: number | null
  training_effect_anaerobic: number | null
  vo2max: number | null
  created_at: string
  // Stryd 파워 데이터
  avg_power: number | null
  max_power: number | null
  normalized_power: number | null
  // 러닝 다이나믹스
  avg_ground_contact_time: number | null
  avg_vertical_oscillation: number | null
  avg_stride_length: number | null
  avg_leg_spring_stiffness: number | null
  // 심박존 시간 (초)
  hr_zone_1_seconds: number | null
  hr_zone_2_seconds: number | null
  hr_zone_3_seconds: number | null
  hr_zone_4_seconds: number | null
  hr_zone_5_seconds: number | null
}

export interface DailyStats {
  id: number
  date: string
  // 심박수
  resting_heart_rate: number | null
  max_heart_rate: number | null
  avg_heart_rate: number | null
  // HRV
  hrv_weekly_avg: number | null
  hrv_last_night: number | null
  hrv_status: string | null
  // Body Battery
  body_battery_high: number | null
  body_battery_low: number | null
  body_battery_charged: number | null
  body_battery_drained: number | null
  // 스트레스
  avg_stress_level: number | null
  max_stress_level: number | null
  stress_duration_seconds: number | null
  rest_duration_seconds: number | null
  // 수면
  sleep_duration_seconds: number | null
  deep_sleep_seconds: number | null
  light_sleep_seconds: number | null
  rem_sleep_seconds: number | null
  awake_seconds: number | null
  sleep_score: number | null
  // 활동
  steps: number | null
  floors_climbed: number | null
  active_calories: number | null
  total_calories: number | null
  // 호흡
  avg_respiration_rate: number | null
  // SpO2
  avg_spo2: number | null
  min_spo2: number | null
  // Training Readiness
  training_readiness_score: number | null
  training_readiness_message: string | null
}

export interface TrainingStatus {
  vo2max_running: number | null
  vo2max_cycling: number | null
  fitness_age: number | null
  training_status: string | null
  training_status_message: string | null
  lactate_threshold_hr: number | null
  lactate_threshold_pace: string | null
  race_predictions: RacePredictions | null
}

export interface RacePredictions {
  five_k: string | null
  ten_k: string | null
  half_marathon: string | null
  marathon: string | null
}

export interface WeeklySummary {
  total_distance_km: number
  total_duration_minutes: number
  total_activities: number
  avg_pace: string | null
  avg_heart_rate: number | null
  total_calories: number
}

export interface DashboardSummary {
  weekly_summary: WeeklySummary
  current_vo2max: number | null
  recovery_time_hours: number | null
  training_status: string | null
  recent_activities: Activity[]
}

export interface TrainingLoadData {
  date: string
  load: number
  acute_load: number
  chronic_load: number
}

export interface Workout {
  id: number
  schedule_id: number
  date: string
  workout_type: string
  title: string
  description: string | null
  target_distance_meters: number | null
  target_duration_seconds: number | null
  target_pace: string | null
  intervals: string | null
  is_completed: boolean
  garmin_workout_id: string | null
}

export interface Schedule {
  id: number
  title: string
  description: string | null
  start_date: string
  end_date: string | null
  goal: string | null
  is_synced_to_garmin: boolean
  workouts: Workout[]
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  created_at?: string
}

export interface GarminAuthStatus {
  is_authenticated: boolean
  email: string | null
}

export interface FitnessStatus {
  acwr: number | null
  status: string
  recommendation: string
  acute_load: number
  chronic_load: number
}
