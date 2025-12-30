# RunningCoach Blueprint

## Goals
- Ingest all accessible Garmin data into a local DB (Runalyze+ coverage).
- Download/parse FIT per activity and store samples.
- Build a dashboard for insights and monitoring.
- Generate training plans using OpenAI with interactive chat + guideline grounding.
- Push plans to Garmin as workouts and scheduled sessions.
- Auto-sync activities to Strava.

## Scope and Constraints
- Primary user is single; small group expansion later.
- Backend in Python.
- Frontend framework is open.
- Deployed on NAS with Docker Compose.
- Garmin integration is unofficial; expect occasional breakage and 2FA flows.
- Default UI language is Korean; sources can be Korean + English.

## Garmin Integration Strategy
- Primary library: `garminconnect` (best coverage + maintenance).
- Abstraction layer: wrap all Garmin calls in a thin adapter so it can be swapped.
- POC checklist:
  1) Login + session refresh/2FA handling.
  2) Fetch core datasets (activities, health, sleep, HR, body metrics).
  3) Initial full-history backfill (all available).
  4) Download/parse FIT per activity; store samples.
  5) Create a workout.
  6) Schedule a workout on a date.
  7) Update and delete a scheduled workout.
- Failure handling:
  - Retry with exponential backoff.
  - Persist failed jobs to a queue for re-run.
  - Alert on repeated auth failures.
  - Rate-limit protection with jitter + concurrency cap.

## High-Level Architecture
- API Service (FastAPI)
- Worker Service (Celery/Redis) for ingestion and sync jobs
- Scheduler (Celery Beat or APScheduler)
- DB (Postgres + TimescaleDB)
- Object Storage (raw JSON + FIT files)
- Frontend (Next.js/SvelteKit/Nuxt)
- OpenAI API (interactive planning)
- Strava API (auto sync)

## Data Flow
1) Garmin -> Ingestion Adapter -> Raw tables (JSON + FIT metadata)
2) Initial full backfill -> Samples -> Normalized tables -> Analytics tables
3) Dashboard reads Analytics tables
4) AI Planning (OpenAI) reads profile + analytics + guidelines -> plan tables
5) Garmin Sync reads plan tables -> Garmin workouts/schedules
6) Strava Sync uploads activities -> Strava

## Data Model (Draft)
Core tables (all with `user_id`, `created_at`, `updated_at`):
- `users`: email, password_hash, display_name, timezone, last_login_at
- `garmin_sessions`: access_token, refresh_token, expires_at, last_login
- `ingestion_state`: last_sync_at, last_success_at, last_error
- `activities`: garmin_id, type, start_time, duration, distance, calories
- `garmin_raw_files`: activity_id, file_path, file_hash, file_type
- `activity_samples`: activity_id, timestamp, hr, pace, cadence, power, lat, lng, alt
- `sleep`: date, duration, score, stages_json
- `health_metrics`: metric_type, metric_time, value, unit, payload_json
- `hr_records`: start_time, end_time, avg_hr, max_hr, resting_hr
- `activity_metrics`: trimp, tss, training_effect, vo2max_est, efficiency_factor
- `fitness_metrics_daily`: date, ctl, atl, tsb
- `plans`: start_date, end_date, goal, status
- `plan_weeks`: plan_id, week_index, notes
- `workouts`: plan_week_id, name, type, structure_json, target_json
- `workout_schedule`: workout_id, scheduled_date, status, garmin_workout_id
- `ai_conversations`: title, language, model
- `ai_messages`: conversation_id, role, content, tokens
- `ai_imports`: source, payload_json
- `strava_sessions`: access_token, refresh_token, expires_at
- `strava_activity_map`: activity_id, strava_activity_id, uploaded_at
- `sync_jobs`: type, payload_json, status, error, attempts

Raw storage:
- `garmin_raw_events`: endpoint, fetched_at, payload_json
- `garmin_raw_files`: activity_id, file_path, file_hash, file_type

