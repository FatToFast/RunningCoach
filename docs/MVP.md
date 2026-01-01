# RunningCoach MVP (Minimum Viable Product)

## 개요

RunningCoach MVP는 Garmin 데이터 연동과 기본 대시보드 기능을 검증하는 최소 기능 제품입니다.
Runalyze 수준 이상의 데이터 커버리지(FIT 다운로드/파싱 포함), OpenAI 기반 대화형 훈련 계획, Strava 자동 동기화까지 검증합니다.
단일 사용자 기반이지만 지인 공유를 고려해 로컬 로그인 + 서버 세션(HTTP-only 쿠키) 기반 최소 인증을 포함합니다.

---

## MVP 목표

1. **Garmin 연동 검증**: 로그인, 데이터 수집, 워크아웃 생성/스케줄링 가능 여부 확인
2. **Runalyze+ 데이터 커버리지**: FIT 다운로드/파싱 포함, 가능한 모든 지표 수집
3. **데이터 파이프라인 구축**: Raw → Normalized → Analytics 데이터 흐름 검증
4. **대화형 AI 훈련 계획**: OpenAI API 기반 인터랙티브 플래닝 + 수동 import 옵션
5. **기본 대시보드**: 활동 목록 및 주간/월간 요약 시각화
6. **Strava 자동 동기화**: 활동 업로드 자동화 검증
7. **최소 인증**: 로컬 로그인 + 서버 세션(HTTP-only 쿠키)으로 API 접근 보호

---

## MVP 범위

### ✅ 포함 (In Scope)

| 기능 | 설명 | 우선순위 |
|------|------|----------|
| Garmin 로그인 | garminconnect 라이브러리 기반 인증 + 2FA 처리 | P0 |
| 세션 관리 | 토큰 저장, 갱신, 만료 처리 | P0 |
| 최소 인증 | 로컬 계정 로그인 + Redis 세션(HTTP-only 쿠키), 계정 생성은 초기 seed/스크립트 | P0 |
| 활동 데이터 수집 | Activities 목록/상세 + 활동별 FIT 다운로드/파싱 | P0 |
| 활동 샘플 저장 | activity_samples (HR/페이스/케이던스/파워/GPS 등) | P0 |
| 수면 데이터 수집 | Sleep 데이터 fetch | P1 |
| 심박수/HRV 수집 | HR/HRV 데이터 fetch | P1 |
| 건강/피트니스 지표 수집 | Body Battery/Stress/Training Load/Recovery 등 가능한 모든 지표 | P1 |
| Raw 데이터 저장 | JSON 원본 + FIT 파일 저장 | P0 |
| 정규화 저장 | activities, sleep, hr_records, health_metrics 테이블 | P0 |
| 파생 지표 계산 | TRIMP/TSS, ATL/CTL/TSB, 효율지수 등 | P1 |
| 활동 목록 API | GET /api/v1/activities 엔드포인트 | P0 |
| 주간 요약 API | GET /api/v1/dashboard/summary 엔드포인트 | P1 |
| Analytics 집계 | 주간/월간 요약 + 파생 지표 집계 저장 | P1 |
| 기본 대시보드 UI | 활동 리스트 + 주간 통계 카드 | P1 |
| 워크아웃 생성 | Garmin에 워크아웃 템플릿 전송 | P2 |
| 워크아웃 스케줄링 | 특정 날짜에 워크아웃 배치 | P2 |
| AI 훈련 계획 | OpenAI 기반 대화형 플래닝 + 수동 JSON import + 로그 저장 | P1 |
| AI 분석용 요약 복사 | ChatGPT 전달용 요약/프롬프트 생성 | P1 |
| 다국어 자료 지원 | 한국어 UI 기본, 영어 자료 포함 RAG | P1 |
| Strava 자동 동기화 | 활동 자동 업로드/중복 방지 | P1 |

### ❌ 제외 (Out of Scope)

- 셀프 가입/조직형 다중 사용자(멀티테넌시), SSO/MFA
- 모바일 앱
- 알림/푸시 기능
- 백업/복구 자동화
- 고급 예측 모델링(부상 예측, 장기 성능 예측)

---

## 동기화 전략 (권장)

