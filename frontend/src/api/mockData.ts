import type {
  DashboardSummary,
  CompareResponse,
  TrendsResponse,
  PersonalRecordsResponse,
  CalendarResponse,
  CalendarDay,
} from '../types/api';

export const mockDashboardSummary: DashboardSummary = {
  period_type: 'week',
  period_start: '2024-12-23',
  period_end: '2024-12-29',
  summary: {
    total_distance_km: 42.5,
    total_duration_hours: 4.2,
    total_activities: 5,
    avg_pace_per_km: '5:56/km',
    avg_pace_seconds: 356, // 5분 56초 = 356초
    avg_hr: 152,
    total_elevation_m: 385,
    total_calories: 2850,
  },
  recent_activities: [
    {
      id: 1,
      name: '트레드밀 러닝',
      activity_type: 'running',
      start_time: '2024-12-29T07:30:00Z',
      distance_km: 20.0,
      duration_seconds: 7202, // 2:00:02
      avg_pace_seconds: 360, // 6:00/km
      avg_hr_percent: 72,
      elevation_gain: null,
      calories: 1248,
      trimp: 153,
      vo2max_est: null,
      avg_cadence: 178,
      avg_ground_time: 258,
      avg_vertical_oscillation: 8.0,
    },
    {
      id: 2,
      name: '템포 러닝',
      activity_type: 'running',
      start_time: '2024-12-27T18:00:00Z',
      distance_km: 10.0,
      duration_seconds: 3120, // 52:00
      avg_pace_seconds: 312, // 5:12/km
      avg_hr_percent: 87,
      elevation_gain: 120,
      calories: 680,
      trimp: 115,
      vo2max_est: 46.2,
      avg_cadence: 182,
      avg_ground_time: 245,
      avg_vertical_oscillation: 7.5,
    },
    {
      id: 3,
      name: '회복 조깅',
      activity_type: 'running',
      start_time: '2024-12-26T07:00:00Z',
      distance_km: 5.5,
      duration_seconds: 2100, // 35:00
      avg_pace_seconds: 382, // 6:22/km
      avg_hr_percent: 71,
      elevation_gain: 45,
      calories: 320,
      trimp: 42,
      vo2max_est: 42.5,
      avg_cadence: 170,
      avg_ground_time: 268,
      avg_vertical_oscillation: 8.5,
    },
    {
      id: 4,
      name: '장거리 러닝',
      activity_type: 'running',
      start_time: '2024-12-24T08:00:00Z',
      distance_km: 15.0,
      duration_seconds: 5700, // 1:35:00
      avg_pace_seconds: 380, // 6:20/km
      avg_hr_percent: 78,
      elevation_gain: 185,
      calories: 980,
      trimp: 145,
      vo2max_est: 44.8,
      avg_cadence: 175,
      avg_ground_time: 262,
      avg_vertical_oscillation: 8.2,
    },
    {
      id: 5,
      name: '인터벌 훈련',
      activity_type: 'running',
      start_time: '2024-12-23T18:30:00Z',
      distance_km: 6.8,
      duration_seconds: 2520, // 42:00
      avg_pace_seconds: 371, // 6:11/km
      avg_hr_percent: 91,
      elevation_gain: 65,
      calories: 520,
      trimp: 111,
      vo2max_est: 48.5,
      avg_cadence: 185,
      avg_ground_time: 235,
      avg_vertical_oscillation: 7.0,
    },
  ],
  health_status: {
    latest_sleep_score: 85,
    latest_sleep_hours: 7.5,
    resting_hr: 52,
    body_battery: 78,
    vo2max: 52.4,
  },
  fitness_status: {
    ctl: 71,
    atl: 70,
    tsb: -27,
    weekly_trimp: 485,
    weekly_tss: 312,
    // Runalyze-style extended metrics
    effective_vo2max: 44.29,
    marathon_shape: 92,
    workload_ratio: 1.29,
    rest_days: 1.1,
    monotony: 54,
    training_strain: 1073,
  },
  upcoming_workouts: [
    {
      id: 1,
      workout_name: 'Easy Recovery',
      workout_type: 'easy',
      scheduled_date: '2024-12-30',
    },
    {
      id: 2,
      workout_name: 'Threshold Intervals',
      workout_type: 'tempo',
      scheduled_date: '2024-12-31',
    },
  ],
  // Daniels Training Paces (VDOT ~44 기준)
  training_paces: {
    vdot: 44,
    easy_min: 343, // 5:43/km
    easy_max: 430, // 7:10/km
    marathon_min: 302, // 5:02/km
    marathon_max: 338, // 5:38/km
    threshold_min: 276, // 4:36/km
    threshold_max: 288, // 4:48/km
    interval_min: 254, // 4:14/km
    interval_max: 267, // 4:27/km
    repetition_min: 231, // 3:51/km
    repetition_max: 242, // 4:02/km
  },
};

