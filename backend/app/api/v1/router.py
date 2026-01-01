"""API v1 router aggregating all endpoint routers.

Routes are organized to match PRD.md and MVP.md specifications.
See docs/api-reference.md for complete API documentation.

Canonical Routes (v1):
======================

Authentication:
  POST   /api/v1/auth/login              - 로컬 로그인
  POST   /api/v1/auth/logout             - 로그아웃
  GET    /api/v1/auth/me                 - 현재 사용자
  POST   /api/v1/auth/garmin/connect     - Garmin 계정 연결
  POST   /api/v1/auth/garmin/refresh     - Garmin 세션 갱신
  DELETE /api/v1/auth/garmin/disconnect  - Garmin 연결 해제
  GET    /api/v1/auth/garmin/status      - Garmin 연결 상태

Note: Strava OAuth endpoints are at /api/v1/strava/* (not /auth/strava/*)

Data Ingestion:
  POST   /api/v1/ingest/run              - 수동 동기화 실행 (비동기)
  POST   /api/v1/ingest/run/sync         - 수동 동기화 실행 (동기)
  GET    /api/v1/ingest/status           - 동기화 상태 조회
  GET    /api/v1/ingest/history          - 동기화 이력 (v1.0)

Activities:
  GET    /api/v1/activities              - 활동 목록 (페이지네이션)
  GET    /api/v1/activities/{id}         - 활동 상세
  GET    /api/v1/activities/{id}/samples - 활동 샘플 (초 단위)
  GET    /api/v1/activities/{id}/fit     - FIT 파일 다운로드
  GET    /api/v1/activities/types/list   - 활동 타입 목록
  GET    /api/v1/activities/{id}/hr-zones - 심박 존 분석
  GET    /api/v1/activities/{id}/laps    - 랩 데이터
  GET    /api/v1/activities/{id}/gear    - 연결된 장비 목록

Health Data:
  GET    /api/v1/sleep                   - 수면 기록 목록
  GET    /api/v1/sleep/{date}            - 특정 날짜 수면 데이터
  GET    /api/v1/hr                      - 심박/HRV 기록 목록
  GET    /api/v1/hr/summary              - 심박 요약
  GET    /api/v1/metrics                 - 건강/피트니스 지표 요약
  GET    /api/v1/metrics/body            - 신체 지표
  GET    /api/v1/metrics/fitness         - 피트니스 지표

Dashboard:
  GET    /api/v1/dashboard/summary       - 주간/월간 요약
  GET    /api/v1/dashboard/trends        - 트렌드 데이터 (차트용)
  GET    /api/v1/dashboard/calendar      - 캘린더 뷰 데이터

Analytics:
  GET    /api/v1/analytics/compare       - 기간 비교 분석
  GET    /api/v1/analytics/personal-records - 개인 최고 기록 (PR)

AI Planning:
  POST   /api/v1/ai/chat                 - 대화형 계획 생성/수정
  GET    /api/v1/ai/conversations        - 대화 목록
  GET    /api/v1/ai/conversations/{id}   - 대화 상세
  POST   /api/v1/ai/import               - 수동 플랜 JSON import
  GET    /api/v1/ai/export               - ChatGPT 분석용 요약 생성

Workouts:
  POST   /api/v1/workouts                - 워크아웃 생성
  GET    /api/v1/workouts                - 워크아웃 목록
  GET    /api/v1/workouts/{id}           - 워크아웃 상세
  PATCH  /api/v1/workouts/{id}           - 워크아웃 수정
  DELETE /api/v1/workouts/{id}           - 워크아웃 삭제
  POST   /api/v1/workouts/{id}/push      - Garmin에 전송
  GET    /api/v1/workouts/schedules/list - 스케줄 목록
  POST   /api/v1/workouts/schedules      - 스케줄 생성
  PATCH  /api/v1/workouts/schedules/{id}/status - 스케줄 상태 변경
  DELETE /api/v1/workouts/schedules/{id} - 스케줄 삭제

Training Plans (v1.0):
  POST   /api/v1/plans                   - 훈련 계획 생성
  GET    /api/v1/plans                   - 계획 목록
  GET    /api/v1/plans/{id}              - 계획 상세
  PATCH  /api/v1/plans/{id}              - 계획 수정
  DELETE /api/v1/plans/{id}              - 계획 삭제
  POST   /api/v1/plans/{id}/approve      - 계획 승인
  POST   /api/v1/plans/{id}/activate     - 계획 활성화
  POST   /api/v1/plans/{id}/weeks        - 주간 계획 추가

Strava Integration:
  GET    /api/v1/strava/connect          - Strava OAuth 시작
  POST   /api/v1/strava/callback         - Strava OAuth 콜백
  GET    /api/v1/strava/status           - Strava 연결 상태
  DELETE /api/v1/strava/disconnect       - Strava 연결 해제
  POST   /api/v1/strava/refresh          - Strava 토큰 갱신
  POST   /api/v1/strava/sync/run         - Strava 수동 동기화
  GET    /api/v1/strava/sync/status      - Strava 동기화 상태
  GET    /api/v1/strava/activities       - 업로드 상태 목록
  POST   /api/v1/strava/activities/{id}/upload - 단일 활동 업로드

Gear Management:
  GET    /api/v1/gear                    - 장비 목록 (필터: status, gear_type)
  GET    /api/v1/gear/stats              - 장비 통계 (대시보드용)
  GET    /api/v1/gear/{id}               - 장비 상세
  POST   /api/v1/gear                    - 장비 생성
  PATCH  /api/v1/gear/{id}               - 장비 수정
  POST   /api/v1/gear/{id}/retire        - 장비 은퇴
  DELETE /api/v1/gear/{id}               - 장비 삭제
  POST   /api/v1/gear/{id}/activities/{activity_id} - 활동에 장비 연결
  DELETE /api/v1/gear/{id}/activities/{activity_id} - 활동-장비 연결 해제
  GET    /api/v1/gear/{id}/activities    - 장비에 연결된 활동 목록

Runalyze Integration:
  GET    /api/v1/runalyze/status         - Runalyze 연결 상태
  GET    /api/v1/runalyze/hrv            - HRV(심박변이도) 데이터
  GET    /api/v1/runalyze/sleep          - 수면 데이터
  GET    /api/v1/runalyze/summary        - 건강 지표 요약
  GET    /api/v1/runalyze/calculations   - 훈련 계산 지표
  GET    /api/v1/runalyze/training-paces - 훈련 페이스

Strength Training:
  GET    /api/v1/strength/types          - 세션 타입 목록
  GET    /api/v1/strength/exercises/presets - 운동 프리셋 목록
  GET    /api/v1/strength                - 세션 목록
  GET    /api/v1/strength/calendar/{year}/{month} - 월별 캘린더
  GET    /api/v1/strength/{id}           - 세션 상세
  POST   /api/v1/strength                - 세션 생성
  PATCH  /api/v1/strength/{id}           - 세션 수정
  DELETE /api/v1/strength/{id}           - 세션 삭제
  POST   /api/v1/strength/{id}/exercises - 운동 추가
  DELETE /api/v1/strength/{id}/exercises/{ex_id} - 운동 삭제

Calendar Notes:
  GET    /api/v1/calendar-notes/types    - 노트 타입 목록
  GET    /api/v1/calendar-notes          - 노트 목록
  GET    /api/v1/calendar-notes/{date}   - 특정 날짜 노트
  POST   /api/v1/calendar-notes          - 노트 생성
  PATCH  /api/v1/calendar-notes/{date}   - 노트 수정
  DELETE /api/v1/calendar-notes/{date}   - 노트 삭제

Races:
  GET    /api/v1/races                   - 대회 목록
  GET    /api/v1/races/upcoming          - 다가오는 대회
  GET    /api/v1/races/garmin/predictions - Garmin 예측 기록
  POST   /api/v1/races/garmin/import     - Garmin 예측 가져오기
  GET    /api/v1/races/{id}              - 대회 상세
  POST   /api/v1/races                   - 대회 생성
  PATCH  /api/v1/races/{id}              - 대회 수정
  DELETE /api/v1/races/{id}              - 대회 삭제
  POST   /api/v1/races/{id}/set-primary  - 주요 대회 설정

Aliases:
  GET    /api/v1/aliases                 - 레거시 경로 목록

Legacy/Alias Support:
  - /sync/garmin/*  → /ingest/*  (deprecated, v2.0에서 제거)
  - /data/*         → /*         (deprecated, v2.0에서 제거)
  - /stats/*        → /dashboard/* (deprecated, v2.0에서 제거)
"""

