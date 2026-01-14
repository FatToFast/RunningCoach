# CLAUDE.md - RunningCoach Project Guide

AI 기반 러닝 코치 앱 프로젝트를 위한 Claude Code 가이드입니다.

## 프로젝트 개요

RunningCoach는 Garmin Connect와 연동하여 개인화된 AI 트레이닝 플랜을 제공하는 러닝 코치 애플리케이션입니다.

**핵심 기능:**
- Garmin/Strava 활동 데이터 동기화
- AI 기반 훈련 계획 생성 (Google Gemini + RAG)
- VDOT 기반 훈련 페이스 계산
- 피트니스 지표 분석 (CTL/ATL/TSB)
- 워크아웃 생성 및 Garmin 푸시

---

## 필수 규칙

### 1. 근본 원인 해결 (Root Cause Fix)

**증상이 아닌 원인을 수정합니다:**

- ❌ 워크어라운드, 임시 패치, 증상 억제
- ✅ 문제의 근본 원인을 파악하고 해결

```python
# ❌ 잘못된 접근: 에러 무시
try:
    result = risky_operation()
except Exception:
    pass  # 왜 실패하는지 모름

# ✅ 올바른 접근: 원인 파악 및 해결
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    # 실패 원인에 따른 적절한 처리
    raise
```

**디버깅 프로세스:**
1. 에러 메시지/스택 트레이스 확인
2. 재현 조건 파악
3. 근본 원인 식별
4. 원인 해결 (증상 아님)
5. 재발 방지책 적용

### 2. 디버그 패턴 기록 (MUST)

**버그를 수정할 때마다 반드시 [docs/debug-patterns.md](docs/debug-patterns.md)에 기록합니다.**

이 문서는 프로젝트의 학습된 지식입니다. 같은 실수를 반복하지 않도록 모든 버그 패턴을 기록하세요.

**기록 형식:**

```markdown
### N. [버그 제목]

**문제**: [간단한 설명 - 왜 발생했는지 근본 원인 포함]

\`\`\`typescript
// ❌ 잘못된 패턴
[버그를 유발한 코드]

// ✅ 올바른 패턴
[수정된 코드]
\`\`\`

**적용 위치**: `파일명`, `함수명`
**날짜**: YYYY-MM-DD
```

**기록해야 하는 경우:**
- 버그 수정 후
- 성능 문제 해결 후
- 타입/스키마 불일치 수정 후
- 보안 취약점 패치 후
- 비동기/동시성 이슈 해결 후

**기록하지 않아도 되는 경우:**
- 단순 오타 수정
- import 정리
- 린터 경고 수정

### 3. 코드 수정 전 확인사항

버그 수정 또는 기능 추가 시:

1. **debug-patterns.md 확인**: 유사한 패턴이 이미 기록되어 있는지 확인
2. **근본 원인 파악**: "왜?"를 최소 3번 질문
3. **영향 범위 확인**: 수정이 다른 부분에 미치는 영향
4. **테스트 가능 여부**: 수정 후 검증 방법

---

## 프로젝트 구조

```
RunningCoach/
├── backend/                    # FastAPI 백엔드 (Python 3.11+)
│   ├── app/
│   │   ├── api/v1/            # API 엔드포인트
│   │   │   ├── router.py      # 메인 라우터
│   │   │   └── endpoints/     # 20+ 엔드포인트 모듈
│   │   ├── adapters/          # 외부 서비스 어댑터
│   │   │   └── garmin_adapter.py  # Garmin Connect 연동
│   │   ├── core/              # 설정, 보안, 세션
│   │   │   ├── config.py      # Pydantic Settings
│   │   │   ├── database.py    # SQLAlchemy async
│   │   │   ├── security.py    # 인증/암호화
│   │   │   ├── session.py     # Redis 세션
│   │   │   └── ai_constants.py # AI 시스템 프롬프트
│   │   ├── models/            # SQLAlchemy 모델 (16개)
│   │   ├── schemas/           # Pydantic 스키마
│   │   ├── services/          # 비즈니스 로직
│   │   │   ├── sync_service.py    # Garmin 동기화 (1,947줄)
│   │   │   ├── dashboard.py       # 대시보드 분석 (1,701줄)
│   │   │   ├── vdot.py           # VDOT 계산
│   │   │   ├── strava_upload.py  # Strava 업로드 큐
│   │   │   └── ai_snapshot.py    # AI 스냅샷
│   │   ├── knowledge/         # RAG 지식베이스
│   │   │   ├── embeddings.py  # Google Embeddings
│   │   │   ├── retriever.py   # 문서 검색
│   │   │   └── loader.py      # 문서 로더
│   │   └── workers/           # Arq 비동기 워커
│   ├── alembic/               # DB 마이그레이션 (15+ 버전)
│   ├── scripts/               # 유틸리티 스크립트
│   │   ├── check_schema.py    # 스키마 검증/수정
│   │   └── build_knowledge_index.py
│   └── .venv/                 # Python 가상환경
├── frontend/                   # React + TypeScript + Vite
│   └── src/
│       ├── api/               # API 클라이언트 (13개 모듈)
│       │   └── client.ts      # Axios 인스턴스
│       ├── components/        # 재사용 컴포넌트
│       │   ├── layout/        # Header, Sidebar, Layout
│       │   ├── dashboard/     # 대시보드 위젯
│       │   └── activity/      # 활동 관련 (Map, Chart)
│       ├── hooks/             # React Query hooks (11개)
│       ├── pages/             # 페이지 컴포넌트 (13개)
│       ├── types/             # TypeScript 타입
│       │   └── generated/     # OpenAPI 자동 생성
│       └── utils/             # 유틸리티 함수
├── docs/                       # 문서
│   ├── debug-patterns.md      # 버그 패턴 (58개 문서화)
│   ├── api-reference.md       # API 상세 문서
│   ├── PRD.md                 # 제품 요구사항
│   └── CHANGELOG.md           # 변경 이력
└── docker-compose.yml          # 로컬 개발 환경
```

