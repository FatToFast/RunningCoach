# RunningCoach 아키텍처

시스템 아키텍처 및 구성 요소 설명입니다.

---

## 시스템 개요

```
┌─────────────────────────────────────────────────────────────────────┐
│                           사용자                                     │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │  Pages   │ │Components│ │  Hooks   │ │API Client│              │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │ HTTP (REST API)
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │   API    │ │ Services │ │ Adapters │ │Knowledge │              │
│  │Endpoints │ │ (Logic)  │ │(External)│ │  (RAG)   │              │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
└───────┬─────────────┬─────────────┬─────────────┬───────────────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐
│PostgreSQL │ │   Redis   │ │  Garmin   │ │ Google AI │
│TimescaleDB│ │  Session  │ │  Strava   │ │  OpenAI   │
│           │ │  + Queue  │ │  Runalyze │ │   FAISS   │
└───────────┘ └───────────┘ └───────────┘ └───────────┘
```

---

## 컴포넌트 상세

### Frontend

**기술 스택**: React 19, TypeScript, Vite 7, Tailwind CSS 4

```
frontend/src/
├── pages/          # 라우트별 페이지 컴포넌트
├── components/     # 재사용 UI 컴포넌트
│   ├── layout/     # Header, Sidebar, Layout
│   ├── dashboard/  # 대시보드 위젯
│   └── activity/   # 활동 관련 (Map, Chart)
├── hooks/          # React Query 커스텀 훅
├── api/            # Axios API 클라이언트
├── types/          # TypeScript 타입 정의
└── utils/          # 유틸리티 함수
```

**데이터 흐름**:
```
User Action → Hook (useQuery/useMutation) → API Client → Backend
     ↑                    ↓
     └──── UI Update ←── Cache Update
```

### Backend

**기술 스택**: FastAPI, SQLAlchemy 2.0, asyncpg, Redis

```
backend/app/
├── api/v1/         # REST API 엔드포인트
│   ├── router.py   # 메인 라우터
│   └── endpoints/  # 개별 엔드포인트 모듈
├── models/         # SQLAlchemy ORM 모델
├── schemas/        # Pydantic 스키마
├── services/       # 비즈니스 로직
├── adapters/       # 외부 서비스 어댑터
├── knowledge/      # RAG 시스템
├── workers/        # Arq 비동기 워커
└── core/           # 설정, 보안, DB
```

**요청 처리 흐름**:
```
HTTP Request
     ↓
FastAPI Router (endpoints/)
     ↓
Pydantic Validation (schemas/)
     ↓
Service Layer (services/)
     ↓
Repository (models/ + SQLAlchemy)
     ↓
Database (PostgreSQL)
```

---

## 데이터베이스

### PostgreSQL + TimescaleDB

**주요 테이블**:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    users    │────<│  activities │────<│    laps     │
└─────────────┘     └─────────────┘     └─────────────┘
      │                   │
      │                   └────<┌─────────────────┐
      │                         │ activity_samples│ (TimescaleDB)
      │                         └─────────────────┘
      │
      ├────<┌─────────────┐     ┌─────────────┐
      │     │  workouts   │────<│workout_steps│
      │     └─────────────┘     └─────────────┘
      │
      ├────<┌─────────────────┐     ┌─────────────┐
      │     │ai_conversations │────<│ ai_messages │
      │     └─────────────────┘     └─────────────┘
      │
      ├────<┌─────────────┐
      │     │    gear     │
      │     └─────────────┘
      │
      ├────<┌─────────────┐
      │     │    races    │
      │     └─────────────┘
      │
      └────<┌───────────────────┐
            │ sleep/hr/health   │
            └───────────────────┘
```

### Redis

**용도**:
- 세션 저장 (HTTP-only 쿠키 기반)
- 동기화 락 (분산 락)
- 작업 큐 (Arq)
- 캐싱 (대시보드 데이터)

```
redis/
├── sessions:*      # 사용자 세션
├── sync_lock:*     # Garmin 동기화 락
├── arq:*           # 작업 큐 (Strava 업로드)
└── cache:*         # 임시 캐시
```

---

## 외부 연동

### Garmin Connect

```
GarminAdapter (adapters/garmin_adapter.py)
     │
     ├── authenticate()      # 로그인
     ├── get_activities()    # 활동 목록
     ├── get_activity_fit()  # FIT 파일 다운로드
     ├── get_sleep_data()    # 수면 데이터
     ├── get_hr_data()       # 심박 데이터
     └── push_workout()      # 워크아웃 전송
