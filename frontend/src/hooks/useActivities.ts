import { useQuery } from '@tanstack/react-query';
import { activitiesApi, type ActivitiesParams } from '../api/activities';
import type {
  ActivityListResponse,
  ActivityDetail,
  ActivitySamplesResponse,
  ActivitySample,
  HRZone,
  ActivityLap,
} from '../types/api';

// Set to true to use mock data (when backend is not running)
const USE_MOCK_DATA = false;

// Mock data for activities list
const mockActivitiesList: ActivityListResponse = {
  items: [
    {
      id: 1,
      garmin_id: 123456789,
      activity_type: 'running',
      name: 'Morning Easy Run',
      start_time: '2024-12-29T06:30:00',
      duration_seconds: 2760,
      distance_meters: 8200,
      avg_hr: 142,
      avg_pace_seconds: 337,
      calories: 520,
    },
    {
      id: 2,
      garmin_id: 123456790,
      activity_type: 'running',
      name: 'Tempo Run',
      start_time: '2024-12-27T17:00:00',
      duration_seconds: 2880,
      distance_meters: 10000,
      avg_hr: 165,
      avg_pace_seconds: 288,
      calories: 680,
    },
    {
      id: 3,
      garmin_id: 123456791,
      activity_type: 'running',
      name: 'Long Run Sunday',
      start_time: '2024-12-22T07:00:00',
      duration_seconds: 7020,
      distance_meters: 21100,
      avg_hr: 148,
      avg_pace_seconds: 332,
      calories: 1420,
    },
    {
      id: 4,
      garmin_id: 123456792,
      activity_type: 'running',
      name: 'Recovery Jog',
      start_time: '2024-12-20T18:30:00',
      duration_seconds: 1800,
      distance_meters: 5000,
      avg_hr: 128,
      avg_pace_seconds: 360,
      calories: 310,
    },
    {
      id: 5,
      garmin_id: 123456793,
      activity_type: 'running',
      name: 'Interval Training',
      start_time: '2024-12-18T06:00:00',
      duration_seconds: 2400,
      distance_meters: 8500,
      avg_hr: 172,
      avg_pace_seconds: 282,
      calories: 620,
    },
  ],
  total: 5,
  page: 1,
  per_page: 20,
};

// Mock data for activity detail (백엔드 응답 구조에 맞춤)
const mockActivityDetail: ActivityDetail = {
  id: 1,
  garmin_id: 123456789,
  activity_type: 'running',
  name: 'Morning Easy Run',
  start_time: '2024-12-29T06:30:00',
  duration_seconds: 2760,
  distance_meters: 8200,
  calories: 520,
  avg_hr: 142,
  max_hr: 158,
  avg_pace_seconds: 337,
  elevation_gain: 45,
  elevation_loss: 42,
  avg_cadence: 172,
  metrics: {
    trimp: 78,
    tss: 65,
    training_effect: 3.2,
    vo2max_est: 52.4,
    efficiency_factor: 1.45,
    intensity_factor: 0.82, // IF (NP/FTP)
    // Stryd Power Metrics
    avg_power: 245,
    normalized_power: 252,
    power_to_hr: 1.73, // Pa:Hr (W/bpm)
    leg_spring_stiffness: 9.8, // kN/m
    running_effectiveness: 1.02, // m/kJ
    form_power: 62,
    ground_time: 218, // ms
    vertical_oscillation: 7.2, // cm
  },
  sensors: {
    has_power_meter: true,
    has_hr_monitor: true,
    has_footpod: false,
    power_meter_name: 'Stryd',
    hr_monitor_name: 'HRM-Pro Plus',
  },
  has_fit_file: true,
  has_samples: true,
  created_at: '2024-12-29T07:30:00',
  updated_at: '2024-12-29T07:30:00',
};

// Mock HR Zones (프론트엔드에서 생성 - 백엔드에서 제공하지 않음)
const mockHRZones: HRZone[] = [
  { zone: 1, name: 'Recovery', min_hr: 0, max_hr: 120, time_seconds: 180, percentage: 6.5 },
  { zone: 2, name: 'Aerobic', min_hr: 120, max_hr: 140, time_seconds: 720, percentage: 26.1 },
  { zone: 3, name: 'Tempo', min_hr: 140, max_hr: 160, time_seconds: 1560, percentage: 56.5 },
  { zone: 4, name: 'Threshold', min_hr: 160, max_hr: 175, time_seconds: 300, percentage: 10.9 },
  { zone: 5, name: 'Max', min_hr: 175, max_hr: 200, time_seconds: 0, percentage: 0 },
];

