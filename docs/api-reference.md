# RunningCoach API Reference (v1)

## 개요

RunningCoach API는 RESTful 설계 원칙을 따르며, JSON 형식으로 데이터를 주고받습니다.

- **Base URL**: `/api/v1`
- **인증**: HTTP-only 쿠키 기반 세션
- **Content-Type**: `application/json`

### 예외 경로 (Non-versioned)

다음 엔드포인트는 `/api/v1` 프리픽스 없이 루트에서 직접 접근합니다:

| Endpoint | 설명 |
|----------|------|
| `GET /health` | 헬스체크 (인증 불필요) |
| `GET /metrics` | Prometheus 메트릭 (인증 불필요) |

이들은 인프라/모니터링 목적으로 API 버전과 무관하게 유지됩니다.

---

## 인증 (Authentication)

세션은 HTTP-only 쿠키로 전달됩니다.

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/auth/login` | 로컬 로그인 |
| POST | `/auth/logout` | 로그아웃 |
| GET | `/auth/me` | 현재 사용자 정보 |

### POST `/auth/login` Request Body

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

### POST `/auth/login` Response

```json
{
  "success": true,
  "message": "Login successful",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "display_name": "Runner",
    "timezone": "Asia/Seoul"
  }
}
```

### Garmin 연동

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/auth/garmin/connect` | Garmin 계정 연결 (이메일/비밀번호) |
| POST | `/auth/garmin/refresh` | 세션 유효성 검증 |
| DELETE | `/auth/garmin/disconnect` | 연결 해제 |
| GET | `/auth/garmin/status` | 연결 상태 확인 |

#### POST `/auth/garmin/connect` Request Body

```json
{
  "email": "user@example.com",
  "password": "garmin_password"
}
```

#### POST `/auth/garmin/connect` Response

```json
{
  "connected": true,
  "message": "Garmin account connected successfully",
  "last_login": "2024-12-30T10:00:00Z"
}
```

**Error Responses**:
- `401 Unauthorized`: 인증 실패 (잘못된 이메일/비밀번호)
- `502 Bad Gateway`: Garmin API 오류

#### POST `/auth/garmin/refresh` Response

세션 유효성을 검증합니다. garminconnect 라이브러리는 명시적 토큰 갱신을 지원하지 않으므로,
저장된 세션 데이터로 재로그인을 시도합니다. 세션이 만료된 경우 `/auth/garmin/connect`로 재연결이 필요합니다.

```json
{
  "success": true,
  "message": "Session validated successfully"
}
```

**Error Responses**:
- `400 Bad Request`: Garmin 계정이 연결되지 않음
- `401 Unauthorized`: 세션 만료 (재연결 필요)

#### GET `/auth/garmin/status` Response

```json
{
  "connected": true,
  "session_valid": true,
  "last_login": "2024-12-30T10:00:00Z",
  "last_sync": "2024-12-30T09:00:00Z"
}
```

**Note**: `session_valid`는 세션 데이터 존재 여부만 확인합니다.
실제 유효성은 `/auth/garmin/refresh`로 검증해야 합니다.

### Strava 연동

Strava 연동은 `/strava/*` 경로에서 처리됩니다 (OAuth + 동기화 통합).

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/strava/connect` | OAuth 시작 (auth_url 반환, CSRF state 토큰 포함) |
| POST | `/strava/callback` | OAuth 콜백 처리 (state 검증 필수) |
| POST | `/strava/refresh` | 토큰 갱신 |
| GET | `/strava/status` | 연결 상태 확인 |
| DELETE | `/strava/disconnect` | 연결 해제 |
| POST | `/strava/sync/run` | 수동 동기화 |
| GET | `/strava/sync/status` | 동기화 상태 |
| GET | `/strava/activities` | 업로드 상태 목록 (페이지네이션) |
| POST | `/strava/activities/{id}/upload` | 단일 활동 업로드 |

#### POST `/strava/refresh` Response

Strava 액세스 토큰을 갱신합니다.

```json
{
  "success": true,
  "message": "Strava tokens refreshed successfully",
  "expires_at": "2024-12-31T10:00:00Z"
}
```

**Error Responses**:
- `400 Bad Request`: Strava 계정이 연결되지 않음
- `401 Unauthorized`: 토큰 갱신 실패 (재연결 필요)
- `501 Not Implemented`: Strava OAuth 미설정

### GET `/strava/activities` Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| page | int | 1 | 페이지 번호 |
| per_page | int | 20 | 페이지당 항목 수 (max: 100) |
| status_filter | string | null | 상태 필터 (pending, uploaded, failed) |

### GET `/strava/activities` Response

```json
{
  "items": [
    {
      "activity_id": 123,
      "garmin_id": 456,
      "strava_activity_id": 789,
      "uploaded_at": "2024-01-15T10:30:00Z",
      "status": "uploaded"
    }
  ],
  "total": 50,
  "page": 1,
  "per_page": 20
}
```

---

## 데이터 수집 (Ingestion)

Garmin에서 데이터를 동기화합니다.

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/ingest/run` | 수동 동기화 실행 (백그라운드) |
| POST | `/ingest/run/sync` | 동기식 동기화 실행 (즉시 결과 반환) |
| GET | `/ingest/status` | 동기화 상태 조회 |
| GET | `/ingest/history` | 동기화 이력 (v1.0) |

