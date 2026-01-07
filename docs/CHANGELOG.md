# 변경 이력 (Changelog)

## 2026-01-07

### 문서화 개선

#### 1. AGENTS.md 파일 생성 (AI 에이전트 규칙)
- **신규**: 루트 `AGENTS.md` - 핵심 규칙, 프로젝트 지도, 작업 흐름
- **신규**: `backend/AGENTS.md` - 백엔드 개발 규칙 (모델, API, 서비스 패턴)
- **신규**: `frontend/AGENTS.md` - 프론트엔드 개발 규칙 (컴포넌트, React Query, 타입)
- **신규**: `docs/AGENTS.md` - 문서화 규칙 (변경 이력, API 문서, 버그 패턴)

#### 2. CLAUDE.md 업데이트
- **추가**: 프로젝트 개요 및 핵심 기능 설명
- **추가**: 기술 스택 섹션 (Backend/Frontend)
- **추가**: 핵심 서비스 설명 (sync_service, dashboard, vdot)
- **추가**: 데이터베이스 모델 테이블 (16개 모델)
- **추가**: 외부 연동 서비스 정리 (Garmin, Strava, Runalyze, AI)
- **추가**: AI 관련 자주 발생하는 이슈
- **추가**: 최근 주요 변경사항 섹션

#### 3. 문서 구조화
- **신규**: `docs/ROADMAP.md` - 프로젝트 로드맵
- **신규**: `docs/ARCHITECTURE.md` - 시스템 아키텍처 문서
- **신규**: `docs/USER_GUIDE.md` - 사용자 가이드

#### 4. 전문가 에이전트 시스템 구축
- **신규**: `.claude/agents/` - 전문가 에이전트 정의
  - `orchestrator.md` - 전체 작업 조율 및 위임
  - `garmin-connector.md` - Garmin Connect 연동 전문가
  - `data-manager.md` - 데이터 처리/분석 전문가
  - `strava-connector.md` - Strava 연동 전문가
  - `ai-coach.md` - AI 기반 훈련 계획 전문가
  - `README.md` - 에이전트 시스템 개요

---

## 2026-01-06

### 주요 개선사항

#### 1. AI 모델 스키마 정렬
- **변경**: SQLAlchemy 모델을 DB 마이그레이션 스키마와 일치시킴
- **수정 내용**:
  - `AIConversation`: `language`, `model` → `context_type`, `context_data`
  - `AIMessage`: `tokens` → `token_count`
  - `AIImport`: 전체 필드 정렬 (`import_type`, `raw_content`, `parsed_data`, `status`, `error_message`, `result_plan_id`)