// Mock Laps (프론트엔드에서 생성 - 백엔드에서 제공하지 않음)
const mockLaps: ActivityLap[] = [
  { lap_number: 1, start_time: '2024-12-29T06:30:00', end_time: '2024-12-29T06:35:37', duration_seconds: 337, distance_meters: 1000, avg_hr: 138, max_hr: 145, avg_pace_seconds: 337, elevation_gain: 5, avg_cadence: 170 },
  { lap_number: 2, start_time: '2024-12-29T06:35:37', end_time: '2024-12-29T06:41:09', duration_seconds: 332, distance_meters: 1000, avg_hr: 142, max_hr: 150, avg_pace_seconds: 332, elevation_gain: 8, avg_cadence: 172 },
  { lap_number: 3, start_time: '2024-12-29T06:41:09', end_time: '2024-12-29T06:46:49', duration_seconds: 340, distance_meters: 1000, avg_hr: 144, max_hr: 152, avg_pace_seconds: 340, elevation_gain: 12, avg_cadence: 171 },
  { lap_number: 4, start_time: '2024-12-29T06:46:49', end_time: '2024-12-29T06:52:24', duration_seconds: 335, distance_meters: 1000, avg_hr: 145, max_hr: 155, avg_pace_seconds: 335, elevation_gain: 6, avg_cadence: 173 },
  { lap_number: 5, start_time: '2024-12-29T06:52:24', end_time: '2024-12-29T06:58:02', duration_seconds: 338, distance_meters: 1000, avg_hr: 143, max_hr: 151, avg_pace_seconds: 338, elevation_gain: 4, avg_cadence: 172 },
  { lap_number: 6, start_time: '2024-12-29T06:58:02', end_time: '2024-12-29T07:03:44', duration_seconds: 342, distance_meters: 1000, avg_hr: 141, max_hr: 148, avg_pace_seconds: 342, elevation_gain: 3, avg_cadence: 170 },
  { lap_number: 7, start_time: '2024-12-29T07:03:44', end_time: '2024-12-29T07:09:20', duration_seconds: 336, distance_meters: 1000, avg_hr: 142, max_hr: 150, avg_pace_seconds: 336, elevation_gain: 5, avg_cadence: 172 },
  { lap_number: 8, start_time: '2024-12-29T07:09:20', end_time: '2024-12-29T07:10:28', duration_seconds: 68, distance_meters: 200, avg_hr: 140, max_hr: 145, avg_pace_seconds: 340, elevation_gain: 2, avg_cadence: 171 },
];

// 서울 한강공원 러닝 코스 GPS 좌표 (잠실 ~ 뚝섬)
const generateGPSRoute = (numPoints: number): { lat: number; lng: number }[] => {
  // 잠실한강공원 시작점
  const startLat = 37.5180;
  const startLng = 127.0780;

  // 뚝섬한강공원 끝점
  const endLat = 37.5295;
  const endLng = 127.0450;

  const route: { lat: number; lng: number }[] = [];

  for (let i = 0; i <= numPoints; i++) {
    const progress = i / numPoints;
    // 약간의 곡선 경로 (한강 따라)
    const curveFactor = Math.sin(progress * Math.PI) * 0.003;

    route.push({
      lat: startLat + (endLat - startLat) * progress + curveFactor,
      lng: startLng + (endLng - startLng) * progress,
    });
  }

  return route;
};