### POST `/ingest/run` Request Body

```json
{
  "endpoints": ["activities", "sleep", "heart_rate"],
  "full_backfill": true,
  "start_date": "2020-01-01",
  "end_date": "2024-12-31"
}
```

### POST `/ingest/run` Response

```json
{
  "started": true,
  "message": "Sync started",
  "endpoints": ["activities", "sleep", "heart_rate"],
  "sync_id": "sync_1_1735632000"
}
```

### POST `/ingest/run/sync`

동기식으로 동기화를 실행하고 즉시 결과를 반환합니다. 테스트나 즉각적인 결과가 필요한 경우에 사용합니다.
프로덕션 환경에서는 `/ingest/run`을 사용하세요.

#### Request Body

`/ingest/run`과 동일한 형식입니다.

#### Response

```json
[
  {
    "endpoint": "activities",
    "success": true,
    "items_fetched": 5,
    "items_created": 3,
    "items_updated": 2,
    "error": null
  },
  {
    "endpoint": "sleep",
    "success": true,
    "items_fetched": 7,
    "items_created": 7,
    "items_updated": 0,
    "error": null
  }
]
```

**Error Responses**:
- `400 Bad Request`: Garmin 계정이 연결되지 않음
- `401 Unauthorized`: Garmin 세션 만료 (재연결 필요)

---

## 활동 (Activities)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/activities` | 활동 목록 (페이지네이션) |
| GET | `/activities/{id}` | 활동 상세 |
| GET | `/activities/{id}/samples` | 활동 샘플 (시계열 데이터) |
| GET | `/activities/{id}/hr-zones` | HR존별 시간 분포 |
| GET | `/activities/{id}/laps` | 랩/구간 데이터 |
| GET | `/activities/{id}/fit` | FIT 파일 다운로드 |
| GET | `/activities/types/list` | 활동 유형 목록 |

### Query Parameters (`/activities`)

| Parameter | Type | Default | 설명 |
|-----------|------|---------|------|
| page | int | 1 | 페이지 번호 |
| per_page | int | 20 | 페이지당 항목 수 (max: 100) |
| activity_type | string | - | 활동 유형 필터 |
| start_date | date | - | 시작 날짜 필터 |
| end_date | date | - | 종료 날짜 필터 |
| sort_by | string | start_time | 정렬 기준: start_time, distance, duration |
| sort_order | string | desc | 정렬 순서: asc, desc |

### GET `/activities/{id}/samples`

FIT 파일에서 파싱한 시계열 데이터를 반환합니다.

#### Query Parameters

| Parameter | Type | Default | 설명 |
|-----------|------|---------|------|
| limit | int | 1000 | 페이지당 샘플 수 (max: 10000) - 다운샘플 미사용 시 적용 |
| offset | int | 0 | 페이지네이션 오프셋 - 다운샘플 미사용 시 적용 |
| downsample | int | - | 다운샘플 목표 개수 (50-2000, 차트용) - 사용 시 limit/offset 무시 |
| fields | string | - | 필터 필드 (hr,pace,cadence,power,gps,altitude)

**Note:**
- `total`은 항상 **전체 샘플 수**를 반환합니다 (반환된 개수가 아님)
- `downsample` 사용 시: `limit`/`offset`은 무시되고, 전체 데이터에서 균등 간격으로 샘플링
- `downsample` 미사용 시: 일반 페이지네이션 (`limit`/`offset` 적용)

#### Example

Query
```
/activities/123/samples?downsample=200&fields=hr,pace
```

Response
```json
{
  "activity_id": 123,
  "samples": [
    { "timestamp": "2024-12-01T00:00:05Z", "hr": 120, "pace_seconds": 330, "cadence": null, "power": null, "latitude": null, "longitude": null, "altitude": null },
    { "timestamp": "2024-12-01T00:00:10Z", "hr": 124, "pace_seconds": 328, "cadence": null, "power": null, "latitude": null, "longitude": null, "altitude": null }
  ],
  "total": 982,
  "is_downsampled": true,
  "original_count": 982
}
```

