# RunningCoach 아키텍처 (현재 스냅샷)

## 목적
- MVP/PRD/blueprint에 흩어진 구조/결정 사항을 한 곳에 정리한다.
- API/UX 변경 시 이 문서를 함께 갱신한다.

## 시스템 개요
- 단일 사용자 우선, 소규모 공유 사용 가능.
- Garmin 데이터 수집 + FIT 파싱 -> 정규화 -> 분석/집계.
- AI 훈련 계획(OpenAI) + 수동 플랜 import/export.
- Garmin 워크아웃 푸시 + Strava 자동 업로드.
- NAS 환경에서 Docker Compose로 배포.

## 상위 구성 요소
- 프론트엔드 UI (MVP는 SvelteKit, Jarvis 스타일 대시보드 컨셉).
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

## API 표면 (현재 문서 기준)
- Auth + Garmin:
  - /api/v1/auth/login, /auth/logout, /auth/me
  - /api/v1/auth/garmin/connect|refresh|disconnect|status
- Ingest:
  - /api/v1/ingest/run, /ingest/status
- Activities:
  - /api/v1/activities, /activities/{id},
    /activities/{id}/samples, /activities/{id}/laps, /activities/{id}/fit
- Health:
  - /api/v1/sleep, /api/v1/hr, /api/v1/metrics
- Dashboard:
  - /api/v1/dashboard/summary (v1.0: trends/calendar)
- AI:
  - /api/v1/ai/chat, /ai/conversations/{id}, /ai/import, /ai/export
- Workouts:
  - /api/v1/workouts, /workouts/{id}, /workouts/{id}/push, /workouts/{id}/schedule
- Plans (v1.0 CRUD):
  - /api/v1/plans/generate, /plans/{id}, /plans/{id}/approve, /plans/{id}/sync
- Strava:
  - /api/v1/auth/strava/connect|refresh|status
  - /api/v1/strava/sync/run, /strava/sync/status

## API 모듈 맵 (사용자 제안)
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

주의: 위 모듈 경로는 현재 문서와 정합이 맞지 않는다
(auth/garmin vs /garmin, ingest vs /sync 등). 정식 경로를 확정하거나
alias 정책을 결정해야 한다.

## 보안
- 로컬 로그인 + 서버 세션(HTTP-only 쿠키).
- 비밀번호 Argon2/bcrypt 해시 저장.
- Garmin/Strava 토큰 암호화 저장.
- HTTPS 필수.
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
- API 모듈 경로/alias 정리.
- 프론트엔드 프레임워크 최종 결정(SvelteKit vs Next.js).
- OpenAI 모델 선택 및 비용표 확정.
- FIT 보관/압축/폐기 정책.