// Generate mock samples (백엔드 응답 구조에 맞춤)
const generateMockSamples = (durationSeconds: number): ActivitySamplesResponse => {
  const samples: ActivitySample[] = [];
  const numPoints = Math.floor(durationSeconds / 10); // One point every 10 seconds
  const startTime = new Date('2024-12-29T06:30:00');
  const gpsRoute = generateGPSRoute(numPoints);

  for (let i = 0; i <= numPoints; i++) {
    const time = i * 10;
    const progress = time / durationSeconds;
    const timestamp = new Date(startTime.getTime() + time * 1000);

    samples.push({
      timestamp: timestamp.toISOString(),
      hr: 95 + Math.floor(Math.random() * 20) + Math.min(Math.floor(progress * 50), 50),
      pace_seconds: 320 + Math.floor(Math.random() * 40),
      cadence: 168 + Math.floor(Math.random() * 10),
      power: null,
      latitude: gpsRoute[i]?.lat ?? null,
      longitude: gpsRoute[i]?.lng ?? null,
      altitude: 50 + Math.sin(progress * Math.PI * 4) * 20,
    });
  }

  return {
    activity_id: 1,
    samples,
    total: samples.length,
    is_downsampled: false,
    original_count: null,
  };
};

export function useActivitiesList(params?: ActivitiesParams) {
  return useQuery({
    queryKey: ['activities', 'list', params],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 300));

        // Apply sorting to mock data
        let items = [...mockActivitiesList.items];
        const sortBy = params?.sort_by || 'start_time';
        const sortOrder = params?.sort_order || 'desc';

        items.sort((a, b) => {
          let comparison = 0;
          switch (sortBy) {
            case 'start_time':
              comparison = new Date(a.start_time).getTime() - new Date(b.start_time).getTime();
              break;
            case 'distance':
              comparison = (a.distance_meters || 0) - (b.distance_meters || 0);
              break;
            case 'duration':
              comparison = (a.duration_seconds || 0) - (b.duration_seconds || 0);
              break;
          }
          return sortOrder === 'asc' ? comparison : -comparison;
        });

        // Apply activity type filter
        if (params?.activity_type) {
          items = items.filter(item => item.activity_type === params.activity_type);
        }

        // Apply pagination
        const page = params?.page || 1;
        const perPage = params?.per_page || 20;
        const startIdx = (page - 1) * perPage;
        const paginatedItems = items.slice(startIdx, startIdx + perPage);

        return {
          items: paginatedItems,
          total: items.length,
          page,
          per_page: perPage,
        };
      }
      return activitiesApi.getList(params);
    },
    staleTime: 1000 * 60 * 5,
  });
}

export function useActivityDetail(id: number) {
  return useQuery({
    queryKey: ['activities', 'detail', id],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 300));
        return mockActivityDetail;
      }
      return activitiesApi.getDetail(id);
    },
    staleTime: 1000 * 60 * 10,
    enabled: !!id,
  });
}

export function useActivitySamples(id: number, downsample?: number) {
  return useQuery({
    queryKey: ['activities', 'samples', id, downsample],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 200));
        return generateMockSamples(2760);
      }
      return activitiesApi.getSamples(id, { downsample });
    },
    staleTime: 1000 * 60 * 30,
    enabled: !!id,
  });
}

// Mock 데이터를 위한 보조 훅들 (백엔드에서 제공하지 않는 데이터)
export function useActivityHRZones(_id: number) {
  return useQuery({
    queryKey: ['activities', 'hr-zones', _id],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 100));
        return mockHRZones;
      }
      // 실제 백엔드에서는 샘플 데이터를 분석해서 HR 존을 계산해야 함
      return [];
    },
    staleTime: 1000 * 60 * 30,
    enabled: !!_id,
  });
}

export function useActivityLaps(_id: number) {
  return useQuery({
    queryKey: ['activities', 'laps', _id],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await new Promise((resolve) => setTimeout(resolve, 100));
        return mockLaps;
      }
      // 실제 백엔드에서는 FIT 파일을 파싱해서 랩 데이터를 추출해야 함
      return [];
    },
    staleTime: 1000 * 60 * 30,
    enabled: !!_id,
  });
}

// Utility functions for formatting
export function formatPace(seconds: number | null): string {
  if (seconds == null) return '--:--';
  const min = Math.floor(seconds / 60);
  const sec = Math.round(seconds % 60);
  return `${min}:${String(sec).padStart(2, '0')}`;
}

export function formatDuration(seconds: number | null): string {
  if (seconds == null) return '--:--';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }
  return `${minutes}:${String(secs).padStart(2, '0')}`;
}

export function formatDistance(meters: number | null): string {
  if (meters == null) return '--';
  const km = meters / 1000;
  return km.toFixed(2);
}