### GET `/activities/{id}/hr-zones`

HR존별 시간 분포를 계산합니다.

#### Query Parameters

| Parameter | Type | Default | 설명 |
|-----------|------|---------|------|
| max_hr | int | - | 사용자 최대 심박수 (100-250). 미지정 시 user.max_hr 또는 샘플 최대값 사용 |

#### Response
```json
{
  "activity_id": 123,
  "max_hr": 190,
  "zones": [
    { "zone": 1, "name": "Recovery", "min_hr": 95, "max_hr": 114, "time_seconds": 300, "percentage": 10.0 },
    { "zone": 2, "name": "Aerobic", "min_hr": 114, "max_hr": 133, "time_seconds": 900, "percentage": 30.0 },
    { "zone": 3, "name": "Tempo", "min_hr": 133, "max_hr": 152, "time_seconds": 1200, "percentage": 40.0 },
    { "zone": 4, "name": "Threshold", "min_hr": 152, "max_hr": 171, "time_seconds": 450, "percentage": 15.0 },
    { "zone": 5, "name": "VO2max", "min_hr": 171, "max_hr": 190, "time_seconds": 150, "percentage": 5.0 }
  ],
  "total_time_in_zones": 3000
}
```

### GET `/activities/{id}/laps`

랩/구간 데이터를 반환합니다. FIT 파일에 저장된 랩이 있으면 그것을 사용하고, 없으면 거리/시간 기반으로 계산합니다.

#### Query Parameters

| Parameter | Type | Default | 설명 |
|-----------|------|---------|------|
| split_distance | int | 1000 | 계산된 랩의 거리 (미터, 100-10000). FIT 랩이 있으면 무시됨 |

#### Response
```json
{
  "activity_id": 123,
  "laps": [
    {
      "lap_number": 1,
      "start_time": "2024-12-01T00:00:00Z",
      "end_time": "2024-12-01T00:05:30Z",
      "duration_seconds": 330,
      "distance_meters": 1000,
      "avg_hr": 145,
      "max_hr": 160,
      "avg_pace_seconds": 330,
      "elevation_gain": 15.5,
      "avg_cadence": 170
    }
  ],
  "total_laps": 5
}
```

---

## 건강 데이터 (Health Data)

### 수면 (Sleep)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/sleep` | 수면 기록 목록 |
| GET | `/sleep/{date}` | 특정 날짜 수면 데이터 |

### 심박수 (Heart Rate)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/hr` | 일별 심박수 기록 목록 (안정심박, 평균심박, 최대심박) |
| GET | `/hr/summary` | 심박수 요약 통계 |

#### GET `/hr` Response

```json
{
  "items": [
    {
      "id": 1,
      "date": "2024-12-30",
      "resting_hr": 52,
      "avg_hr": 65,
      "max_hr": 145
    }
  ],
  "total": 30,
  "page": 1,
  "per_page": 20
}
```

#### GET `/hr/summary` Response

```json
{
  "avg_resting_hr": 54.2,
  "min_resting_hr": 48,
  "max_resting_hr": 62,
  "avg_max_hr": 148.5,
  "record_count": 30
}
```

### 건강/피트니스 지표 (Metrics)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/metrics` | 지표 요약 (최신 체중, 체지방, CTL/ATL/TSB, VO2max) |
| GET | `/metrics/body` | 체성분 기록 (체중, 체지방률, 근육량, BMI) |
| GET | `/metrics/fitness` | 피트니스 지표 (CTL/ATL/TSB 일별 기록) |

#### GET `/metrics` Response

```json
{
  "has_body_composition": true,
  "has_fitness_metrics": true,
  "latest_weight_kg": 72.5,
  "latest_body_fat_pct": 15.2,
  "latest_ctl": 58.2,
  "latest_atl": 72.5,
  "latest_tsb": -14.3,
  "latest_vo2max": 52.4
}
```

#### GET `/metrics/fitness` Response

```json
{
  "items": [
    {
      "id": 1,
      "date": "2024-12-30",
      "ctl": 58.2,
      "atl": 72.5,
      "tsb": -14.3
    }
  ],
  "total": 90,
  "page": 1,
  "per_page": 20
}
```

**Note:** `weekly_trimp`/`weekly_tss`는 `/dashboard/summary`의 `fitness_status`에서 조회 가능합니다.

---

## 대시보드 (Dashboard)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/dashboard/summary` | 주간/월간 요약 |
| GET | `/dashboard/trends` | 트렌드 데이터 (차트용) |
| GET | `/dashboard/calendar` | 캘린더 뷰 데이터 |