export const mockCompareResponse: CompareResponse = {
  current_period: {
    period_start: '2024-12-23',
    period_end: '2024-12-29',
    total_distance_km: 42.5,
    total_duration_hours: 4.2,
    total_activities: 5,
    avg_pace_per_km: '5:56/km',
    avg_hr: 152,
    total_elevation_m: 385,
    total_calories: 2850,
    total_trimp: 485,
    total_tss: 312,
  },
  previous_period: {
    period_start: '2024-12-16',
    period_end: '2024-12-22',
    total_distance_km: 38.2,
    total_duration_hours: 3.8,
    total_activities: 4,
    avg_pace_per_km: '6:02/km',
    avg_hr: 148,
    total_elevation_m: 320,
    total_calories: 2450,
    total_trimp: 410,
    total_tss: 275,
  },
  change: {
    distance_change_pct: 11.3,
    duration_change_pct: 10.5,
    activities_change: 1,
    pace_change_seconds: -6,
    elevation_change_pct: 20.3,
  },
  improvement_summary: '거리 11.3% 증가, 페이스 6초/km 향상, 활동 1회 증가',
};

export const mockTrendsResponse: TrendsResponse = {
  weekly_distance: [
    { date: '2024-11-04', value: 35.2 },
    { date: '2024-11-11', value: 38.5 },
    { date: '2024-11-18', value: 42.1 },
    { date: '2024-11-25', value: 36.8 },
    { date: '2024-12-02', value: 40.2 },
    { date: '2024-12-09', value: 44.5 },
    { date: '2024-12-16', value: 38.2 },
    { date: '2024-12-23', value: 42.5 },
  ],
  weekly_duration: [
    { date: '2024-11-04', value: 3.5 },
    { date: '2024-11-11', value: 3.8 },
    { date: '2024-11-18', value: 4.2 },
    { date: '2024-11-25', value: 3.6 },
    { date: '2024-12-02', value: 4.0 },
    { date: '2024-12-09', value: 4.4 },
    { date: '2024-12-16', value: 3.8 },
    { date: '2024-12-23', value: 4.2 },
  ],
  avg_pace: [
    { date: '2024-11-04', value: 362 },
    { date: '2024-11-11', value: 358 },
    { date: '2024-11-18', value: 355 },
    { date: '2024-11-25', value: 360 },
    { date: '2024-12-02', value: 356 },
    { date: '2024-12-09', value: 352 },
    { date: '2024-12-16', value: 362 },
    { date: '2024-12-23', value: 356 },
  ],
  resting_hr: [
    { date: '2024-11-04', value: 54 },
    { date: '2024-11-11', value: 53 },
    { date: '2024-11-18', value: 52 },
    { date: '2024-11-25', value: 54 },
    { date: '2024-12-02', value: 53 },
    { date: '2024-12-09', value: 51 },
    { date: '2024-12-16', value: 53 },
    { date: '2024-12-23', value: 52 },
  ],
  ctl_atl: [
    { date: '2024-11-04', ctl: 45.2, atl: 52.1, tsb: -6.9 },
    { date: '2024-11-11', ctl: 48.5, atl: 58.3, tsb: -9.8 },
    { date: '2024-11-18', ctl: 52.1, atl: 65.2, tsb: -13.1 },
    { date: '2024-11-25', ctl: 50.8, atl: 55.4, tsb: -4.6 },
    { date: '2024-12-02', ctl: 53.2, atl: 62.8, tsb: -9.6 },
    { date: '2024-12-09', ctl: 56.5, atl: 70.2, tsb: -13.7 },
    { date: '2024-12-16', ctl: 55.8, atl: 65.5, tsb: -9.7 },
    { date: '2024-12-23', ctl: 58.2, atl: 72.5, tsb: -14.3 },
  ],
};

// Calendar mock data - 2024년 12월 기준 4주간 데이터
export const mockCalendarResponse: CalendarResponse = {
  start_date: '2024-12-01',
  end_date: '2024-12-31',
  days: generateMockCalendarDays(),
};