- **파일**: `backend/app/models/ai.py`
- **관련 패턴**: [debug-patterns.md #50](debug-patterns.md#50-sqlalchemy-모델과-migration-컬럼명-불일치)

#### 2. AI Plan Import 날짜 계산 수정
- **변경**: inclusive end_date 계산으로 수정
- **이전**: `weeks * 7` (exclusive, 1일 초과)
- **현재**: `weeks * 7 - 1` (inclusive, 정확한 기간)
- **파일**: `backend/app/api/v1/endpoints/ai.py`
- **관련 패턴**: [debug-patterns.md #52](debug-patterns.md#52-기간-계산-시-inclusiveexclusive-혼동)

#### 3. 워크아웃 스케줄 스키마 드리프트 수정
- **변경**: 모델에 DB 제약조건 명시
- **추가 내용**:
  - `UniqueConstraint('workout_id', 'scheduled_date')` - 중복 스케줄 방지
  - `Index('ix_workout_schedules_status')` - 상태 필터 성능 개선
  - `IntegrityError` 처리 → 409 Conflict 반환
- **파일**:
  - `backend/app/models/workout.py`
  - `backend/app/api/v1/endpoints/workouts.py`
  - `backend/alembic/versions/015_fix_workout_schedule_schema.py`

#### 4. AI Export (ChatGPT 분석용 요약) 개선
- **수정 내용**:
  - Frontend: `await` 추가하여 clipboard 에러 감지
  - Frontend: `response.content`만 복사 (전체 객체 대신)
  - Backend: `avg_hr` None일 때 "N/A" 표시 (기존: "Nonebpm")
  - TypeScript: `ExportSummaryResponse` 타입 추가
- **파일**:
  - `frontend/src/pages/Coach.tsx:136-147`
  - `frontend/src/types/api.ts` - ExportSummaryResponse 추가
  - `frontend/src/api/ai.ts` - 반환 타입 수정
  - `backend/app/api/v1/endpoints/ai.py:1183`
- **관련 패턴**: [debug-patterns.md #54-56](debug-patterns.md#54-clipboard-api-await-누락)

#### 5. Dashboard 서비스 개선
- **Training Paces**: Daniels-Gilbert VDOT 공식 기반 페이스 계산
- **Fitness Metrics**: EMA 기반 CTL/ATL/TSB 계산 최적화
- **Analytics Summary**: 주/월간 요약 캐싱 로직 추가
- **파일**: `backend/app/services/dashboard.py`

#### 6. Compact Dashboard 컴포넌트 추가
- **새 컴포넌트**:
  - `CompactActivities.tsx` - 최근 활동 요약
  - `CompactFitness.tsx` - 피트니스 지표 요약
  - `CompactMileage.tsx` - 주간 주행거리 요약
  - `CompactStats.tsx` - 통계 요약

#### 7. Strava Upload Jobs 마이그레이션
- **새 마이그레이션**: `014_add_strava_upload_jobs.py`
- **새 서비스**: `backend/app/services/strava_upload.py`

#### 8. AI 코치 대회 목표 참조 강화
- **변경**: 시스템 프롬프트에 `primary_race` 필드 활용 지침 추가
- **추가 지침**:
  - 대회 날짜(`race_date`) 기준 역산 훈련 계획
  - 목표 기록(`goal_time_seconds`) 기반 페이스 전략
  - 남은 일수(`days_until`) 기반 주기화(Periodization) 권장
  - 대회까지 남은 일수 언급으로 동기부여
- **파일**: `backend/app/core/ai_constants.py`

#### 9. AI 엔드포인트 버그 수정
- **UnboundLocalError 수정**: `status` 변수가 FastAPI의 `status` 모듈을 shadowing
  - `status = payload.get("status")` → `response_status = payload.get("status")`
  - 영향 함수: `chat()`, `quick_chat()`
- **AttributeError 수정**: `AIConversation` 응답 필드명 불일치
  - `language`, `model` → `context_type`, `context_data`
- **Gemini 모델 변경**: `gemini-2.5-flash-preview-05-20` → `gemini-2.5-flash-lite`
- **파일**:
  - `backend/app/api/v1/endpoints/ai.py`
  - `backend/app/core/config.py`
  - `backend/.env`
- **관련 패턴**: [debug-patterns.md #57-58](debug-patterns.md#57-python-변수명이-import된-모듈을-shadowing)

#### 10. 워크아웃 페이지 추가
- **새 페이지**: `frontend/src/pages/Workouts.tsx`
- **새 API**: `frontend/src/api/workouts.ts`
- **새 Hooks**: `frontend/src/hooks/useWorkouts.ts`
- **타입 추가**: `WorkoutStep`, `Workout`, `WorkoutSchedule` 등
- **라우팅**: `/workouts` 경로 추가

### 문서화
- `docs/api-reference.md`: `/ai/export` 엔드포인트 문서 추가
- `docs/debug-patterns.md`: 9개 새 패턴 추가 (#50-58)
  - #50: SQLAlchemy 모델/마이그레이션 컬럼명 불일치
  - #51: 외부 API JSON 파싱 예외 미처리
  - #52: 기간 계산 inclusive/exclusive 혼동
  - #53: 날짜 검증 누락
  - #54: Clipboard API await 누락
  - #55: API 응답 객체 vs 필드 추출 혼동
  - #56: None/null 값의 f-string 연결
  - #57: Python 변수명이 import된 모듈을 shadowing
  - #58: SQLAlchemy 모델 필드 변경 후 응답 코드 미동기화

---

## 2026-01-05

### 주요 개선사항

#### 1. HR 존 계산 시스템 개선
- **변경**: 표준 5존 HRR (Heart Rate Reserve) 방식으로 수정
- **이전**: 고정 비율 사용 (30-44%, 45-58% 등)
- **현재**: 업계 표준 5존 방식
  - Zone 1: 50-60% HRR (Recovery)
  - Zone 2: 60-70% HRR (Aerobic)
  - Zone 3: 70-80% HRR (Tempo)
  - Zone 4: 80-90% HRR (Threshold)
  - Zone 5: 90-100% HRR (Maximum)
- **파일**: `backend/app/api/v1/endpoints/activities.py:754-788`
- **관련 패턴**: [debug-patterns.md #30](debug-patterns.md#30-hr-존-계산---주석과-코드-불일치)

#### 2. Runalyze API 호출 수정
- **변경**: httpx base_url 사용 시 leading slash 제거
- **이유**: leading slash가 base_url의 경로를 덮어쓰는 문제 해결
- **파일**: `backend/app/api/v1/endpoints/dashboard.py:71-99`
- **관련 패턴**: [debug-patterns.md #31](debug-patterns.md#31-httpx-base_url--leading-slash-오류)

#### 3. 동기화 락 시스템 개선
- **TTL 증가**: 1시간 → 3시간 (대용량 백필 대응)
- **새 기능**: `extend_lock()` 함수 추가 (Lua 스크립트 기반 원자적 TTL 연장)
- **사용 시나리오**:
  - 100개 활동: ~8분 (기존 TTL로 충분)
  - 500개 활동: ~40분 (3시간 TTL 권장)
  - 1000+ 활동: ~1.5시간 (주기적 `extend_lock()` 호출 권장)
- **파일**: 
  - `backend/app/core/session.py:212-244` - extend_lock() 함수
  - `backend/app/api/v1/endpoints/ingest.py:32` - TTL 증가
- **관련 패턴**: [debug-patterns.md #32](debug-patterns.md#32-동기화-락-ttl-부족-및-연장-로직-누락)

#### 4. Strava OAuth 프로덕션 가이드 추가
- **변경**: Redis 마이그레이션 TODO 주석 추가
- **현재 상태**: 단일 워커 환경에서는 in-memory 방식 사용 중
- **프로덕션 배포 시**: Redis 기반 state 저장 필요
- **파일**: `backend/app/api/v1/endpoints/strava.py:25-36`
- **관련 패턴**: [debug-patterns.md #33](debug-patterns.md#33-strava-oauth-state가-프로세스-메모리에만-저장)

### 문서화
- `docs/debug-patterns.md`에 4개 새로운 패턴 추가 (#30-33)
- `docs/feature-map.md` 업데이트 (HR 존, Runalyze, 동기화 락, Strava OAuth 관련 파일 맵 추가)

---

## 이전 변경사항

프로젝트 초기화부터 현재까지의 주요 변경사항은 Git 히스토리를 참조하세요.

```bash
git log --oneline
```