### GET `/dashboard/summary` Query Parameters

| Parameter | Type | Default | 설명 |
|-----------|------|---------|------|
| target_date | date | today | 조회 기준 날짜 |
| period | string | "week" | 기간 유형: "week" \| "month" |

**기간 계산 방식 (달력 기준):**
- **week**: target_date가 속한 주의 월요일~일요일
- **month**: target_date가 속한 월의 1일~말일

### GET `/dashboard/summary` Response

```json
{
  "period_type": "week",
  "period_start": "2024-12-30",
  "period_end": "2025-01-05",
  "summary": {
    "total_distance_km": 42.5,
    "total_duration_hours": 4.2,
    "total_activities": 5,
    "avg_pace_per_km": "5:55/km",
    "avg_pace_seconds": 355,
    "avg_hr": 152,
    "total_elevation_m": 320.5,
    "total_calories": 2100
  },
  "recent_activities": [
    {
      "id": 123,
      "name": "Morning Run",
      "activity_type": "running",
      "start_time": "2024-12-30T07:00:00Z",
      "distance_km": 10.2,
      "duration_seconds": 3480,
      "avg_pace_seconds": 341,
      "avg_hr_percent": 82,
      "elevation_gain": 45.5,
      "calories": 520,
      "trimp": 85.2,
      "vo2max_est": 48.5,
      "avg_cadence": 175,
      "avg_ground_time": 245,
      "avg_vertical_oscillation": 8.2
    }
  ],
  "health_status": {
    "latest_sleep_score": 85,
    "latest_sleep_hours": 7.5,
    "resting_hr": 52,
    "body_battery": 78,
    "vo2max": 48.5
  },
  "fitness_status": {
    "ctl": 45.2,
    "atl": 52.8,
    "tsb": -7.6,
    "weekly_trimp": 320.5,
    "weekly_tss": 280.0,
    "effective_vo2max": 48.5,
    "marathon_shape": 85.0,
    "workload_ratio": 1.2,
    "rest_days": 2.0,
    "monotony": 25.0,
    "training_strain": 450.0
  },
  "training_paces": {
    "vdot": 48.5,
    "easy_min": 343,
    "easy_max": 430,
    "marathon_min": 302,
    "marathon_max": 338,
    "threshold_min": 276,
    "threshold_max": 288,
    "interval_min": 254,
    "interval_max": 267,
    "repetition_min": 231,
    "repetition_max": 242
  },
  "upcoming_workouts": [
    {
      "id": 456,
      "workout_name": "Tempo Run",
      "workout_type": "tempo",
      "scheduled_date": "2025-01-06"
    }
  ]
}
```

### GET `/dashboard/trends` Query Parameters

| Parameter | Type | Default | 설명 |
|-----------|------|---------|------|
| weeks | int | 12 | 조회 주 수 (4-52) |

### GET `/dashboard/trends` Response

```json
{
  "weekly_distance": [
    { "date": "2024-12-16", "value": 35.2 },
    { "date": "2024-12-23", "value": 42.5 }
  ],
  "weekly_duration": [
    { "date": "2024-12-16", "value": 3.5 },
    { "date": "2024-12-23", "value": 4.2 }
  ],
  "avg_pace": [
    { "date": "2024-12-16", "value": 355 },
    { "date": "2024-12-23", "value": 350 }
  ],
  "resting_hr": [
    { "date": "2024-12-16", "value": 54 },
    { "date": "2024-12-23", "value": 52 }
  ],
  "ctl_atl": [
    { "date": "2024-12-30", "ctl": 45.2, "atl": 52.8, "tsb": -7.6 }
  ]
}
```

### GET `/dashboard/calendar` Query Parameters

| Parameter | Type | Required | 설명 |
|-----------|------|----------|------|
| start_date | date | ✅ | 캘린더 시작 날짜 |
| end_date | date | ✅ | 캘린더 종료 날짜 |

### GET `/dashboard/calendar` Response

```json
{
  "start_date": "2024-12-01",
  "end_date": "2024-12-31",
  "days": [
    {
      "date": "2024-12-15",
      "activities": [
        {
          "id": 123,
          "name": "Morning Run",
          "activity_type": "running",
          "start_time": "2024-12-15T07:00:00Z",
          "distance_km": 10.2,
          "duration_seconds": 3480,
          "avg_pace_seconds": 341,
          "avg_hr_percent": 82,
          "elevation_gain": 45.5,
          "calories": 520,
          "trimp": 85.2,
          "vo2max_est": 48.5,
          "avg_cadence": 175,
          "avg_ground_time": 245,
          "avg_vertical_oscillation": 8.2
        }
      ],
      "scheduled_workouts": [
        {
          "id": 456,
          "workout_name": "Long Run",
          "workout_type": "long_run",
          "scheduled_date": "2024-12-15"
        }
      ]
    }
  ]
}
```

