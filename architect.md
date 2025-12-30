# RunningCoach 아키텍처 (현재 스냅샷)

## 목적
- MVP/PRD/blueprint에 흩어진 구조/결정 사항을 한 곳에 정리한다.
- API/UX 변경 시 이 문서를 함께 갱신한다.

## 관련 문서
- 기능 맵: `docs/feature-map.md`
- API 레퍼런스: `docs/api-reference.md`
- 제품 문서: `docs/MVP.md`, `docs/PRD.md`, `docs/blueprint.md`

## 시스템 개요
- 단일 사용자 우선, 소규모 공유 사용 가능.
- Garmin 데이터 수집 + FIT 파싱 -> 정규화 -> 분석/집계.
- AI 훈련 계획(OpenAI) + 수동 플랜 import/export.
- Garmin 워크아웃 푸시 + Strava 자동 업로드.
- NAS 환경에서 Docker Compose로 배포.

## 상위 구성 요소
- 프론트엔드 UI (React + Vite + TypeScript, Tailwind v4, React Router, React Query, Recharts, Jarvis 스타일 대시보드).
- API 서비스 (FastAPI).
- 워커 서비스 (Celery): 동기화, 파싱, 분석.
- 스케줄러 (Celery Beat 또는 cron).
- DB (PostgreSQL 15+, 샘플은 TimescaleDB 선택).
- 캐시/세션 (Redis).
- RAG 스토어 (pgvector).
- 파일 스토리지 (FIT 및 raw payloads, NAS 볼륨).

## 데이터 흐름
1) Garmin -> Ingestion 어댑터 -> raw JSON + FIT 메타데이터.
2) 초기 전체 백필 -> FIT 다운로드/파싱 -> 샘플 적재.
3) Raw -> 정규화 테이블 -> 파생 지표 -> 요약/분석.
4) 대시보드가 요약/분석을 조회.
5) AI 플래닝이 프로필 + 분석 + 가이드라인을 참조.
6) Garmin 동기화가 워크아웃/스케줄을 푸시.
7) Strava 동기화가 Garmin 이후 활동 업로드.

## 동기화 전략
- 초기 백필: 가능한 전체 이력 (GARMIN_BACKFILL_DAYS=0).
- 증분: last_success_at + safety window 3일.
- 목록 -> 상세 fetch로 정합성 확보.
- 활동별 FIT 다운로드, 파일 해시/경로 저장.
- idempotent 변환 및 재계산.
- 레이트리밋 보호(jitter) + 재시도(backoff).
- cursor/last_success_at 기반 체크포인트 재개.

## 분석/파생 지표
- 주간 요약(월요일 시작) 및 월간 요약(매월 1일).
- Runalyze+ 파생 지표: TRIMP, TSS, ATL/CTL/TSB,
  효율지수, Training Effect, VO2max 트렌드.
- AI를 위한 전체 이력 기반 베이스라인 생성.

## AI 플래닝
- OpenAI API 기반 대화형 플래닝.
- 대화 로그 저장(감사/재현 목적).
- 외부 채팅 결과 JSON 수동 import.
- ChatGPT 복사용 요약 export.
- 한국어 UI + 영어 자료 RAG 지원.
- 토큰 예산 관리: 최근 6주 + 12주 추세 + 전체 요약.

## Strava 동기화
- OAuth 연결/갱신.
- Garmin 동기화 완료 후 자동 업로드.
- 매핑 테이블로 중복 업로드 방지.
- 레이트리밋/실패 시 재시도 및 큐 처리.

## 데이터 모델 (핵심 테이블)
- users, garmin_sessions, garmin_sync_state
- garmin_raw_events, garmin_raw_files
- activities, activity_samples
- sleep, hr_records, health_metrics
- activity_metrics, fitness_metrics_daily
- analytics_summaries
- workouts, workout_schedules
- ai_conversations, ai_messages, ai_imports
- strava_sessions, strava_sync_state, strava_activity_map