- 초기 백필 범위: 전체 이력(가능한 범위), 필요 시 GARMIN_BACKFILL_DAYS로 제한
- 엔드포인트별 last_success_at 저장 후, 동기화 시 safety window 3일을 두고 재조회해 수정/삭제를 반영
- 목록 → 상세 fetch로 정합성 확보, 상세 미존재 시 soft delete(또는 상태 플래그)
- 활동별 FIT 다운로드/파싱 수행, 파일 해시/경로 저장
- 활동은 garmin_id 기준 UPSERT, 수면은 (user_id, date) 기준 UPSERT
- Raw는 모든 응답 저장, Normalized/Analytics는 idempotent 변환
- 실패 시 재시도(backoff) 및 rate limit 보호
- 기준 타임존은 user timezone (기본 Asia/Seoul)
- 동기화 완료 후 Strava 자동 업로드(연결된 경우)
- 초기 백필 완료 후 AI 상태 추정용 베이스라인 생성
- 전체 백필 정책:
  - 배치 크기: 활동 200~500개 단위 페이지네이션
  - 재시도: 429/5xx는 지수 백오프, 최대 N회 후 큐에 격리
  - 레이트리밋 보호: 요청 간 jitter + 동시성 제한
  - 장기 작업은 체크포인트(cursor/last_success_at)로 이어서 처리

---

## Runalyze+ 데이터 기준 (MVP)

- 활동 요약 + 랩 + 샘플(초 단위)까지 저장
- FIT 기반 원본 보관(활동별 파일 저장) 및 재파싱 가능
- 건강/피트니스 지표는 Garmin에서 제공 가능한 항목 전수 수집
- 과거 전체 이력 포함(가능 범위 내)
- 파생 지표는 Runalyze 수준 이상(TRIMP/TSS, ATL/CTL/TSB, 효율지수 등)

---

## Analytics 정의 (MVP)

- 주간 요약: 사용자 타임존 기준 월요일 시작, 7일 단위
- 월간 요약: 사용자 타임존 기준 매월 1일 시작
- 집계 항목: 총 거리/시간/활동 수/평균 페이스/평균 심박/누적 상승고도
- 파생 지표: TRIMP/TSS, ATL/CTL/TSB, 효율지수, 훈련효과, VO2max 트렌드
- 생성 방식: 동기화 완료 후 재계산 가능하도록 idempotent 집계
- 장기 베이스라인: 최근 6주/12주 기준 피트니스 추정치 생성

---

## AI 훈련 계획 (MVP)

- OpenAI API 기반 대화형 플래닝 (한국어 기본, 영어 자료 포함)
- 대화 로그 저장 및 계획 버전 관리
- 수동 플랜 import: ChatGPT 결과를 JSON으로 붙여넣어 워크아웃/스케줄 생성
- 과거 전체 이력 기반 현재 상태 추정(피로/체력/부하)
- 안전 제약: 주간 볼륨 증가 상한, 회복 주기, 연속 고강도 제한
- 모델/예산 비교 문서화 (토큰 사용량 추정 + 모델별 비용 비교)
- 히스토리 요약/특징화로 토큰 사용량 최적화
- AI 입력 요약 (권장):
  - 기간: 최근 6주 + 12주 추세 + 전체 이력 요약
  - 핵심 피처: 주간 거리/시간, ATL/CTL/TSB, HRV/안정시HR, 수면 점수
  - 활동 분포: 강도 구간, 장거리/인터벌 비중, 휴식일 패턴
  - 최근 부상/컨디션 노트 (사용자 입력)

### 플랜 import JSON 스키마 (초안)

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

규칙:
- 날짜는 ISO-8601 (`YYYY-MM-DD`)
- steps는 `duration_min` 또는 `distance_km` 중 하나 필수
- target은 `target_pace` 또는 `target_hr` 중 하나 사용

### ChatGPT 분석용 요약 포맷 (초안)

```text
PROFILE
- Age: ??, Sex: ??, Goal: ??
- Experience: ?? years, Weekly runs: ??

TRAINING SUMMARY
- Last 6w distance/time: ??
- Last 12w trend: ??
- Lifetime summary: ??

FITNESS METRICS
- CTL/ATL/TSB: ?? / ?? / ??
- HRV/RHR/Sleep score: ?? / ?? / ??
- VO2max trend: ??

WORKOUT DISTRIBUTION
- Easy/Tempo/Interval/Long ratio: ??
- Rest days pattern: ??

CONTEXT
- Injuries/constraints: ??
- Preferences: ??
```