---

## 분석 (Analytics)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/analytics/compare` | 기간 비교 분석 |
| GET | `/analytics/personal-records` | 개인 최고 기록 (PR) |

### GET `/analytics/compare` Query Parameters

| Parameter | Type | Default | 설명 |
|-----------|------|---------|------|
| period | string | "week" | 기간 유형: "week" (월~일) \| "month" (달력 기준 월) |
| current_end | date | today | **기준일**: 이 날짜가 속한 주/월을 현재 기간으로 사용 |

**Note:**
- `period=week`: ISO 주(월요일~일요일) 기준. `current_end`가 속한 주 vs 직전 주 비교
- `period=month`: 달력 기준 월(1일~말일). `current_end`가 속한 월 vs 직전 월 비교
- `current_end`는 "종료일"이 아닌 "기준일"입니다. 해당 날짜가 속한 전체 주/월이 현재 기간이 됩니다.

### GET `/analytics/compare` Response

```json
{
  "current_period": {
    "period_start": "2024-12-01",
    "period_end": "2024-12-31",
    "total_distance_km": 120.5,
    "total_duration_hours": 12.5,
    "total_activities": 15,
    "avg_pace_per_km": "5:30/km",
    "avg_hr": 145,
    "total_elevation_m": 850.5,
    "total_calories": 8500,
    "total_trimp": 1200.5,
    "total_tss": 450.2
  },
  "previous_period": { /* same structure */ },
  "change": {
    "distance_change_pct": 15.2,
    "duration_change_pct": 10.5,
    "activities_change": 3,
    "pace_change_seconds": -5.2,
    "elevation_change_pct": 8.0
  },
  "improvement_summary": "거리 15.2% 증가, 페이스 5초/km 향상"
}
```

### GET `/analytics/personal-records` Query Parameters

| Parameter | Type | Default | 설명 |
|-----------|------|---------|------|
| activity_type | string | "running" | 활동 유형 필터 |

### GET `/analytics/personal-records` Response

```json
{
  "distance_records": [
    {
      "category": "5K",
      "value": 1320,
      "unit": "seconds",
      "activity_id": 123,
      "activity_name": "Morning 5K Race",
      "achieved_date": "2024-11-15",
      "previous_best": 1380,
      "improvement_pct": -4.3
    }
  ],
  "pace_records": [
    {
      "category": "5K Pace",
      "value": 264.0,
      "unit": "sec/km",
      "activity_id": 123,
      "activity_name": "Morning 5K Race",
      "achieved_date": "2024-11-15",
      "previous_best": 276.0,
      "improvement_pct": -4.3
    }
  ],
  "endurance_records": [
    {
      "category": "Longest Run",
      "value": 42195,
      "unit": "meters",
      "activity_id": 456,
      "activity_name": "Marathon",
      "achieved_date": "2024-10-20",
      "previous_best": 32000,
      "improvement_pct": 31.9
    }
  ],
  "recent_prs": [
    { /* PRs achieved in last 30 days */ }
  ]
}
```

**Note:**
- `improvement_pct`가 음수면 개선(시간/페이스가 줄어듦), 양수면 증가(거리가 늘어남)
- `recent_prs`는 최근 30일 내 달성한 PR 목록

---

