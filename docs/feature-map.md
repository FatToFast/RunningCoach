# 기능 맵 (디버깅용)

이 문서는 기능별로 관련 파일과 책임 위치를 묶어 빠르게 추적할 수 있도록 정리한 맵입니다.

## API 엔드포인트 요약표
- 공통 prefix: `/api/v1`
- Auth/Session: POST `/auth/login`, POST `/auth/logout`, GET `/auth/me`, POST `/auth/garmin/connect`, POST `/auth/garmin/refresh`, DELETE `/auth/garmin/disconnect`, GET `/auth/garmin/status`
- Ingest: POST `/ingest/run`, POST `/ingest/run/sync`, GET `/ingest/status`, GET `/ingest/history`
- Activities: GET `/activities`, GET `/activities/{id}`, GET `/activities/{id}/samples`, GET `/activities/{id}/fit`, GET `/activities/types/list`, GET `/activities/{id}/hr-zones`, GET `/activities/{id}/laps`
- Dashboard: GET `/dashboard/summary`, GET `/dashboard/trends`, GET `/dashboard/calendar`
- Analytics: GET `/analytics/compare`, GET `/analytics/personal-records`
- Health: GET `/sleep`, GET `/sleep/{sleep_date}`, GET `/hr`, GET `/hr/summary`, GET `/metrics`, GET `/metrics/body`, GET `/metrics/fitness`
- AI: POST `/ai/chat`, GET `/ai/conversations`, POST `/ai/conversations`, GET `/ai/conversations/{id}`, DELETE `/ai/conversations/{id}`, POST `/ai/conversations/{id}/chat`, POST `/ai/import`, GET `/ai/export`
- Workouts: GET `/workouts`, POST `/workouts`, GET `/workouts/{id}`, PATCH `/workouts/{id}`, DELETE `/workouts/{id}`, POST `/workouts/{id}/push`, GET `/workouts/schedules/list`, POST `/workouts/schedules`, PATCH `/workouts/schedules/{schedule_id}/status`, DELETE `/workouts/schedules/{schedule_id}`
- Plans: GET `/plans`, POST `/plans`, GET `/plans/{id}`, PATCH `/plans/{id}`, DELETE `/plans/{id}`, POST `/plans/{id}/approve`, POST `/plans/{id}/activate`, POST `/plans/{id}/weeks`
- Strava: GET `/strava/connect`, POST `/strava/callback`, POST `/strava/refresh`, GET `/strava/status`, DELETE `/strava/disconnect`, POST `/strava/sync/run`, GET `/strava/sync/status`, GET `/strava/activities`, POST `/strava/activities/{activity_id}/upload`
- Runalyze: GET `/runalyze/status`, GET `/runalyze/hrv`, GET `/runalyze/sleep`, GET `/runalyze/summary`
- Gear: GET `/gear`, GET `/gear/stats`, GET `/gear/{gear_id}`, POST `/gear`, PATCH `/gear/{gear_id}`, POST `/gear/{gear_id}/retire`, DELETE `/gear/{gear_id}`, POST `/gear/{gear_id}/activities/{activity_id}`, DELETE `/gear/{gear_id}/activities/{activity_id}`, GET `/gear/{gear_id}/activities`
- Aliases: GET `/aliases`

