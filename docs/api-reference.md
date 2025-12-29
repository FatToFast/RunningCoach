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

### Garmin 연동

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/auth/garmin/connect` | Garmin 계정 연결 (이메일/비밀번호) |
| POST | `/auth/garmin/refresh` | 세션 갱신 |
| DELETE | `/auth/garmin/disconnect` | 연결 해제 |
| GET | `/auth/garmin/status` | 연결 상태 확인 |

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
  "full_backfill": false
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
| GET | `/metrics` | 지표 목록 |
| GET | `/metrics/summary` | 지표 요약 |
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

### GET `/dashboard/trends` Query Parameters

| Parameter | Type | Default | 설명 |
|-----------|------|---------|------|
| weeks | int | 12 | 조회 주 수 (4-52) |

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
| PUT | `/workouts/{id}` | 워크아웃 수정 |
| DELETE | `/workouts/{id}` | 워크아웃 삭제 |
| POST | `/workouts/{id}/push` | Garmin에 전송 |
| POST | `/workouts/{id}/schedule` | 날짜 스케줄링 |

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

## 변경 이력

| 버전 | 날짜 | 변경 사항 |
|------|------|-----------|
| v1.0 | 2025-01-01 | 초기 API 릴리스 |
| v1.1 | 2025-01-15 | Analytics 엔드포인트 추가 |
| v1.2 | 2025-01-30 | 레거시 라우팅 정책 추가 |