## AI 훈련 계획 (AI Planning)

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/ai/chat` | 빠른 채팅 (대화 자동 생성) |
| GET | `/ai/conversations` | 대화 목록 |
| POST | `/ai/conversations` | 새 대화 생성 |
| GET | `/ai/conversations/{id}` | 대화 상세 (메시지 포함) |
| DELETE | `/ai/conversations/{id}` | 대화 삭제 |
| POST | `/ai/conversations/{id}/chat` | 대화에 메시지 전송 |
| POST | `/ai/import` | 수동 플랜 JSON import |
| GET | `/ai/export` | ChatGPT 분석용 요약 생성 |

### POST `/ai/conversations` Request Body

```json
{
  "title": "마라톤 훈련 계획",
  "language": "ko"
}
```

### POST `/ai/conversations/{id}/chat` Request Body

```json
{
  "message": "이번 주 템포런 계획을 조정해줘",
  "context": { "goal": "10k PR" }
}
```

### POST `/ai/chat` (Quick Chat)

대화를 자동 생성하고 메시지를 전송합니다.

Request Body:
```json
{
  "message": "이번 주 템포런 계획을 조정해줘",
  "context": { "language": "ko", "goal": "10k PR" }
}
```

Response:
```json
{
  "conversation_id": 10,
  "message": {
    "id": 101,
    "role": "user",
    "content": "이번 주 템포런 계획을 조정해줘",
    "tokens": 12,
    "created_at": "2024-12-01T09:10:00Z"
  },
  "reply": {
    "id": 102,
    "role": "assistant",
    "content": "이번 주는 템포런을 1회로 줄이고 회복주로 조정할게요.",
    "tokens": 38,
    "created_at": "2024-12-01T09:10:02Z"
  }
}
```

### POST `/ai/import` Request Body

훈련 계획을 외부 소스(ChatGPT 등)에서 import합니다.

```json
{
  "source": "chatgpt",
  "plan_name": "10K Base 4w",
  "goal_type": "10k",
  "goal_date": "2025-03-15",
  "goal_time": "00:45:00",
  "weeks": [
    {
      "week_number": 1,
      "focus": "build",
      "weekly_distance_km": 35,
      "notes": "기초 체력 구축",
      "workouts": [
        {
          "name": "Tempo Run",
          "type": "tempo",
          "steps": [
            { "type": "warmup", "duration_minutes": 10 },
            { "type": "main", "duration_minutes": 30, "target_pace": "5:10-5:20" },
            { "type": "cooldown", "duration_minutes": 10 }
          ],
          "notes": "목표 페이스 유지"
        }
      ]
    }
  ],
  "notes": "점진적 거리 증가"
}
```

**Note:**
- `start_date`는 import 시점(오늘) 기준으로 자동 설정
- `end_date`는 `goal_date` 또는 `weeks * 7일`로 계산

---

## 워크아웃 (Workouts)

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/workouts` | 워크아웃 생성 |
| GET | `/workouts` | 워크아웃 목록 (페이지네이션) |
| GET | `/workouts/{id}` | 워크아웃 상세 |
| PATCH | `/workouts/{id}` | 워크아웃 수정 |
| DELETE | `/workouts/{id}` | 워크아웃 삭제 |
| POST | `/workouts/{id}/push` | Garmin에 전송 (미구현) |
| GET | `/workouts/schedules/list` | 스케줄 목록 (페이지네이션) |
| POST | `/workouts/schedules` | 날짜 스케줄링 |
| PATCH | `/workouts/schedules/{schedule_id}/status` | 스케줄 상태 변경 |
| DELETE | `/workouts/schedules/{schedule_id}` | 스케줄 삭제 |

### POST `/workouts` Request Body

```json
{
  "name": "Tempo Run",
  "workout_type": "tempo",
  "structure": [
    { "type": "warmup", "duration_minutes": 10, "description": "Easy jog" },
    { "type": "main", "duration_minutes": 30, "target_pace": "5:10/km" },
    { "type": "cooldown", "duration_minutes": 10 }
  ],
  "target": { "hr_zone": 3, "pace_range": "5:00-5:20/km" },
  "notes": "목표 페이스 유지, 호흡 체크"
}
```

### Workout Response

```json
{
  "id": 55,
  "name": "Tempo Run",
  "workout_type": "tempo",
  "structure": [
    { "type": "warmup", "duration_minutes": 10 },
    { "type": "main", "duration_minutes": 30, "target_pace": "5:10/km" },
    { "type": "cooldown", "duration_minutes": 10 }
  ],
  "target": { "hr_zone": 3 },
  "notes": "목표 페이스 유지",
  "garmin_workout_id": null,
  "plan_week_id": null,
  "created_at": "2024-12-30T10:00:00Z",
  "updated_at": "2024-12-30T10:00:00Z"
}
```

### GET `/workouts/schedules/list` Query Parameters

| Parameter | Type | Default | 설명 |
|-----------|------|---------|------|
| page | int | 1 | 페이지 번호 |
| per_page | int | 20 | 페이지당 항목 수 (max: 100) |
| start_date | date | - | 시작 날짜 필터 |
| end_date | date | - | 종료 날짜 필터 |
| status_filter | string | - | 상태 필터: scheduled, completed, skipped, cancelled |

### POST `/workouts/schedules` Request Body

```json
{
  "workout_id": 55,
  "scheduled_date": "2024-12-07"
}
```

### POST `/workouts/schedules` Response

```json
{
  "id": 9001,
  "workout_id": 55,
  "scheduled_date": "2024-12-07",
  "status": "scheduled",
  "garmin_schedule_id": null,
  "workout": null
}
```