---

## OpenAI 모델/예산 비교 (초안)

| 모델 | 용도 | 비용(USD/1M tokens) |
|------|------|--------------------|
| gpt-4o | 최종 플랜 검토 | TBD |
| gpt-4o-mini | 대화/초안 | TBD |

---

## 기술 스택

### Backend
```
- Python 3.11+
- FastAPI (REST API)
- SQLAlchemy 2.0 (ORM)
- PostgreSQL 15+ (Database)
- pgvector (RAG)
- Redis (캐시/세션)
- garminconnect (Garmin API)
- fitparse 또는 FIT SDK (FIT 파싱)
- OpenAI API (대화형 플랜)
- Strava API (자동 동기화)
```

### Frontend
```
- SvelteKit (MVP 속도 우선)
- TailwindCSS (스타일링)
- Chart.js 또는 Apache ECharts (차트)
```

### Infrastructure
```
- Docker + Docker Compose
- NAS 배포 (Synology/QNAP)
- FIT/Raw 파일 스토리지 (NAS 볼륨)
```

---

## MVP 마일스톤

### Phase 1: Garmin 연동 POC (1주)

**목표**: Garmin 로그인 및 데이터 수집 검증

- [ ] garminconnect 라이브러리 설정
- [ ] 로그인 + 2FA 처리 구현
- [ ] 세션 저장/갱신 로직
- [ ] Activities 데이터 fetch 테스트
- [ ] Sleep 데이터 fetch 테스트
- [ ] Raw JSON 저장 구현
- [ ] 활동별 FIT 다운로드/파싱 테스트
- [ ] 건강/피트니스 지표 엔드포인트 탐색 및 fetch 테스트

**완료 기준**: CLI에서 Garmin 로그인 후 최근 7일 활동 데이터 + FIT 파싱 결과 출력

### Phase 2: 데이터 파이프라인 (1주)

**목표**: DB 스키마 구축 및 데이터 정규화

- [ ] PostgreSQL + Docker 설정
- [ ] SQLAlchemy 모델 정의
- [ ] Raw → Normalized 변환 로직
- [ ] Ingestion 서비스 구현
- [ ] 동기화 상태 저장/업데이트 (garmin_sync_state)
- [ ] FIT 파일 저장 + activity_samples 파싱/적재
- [ ] health_metrics 저장 (가능한 모든 지표)
- [ ] 파생 지표 계산(활동/일간)
- [ ] 전체 이력 백필 실행 및 검증
- [ ] Analytics 집계(주/월) 생성 로직
- [ ] 수동 동기화 API (POST /api/v1/ingest/run)

**완료 기준**: Garmin 데이터가 DB에 정규화되어 저장되며 주간/월간 요약 + 파생 지표가 생성되고 초기 전체 백필이 완료됨

### Phase 3: REST API (1주)

**목표**: 프론트엔드용 API 구축

- [ ] FastAPI 프로젝트 구조 설정
- [ ] 최소 인증 (로컬 로그인 + Redis 세션/HTTP-only 쿠키)
- [ ] 초기 계정 생성(환경변수/스크립트)
- [ ] 인증 미들웨어 (보호 엔드포인트)
- [ ] GET /api/v1/activities 엔드포인트
- [ ] GET /api/v1/activities/{id} 엔드포인트
- [ ] GET /api/v1/activities/{id}/samples 엔드포인트
- [ ] GET /api/v1/sleep 엔드포인트
- [ ] GET /api/v1/metrics 엔드포인트
- [ ] GET /api/v1/dashboard/summary 엔드포인트
- [ ] API 문서화 (OpenAPI)

**완료 기준**: Swagger UI에서 인증 포함해 모든 API 테스트 가능

### Phase 4: 기본 대시보드 (1주)

**목표**: 데이터 시각화 UI