## API Design (Draft)
Auth and Users:
- `POST /api/v1/auth/login` (local admin login)
- `POST /api/v1/auth/garmin/connect` (store Garmin creds or token)
- `POST /api/v1/auth/garmin/refresh`
- `GET /api/v1/auth/me`

Strava (OAuth + Sync):
- `GET /api/v1/strava/connect` (OAuth start)
- `POST /api/v1/strava/callback` (OAuth callback)
- `POST /api/v1/strava/refresh`
- `GET /api/v1/strava/status`

Garmin Data:
- `POST /api/v1/ingest/run` (manual sync)
- `GET /api/v1/ingest/status`
- `GET /api/v1/activities`
- `GET /api/v1/activities/{id}`
- `GET /api/v1/activities/{id}/samples`
- `GET /api/v1/activities/{id}/fit`
- `GET /api/v1/sleep`
- `GET /api/v1/hr`
- `GET /api/v1/metrics` (all available metrics)

Plans and Workouts:
- `POST /api/v1/ai/chat` (interactive plan)
- `GET /api/v1/ai/conversations/{id}`
- `POST /api/v1/ai/import` (manual plan import)
- `GET /api/v1/ai/export` (ChatGPT summary export)
- `POST /api/v1/plans/generate` (AI plan draft)
- `GET /api/v1/plans/{id}`
- `POST /api/v1/plans/{id}/approve`
- `POST /api/v1/workouts/{id}/push` (send to Garmin)
- `POST /api/v1/workouts/{id}/schedule`
- `PATCH /api/v1/workouts/{id}` (manual edits)

Dashboard:
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/dashboard/trends`
- `GET /api/v1/dashboard/calendar`

Strava:
- `POST /api/v1/strava/sync/run`
- `GET /api/v1/strava/sync/status`

## AI Planning Pipeline
- Guidelines ingestion:
  - Chunk text, embed, store in `pgvector`.
  - Retrieve top-k chunks by goal/timeframe.
- English + Korean sources supported (language metadata stored).
- Safety constraints:
  - Weekly volume increase cap.
  - Deload weeks.
  - Recovery days after hard sessions.
  - Injury risk flags if data indicates fatigue.
- Output:
  - Structured plan JSON with workout templates and targets.
  - Interactive chat logs stored for audit/replay.
  - Human approval required before Garmin sync.
- Model usage:
  - OpenAI API with budget cap + token logging.
  - Baseline features derived from full history.
  - History summarization: recent 6w + 12w trend + lifetime summary.
- Manual import option: accept JSON plan from external chat (e.g., ChatGPT UI).
- Export option: provide a copyable summary block for ChatGPT analysis.

## Frontend Options (Quick Comparison)
- Next.js (React)
  - Pros: large ecosystem, charting libs, stable SSR.
  - Cons: more boilerplate for simple dashboards.
- SvelteKit
  - Pros: fast iteration, simple state handling, great performance.
  - Cons: smaller ecosystem, fewer enterprise patterns.
- Nuxt 3 (Vue)
  - Pros: balanced ecosystem, good DX.
  - Cons: smaller charting community vs React.

Default suggestion: SvelteKit for MVP speed, Next.js if you want long-term ecosystem depth.

## Deployment on NAS
- Docker Compose services:
  - `api`, `worker`, `scheduler`, `db`, `redis`
- Volumes:
  - `db_data`, `raw_payloads`, `fit_data`, `logs`, `backups`
- Backups:
  - Nightly DB dump + NAS snapshot
  - Weekly offsite copy (optional)

## Security and Privacy
- Encrypt Garmin credentials at rest (KMS or libsodium).
- Restrict admin endpoints behind auth.
- Store minimal PII.
- Allow user data export/delete.
- Store AI chat logs with retention controls.
- Minimize sensitive data sent to OpenAI.

## POC Milestones
1) Garmin login + fetch activities/sleep + FIT parse (store raw + normalized).
2) Dashboard basics (activity list + weekly summary + derived metrics).
3) Create/schedule a Garmin workout from a template.
4) AI interactive plan with chat log + approval flow.
5) Manual plan import -> Garmin workout push.
6) Strava auto sync from Garmin activities.