---

## 기술 스택

### Backend
- **Framework**: FastAPI + Uvicorn
- **Database**: PostgreSQL + TimescaleDB (asyncpg)
- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **Cache/Session**: Redis + arq (task queue)
- **AI**: Google Gemini (primary), OpenAI (fallback)
- **RAG**: FAISS + Google Embeddings

### Frontend
- **Framework**: React 19 + TypeScript
- **Build**: Vite 7
- **State**: TanStack React Query
- **Styling**: Tailwind CSS 4
- **Charts**: Recharts
- **Maps**: MapLibre GL

---

## 개발 명령어

### 로컬 환경 시작

```bash
# 1. Docker 서비스 (DB, Redis)
docker-compose up -d db redis

# 2. 백엔드 시작
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 3. 프론트엔드 시작 (별도 터미널)
cd frontend
npm run dev

# 4. 브라우저에서 http://localhost:5173 접속
```

### Backend 명령어

```bash
cd backend
source .venv/bin/activate   # 가상환경 활성화

# 서버 실행
uvicorn app.main:app --reload --port 8000

# 스키마 확인/수정
python scripts/check_schema.py
python scripts/check_schema.py --fix  # 누락된 컬럼 자동 추가

# RAG 인덱스 빌드
python scripts/build_knowledge_index.py

# 테스트
pytest

# 타입 체크 & 린팅
mypy app/
ruff check .
black app/
```

### Frontend 명령어

```bash
cd frontend
npm run dev          # 개발 서버 (포트 5173)
npm run build        # 프로덕션 빌드
npx tsc --noEmit     # 타입 체크
npm run lint         # ESLint

# API 타입 자동 생성
npm run generate:api
```

### git pull 후 필수 작업

```bash
git pull
cd backend && source .venv/bin/activate
python scripts/check_schema.py --fix
```

---

## API 구조

- **Base URL**: `/api/v1`
- **인증**: 세션 기반 (HTTP-only 쿠키)
- **문서**: `/api/v1/docs` (Swagger UI)

### 주요 엔드포인트

| 카테고리 | 경로 | 설명 |
|----------|------|------|
| 인증 | `/auth/*` | 로그인, Garmin/Strava OAuth |
| 대시보드 | `/dashboard/*` | 요약, 트렌드, 캘린더 |
| 활동 | `/activities/*` | 활동 목록, 상세, HR존, 샘플 |
| AI | `/ai/*` | 대화, 플랜 생성/가져오기 |
| 워크아웃 | `/workouts/*` | 생성, Garmin 푸시 |
| 동기화 | `/ingest/*` | Garmin 데이터 동기화 |
| Strava | `/strava/*` | OAuth, 업로드 관리 |
| 건강 | `/health/*`, `/hr/*`, `/sleep/*` | 건강 지표 |
| 기어 | `/gear/*` | 장비 관리 |
| 근력 | `/strength/*` | 근력 운동 |
| 대회 | `/races/*` | 대회 목표, 예측 |

---

## 핵심 서비스

### sync_service.py (1,947줄)
Garmin Connect 데이터 동기화:
- 활동, 수면, HR, 건강 지표 가져오기
- FIT 파일 파싱 및 저장
- 증분/전체 동기화 지원
- 동기화 락 관리 (대용량 백필 시 TTL 연장)

### dashboard.py (1,701줄)
대시보드 분석 서비스:
- VDOT 계산 (Jack Daniels 공식)
- 훈련 페이스 존 (Easy, Marathon, Threshold, Interval, Repetition)
- 피트니스 지표 (CTL/ATL/TSB - EMA 기반)
- 주간/월간 요약 및 캐싱

### vdot.py (321줄)
Jack Daniels VDOT 계산:
- 최근 경주/레이스 기반 VDOT 산출
- 거리별 훈련 페이스 권장
- Daniels-Gilbert 공식 적용

---

## 데이터베이스 모델 (16개)