## 응답 모델 요약 (핵심)
- 기준: `backend/app/api/v1/endpoints/*.py`의 `response_model` 선언
- Auth: `/auth/login` → `LoginResponse`, `/auth/me` → `UserResponse`, `/auth/garmin/connect` → `GarminConnectResponse`, `/auth/garmin/status` → `GarminStatusResponse`
- Ingest: `/ingest/run` → `IngestRunResponse`, `/ingest/run/sync` → `list[SyncResultItem]`, `/ingest/status` → `IngestStatusResponse`, `/ingest/history` → `SyncHistoryResponse`
- Activities: `/activities` → `ActivityListResponse`, `/activities/{id}` → `ActivityDetailResponse`, `/activities/{id}/samples` → `SamplesListResponse`, `/activities/{id}/fit` → `FileResponse`, `/activities/{id}/hr-zones` → `HRZonesResponse`, `/activities/{id}/laps` → `LapsResponse`
- Dashboard: `/dashboard/summary` → `DashboardSummaryResponse`, `/dashboard/trends` → `TrendsResponse`, `/dashboard/calendar` → `CalendarResponse`
- Analytics: `/analytics/compare` → `CompareResponse`, `/analytics/personal-records` → `PersonalRecordsResponse`
- Health: `/sleep` → `SleepListResponse`, `/sleep/{sleep_date}` → `SleepDetailResponse`, `/hr` → `HeartRateListResponse`, `/hr/summary` → `HeartRateSummary`, `/metrics` → `MetricsSummary`, `/metrics/body` → `BodyCompositionListResponse`, `/metrics/fitness` → `FitnessMetricListResponse`
- AI: `/ai/conversations` → `ConversationListResponse`, `/ai/conversations`(POST) → `ConversationResponse`, `/ai/conversations/{id}` → `ConversationDetailResponse`, `/ai/conversations/{id}/chat` → `ChatResponse`, `/ai/chat` → `ChatResponse`, `/ai/import` → `PlanImportResponse`, `/ai/export` → `ExportSummaryResponse`
- Workouts: `/workouts` → `WorkoutListResponse`, `/workouts`(POST) → `WorkoutResponse`, `/workouts/{id}` → `WorkoutResponse`, `/workouts/{id}/push` → `GarminPushResponse`, `/workouts/schedules/list` → `ScheduleListResponse`, `/workouts/schedules` → `ScheduleResponse`
- Plans: `/plans` → `PlanListResponse`, `/plans`(POST) → `PlanResponse`, `/plans/{id}` → `PlanDetailResponse`, `/plans/{id}`(PATCH) → `PlanResponse`, `/plans/{id}/approve` → `PlanResponse`, `/plans/{id}/activate` → `PlanResponse`, `/plans/{id}/weeks` → `PlanWeekResponse`
- Strava: `/strava/connect` → `StravaConnectResponse`, `/strava/callback` → `StravaCallbackResponse`, `/strava/status` → `StravaStatusResponse`, `/strava/refresh` → `RefreshResponse`, `/strava/sync/run` → `SyncRunResponse`, `/strava/sync/status` → `SyncStatusResponse`, `/strava/activities` → `list[UploadStatusResponse]`, `/strava/activities/{activity_id}/upload` → `UploadStatusResponse`
- Runalyze: `/runalyze/status` → `RunalyzeStatusResponse`, `/runalyze/hrv` → `HRVResponse`, `/runalyze/sleep` → `SleepResponse`, `/runalyze/summary` → `RunalyzeSummary`
- Gear: `/gear` → `GearListResponse`, `/gear/stats` → `GearStatsResponse`, `/gear/{gear_id}` → `GearDetailResponse`, `/gear`(POST) → `GearDetailResponse`, `/gear/{gear_id}`(PATCH) → `GearDetailResponse`
- 참고: 일부 엔드포인트는 204(No Content) 또는 파일 스트림(FileResponse)을 반환