- [ ] SvelteKit 프로젝트 설정
- [ ] 활동 목록 페이지
- [ ] 활동 상세 페이지
- [ ] 주간 요약 카드
- [ ] 기본 차트 (주간 거리, 시간)
- [ ] 파생 지표 카드 (TRIMP/TSS/CTL/ATL)

**완료 기준**: 웹에서 최근 활동 목록과 주간 통계 및 파생 지표 확인 가능

### Phase 5: Garmin 워크아웃 연동 (1주)

**목표**: 워크아웃 생성/스케줄링 검증

- [ ] 워크아웃 템플릿 구조 정의
- [ ] Garmin 워크아웃 생성 API 연동
- [ ] 워크아웃 스케줄링 API 연동
- [ ] POST /api/v1/workouts/{id}/push 엔드포인트
- [ ] POST /api/v1/workouts/{id}/schedule 엔드포인트

**완료 기준**: 웹에서 생성한 워크아웃이 Garmin Connect 앱에 표시됨

### Phase 6: 대화형 AI 훈련 계획 (1주)

**목표**: OpenAI API 기반 대화형 플래닝

- [ ] 대화 세션/메시지 저장 (ai_conversations, ai_messages)
- [ ] 한국어 기본 응답 + 영어 자료 RAG 연동
- [ ] 계획 생성/수정 대화 플로우
- [ ] 수동 플랜 import 엔드포인트 + 스키마 문서화
- [ ] ChatGPT 분석용 요약 export + 복사 버튼
- [ ] 모델/예산 비교 문서화 및 토큰 로깅

**완료 기준**: 대화형으로 생성한 계획이 워크아웃 템플릿으로 변환됨

### Phase 7: Strava 자동 동기화 (1주)

**목표**: 활동 자동 업로드 및 중복 방지

- [ ] Strava OAuth 연동
- [ ] 활동 업로드 자동화 (FIT/TCX)
- [ ] Garmin ↔ Strava 매핑 및 중복 방지
- [ ] 동기화 상태/실패 기록

**완료 기준**: 신규 활동이 자동으로 Strava에 업로드됨

---

## MVP 데이터 모델 (최소)