**Note:** 동일 워크아웃을 같은 날짜에 중복 스케줄링하면 `409 Conflict` 에러가 반환됩니다.

---

## 훈련 계획 (Training Plans) - v1.0

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/plans` | 훈련 계획 생성 |
| GET | `/plans` | 계획 목록 |
| GET | `/plans/{id}` | 계획 상세 |
| PUT | `/plans/{id}` | 계획 수정 |
| POST | `/plans/{id}/approve` | 계획 승인 |
| POST | `/plans/{id}/sync` | Garmin 동기화 |

---

## 장비 관리 (Gear)

러닝화 및 장비를 관리합니다.

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/gear` | 장비 목록 |
| GET | `/gear/stats` | 장비 통계 (대시보드용) |
| GET | `/gear/{id}` | 장비 상세 |
| POST | `/gear` | 장비 생성 |
| PATCH | `/gear/{id}` | 장비 수정 |
| POST | `/gear/{id}/retire` | 장비 은퇴 |
| DELETE | `/gear/{id}` | 장비 삭제 |
| POST | `/gear/{id}/activities/{activity_id}` | 활동에 장비 연결 |
| DELETE | `/gear/{id}/activities/{activity_id}` | 활동-장비 연결 해제 |
| GET | `/gear/{id}/activities` | 장비에 연결된 활동 ID 목록 |

### Configuration Constants

| Constant | Value | Description |
|----------|-------|-------------|
| DEFAULT_MAX_DISTANCE_METERS | 800,000 (800km) | 기본 최대 거리 (신발 기준) |
| RETIREMENT_WARNING_THRESHOLD | 80% | "은퇴 임박" 경고 기준 사용률 |

### GET `/gear` Query Parameters

| Parameter | Type | Default | 설명 |
|-----------|------|---------|------|
| status | string | - | 상태 필터: "active" \| "retired" \| "all" |
| gear_type | string | - | 장비 유형 필터: "running_shoes" \| "cycling_shoes" \| "bike" \| "other" |

**Valid gear_type values:** `running_shoes`, `cycling_shoes`, `bike`, `other`
**Valid status values:** `active`, `retired`

### GET `/gear` Response

```json
{
  "items": [
    {
      "id": 1,
      "name": "Nike Vaporfly 3",
      "brand": "Nike",
      "gear_type": "running_shoes",
      "status": "active",
      "total_distance_meters": 245000,
      "max_distance_meters": 500000,
      "activity_count": 32,
      "usage_percentage": 49.0
    }
  ],
  "total": 1
}
```

### GET `/gear/stats` Response

```json
{
  "total_gears": 4,
  "active_gears": 3,
  "retired_gears": 1,
  "gears_near_retirement": [
    {
      "id": 2,
      "name": "ASICS Gel-Kayano 30",
      "brand": "ASICS",
      "gear_type": "running_shoes",
      "status": "active",
      "total_distance_meters": 680000,
      "max_distance_meters": 800000,
      "activity_count": 85,
      "usage_percentage": 85.0
    }
  ]
}
```

### POST `/gear` Request Body

```json
{
  "name": "Nike Vaporfly 3",
  "brand": "Nike",
  "model": "Vaporfly 3",
  "gear_type": "running_shoes",
  "purchase_date": "2024-06-15",
  "initial_distance_meters": 0,
  "max_distance_meters": 500000,
  "notes": "레이스용 신발"
}
```

### GET `/gear/{id}` Response

```json
{
  "id": 1,
  "garmin_uuid": "abc-123-def",
  "name": "Nike Vaporfly 3",
  "brand": "Nike",
  "model": "Vaporfly 3",
  "gear_type": "running_shoes",
  "status": "active",
  "purchase_date": "2024-06-15",
  "retired_date": null,
  "initial_distance_meters": 0,
  "total_distance_meters": 245000,
  "max_distance_meters": 500000,
  "activity_count": 32,
  "usage_percentage": 49.0,
  "notes": "레이스용 신발",
  "image_url": null,
  "created_at": "2024-06-15T10:00:00Z",
  "updated_at": "2024-12-29T08:00:00Z"
}
```

### PATCH `/gear/{id}` Request Body

모든 필드는 선택사항입니다. `gear_type`과 `status`는 유효한 enum 값만 허용됩니다.

```json
{
  "name": "Nike Vaporfly 3 (Updated)",
  "gear_type": "running_shoes",
  "status": "retired",
  "max_distance_meters": 600000,
  "notes": "마모로 인해 은퇴"
}
```