from fastapi import APIRouter

from app.api.v1.aliases import alias_router
from app.api.v1.endpoints import (
    activities,
    ai,
    analytics,
    auth,
    calendar_notes,
    dashboard,
    gear,
    hr,
    ingest,
    metrics,
    plans,
    races,
    runalyze,
    sleep,
    strava,
    strength,
    workouts,
)

api_router = APIRouter()

# -------------------------------------------------------------------------
# Authentication (includes Garmin/Strava connection)
# -------------------------------------------------------------------------
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# -------------------------------------------------------------------------
# Data Ingestion
# -------------------------------------------------------------------------
api_router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])

# -------------------------------------------------------------------------
# Activities (read-only from Garmin)
# -------------------------------------------------------------------------
api_router.include_router(activities.router, prefix="/activities", tags=["activities"])

# -------------------------------------------------------------------------
# Health Data (separate endpoints per PRD)
# -------------------------------------------------------------------------
api_router.include_router(sleep.router, prefix="/sleep", tags=["sleep"])
api_router.include_router(hr.router, prefix="/hr", tags=["hr"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])

# -------------------------------------------------------------------------
# Dashboard
# -------------------------------------------------------------------------
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])

# -------------------------------------------------------------------------
# Analytics (기간 비교, PR 기록)
# -------------------------------------------------------------------------
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])