```sql
-- 사용자 (MVP는 기본 단일 사용자, 소수 계정 허용)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name VARCHAR(100),
    timezone VARCHAR(50) DEFAULT 'Asia/Seoul',
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Garmin 세션
CREATE TABLE garmin_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    oauth1_token TEXT,
    oauth2_token TEXT,
    expires_at TIMESTAMPTZ,
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 동기화 상태
CREATE TABLE garmin_sync_state (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    endpoint VARCHAR(100) NOT NULL,
    last_sync_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    cursor TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, endpoint)
);

-- Raw 이벤트 (JSON 원본)
CREATE TABLE garmin_raw_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    endpoint VARCHAR(100) NOT NULL,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    payload JSONB NOT NULL
);

-- 활동
CREATE TABLE activities (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    garmin_id BIGINT UNIQUE NOT NULL,
    activity_type VARCHAR(50),
    start_time TIMESTAMPTZ NOT NULL,
    duration_seconds INTEGER,
    distance_meters REAL,
    calories INTEGER,
    avg_hr INTEGER,
    max_hr INTEGER,
    avg_pace_seconds INTEGER,
    elevation_gain REAL,
    raw_event_id INTEGER REFERENCES garmin_raw_events(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 활동 FIT 파일
CREATE TABLE garmin_raw_files (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    activity_id INTEGER REFERENCES activities(id),
    file_type VARCHAR(20) DEFAULT 'fit',
    file_path TEXT NOT NULL,
    file_hash VARCHAR(64),
    fetched_at TIMESTAMPTZ DEFAULT NOW()
);

-- 활동 샘플 (초 단위)
CREATE TABLE activity_samples (
    id SERIAL PRIMARY KEY,
    activity_id INTEGER REFERENCES activities(id),
    timestamp TIMESTAMPTZ NOT NULL,
    hr INTEGER,
    pace_seconds INTEGER,
    cadence INTEGER,
    power INTEGER,
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    altitude REAL
);

-- 수면
CREATE TABLE sleep (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    date DATE NOT NULL,
    duration_seconds INTEGER,
    score INTEGER,
    stages JSONB,
    raw_event_id INTEGER REFERENCES garmin_raw_events(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, date)
);

-- 심박수
CREATE TABLE hr_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    avg_hr INTEGER,
    max_hr INTEGER,
    resting_hr INTEGER,
    samples JSONB,
    raw_event_id INTEGER REFERENCES garmin_raw_events(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 건강/피트니스 지표 (Garmin 제공 가능한 항목 전수)
CREATE TABLE health_metrics (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    metric_type VARCHAR(50) NOT NULL,
    metric_time TIMESTAMPTZ NOT NULL,
    value NUMERIC,
    unit VARCHAR(20),
    payload JSONB,
    raw_event_id INTEGER REFERENCES garmin_raw_events(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 활동 파생 지표 (Runalyze 수준 이상)
CREATE TABLE activity_metrics (
    id SERIAL PRIMARY KEY,
    activity_id INTEGER REFERENCES activities(id),
    trimp REAL,
    tss REAL,
    training_effect REAL,
    vo2max_est REAL,
    efficiency_factor REAL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 일별 피트니스 지표
CREATE TABLE fitness_metrics_daily (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    date DATE NOT NULL,
    ctl REAL,
    atl REAL,
    tsb REAL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, date)
);

-- Analytics 요약 (주/월)
CREATE TABLE analytics_summaries (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    period_type VARCHAR(10) NOT NULL, -- 'week' or 'month'
    period_start DATE NOT NULL,
    total_distance_meters REAL,
    total_duration_seconds INTEGER,
    total_activities INTEGER,
    avg_pace_seconds INTEGER,
    avg_hr INTEGER,
    elevation_gain REAL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, period_type, period_start)
);

-- 워크아웃
CREATE TABLE workouts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    name VARCHAR(200) NOT NULL,
    workout_type VARCHAR(50),
    structure JSONB,
    garmin_workout_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 워크아웃 스케줄
CREATE TABLE workout_schedules (
    id SERIAL PRIMARY KEY,
    workout_id INTEGER REFERENCES workouts(id),
    scheduled_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'scheduled',
    garmin_schedule_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- AI 대화 세션
CREATE TABLE ai_conversations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    title VARCHAR(200),
    language VARCHAR(10) DEFAULT 'ko',
    model VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- AI 대화 메시지
CREATE TABLE ai_messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES ai_conversations(id),
    role VARCHAR(20) NOT NULL, -- 'user' or 'assistant'
    content TEXT NOT NULL,
    tokens INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- AI 플랜 import
CREATE TABLE ai_imports (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    source VARCHAR(50) DEFAULT 'manual',
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Strava 세션
CREATE TABLE strava_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    access_token TEXT,
    refresh_token TEXT,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Strava 동기화 상태
CREATE TABLE strava_sync_state (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    last_sync_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Garmin ↔ Strava 매핑
CREATE TABLE strava_activity_map (
    id SERIAL PRIMARY KEY,
    activity_id INTEGER REFERENCES activities(id),
    strava_activity_id BIGINT,
    uploaded_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(activity_id)
);
```

---

## MVP API 명세 (최소)

### 인증
세션은 HTTP-only 쿠키로 전달

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | /api/v1/auth/login | 로컬 로그인 |
| POST | /api/v1/auth/logout | 로그아웃 |
| GET | /api/v1/auth/me | 현재 사용자 |
| POST | /api/v1/auth/garmin/connect | Garmin 계정 연결 (2FA 미지원, 수동 재연결 필요) |
| GET | /api/v1/auth/garmin/status | Garmin 연결 상태 조회 |
| POST | /api/v1/auth/garmin/refresh | Garmin 세션 갱신 |
| DELETE | /api/v1/auth/garmin/disconnect | Garmin 연결 해제 |
| GET | /api/v1/strava/connect | Strava OAuth 시작 (auth_url 반환) |
| GET | /api/v1/strava/callback | Strava OAuth 콜백 |
| GET | /api/v1/strava/status | Strava 연결 상태 |

### 데이터 수집
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | /api/v1/ingest/run | 수동 동기화 실행 (백그라운드) |
| POST | /api/v1/ingest/run/sync | 동기화 실행 (블로킹, 테스트용) |
| GET | /api/v1/ingest/status | 동기화 상태 조회 |
| GET | /api/v1/ingest/history | 동기화 이력 조회 (페이지네이션) |