## 요청/응답 예시 (정확 샘플)
### POST `/auth/login`
Request
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```
Response
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

### POST `/ingest/run`
Request
```json
{
  "endpoints": ["activities", "sleep", "heart_rate"],
  "full_backfill": true,
  "start_date": "2020-01-01",
  "end_date": "2024-12-31"
}
```
지원 endpoints:
- activities, sleep, heart_rate
- body_battery, stress, hrv, respiration, spo2
- training_status, max_metrics, stats
- race_predictions, personal_records, goals

Response
```json
{
  "started": true,
  "message": "Sync started in background",
  "endpoints": ["activities", "sleep", "heart_rate"],
  "sync_id": "sync_1_1735632000"
}
```

### GET `/dashboard/summary?period=week`
Response
```json
{
  "period_type": "week",
  "period_start": "2024-12-02",
  "period_end": "2024-12-08",
  "summary": {
    "total_distance_km": 42.3,
    "total_duration_hours": 3.8,
    "total_activities": 4,
    "avg_pace_per_km": "5:24/km",
    "avg_pace_seconds": 324,
    "avg_hr": 148,
    "total_elevation_m": 320.0,
    "total_calories": 2480
  },
  "recent_activities": [],
  "health_status": {
    "latest_sleep_score": 82,
    "latest_sleep_hours": 7.1,
    "resting_hr": 52,
    "body_battery": 75,
    "vo2max": 52.1
  },
  "fitness_status": {
    "ctl": 42.3,
    "atl": 38.1,
    "tsb": 4.2,
    "weekly_trimp": 320.0,
    "weekly_tss": 280.5
  },
  "upcoming_workouts": []
}
```

### GET `/activities/{id}/samples?downsample=200&fields=hr,pace`
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

### POST `/ai/chat`
Request
```json
{
  "message": "이번 주 템포런 계획을 조정해줘",
  "context": { "language": "ko", "goal": "10k PR" }
}
```
Response
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

### POST `/workouts/schedules`
Request
```json
{
  "workout_id": 55,
  "scheduled_date": "2024-12-07"
}
```
Response
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

### GET `/activities/{id}/fit`
Response
```
FIT 파일 스트림 (binary)
```

## 디버깅 체크리스트

### 요청/라우팅
- 요청 경로/프리픽스 확인: `/api/v1` 누락 여부와 `frontend/src/api/client.ts`의 base URL
- 레거시 경로 사용 여부: `backend/app/api/v1/aliases.py` (`/api/v1` prefix 아래에서만 지원, 예: `/api/v1/sync/garmin/run` → `/api/v1/ingest/run`)

### 인증/세션
- 로컬 인증 (쿠키 기반): `backend/app/core/session.py`, `config.py`의 `cookie_secure`/`cookie_samesite`
- 외부 연동 (토큰 기반): Garmin(`garmin_sessions`), Strava(`strava_tokens`), Runalyze(`runalyze_api_token`)
- CORS/credentials 확인: `backend/app/main.py`의 `allow_origins` + `frontend/src/api/client.ts`의 `withCredentials: true`
- 401 리다이렉트 예외: `client.ts`의 인터셉터에서 `/garmin/`, `/strava/`, `/auth/login` 제외 여부

### DB/마이그레이션
- DB 연동 확인: 쿼리 결과 유무, `backend/app/core/config.py`의 `database_url`/`database_echo`
- 마이그레이션 상태: `alembic current`, `alembic history` 명령으로 스키마 일치 확인
- 모델/DB 불일치: `backend/alembic/versions/` 파일과 `backend/app/models/` 비교

### 동기화/외부 API
- 동기화 상태 확인: `/ingest/status` 결과와 `backend/app/services/sync_service.py`의 로그
- 외부 API 확인: Garmin/Strava/Runalyze 토큰 만료·갱신 흐름, 어댑터 응답 값
- FIT/파일 확인: `fit_storage_path` 경로, `has_fit_file` 플래그, 파일 존재 여부

### 문서/스키마 일치
- 문서/구현 차이 확인: `docs/api-reference.md`, `docs/PRD.md`, `docs/MVP.md`와 `backend/app/api/v1/router.py` 비교
- 프론트/백 스키마 확인: `frontend/src/types/api.ts`, `frontend/src/api/auth.ts`와 백엔드 `response_model` 정의 불일치 여부

### 로그 포인트
- 요청 로그: 시작/끝, 응답 시간 (`backend/app/observability.py` 미들웨어)
- 사용자/세션 ID: 현재 미들웨어에서 미기록 → 필요 시 `RequestLoggingMiddleware` 보강
- 동기화 로그: 시작/종료(엔드포인트/기간), 에러, 재시도 횟수 (`backend/app/services/sync_service.py`)
- 외부 API 로그: 요청/응답 코드 및 레이트리밋 헤더 (`backend/app/adapters/garmin_adapter.py`, `strava.py`, `runalyze.py`)

### 메트릭 포인트
- HTTP: endpoint별 요청 수/지연(p95/p99), 4xx/5xx 비율
- 동기화: 성공률/처리량, FIT 다운로드 시간·바이트, 외부 API 오류율
- DB: 슬로우 쿼리, 커넥션 풀 사용률, 큐 적체(Celery/Redis 사용 시)

## 관측성 설계 초안
- 로그 포맷: 구조화(JSON) + `request_id` + `method` + `path` + `route` + `status_code` + `elapsed_ms` + `client`
  - 참고: `user_id`는 현재 미포함, 필요시 `RequestLoggingMiddleware` 보강 필요
- 미들웨어: 요청 시작/종료 시점에 `request_id`를 발급하고 응답 헤더로 반환
- 트레이싱: OpenTelemetry로 HTTP 요청/DB/외부 API 호출 span 연결
- 메트릭: Prometheus 포맷 (단위: 밀리초)
  - `http_requests_total` - 요청 수 (method, route, status)
  - `http_request_duration_ms` - 요청 지연 히스토그램
  - 참고: 매칭되지 않는 경로는 `/__unknown__`으로 정규화하여 라벨 카디널리티 제한
- 메트릭 엔드포인트: `GET /metrics` (Prometheus 텍스트, `/api/v1` 외부)
- 경보 기준: 5xx 비율, 외부 API 오류율, 동기화 실패율, 대기 큐 적체
- 대시보드: 요청 지연(p95/p99), 동기화 처리량, 외부 API 레이트리밋, DB 커넥션 풀

## 공통/진입점
- Backend 부트스트랩/라우팅: `backend/app/main.py`, `backend/app/api/v1/router.py`, `backend/app/api/v1/aliases.py`
- Backend 설정/세션/DB: `backend/app/core/config.py`, `backend/app/core/session.py`, `backend/app/core/security.py`, `backend/app/core/database.py`
- Backend 관측성: `backend/app/observability.py`
- Frontend 부트스트랩/라우팅: `frontend/src/main.tsx`, `frontend/src/App.tsx`
  - SPA이므로 운영 배포 시 웹서버에서 모든 경로를 `index.html`로 rewrite 필요 (Nginx: `try_files $uri /index.html;`)
  - 404 catch-all 라우트로 잘못된 URL 접근 시 Not Found 페이지 표시
- 공통 API 클라이언트: `frontend/src/api/client.ts`

## 인증/세션
- API: `/api/v1/auth/*`
- Backend: `backend/app/api/v1/endpoints/auth.py`
- Models: `backend/app/models/user.py`, `backend/app/models/garmin.py`, `backend/app/models/strava.py`
- Frontend: `frontend/src/pages/Login.tsx`, `frontend/src/api/auth.ts`, `frontend/src/hooks/useAuth.ts`

## Garmin 동기화/수집
- API: `/api/v1/auth/garmin/*`, `/api/v1/ingest/*`
- Backend: `backend/app/api/v1/endpoints/ingest.py`, `backend/app/services/sync_service.py`, `backend/app/adapters/garmin_adapter.py`
- Models: `backend/app/models/garmin.py`, `backend/app/models/activity.py`, `backend/app/models/health.py`

## 활동/샘플/FIT
- API: `/api/v1/activities/*`
- Backend: `backend/app/api/v1/endpoints/activities.py`
- Models: `backend/app/models/activity.py`, `backend/app/models/garmin.py`
- Frontend: `frontend/src/pages/Activities.tsx`, `frontend/src/pages/ActivityDetail.tsx`, `frontend/src/api/activities.ts`, `frontend/src/hooks/useActivities.ts`, `frontend/src/components/activity/ActivityMap.tsx`, `frontend/src/components/activity/KmPaceChart.tsx`

## 대시보드/캘린더
- API: `/api/v1/dashboard/*`
- Backend: `backend/app/api/v1/endpoints/dashboard.py`, `backend/app/services/dashboard.py`
- Frontend: `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/Calendar.tsx`, `frontend/src/components/dashboard/StatCard.tsx`, `frontend/src/components/dashboard/MileageChart.tsx`, `frontend/src/components/dashboard/RecentActivities.tsx`, `frontend/src/components/dashboard/FitnessGauge.tsx`, `frontend/src/hooks/useDashboard.ts`, `frontend/src/api/dashboard.ts`

## Analytics/트렌드
- API: `/api/v1/analytics/*`
- Backend: `backend/app/api/v1/endpoints/analytics.py`
- Models: `backend/app/models/analytics.py`
- Frontend: `frontend/src/pages/Trends.tsx`, `frontend/src/pages/Records.tsx`

## 수면/심박/헬스 지표
- API: `/api/v1/sleep`, `/api/v1/hr`, `/api/v1/metrics`
- Backend: `backend/app/api/v1/endpoints/sleep.py`, `backend/app/api/v1/endpoints/hr.py`, `backend/app/api/v1/endpoints/metrics.py`
- Models: `backend/app/models/health.py`, `backend/app/models/analytics.py`

## 워크아웃/플랜
- API: `/api/v1/workouts/*`, `/api/v1/plans/*`
- Backend: `backend/app/api/v1/endpoints/workouts.py`, `backend/app/api/v1/endpoints/plans.py`
- Models: `backend/app/models/workout.py`, `backend/app/models/plan.py`
- Frontend: `frontend/src/pages/Calendar.tsx` (스케줄/캘린더 렌더링)

## AI 코치/대화
- API: `/api/v1/ai/*`
- Backend: `backend/app/api/v1/endpoints/ai.py`
- Models: `backend/app/models/ai.py`
- Frontend: 아직 전용 UI 없음 (필요 시 신규 페이지 추가)

## Strava 연동
- API: `/api/v1/strava/*`
- Backend: `backend/app/api/v1/endpoints/strava.py`
- Models: `backend/app/models/strava.py`

## Runalyze 연동
- API: `/api/v1/runalyze/*`
- Backend: `backend/app/api/v1/endpoints/runalyze.py`
- Frontend: `frontend/src/api/runalyze.ts`, `frontend/src/hooks/useRunalyze.ts`

## Gear 관리
- API: `/api/v1/gear/*`
- Backend: `backend/app/api/v1/endpoints/gear.py`
- Models: `backend/app/models/gear.py`
- Frontend: `frontend/src/pages/Gear.tsx`, `frontend/src/api/gear.ts`, `frontend/src/hooks/useGear.ts`

## 앱 레이아웃/설정
- Frontend 레이아웃: `frontend/src/components/layout/Layout.tsx`, `frontend/src/components/layout/Header.tsx`, `frontend/src/components/layout/Sidebar.tsx`
- Frontend 설정: `frontend/src/pages/Settings.tsx`

## 타입/모의데이터/유틸
- API 타입: `frontend/src/types/api.ts`
- 모의 데이터: `frontend/src/api/mockData.ts`
- 포맷 유틸: `frontend/src/utils/format.ts`

## 문서
- MVP/PRD: `docs/MVP.md`, `docs/PRD.md`
- 아키텍처: `architect.md`
- API 레퍼런스: `docs/api-reference.md`
- 블루프린트: `docs/blueprint.md`