**Note:**
- `status`를 `retired`로 변경하면 `retired_date`가 자동으로 오늘 날짜로 설정됩니다.
- `status`를 `active`로 변경하면 `retired_date`가 자동으로 `null`로 초기화됩니다.
- 유효하지 않은 `gear_type` 또는 `status` 값을 전달하면 `422 Unprocessable Entity` 에러가 반환됩니다.

### GET `/gear/{id}/activities` Query Parameters

| Parameter | Type | Default | 설명 |
|-----------|------|---------|------|
| limit | int | 50 | 최대 결과 수 (max: 100) |
| offset | int | 0 | 페이지네이션 오프셋 |

**Note:** 결과는 활동 시작 시간 기준 내림차순(최신 순)으로 정렬됩니다.

---

## Strava 동기화

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/strava/connect` | Strava OAuth 시작 |
| POST | `/strava/callback` | OAuth 콜백 처리 |
| GET | `/strava/status` | 연결 상태 확인 |
| DELETE | `/strava/disconnect` | 연결 해제 |
| POST | `/strava/sync/run` | 수동 동기화 실행 |
| GET | `/strava/sync/status` | 동기화 상태 |
| GET | `/strava/activities` | 업로드 상태 목록 |
| POST | `/strava/activities/{id}/upload` | 단일 활동 업로드 |

---

## 레거시 경로 (Legacy Routes)

하위 호환성을 위해 일부 레거시 경로를 지원합니다.
레거시 경로는 308 Permanent Redirect로 정식 경로로 리다이렉트됩니다.

| Deprecated Path | Canonical Path | 제거 예정 버전 |
|-----------------|----------------|----------------|
| `/sync/garmin/run` | `/ingest/run` | v2.0 |
| `/sync/garmin/status` | `/ingest/status` | v2.0 |
| `/data/activities` | `/activities` | v2.0 |
| `/data/sleep` | `/sleep` | v2.0 |
| `/data/hr` | `/hr` | v2.0 |
| `/stats/summary` | `/dashboard/summary` | v2.0 |
| `/stats/trends` | `/dashboard/trends` | v2.0 |
| `/strava/upload` | `/strava/sync/run` | v2.0 |

### 레거시 경로 목록 조회

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/aliases` | 모든 레거시 경로 목록 |

### Deprecation 정책

1. 레거시 경로는 2개 메이저 버전 동안 유지됩니다.
2. 레거시 경로 사용 시 `X-API-Deprecation-Warning` 헤더가 포함됩니다.
3. 안정적인 통합을 위해 항상 정식(Canonical) 경로를 사용하세요.

---

## 에러 응답

모든 에러는 다음 형식으로 반환됩니다:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP 상태 코드

| Code | 의미 |
|------|------|
| 200 | 성공 |
| 201 | 생성됨 |
| 204 | 내용 없음 (삭제 성공) |
| 308 | 영구 리다이렉트 (레거시 경로) |
| 400 | 잘못된 요청 |
| 401 | 인증 필요 |
| 403 | 권한 없음 |
| 404 | 리소스 없음 |
| 422 | 유효성 검사 실패 |
| 500 | 서버 에러 |
| 501 | 미구현 (OAuth 미설정 등) |

---

## 버전 관리

- 현재 버전: **v1**
- API 버전은 URL 경로에 포함됩니다: `/api/v1/...`
- 메이저 버전 변경 시 새로운 경로가 추가됩니다: `/api/v2/...`
- `Accept-Version` 헤더로 버전 협상이 가능합니다 (선택사항)

---

## Rate Limiting

현재 MVP에서는 Rate Limiting이 적용되지 않습니다.
향후 버전에서 요청 제한이 추가될 수 있습니다.

---

## Observability

- 모든 응답에 `X-Request-ID` 헤더가 포함됩니다.
- Prometheus 메트릭: `GET /metrics` (JSON이 아닌 텍스트 포맷)

---

## 변경 이력

| 버전 | 날짜 | 변경 사항 |
|------|------|-----------|
| v1.0 | 2025-01-01 | 초기 API 릴리스 |
| v1.1 | 2025-01-15 | Analytics 엔드포인트 추가 |
| v1.2 | 2025-01-30 | 레거시 라우팅 정책 추가 |
| v1.3 | 2024-12-30 | Gear API 추가, 대시보드 기간 계산 달력 기준으로 변경 |
| v1.4 | 2024-12-30 | Garmin 인증 API 문서화, health_status/trends 데이터 연결 |
| v1.5 | 2024-12-30 | 보안 강화: 에러 메시지 일반화 (Auth/Strava/Runalyze), 레거시 라우트 리다이렉트 헤더 수정, Strava refresh 문서 추가 |