# -------------------------------------------------------------------------
# AI Conversations
# -------------------------------------------------------------------------
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])

# -------------------------------------------------------------------------
# Workouts
# -------------------------------------------------------------------------
api_router.include_router(workouts.router, prefix="/workouts", tags=["workouts"])

# -------------------------------------------------------------------------
# Training Plans (v1.0)
# -------------------------------------------------------------------------
api_router.include_router(plans.router, prefix="/plans", tags=["plans"])

# -------------------------------------------------------------------------
# Strava Sync (separate from auth connection)
# -------------------------------------------------------------------------
api_router.include_router(strava.router, prefix="/strava", tags=["strava"])

# -------------------------------------------------------------------------
# Gear Management (shoes, equipment tracking)
# -------------------------------------------------------------------------
api_router.include_router(gear.router, prefix="/gear", tags=["gear"])

# -------------------------------------------------------------------------
# Runalyze Integration (HRV, Sleep metrics)
# -------------------------------------------------------------------------
api_router.include_router(runalyze.router, prefix="/runalyze", tags=["runalyze"])

# -------------------------------------------------------------------------
# Strength Training (보강운동)
# -------------------------------------------------------------------------
api_router.include_router(strength.router, prefix="/strength", tags=["strength"])

# -------------------------------------------------------------------------
# Calendar Notes (personal memos)
# -------------------------------------------------------------------------
api_router.include_router(calendar_notes.router, prefix="/calendar-notes", tags=["calendar-notes"])

# -------------------------------------------------------------------------
# Races (대회 일정)
# -------------------------------------------------------------------------
api_router.include_router(races.router, prefix="/races", tags=["races"])

# -------------------------------------------------------------------------
# Legacy/Alias Routes (backward compatibility)
# -------------------------------------------------------------------------
api_router.include_router(alias_router, tags=["aliases"])
