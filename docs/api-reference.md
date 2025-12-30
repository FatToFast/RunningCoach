# RunningCoach API Reference (v1)

## 개요

RunningCoach API는 RESTful 설계 원칙을 따르며, JSON 형식으로 데이터를 주고받습니다.

- **Base URL**: `/api/v1`
- **인증**: HTTP-only 쿠키 기반 세션
- **Content-Type**: `application/json`

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

### Strava 연동 (OAuth)

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/auth/strava/connect` | OAuth 시작 (auth_url 반환) |
| POST | `/auth/strava/callback` | OAuth 콜백 처리 |
| POST | `/auth/strava/refresh` | 토큰 갱신 |
| GET | `/auth/strava/status` | 연결 상태 확인 |

---

## 데이터 수집 (Ingestion)

Garmin에서 데이터를 동기화합니다.

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/ingest/run` | 수동 동기화 실행 |
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

---

## 활동 (Activities)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/activities` | 활동 목록 (페이지네이션) |
| GET | `/activities/{id}` | 활동 상세 |
| GET | `/activities/{id}/samples` | 활동 샘플 (초 단위 데이터) |
| GET | `/activities/{id}/fit` | FIT 파일 다운로드 |

### Query Parameters

| Parameter | Type | Default | 설명 |
|-----------|------|---------|------|
| page | int | 1 | 페이지 번호 |
| per_page | int | 20 | 페이지당 항목 수 (max: 100) |
| activity_type | string | - | 활동 유형 필터 |
| start_date | date | - | 시작 날짜 필터 |
| end_date | date | - | 종료 날짜 필터 |

### GET `/activities/{id}/samples` Example

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
  "total": 200,
  "is_downsampled": true,
  "original_count": 982
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
| GET | `/hr` | 심박/HRV 기록 목록 |
| GET | `/hr/summary` | 심박 요약 |

### 건강/피트니스 지표 (Metrics)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/metrics` | 지표 요약 |
| GET | `/metrics/body` | 신체 지표 (Body Battery, Stress 등) |
| GET | `/metrics/fitness` | 피트니스 지표 (VO2max, Training Load 등) |

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
      "duration_minutes": 58,
      "avg_hr": 155
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
    "weekly_tss": 280.0
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
          "duration_minutes": 58,
          "avg_hr": 155
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
| period | string | "week" | 기간 유형: "week" \| "month" |
| current_end | date | today | 현재 기간 종료일 |

### GET `/analytics/personal-records` Query Parameters

| Parameter | Type | Default | 설명 |
|-----------|------|---------|------|
| activity_type | string | "running" | 활동 유형 필터 |

---

## AI 훈련 계획 (AI Planning)

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/ai/chat` | 대화형 계획 생성/수정 |
| GET | `/ai/conversations` | 대화 목록 |
| GET | `/ai/conversations/{id}` | 대화 상세 |
| POST | `/ai/import` | 수동 플랜 JSON import |
| GET | `/ai/export` | ChatGPT 분석용 요약 생성 |

### POST `/ai/chat` Request Body

```json
{
  "message": "이번 주 템포런 계획을 조정해줘",
  "context": { "language": "ko", "goal": "10k PR" }
}
```

### POST `/ai/chat` Response

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

```json
{
  "plan_name": "10K Base 4w",
  "start_date": "2025-01-06",
  "workouts": [
    {
      "date": "2025-01-08",
      "name": "Tempo",
      "type": "run",
      "steps": [
        { "type": "warmup", "duration_min": 10 },
        { "type": "run", "duration_min": 30, "target_pace": "5:10/km" },
        { "type": "cooldown", "duration_min": 10 }
      ]
    }
  ]
}
```

---

## 워크아웃 (Workouts)

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/workouts` | 워크아웃 생성 |
| GET | `/workouts` | 워크아웃 목록 |
| GET | `/workouts/{id}` | 워크아웃 상세 |
| PATCH | `/workouts/{id}` | 워크아웃 수정 |
| DELETE | `/workouts/{id}` | 워크아웃 삭제 |
| POST | `/workouts/{id}/push` | Garmin에 전송 |
| GET | `/workouts/schedules/list` | 스케줄 목록 |
| POST | `/workouts/schedules` | 날짜 스케줄링 |
| PATCH | `/workouts/schedules/{schedule_id}/status` | 스케줄 상태 변경 |
| DELETE | `/workouts/schedules/{schedule_id}` | 스케줄 삭제 |

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
  "garmin_schedule_id": 345678,
  "workout": null
}
```

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

### GET `/gear` Query Parameters

| Parameter | Type | Default | 설명 |
|-----------|------|---------|------|
| status | string | - | 상태 필터: "active" \| "retired" \| "all" |
| gear_type | string | - | 장비 유형 필터: "running_shoes" \| "cycling_shoes" \| "bike" \| "other" |

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