## API 표면 (구현 기준)
- Auth:
  - /api/v1/auth/login, /auth/logout, /auth/me
  - /api/v1/auth/garmin/connect|refresh|disconnect|status
  (Note: Strava OAuth는 /api/v1/strava/* 에서 처리)
- Ingest:
  - /api/v1/ingest/run, /ingest/run/sync, /ingest/status, /ingest/history
- Activities:
  - /api/v1/activities, /activities/{id},
    /activities/{id}/samples, /activities/{id}/fit, /activities/types/list
- Health:
  - /api/v1/sleep, /api/v1/hr, /api/v1/metrics
- Dashboard:
  - /api/v1/dashboard/summary, /api/v1/dashboard/trends, /api/v1/dashboard/calendar
- Analytics:
  - /api/v1/analytics/compare, /analytics/personal-records
- AI:
  - /api/v1/ai/chat, /ai/conversations, /ai/conversations/{id},
    /ai/conversations/{id}/chat, /ai/import, /ai/export
- Workouts:
  - /api/v1/workouts, /workouts/{id}, /workouts/{id}/push
  - /api/v1/workouts/schedules/list, /workouts/schedules,
    /workouts/schedules/{id}/status, /workouts/schedules/{id}
- Plans:
  - /api/v1/plans, /plans/{id}, /plans/{id}/approve,
    /plans/{id}/activate, /plans/{id}/weeks
- Strava:
  - /api/v1/strava/connect, /strava/callback, /strava/status, /strava/disconnect
  - /api/v1/strava/sync/run, /strava/sync/status
  - /api/v1/strava/activities, /strava/activities/{id}/upload
- Runalyze:
  - /api/v1/runalyze/status - 연결 상태 확인
  - /api/v1/runalyze/hrv - HRV(심박변이도) 데이터 조회
  - /api/v1/runalyze/sleep - 수면 데이터 조회
  - /api/v1/runalyze/summary - 건강 지표 요약 (대시보드용)
- Aliases:
  - /api/v1/aliases (레거시 목록), /sync/garmin/* → /ingest/*

## API 모듈 맵 (초기 제안, 미채택)
- /api/v1/auth: login, token refresh, me
- /api/v1/garmin: connect, 2FA, data ingest
- /api/v1/strava: OAuth, upload
- /api/v1/activities: CRUD + samples + FIT
- /api/v1/dashboard: summary, trends, calendar
- /api/v1/plans: plan CRUD + approve/activate
- /api/v1/workouts: CRUD + push + schedule
- /api/v1/health: sleep, hr, body
- /api/v1/analytics: summary stats
- /api/v1/ai: chat + import/export
- /api/v1/sync: legacy sync

주의: 위 모듈 경로는 현재 구현/문서와 정합이 맞지 않는다
(auth/garmin vs /garmin, ingest vs /sync 등). 정식 경로 확정 또는 alias 정책이 필요.

## 정합성 이슈 (문서/프론트/백엔드) - 해결 완료
- ✅ 활동 상세/샘플 응답 스키마 → 백엔드에 `/activities/{id}/hr-zones`, `/laps` 엔드포인트 추가 예정.
- ✅ `/activities/{id}/samples` 파라미터 → 아래 API 문서에 명시됨.
- ✅ 워크아웃 스케줄 경로 → `/workouts/schedules/*` (컬렉션 기반)으로 확정.
- ✅ 플랜 동기화 경로 → `/plans/{id}/activate`로 확정 (approve → activate 워크플로우).
- ✅ Strava 연결 → `/strava/*`로 통합, `/auth/strava/*` 제거 예정.

### `/activities/{id}/samples` 파라미터
| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| limit | int | 1000 | 페이지당 샘플 수 (max: 10000) |
| offset | int | 0 | 페이지네이션 오프셋 |
| downsample | int | - | 다운샘플 목표 개수 (50-2000, 차트용) |
| fields | str | - | 필터 필드 (hr,pace,cadence,power,gps,altitude)

## 보안
- 로컬 로그인 + 서버 세션(HTTP-only 쿠키).
- 비밀번호 bcrypt 해시 저장.
- Garmin/Strava 세션 토큰은 DB에 저장 (개인용 NAS 환경 기준, 암호화 미적용).
- 로컬 개발 시 HTTPS 권장 (cookie_secure=true 기본값).
- AI 로그 보관/삭제 정책 필요.

## 성능 목표
- API 응답 p95 < 500ms.
- 증분 동기화 p95 < 5분 (초기 백필 제외).
- 대용량 응답(samples, FIT)은 스트리밍/페이징 필요.

## 배포
- NAS에서 Docker Compose 운영.
- 볼륨: db_data, redis_data, fit_data, logs, backups.
- 모니터링: Prometheus + Grafana.
- 로깅: Loki.

## 남은 과제
- ✅ API 모듈 경로/alias 정리 → 완료 (위 정합성 이슈 참조).
- ✅ 문서(api-reference)와 구현 정합성 업데이트 → 완료.
- OpenAI 모델 선택 및 비용표 확정.
- FIT 보관/압축/폐기 정책.
- ⏳ 프론트 타입/백엔드 응답 정합성 정리 → HR존/랩 엔드포인트 구현 후 완료 예정.

## 구현 완료 (Activity 확장 API)
- `GET /api/v1/activities/{id}/hr-zones` - HR존별 시간 분포 ✅
- `GET /api/v1/activities/{id}/laps` - 랩/구간 데이터 ✅
- `GET /api/v1/activities/types/list` - 활동 유형 목록 ✅

## 구현 예정
- `GET /api/v1/activities/{id}/weather` - 활동 시점 날씨 (선택)

## Runalyze 연동

### 개요
Runalyze는 러닝/훈련 데이터 분석 플랫폼으로, HRV(심박변이도)와 수면 데이터를 제공한다.
RunningCoach에서는 Runalyze Personal API를 통해 건강 지표를 가져와 대시보드에 표시한다.

### 인증
- 인증 방식: Header 기반 토큰 (`token: <api_key>`)
- API Base URL: `https://runalyze.com/api/v1`
- 설정: `RUNALYZE_API_TOKEN` 환경변수

### 사용 가능한 엔드포인트 (Free tier)
| Runalyze API | 설명 | 응답 예시 |
|--------------|------|-----------|
| `/api/v1/ping` | 연결 확인 | `["pong"]` |
| `/api/v1/metrics/hrv` | HRV (RMSSD) 데이터 | `[{id, hrv, rmssd, metric, measurement_type, date_time}]` |
| `/api/v1/metrics/sleep` | 수면 데이터 | `[{id, duration, rem_duration, deep_sleep_duration, quality, date_time}]` |

### 백엔드 구현
- 위치: `/backend/app/api/v1/endpoints/runalyze.py`
- httpx AsyncClient로 외부 API 호출
- 응답 캐싱: staleTime 10-15분

### 프론트엔드 구현
- API 클라이언트: `/frontend/src/api/runalyze.ts`
- React Query 훅: `/frontend/src/hooks/useRunalyze.ts`
  - `useRunalyzeStatus()` - 연결 상태
  - `useRunalyzeHRV(limit)` - HRV 데이터
  - `useRunalyzeSleep(limit)` - 수면 데이터
  - `useRunalyzeSummary()` - 대시보드용 요약

### 데이터 모델
```typescript
// HRV 데이터
interface RunalyzeHRVDataPoint {
  id: number;
  date_time: string;
  hrv: number;
  rmssd: number;
  metric: string;           // 'rmssd'
  measurement_type: string; // 'sleep'
}

// 수면 데이터
interface RunalyzeSleepDataPoint {
  id: number;
  date_time: string;
  duration: number;         // 분 단위
  rem_duration: number | null;
  light_sleep_duration: number | null;
  deep_sleep_duration: number | null;
  awake_duration: number | null;
  quality: number | null;   // 1-10
  source: string | null;    // 'garmin' 등
}

// 요약 (대시보드용)
interface RunalyzeSummary {
  latest_hrv: number | null;
  latest_hrv_date: string | null;
  avg_hrv_7d: number | null;
  latest_sleep_quality: number | null;
  latest_sleep_duration: number | null;
  latest_sleep_date: string | null;
  avg_sleep_quality_7d: number | null;
}
```

### 제한사항
- Free tier에서는 일부 엔드포인트만 접근 가능
- 활동 데이터, 훈련 로그 등은 404 반환 (유료 기능으로 추정)
- API 문서가 공개되지 않아 직접 테스트로 엔드포인트 확인

### 데이터 소스 정책 (Garmin vs Runalyze)

Runalyze는 Garmin에서 동기화된 데이터를 기반으로 일부 지표를 계산한다.
중복 데이터 처리 원칙:

| 지표 | 소스 | 비고 |
|------|------|------|
| 수면 점수 | **Garmin** | Garmin 기본 제공 |
| 수면 시간/단계 | Garmin (우선) | Runalyze도 제공하지만 Garmin 우선 |
| 안정 심박 | **Garmin** | Garmin 직접 측정 |
| VO2max | **Garmin** | Garmin 워치 계산 |
| HRV (RMSSD) | **Runalyze** | Garmin Connect에서 직접 API 제공 안함 (워치에서만 표시) |
| Body Battery | **Garmin** | Garmin 독점 지표 |

**원칙**:
1. Garmin에서 직접 제공하는 지표는 Garmin 데이터 사용
2. Runalyze 고유 지표(HRV 등)는 Runalyze 데이터 사용
3. 동일 지표가 양쪽에서 다른 값을 보이면, 출처를 명시 (예: "HRV (Runalyze)", "VO2max (Garmin)")
4. UI에서는 소스 라벨을 작은 텍스트로 표시하여 혼란 방지