function generateMockCalendarDays(): CalendarDay[] {
  const days: CalendarDay[] = [];

  // 활동 데이터 (완료된 러닝)
  const activityDates: Record<string, { id: number; name: string; distance_km: number; duration_minutes: number; avg_hr: number }[]> = {
    '2024-12-29': [{ id: 1, name: '아침 이지런', distance_km: 8.2, duration_minutes: 48, avg_hr: 145 }],
    '2024-12-27': [{ id: 2, name: '템포런', distance_km: 10.0, duration_minutes: 52, avg_hr: 165 }],
    '2024-12-26': [{ id: 3, name: '회복 조깅', distance_km: 5.5, duration_minutes: 35, avg_hr: 135 }],
    '2024-12-24': [{ id: 4, name: '장거리 러닝', distance_km: 15.0, duration_minutes: 95, avg_hr: 148 }],
    '2024-12-23': [{ id: 5, name: '인터벌 훈련', distance_km: 6.8, duration_minutes: 42, avg_hr: 172 }],
    '2024-12-21': [{ id: 6, name: '주말 롱런', distance_km: 18.5, duration_minutes: 108, avg_hr: 150 }],
    '2024-12-19': [{ id: 7, name: '이지런', distance_km: 7.0, duration_minutes: 42, avg_hr: 140 }],
    '2024-12-17': [{ id: 8, name: '파틀렉', distance_km: 8.0, duration_minutes: 45, avg_hr: 158 }],
    '2024-12-15': [{ id: 9, name: '롱런', distance_km: 16.2, duration_minutes: 98, avg_hr: 145 }],
    '2024-12-13': [{ id: 10, name: '회복 러닝', distance_km: 5.0, duration_minutes: 32, avg_hr: 138 }],
    '2024-12-11': [{ id: 11, name: '템포런', distance_km: 10.5, duration_minutes: 54, avg_hr: 162 }],
    '2024-12-09': [{ id: 12, name: '아침 러닝', distance_km: 7.5, duration_minutes: 44, avg_hr: 142 }],
    '2024-12-07': [{ id: 13, name: '롱런', distance_km: 20.0, duration_minutes: 120, avg_hr: 148 }],
    '2024-12-05': [{ id: 14, name: '이지런', distance_km: 6.0, duration_minutes: 36, avg_hr: 135 }],
    '2024-12-03': [{ id: 15, name: '인터벌', distance_km: 8.2, duration_minutes: 46, avg_hr: 170 }],
  };

  // 예정된 운동
  const workoutDates: Record<string, { id: number; workout_name: string; workout_type: string }[]> = {
    '2024-12-30': [{ id: 1, workout_name: '회복 러닝', workout_type: 'easy' }],
    '2024-12-31': [{ id: 2, workout_name: '역치 인터벌', workout_type: 'tempo' }],
  };

  // 12월 전체 날짜 생성
  for (let day = 1; day <= 31; day++) {
    const dateStr = `2024-12-${String(day).padStart(2, '0')}`;
    const activities = activityDates[dateStr] || [];
    const workouts = workoutDates[dateStr] || [];

    days.push({
      date: dateStr,
      activities: activities.map(a => ({
        id: a.id,
        name: a.name,
        activity_type: 'running',
        start_time: `${dateStr}T07:00:00Z`,
        distance_km: a.distance_km,
        duration_seconds: a.duration_minutes * 60,
        avg_pace_seconds: Math.round((a.duration_minutes * 60) / a.distance_km),
        avg_hr_percent: Math.round((a.avg_hr / 190) * 100),
        elevation_gain: 50,
        calories: Math.round(a.distance_km * 60),
        trimp: Math.round(a.duration_minutes * 1.5),
        vo2max_est: null,
        avg_cadence: 175,
        avg_ground_time: 255,
        avg_vertical_oscillation: 8.0,
      })),
      scheduled_workouts: workouts.map(w => ({
        id: w.id,
        workout_name: w.workout_name,
        workout_type: w.workout_type,
        scheduled_date: dateStr,
      })),
    });
  }

  return days;
}

export const mockPersonalRecords: PersonalRecordsResponse = {
  distance_records: [
    {
      category: '5K',
      value: 1245,
      unit: 'seconds',
      activity_id: 101,
      activity_name: '5K Race',
      achieved_date: '2024-10-15',
      previous_best: 1280,
      improvement_pct: 2.7,
    },
    {
      category: '10K',
      value: 2680,
      unit: 'seconds',
      activity_id: 85,
      activity_name: '10K Tempo',
      achieved_date: '2024-09-22',
      previous_best: 2750,
      improvement_pct: 2.5,
    },
    {
      category: 'Half Marathon',
      value: 5820,
      unit: 'seconds',
      activity_id: 62,
      activity_name: 'Seoul Half Marathon',
      achieved_date: '2024-04-14',
      previous_best: 6120,
      improvement_pct: 4.9,
    },
  ],
  pace_records: [
    {
      category: '5K Pace',
      value: 249,
      unit: 'sec/km',
      activity_id: 101,
      activity_name: '5K Race',
      achieved_date: '2024-10-15',
      previous_best: 256,
      improvement_pct: 2.7,
    },
    {
      category: '10K Pace',
      value: 268,
      unit: 'sec/km',
      activity_id: 85,
      activity_name: '10K Tempo',
      achieved_date: '2024-09-22',
      previous_best: 275,
      improvement_pct: 2.5,
    },
  ],
  endurance_records: [
    {
      category: 'Longest Run',
      value: 32500,
      unit: 'meters',
      activity_id: 45,
      activity_name: 'Long Run Sunday',
      achieved_date: '2024-03-10',
      previous_best: 28000,
      improvement_pct: 16.1,
    },
    {
      category: 'Longest Duration',
      value: 12600,
      unit: 'seconds',
      activity_id: 45,
      activity_name: 'Long Run Sunday',
      achieved_date: '2024-03-10',
      previous_best: 10800,
      improvement_pct: 16.7,
    },
  ],
  recent_prs: [],
};