```

### Strava API

```
StravaUploadService (services/strava_upload.py)
     │
     ├── OAuth2 인증        # 토큰 관리
     ├── upload_activity()  # 활동 업로드
     └── retry_queue        # 실패 시 재시도 (Arq)
```

### AI 서비스

```
AI Integration
     │
     ├── Google Gemini (Primary)
     │   └── gemini-2.5-flash-lite
     │
     ├── OpenAI (Fallback)
     │   └── gpt-4o-mini
     │
     └── RAG System (knowledge/)
         ├── embeddings.py  # Google Embeddings
         ├── retriever.py   # FAISS 검색
         └── loader.py      # 문서 로더
```

---

## 인증 흐름

```
┌──────────┐      ┌──────────┐      ┌──────────┐
│  Client  │      │  Server  │      │  Redis   │
└────┬─────┘      └────┬─────┘      └────┬─────┘
     │                 │                 │
     │ POST /auth/login                  │
     │ {email, password}                 │
     │─────────────────>                 │
     │                 │                 │
     │                 │ SET session:uuid│
     │                 │─────────────────>
     │                 │                 │
     │ Set-Cookie: session_id=uuid       │
     │<─────────────────                 │
     │                 │                 │
     │ GET /api/v1/me                    │
     │ Cookie: session_id=uuid           │
     │─────────────────>                 │
     │                 │ GET session:uuid│
     │                 │─────────────────>
     │                 │     user_data   │
     │                 │<─────────────────
     │ {user}          │                 │
     │<─────────────────                 │
```

---

## 데이터 동기화

### Garmin Sync Flow

```
사용자 요청
     │
     ▼
┌─────────────────┐
│ acquire_lock()  │ ← Redis 분산 락
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ get_activities()│ ← Garmin API
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ parse_fit_file()│ ← fitparse
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ save_to_db()    │ ← PostgreSQL
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ release_lock()  │
└─────────────────┘
```

---

## 성능 고려사항

### TimescaleDB

활동 샘플 데이터 (초당 데이터)는 TimescaleDB hypertable 사용:
- 자동 시간 기반 파티셔닝
- 효율적인 시계열 쿼리
- 압축을 통한 저장 공간 절약

### 캐싱 전략

```python
# 대시보드 요약 캐싱
@cached(ttl=300)  # 5분
async def get_dashboard_summary(user_id: int):
    ...
```

### 비동기 처리

```python
# Strava 업로드는 백그라운드 작업으로 처리
async def upload_to_strava(activity_id: int):
    await arq_queue.enqueue_job(
        "strava_upload",
        activity_id,
        _defer_by=timedelta(seconds=1),
    )
```

---

## 배포 구조

### Docker Compose (개발)

```yaml
services:
  db:
    image: timescale/timescaledb:latest-pg15
    ports: ["5432:5432"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  api:
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [db, redis]
```

### 프로덕션 권장

```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer (Nginx)                    │
└─────────────────────────────┬───────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │  API #1  │   │  API #2  │   │  API #3  │
        └──────────┘   └──────────┘   └──────────┘
              │               │               │
              └───────────────┼───────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │PostgreSQL│   │  Redis   │   │  Worker  │
        │ Primary  │   │ Cluster  │   │  (Arq)   │
        └──────────┘   └──────────┘   └──────────┘
```

---

## 보안

### 인증
- HTTP-only 쿠키 기반 세션
- Secure, SameSite 플래그 설정
- CSRF 토큰 (향후 구현)

### 데이터 암호화
- Garmin 자격 증명: Fernet 암호화
- 비밀번호: bcrypt 해싱
- 환경 변수: 민감 정보 저장

### API 보안
- CORS 설정 (허용된 origin만)
- Rate limiting (향후 구현)
- 입력 유효성 검사 (Pydantic)

---

*최종 업데이트: 2026-01-07*