| 모델 | 파일 | 설명 |
|------|------|------|
| User | user.py | 사용자 프로필, Garmin/Strava 인증 |
| Activity, Lap, ActivitySample | activity.py | 활동 데이터 (TimescaleDB) |
| AIConversation, AIMessage, AIPlan, AIImport | ai.py | AI 대화 및 플랜 |
| Workout, WorkoutStep, WorkoutSchedule | workout.py | 워크아웃 |
| Gear | gear.py | 장비 |
| StrengthSession, StrengthExercise | strength.py | 근력 운동 |
| Race | race.py | 대회 목표 |
| SleepRecord, HRRecord, HealthMetric | health.py | 건강 데이터 |

---

## 외부 연동

| 서비스 | 용도 | 설정 |
|--------|------|------|
| **Garmin Connect** | 활동/건강 데이터 동기화 | `GARMIN_ENCRYPTION_KEY` |
| **Strava API** | 활동 업로드 | `STRAVA_CLIENT_ID/SECRET` |
| **Runalyze** | HRV, 훈련 지표 | `RUNALYZE_API_TOKEN` |
| **Google Gemini** | AI 플랜 생성 (주) | `GOOGLE_AI_API_KEY` |
| **OpenAI** | AI 플랜 생성 (보조) | `OPENAI_API_KEY` |

---

## 환경 변수

### Backend (.env)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/running
REDIS_URL=redis://localhost:6379/0

# Security
SESSION_SECRET=...
SECRET_KEY=...
COOKIE_SECURE=false  # 프로덕션: true
COOKIE_SAMESITE=lax

# Garmin
GARMIN_ENCRYPTION_KEY=...
GARMIN_BACKFILL_DAYS=0
FIT_STORAGE_PATH=./data/fit_files

# AI (Primary: Gemini)
GOOGLE_AI_API_KEY=...
GOOGLE_AI_MODEL=gemini-2.5-flash-lite
OPENAI_API_KEY=...       # Fallback
OPENAI_MODEL=gpt-4o-mini

# RAG
RAG_ENABLED=true
RAG_TOP_K=3
RAG_MIN_SCORE=0.3

# Strava
STRAVA_CLIENT_ID=...
STRAVA_CLIENT_SECRET=...
STRAVA_AUTO_UPLOAD=true

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

### Frontend (.env)

```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCK_DATA=false
```

---

## 자주 발생하는 이슈

### Frontend

1. **시간 포맷팅 오류**: `format.ts`에서 Math.round 60초 오버플로우 주의
2. **API 타입 불일치**: Backend Pydantic ↔ Frontend TypeScript 동기화 필요 (`npm run generate:api`)
3. **React Query**: mutation 후 관련 쿼리 invalidation 확인

### Backend

1. **스키마 드리프트**: 모델 변경 후 `check_schema.py --fix` 실행
2. **CORS**: `CORS_ORIGINS` 환경변수 설정 필수
3. **가상환경**: 항상 `.venv` 활성화 후 실행
4. **동기화 락**: 대용량 백필(500+ 활동) 시 3시간 TTL, 1000+ 활동 시 `extend_lock()` 사용
5. **httpx base_url**: leading slash 사용 시 base_url 경로가 덮어써지므로 주의
6. **HR 존 계산**: 표준 5존 HRR 방식 (50-60%, 60-70%, 70-80%, 80-90%, 90-100%)
7. **Strava OAuth**: 프로덕션 배포 시 Redis 기반 state 저장 필요

### AI 관련

1. **AI 모델 필드명**: `context_type`/`context_data` 사용 (구: `language`/`model`)
2. **토큰 카운트**: `token_count` 사용 (구: `tokens`)
3. **RAG 스코어**: `min_score=0.3` 기본값, 낮은 스코어는 컨텍스트에서 제외

자세한 내용은 [docs/debug-patterns.md](docs/debug-patterns.md) 참조.

---

## 핵심 문서

| 문서 | 설명 |
|------|------|
| [docs/debug-patterns.md](docs/debug-patterns.md) | 발견된 버그 패턴과 해결책 (58개) |
| [docs/api-reference.md](docs/api-reference.md) | API 상세 문서 |
| [docs/PRD.md](docs/PRD.md) | 제품 요구사항 |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | 변경 이력 |
| [docs/blueprint.md](docs/blueprint.md) | 아키텍처 설계 |

---

## 코드 스타일

- **Python**: Black + Ruff, Type hints 필수
- **TypeScript**: ESLint + Prettier
- **커밋 메시지**: Conventional Commits (feat:, fix:, docs:, refactor:, test:)

---

## 최근 주요 변경사항 (2026-01)

1. **AI 플래닝 스키마 정리**: AIConversation, AIMessage 필드명 일치
2. **VDOT 계산 서비스**: Jack Daniels 공식 기반 훈련 페이스
3. **RAG 통합**: 러닝 가이드 문서 기반 AI 컨텍스트 강화
4. **Strava 업로드 큐**: arq 기반 비동기 업로드 (재시도: 1m, 5m, 30m, 2h)
5. **대시보드 컴팩트 뷰**: CompactActivities, CompactFitness, CompactMileage
6. **대회 목표 연동**: AI 코치에서 대회 정보 참조

---

*이 문서는 Claude Code가 프로젝트를 이해하는 데 사용됩니다.*