### 활동
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | /api/v1/activities | 활동 목록 (페이지네이션) |
| GET | /api/v1/activities/{id} | 활동 상세 |
| GET | /api/v1/activities/{id}/samples | 활동 샘플 |
| GET | /api/v1/activities/{id}/fit | FIT 파일 다운로드 |

### 수면
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | /api/v1/sleep | 수면 기록 목록 |

### 심박수
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | /api/v1/hr | 심박/HRV 기록 목록 |

### 건강/피트니스 지표
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | /api/v1/metrics | 가능한 모든 지표 목록 |

### 대시보드
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | /api/v1/dashboard/summary | 주간/월간 요약 (analytics_summaries 기반) |

### AI 플래닝
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | /api/v1/ai/chat | 대화형 계획 생성/수정 |
| GET | /api/v1/ai/conversations/{id} | 대화 로그 조회 |
| POST | /api/v1/ai/import | 수동 플랜 JSON import |
| GET | /api/v1/ai/export | ChatGPT 분석용 요약 생성 |

### 워크아웃
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | /api/v1/workouts | 워크아웃 생성 |
| GET | /api/v1/workouts/{id} | 워크아웃 조회 |
| POST | /api/v1/workouts/{id}/push | Garmin에 전송 |
| POST | /api/v1/workouts/{id}/schedule | 날짜 스케줄링 |

### Strava 동기화
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | /api/v1/strava/sync/run | Strava 수동 동기화 |
| GET | /api/v1/strava/sync/status | Strava 동기화 상태 |

---

## 성공 기준

### 기능적 기준
- [ ] Garmin 로그인 성공률 > 95%
- [ ] 로컬 로그인 성공률 > 95%
- [ ] 데이터 동기화 지연 < 5분
- [ ] 활동별 FIT 파싱 성공률 > 95%
- [ ] Runalyze 수준 파생 지표 계산 성공률 > 90%
- [ ] API 응답 시간 < 500ms (p95)
- [ ] 워크아웃 Garmin 전송 성공률 > 90%
- [ ] 주간/월간 요약 집계 생성 및 갱신 정상
- [ ] AI 대화형 계획 생성 성공률 > 90%
- [ ] 수동 플랜 import 성공률 > 95%
- [ ] ChatGPT 분석용 요약 export 가능
- [ ] Strava 자동 업로드 성공률 > 90%
- [ ] 초기 전체 백필 완료

### 비기능적 기준
- [ ] Docker Compose로 단일 명령 배포 가능
- [ ] API 문서 자동 생성 (OpenAPI)
- [ ] 기본 에러 로깅 구현
- [ ] OpenAI 비용/토큰 사용량 로깅

---

## 리스크 및 완화 방안

| 리스크 | 영향 | 완화 방안 |
|--------|------|-----------|
| Garmin API 비공식 | 갑작스런 차단 가능 | 추상화 레이어로 라이브러리 교체 용이하게 |
| 2FA 처리 복잡성 | UX 저하 | 세션 캐시 최대화, 수동 재인증 플로우 |
| 데이터 스키마 변경 | 마이그레이션 비용 | Raw JSON 저장으로 원본 보존 |
| 로컬 인증 보안 | 계정 공유/취약 비밀번호 | 강한 비밀번호 정책 + Argon2/bcrypt + HTTPS + 세션 만료 |
| FIT 파일 용량 | 스토리지/성능 부담 | NAS 볼륨 분리 + 압축/보관 정책 |
| LLM 비용/환각 | 운영비 증가, 계획 품질 저하 | 모델 선택/예산 제한 + 휴먼 승인 |
| Strava API 제한 | 동기화 실패 | 레이트리밋 대응 + 재시도/큐 |

---

## 다음 단계 (Post-MVP)

1. **고급 예측/코칭**: 부상 위험/성과 예측, 자동 조정
2. **자동 동기화 고도화**: 스케줄러/큐 안정화
3. **다중 사용자**: 인증/인가 시스템
4. **모바일 최적화**: PWA 또는 네이티브 앱
5. **데이터 보관 정책**: 장기 보관/백업 자동화
