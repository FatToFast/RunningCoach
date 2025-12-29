"""API v1 router aggregating all endpoint routers.

Routes are organized to match PRD.md and MVP.md specifications:

Authentication:
  /api/v1/auth/login, /logout, /me
  /api/v1/auth/garmin/* (connect, refresh, disconnect, status)
  /api/v1/auth/strava/* (connect, callback, refresh, status)

Data Ingestion:
  /api/v1/ingest/run, /status, /history

Activities:
  /api/v1/activities (list, detail, samples, fit)

Health Data:
  /api/v1/sleep (list, by date)
  /api/v1/hr (list, summary)
  /api/v1/metrics (summary, body, fitness)

Dashboard:
  /api/v1/dashboard/summary, /trends, /calendar

Analytics:
  /api/v1/analytics/compare - 기간 비교 분석
  /api/v1/analytics/personal-records - 개인 최고 기록 (PR)

AI:
  /api/v1/ai/chat, /conversations, /import, /export

Workouts:
  /api/v1/workouts (CRUD, push, schedule)

Plans (v1.0):
  /api/v1/plans (CRUD, approve, sync)

Strava Sync:
  /api/v1/strava/sync/run, /status
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    activities,
    ai,
    analytics,
    auth,
    dashboard,
    hr,
    ingest,
    metrics,
    plans,
    sleep,
    strava,
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
