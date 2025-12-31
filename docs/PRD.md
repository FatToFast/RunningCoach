# RunningCoach PRD (Product Requirements Document)

## 문서 정보

| 항목 | 내용 |
|------|------|
| 버전 | 1.0 |
| 작성일 | 2025-12-29 |
| 상태 | Draft |
| 작성자 | JY Jeong |

---

## 1. 제품 개요

### 1.1 배경

러닝 훈련의 효과를 극대화하려면 **데이터 기반 의사결정**이 필수입니다. Garmin 워치를 통해 수집되는 방대한 데이터(활동, 수면, 심박수, 회복 지표 등)가 있지만, 이를 체계적으로 분석하고 개인화된 훈련 계획으로 연결하는 도구는 부족합니다.

### 1.2 제품 비전

> **"Garmin 데이터를 기반으로 AI가 생성한 과학적 훈련 계획을 제공하는 개인 러닝 코치"**

### 1.3 목표 사용자

**Primary Persona**: 데이터 지향적 아마추어 러너
- 주 3-5회 러닝
- Garmin 워치 사용
- 마라톤/하프 마라톤 목표
- 체계적 훈련 계획 필요
- 기술적 역량 중간 이상

### 1.4 핵심 가치 제안

1. **통합 데이터 허브**: 모든 Garmin 데이터를 한 곳에서 관리
2. **지능형 분석**: 트렌드, 패턴, 위험 신호 자동 감지
3. **AI 코칭**: 교과서/가이드라인 기반 훈련 계획 생성
4. **원활한 연동**: 생성된 계획을 Garmin에 직접 전송

---

## 2. 기능 요구사항

### 2.1 기능 우선순위 매트릭스

| 기능 | 사용자 가치 | 기술 복잡도 | MVP | v1.0 | v2.0 |
|------|------------|------------|-----|------|------|
| 로컬 로그인/세션 | 높음 | 낮음 | ✅ | ✅ | ✅ |
| Garmin 로그인/연동 | 높음 | 중간 | ✅ | ✅ | ✅ |
| 활동 데이터 수집 | 높음 | 낮음 | ✅ | ✅ | ✅ |
| 활동 FIT 다운로드/파싱 | 높음 | 중간 | ✅ | ✅ | ✅ |
| 수면 데이터 수집 | 중간 | 낮음 | ✅ | ✅ | ✅ |
| 심박수/HRV 수집 | 중간 | 낮음 | ✅ | ✅ | ✅ |
| 체성분 데이터 수집 | 낮음 | 낮음 | ❌ | ✅ | ✅ |
| 훈련 부하 수집 | 중간 | 낮음 | ❌ | ✅ | ✅ |
| 활동 목록 대시보드 | 높음 | 낮음 | ✅ | ✅ | ✅ |
| 활동 상세 보기 | 중간 | 중간 | ✅ | ✅ | ✅ |
| 주간/월간 요약 | 높음 | 중간 | ✅ | ✅ | ✅ |
| Runalyze+ 파생 지표 | 높음 | 높음 | ✅ | ✅ | ✅ |
| 트렌드 차트 | 중간 | 중간 | ❌ | ✅ | ✅ |
| 워크아웃 생성 | 높음 | 높음 | ✅ | ✅ | ✅ |
| 워크아웃 스케줄링 | 높음 | 중간 | ✅ | ✅ | ✅ |
| AI 훈련 계획 생성(대화형/수동 import) | 매우 높음 | 매우 높음 | ✅ | ✅ | ✅ |
| ChatGPT 분석용 요약/복사 | 높음 | 낮음 | ✅ | ✅ | ✅ |
| 계획 승인/수정 플로우 | 높음 | 중간 | ❌ | ✅ | ✅ |
| 자동 데이터 동기화 | 중간 | 중간 | ❌ | ✅ | ✅ |
| Strava 자동 동기화 | 중간 | 중간 | ✅ | ✅ | ✅ |
| 피로도/부상 경고 | 높음 | 높음 | ❌ | ❌ | ✅ |
| 다중 사용자 | 낮음 | 높음 | ❌ | ❌ | ✅ |
| 모바일 최적화 | 중간 | 중간 | ❌ | ❌ | ✅ |

### 2.2 상세 기능 명세

#### 2.2.0 로컬 인증

**FR-000: 로컬 로그인**
- 설명: 지인 공유를 고려한 최소 인증으로 로컬 계정 로그인을 제공한다
- 입력: 이메일, 비밀번호
- 출력: 로그인 성공/실패, 세션 쿠키
- 제약조건:
  - 계정 생성은 초기 seed/스크립트로만 진행 (셀프 가입 없음)
  - 세션은 서버에 저장(Redis), HTTP-only 쿠키로 전달
  - 비밀번호는 Argon2/bcrypt 해시로 저장
  - 세션 만료/로그아웃 지원

#### 2.2.1 Garmin 데이터 연동

**FR-001: Garmin 계정 연결**
- 설명: 사용자가 Garmin Connect 계정을 연결할 수 있어야 한다
- 입력: Garmin 이메일, 비밀번호
- 출력: 연결 성공/실패 상태
- 제약조건:
  - 2FA 지원 필수
  - 세션 만료 시 자동 갱신 시도
  - 실패 시 사용자에게 재인증 요청

**FR-002: 활동 데이터 수집**
- 설명: Garmin에서 러닝/운동 활동 데이터를 가져온다
- 데이터 항목:
  - 기본: 날짜, 유형, 거리, 시간, 칼로리
  - 심박: 평균HR, 최대HR, HR 존별 시간
  - 페이스: 평균 페이스, 최고 페이스, 랩별 페이스
  - GPS: 경로 데이터 (선택적)
  - 고급: 케이던스, 보폭, 상하진동 (가용시)
- FIT 파일: 활동별 원본 다운로드 및 파싱(샘플/랩)
- 기준: Runalyze 수준 이상 데이터 커버리지
- 동기화 정책:
  - 초기 백필: 전체 이력(가능한 범위), 필요 시 GARMIN_BACKFILL_DAYS로 제한
  - 증분: endpoint별 last_success_at 저장 + safety window 3일 재조회
  - 목록 → 상세 fetch, garmin_id 기준 UPSERT, 누락 시 soft delete(또는 상태 플래그)
  - 사용자 타임존 기준(기본 Asia/Seoul)
- 동기화 주기: MVP는 수동, v1.0부터 자동(6시간)
- 백필 운영:
  - 배치 처리(페이지네이션), 체크포인트 기반 재개
  - 429/5xx 재시도(backoff), 레이트리밋 보호

**FR-003: 수면 데이터 수집**
- 데이터 항목: 총 수면시간, 수면 점수, 수면 단계(깊은/얕은/REM)
- 동기화 주기: MVP는 수동, 자동 동기화 시 일 1회

**FR-004: 건강 지표 수집**
- 데이터 항목:
  - 심박수: 안정시 심박, HRV
  - 체성분: 체중, BMI, 체지방률
  - 피트니스: VO2max, 훈련 상태, Body Battery
  - 부하: 급성 부하, 만성 부하, 회복 시간
- 스트레스/수면 회복 지표: Stress, Sleep Score 등
- MVP 범위: 가능한 모든 Garmin 지표 수집 (기기/계정 제공 범위 내)

**FR-005: Analytics 요약 집계 (MVP)**
- 설명: 정규화된 데이터를 기반으로 주간/월간 요약을 생성한다
- 산출: analytics_summaries (period_type, period_start, total_distance_meters, total_duration_seconds, total_activities, avg_pace_seconds, avg_hr, elevation_gain)
- 기준: 주간은 월요일 시작, 월간은 매월 1일 시작 (사용자 타임존)
- 동작: 동기화 완료 후 재계산 가능하도록 idempotent 처리

**FR-006: Runalyze+ 파생 지표 (MVP)**
- 설명: Runalyze 수준 이상 파생 지표를 계산한다
- 활동 단위: TRIMP, TSS, Training Effect, 효율지수, VO2max 추정
- 일/주 단위: ATL/CTL/TSB, 주간 부하, 페이스 추세
- 동작: FIT/샘플 데이터 기반 계산, 전체 이력 기반 베이스라인 생성, 재계산 가능

#### 2.2.2 대시보드

**FR-010: 메인 대시보드**
- 주간 요약 카드: 총 거리, 총 시간, 평균 페이스, 활동 수
- 최근 활동 리스트: 최근 7일 활동
- 건강 상태 표시: MVP는 수면 점수 중심, Body Battery는 v1.0
- 다음 예정 워크아웃
- 파생 지표 카드: TRIMP/TSS/CTL/ATL

**FR-011: 활동 목록**
- 페이지네이션 (20개/페이지)
- 필터: 날짜 범위, 활동 유형
- 정렬: 날짜, 거리, 시간
- 검색: 활동 이름

**FR-012: 활동 상세**
- 기본 정보 표시
- 랩 데이터 테이블
- 심박수 차트 (시간별)
- 페이스 차트 (거리별)
- 지도 표시 (GPS 데이터 있을 시)

**FR-013: 트렌드 분석**
- 주간 거리/시간 트렌드
- 평균 페이스 변화
- 안정시 심박수 트렌드
- VO2max 변화

#### 2.2.3 훈련 계획

**FR-020: 워크아웃 템플릿**
- 워크아웃 유형:
  - Easy Run (회복 달리기)
  - Long Run (장거리)
  - Tempo Run (임계 속도)
  - Interval (인터벌)
  - Hill Repeats (언덕 반복)
  - Fartlek (파틀렉)
- 템플릿 구조:
  - 웜업, 메인, 쿨다운 구간
  - 각 구간: 시간/거리, 목표 페이스/HR 존

**FR-021: 워크아웃 생성**
- 템플릿 기반 생성
- 커스텀 구간 추가/수정
- 목표 설정 (페이스, HR 존, 파워)
- 미리보기

**FR-022: Garmin 워크아웃 전송**
- 생성된 워크아웃을 Garmin Connect에 업로드
- 전송 상태 추적
- 실패 시 재시도

**FR-023: 워크아웃 스케줄링**
- 달력에서 날짜 선택
- Garmin에 스케줄 동기화
- 완료/미완료 상태 추적

#### 2.2.4 AI 훈련 계획 (MVP)

**FR-030: 훈련 목표 설정**
- 목표 유형: 마라톤, 하프, 10K, 5K, 일반 피트니스
- 목표 날짜
- 목표 기록 (선택)
- 현재 수준 평가

**FR-031: AI 계획 생성**
- 입력: 목표, 현재 데이터, 가용 훈련일, 과거 이력
- 처리: 가이드라인 RAG + OpenAI API 기반 대화형 생성
- 출력: 주차별 훈련 계획 (버전 관리)
- 제약 조건:
  - 주간 볼륨 증가 10% 이하
  - 3주 빌드업 + 1주 회복
  - 연속 하드 세션 금지
  - 과거 전체 이력 기반 현재 상태 추정
  - 입력 요약: 최근 6주 + 12주 추세 + 전체 이력 요약

**FR-032: 계획 승인 플로우**
- 계획 미리보기
- 주차별 조정 가능
- 개별 워크아웃 수정 가능
- 승인 후 Garmin 일괄 전송

**FR-033: 계획 모니터링**
- 예정 vs 실제 비교
- 완료율 추적
- 적응형 조정 제안

**FR-034: 대화 로그 보관**
- 설명: 대화형 플랜 생성 과정 로그를 저장한다
- 항목: role, content, model, tokens, language, created_at
- 요구: 삭제/익명화 옵션 제공

**FR-035: 다국어 자료 처리**
- 설명: 한국어 기본 응답, 영어 자료 포함 RAG
- 처리: 언어 감지/메타데이터 저장, 필요 시 번역

**FR-036: 수동 플랜 import**
- 설명: ChatGPT 등 외부에서 생성한 플랜 JSON을 붙여넣어 워크아웃/스케줄 생성
- 요구사항:
  - JSON 스키마 검증
  - import 로그 저장
  - 실패 시 상세 오류 반환

**FR-037: ChatGPT 분석용 요약/복사**
- 설명: AI 분석을 위한 요약 포맷을 생성하고 복사할 수 있어야 한다
- 요구사항:
  - Markdown/JSON 포맷 제공
  - 최근 6주 + 12주 추세 + 전체 이력 요약 포함
  - 민감정보 최소화 옵션

#### 2.2.5 Strava 연동

**FR-040: Strava 자동 동기화**
- 설명: Garmin에서 수집된 활동을 Strava로 자동 업로드한다
- 요구사항:
  - Strava OAuth 연결/갱신
  - 중복 업로드 방지 (Garmin activity_id 기준 매핑)
  - 실패 시 재시도 및 상태 기록

---

## 3. 비기능 요구사항

### 3.1 성능

| 항목 | 요구사항 |
|------|----------|
| API 응답 시간 | p50 < 200ms, p95 < 500ms, p99 < 1s |
| 페이지 로드 | < 3초 (LCP) |
| 동기화 지연 | 증분 동기화 p95 < 5분 (초기 전체 백필 제외) |
| 동시 사용자 | MVP: 5, v1.0: 10, v2.0: 100 |

### 3.2 가용성

| 항목 | 요구사항 |
|------|----------|
| 업타임 | 99% (월 7시간 다운타임 허용) |
| 백업 | 일 1회 DB 백업 |
| 복구 | RTO 4시간, RPO 24시간 |

### 3.3 보안

| 항목 | 요구사항 |
|------|----------|
| 인증 정보 저장 | 비밀번호: Argon2/bcrypt 해시, Garmin 토큰: AES-256 암호화 |
| API 통신 | HTTPS 필수 |
| 세션 관리 | 서버 세션 + HTTP-only 쿠키 (Redis), 만료 정책 |
| 데이터 접근 | 소유자 본인만 접근 가능 |
| LLM 데이터 처리 | 민감정보 최소화, 대화 로그 보관/삭제 정책 |

### 3.4 확장성

- 수평 확장: Docker Compose → Kubernetes 마이그레이션 경로
- 데이터 증가: TimescaleDB 파티셔닝 적용
- API 버저닝: /api/v1 형식으로 하위 호환성 유지

### 3.5 AI 비용/모델 예산 비교

- 모델별 비용은 변동 가능하므로 최신 OpenAI 가격을 기준으로 갱신
- 비용 산식: (입력 토큰 + 출력 토큰) * 모델별 단가
- 예산 목표: 사용자 1인/월 상한 설정 + 초과 시 저비용 모델로 전환
- 입력 요약으로 토큰 사용량 상한을 관리 (장기 이력은 요약/집계로 축약)

| 모델 | 용도 | 품질 | 비용(USD/1M tokens) |
|------|------|------|--------------------|
| gpt-4o | 계획 최종화/검토 | 높음 | TBD |
| gpt-4o-mini | 대화/초안 | 중간 | TBD |

---

## 4. 시스템 아키텍처

### 4.1 컴포넌트 다이어그램

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (SvelteKit)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │Dashboard │ │Activities│ │ Workouts │ │ Training Plans   │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway (FastAPI)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │Auth API  │ │Data API  │ │Workout   │ │ Planning API     │   │
│  │          │ │          │ │API       │ │                  │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
         │              │              │                │
         ▼              ▼              ▼                ▼
┌──────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Garmin      │ │ PostgreSQL  │ │   Redis     │ │ AI Service  │
│ Adapter     │ │ + Timescale │ │   Cache     │ │ (LLM+RAG)   │
└──────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
         │
         ▼
┌──────────────┐
│ Garmin      │
│ Connect API │
└──────────────┘
```

AI Planning은 OpenAI API를 사용하며, Strava 자동 동기화는 Strava API를 사용한다.

### 4.2 데이터 흐름

```
[Garmin Connect]
       │
       ▼ (garminconnect library)
[Garmin Adapter] ──► [Raw Storage] (garmin_raw_events, garmin_raw_files)
       │
       ▼ (Transform)
[Normalized Tables] (activities, sleep, hr_records, health_metrics, activity_samples, ...)
       │
       ▼ (Aggregate)
[Analytics Tables] (analytics_summaries, trends, ...)
       │
       ▼
[Dashboard API] ──► [Frontend]
       │
       ▼
[AI Planning Service] (OpenAI API)
       │
       ├──► [Guidelines RAG] (pgvector)
       │
       ▼
[Training Plan] ──► [Workout Schedule]
       │
       ▼ (Push)
[Garmin Workouts]
       │
       ▼ (Upload)
[Strava Activities]
```

### 4.3 기술 스택 상세

#### Backend
| 컴포넌트 | 기술 | 버전 | 용도 |
|----------|------|------|------|
| Web Framework | FastAPI | 0.109+ | REST API |
| ORM | SQLAlchemy | 2.0+ | DB 추상화 |
| Validation | Pydantic | 2.5+ | 데이터 검증 |
| Task Queue | Celery | 5.3+ | 비동기 작업 |
| Scheduler | Celery Beat | - | 정기 동기화 |
| Database | PostgreSQL | 15+ | 메인 DB |
| Time-series | TimescaleDB | 2.13+ | 시계열 최적화 |
| Cache | Redis | 7+ | 캐시/세션 |
| Vector DB | pgvector | 0.5+ | RAG 임베딩 |
| FIT Parser | fitparse/FIT SDK | - | 활동 FIT 파싱 |
| LLM API | OpenAI | - | 대화형 플랜 |
| External Sync | Strava API | - | 활동 업로드 |

#### Frontend
| 컴포넌트 | 기술 | 버전 | 용도 |
|----------|------|------|------|
| Framework | SvelteKit | 2.0+ | SSR/SPA |
| Styling | TailwindCSS | 3.4+ | UI 스타일 |
| Charts | ECharts | 5.4+ | 데이터 시각화 |
| State | Svelte Stores | - | 상태 관리 |
| HTTP | Fetch API | - | API 통신 |

#### Infrastructure
| 컴포넌트 | 기술 | 용도 |
|----------|------|------|
| Containerization | Docker | 앱 패키징 |
| Orchestration | Docker Compose | 로컬/NAS 배포 |
| Reverse Proxy | Nginx/Traefik | 라우팅, SSL |
| Monitoring | Prometheus + Grafana | 메트릭 수집 |
| Logging | Loki | 로그 집계 |

---

## 5. 데이터 모델

### 5.1 ER 다이어그램

```
┌──────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    users     │     │ garmin_sessions │     │garmin_raw_events│
├──────────────┤     ├─────────────────┤     ├─────────────────┤
│ id (PK)      │◄───┤│ user_id (FK)    │     │ id (PK)        │
│ email        │     │ oauth1_token    │     │ user_id (FK)   │
│ password_hash│     │ oauth2_token    │     │ endpoint       │
│ display_name │     │ expires_at      │     │ fetched_at     │
│ timezone     │     │ last_login      │     │ payload (JSONB)│
│ last_login_at│     └─────────────────┘     └─────────────────┘
│ created_at   │
└──────────────┘
       │                                              │
       │         ┌────────────────────────────────────┤
       │         │                                    │
       ▼         ▼                                    ▼
┌──────────────────┐  ┌──────────────┐  ┌─────────────────────┐
│   activities     │  │    sleep     │  │    hr_records       │
├──────────────────┤  ├──────────────┤  ├─────────────────────┤
│ id (PK)          │  │ id (PK)      │  │ id (PK)             │
│ user_id (FK)     │  │ user_id (FK) │  │ user_id (FK)        │
│ garmin_id        │  │ date         │  │ start_time          │
│ activity_type    │  │ duration     │  │ end_time            │
│ start_time       │  │ score        │  │ avg_hr, max_hr      │
│ duration_seconds │  │ stages(JSON) │  │ resting_hr          │
│ distance_meters  │  │ raw_event_id │  │ samples (JSON)      │
│ calories         │  └──────────────┘  └─────────────────────┘
│ avg_hr, max_hr   │
│ avg_pace_seconds │
│ elevation_gain   │
│ raw_event_id(FK) │
                                             └──────────────────┘
       │
       ▼
┌───────────────────┐
│ activity_samples  │
├───────────────────┤
│ id (PK)           │
│ activity_id (FK)  │
│ timestamp         │
│ hr, pace, cadence │
│ lat, lng, alt     │
└───────────────────┘

┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│    plans     │     │   plan_weeks    │     │    workouts      │
├──────────────┤     ├─────────────────┤     ├──────────────────┤
│ id (PK)      │◄───┤│ plan_id (FK)    │◄───┤│ plan_week_id(FK) │
│ user_id (FK) │     │ week_index      │     │ id (PK)          │
│ goal_type    │     │ focus           │     │ name             │
│ goal_date    │     │ notes           │     │ workout_type     │
│ status       │     └─────────────────┘     │ structure (JSON) │
│ start_date   │                             │ target (JSON)    │
│ end_date     │                             │ garmin_workout_id│
└──────────────┘                             └──────────────────┘
                                                      │
                                                      ▼
                                             ┌──────────────────┐
                                             │workout_schedules │
                                             ├──────────────────┤
                                             │ id (PK)          │
                                             │ workout_id (FK)  │
                                             │ scheduled_date   │
                                             │ status           │
                                             │ garmin_schedule_id│
└──────────────────┘
```

**MVP 보정 사항**
- `users`에 `password_hash`, `last_login_at` 추가
- `garmin_sync_state` 추가: endpoint별 last_sync_at/last_success_at/cursor 관리
- `analytics_summaries` 추가: 주간/월간 요약 집계 테이블
- `garmin_raw_files` 추가: 활동별 FIT 파일 저장
- `activity_samples` 추가: FIT 기반 샘플 저장
- `health_metrics` 추가: 가능한 모든 Garmin 지표 저장
- `activity_metrics`/`fitness_metrics_daily` 추가: Runalyze+ 파생 지표
- `ai_conversations`/`ai_messages` 추가: 대화 로그 저장
- `ai_imports` 추가: 수동 플랜 import 로그 저장
- `strava_sessions`/`strava_sync_state`/`strava_activity_map` 추가: Strava 자동 동기화

### 5.2 인덱스 전략

```sql
-- 활동 조회 최적화
CREATE INDEX idx_activities_user_date ON activities(user_id, start_time DESC);
CREATE INDEX idx_activities_type ON activities(activity_type);

-- 수면 조회 최적화
CREATE INDEX idx_sleep_user_date ON sleep(user_id, date DESC);

-- HR 시계열 최적화 (v1.0, hr_samples 테이블 사용 시)
SELECT create_hypertable('hr_samples', 'timestamp');

-- 워크아웃 스케줄 조회
CREATE INDEX idx_workout_schedule_date ON workout_schedules(scheduled_date);

-- Analytics 요약 조회
CREATE INDEX idx_analytics_user_period ON analytics_summaries(user_id, period_type, period_start);

-- 활동 샘플 조회
CREATE INDEX idx_activity_samples_activity_time ON activity_samples(activity_id, timestamp);

-- 건강 지표 조회
CREATE INDEX idx_health_metrics_user_type_time ON health_metrics(user_id, metric_type, metric_time);

-- FIT 파일 조회
CREATE INDEX idx_garmin_raw_files_activity ON garmin_raw_files(activity_id);

-- Strava 매핑 조회
CREATE INDEX idx_strava_activity_map_activity ON strava_activity_map(activity_id);

-- AI 대화 로그 조회
CREATE INDEX idx_ai_messages_conversation_time ON ai_messages(conversation_id, created_at);

-- AI 플랜 import 조회
CREATE INDEX idx_ai_imports_user_time ON ai_imports(user_id, created_at DESC);
```

---

## 6. API 설계

### 6.1 API 원칙

- RESTful 설계
- JSON 응답
- 일관된 에러 형식
- 페이지네이션 지원
- 버전 관리 (/api/v1, MVP부터 동일 경로 사용 권장)

### 6.2 공통 응답 형식

```json
// 성공 응답
{
  "success": true,
  "data": { ... },
  "meta": {
    "timestamp": "2025-12-29T10:30:00Z",
    "request_id": "uuid"
  }
}

// 에러 응답
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": { ... }
  },
  "meta": {
    "timestamp": "2025-12-29T10:30:00Z",
    "request_id": "uuid"
  }
}

// 페이지네이션
{
  "success": true,
  "data": [ ... ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

### 6.3 주요 API 엔드포인트

#### 인증

세션은 HTTP-only 쿠키 기반
```
POST   /api/v1/auth/login             - 로컬 로그인
POST   /api/v1/auth/logout            - 로그아웃
GET    /api/v1/auth/me                - 현재 사용자
POST   /api/v1/auth/garmin/connect     - Garmin 계정 연결
POST   /api/v1/auth/garmin/refresh     - 세션 갱신
DELETE /api/v1/auth/garmin/disconnect  - 연결 해제
GET    /api/v1/auth/garmin/status      - 연결 상태 확인
```

#### 데이터 동기화
```
POST   /api/v1/ingest/run              - 수동 동기화 실행
GET    /api/v1/ingest/status           - 동기화 상태 조회
GET    /api/v1/ingest/history          - 동기화 이력 (v1.0)
```

#### 활동
```
GET    /api/v1/activities              - 활동 목록 (페이지네이션)
GET    /api/v1/activities/:id          - 활동 상세
GET    /api/v1/activities/:id/samples  - 활동 샘플 데이터
GET    /api/v1/activities/:id/laps     - 랩 데이터
GET    /api/v1/activities/:id/fit      - FIT 파일 다운로드
```

#### 건강 데이터
```
GET    /api/v1/sleep                   - 수면 기록
GET    /api/v1/sleep/:date             - 특정 날짜 수면 (v1.0)
GET    /api/v1/hr                      - 심박수 기록
GET    /api/v1/metrics                - 건강/피트니스 지표 통합 조회
GET    /api/v1/metrics/body            - 체성분 기록 (v1.0)
GET    /api/v1/metrics/fitness         - 피트니스 지표 (v1.0)
```

#### 대시보드
```
GET    /api/v1/dashboard/summary       - 주간/월간 요약
GET    /api/v1/dashboard/trends        - 트렌드 데이터 (v1.0)
GET    /api/v1/dashboard/calendar      - 달력 뷰 데이터 (v1.0)
```

#### AI 플래닝
```
POST   /api/v1/ai/chat                 - 대화형 계획 생성/수정
GET    /api/v1/ai/conversations/:id    - 대화 로그 조회
POST   /api/v1/ai/import               - 수동 플랜 JSON import
GET    /api/v1/ai/export               - ChatGPT 분석용 요약
```
MVP는 대화형 생성/수정에 집중하고, v1.0에서 계획 CRUD를 보강

#### 워크아웃
```
GET    /api/v1/workouts                - 워크아웃 목록
POST   /api/v1/workouts                - 워크아웃 생성
GET    /api/v1/workouts/:id            - 워크아웃 상세
PUT    /api/v1/workouts/:id            - 워크아웃 수정
DELETE /api/v1/workouts/:id            - 워크아웃 삭제
POST   /api/v1/workouts/:id/push       - Garmin 전송
POST   /api/v1/workouts/:id/schedule   - 스케줄링
```

#### Strava 동기화
```
GET    /api/v1/strava/connect          - Strava OAuth 시작 (auth_url 반환)
GET    /api/v1/strava/callback         - Strava OAuth 콜백
GET    /api/v1/strava/status           - Strava 연결 상태
POST   /api/v1/strava/refresh          - Strava 토큰 갱신
DELETE /api/v1/strava/disconnect       - Strava 연결 해제
POST   /api/v1/strava/sync             - Strava 수동 동기화
```

#### 훈련 계획 (v1.0, CRUD)
```
GET    /api/v1/plans                   - 계획 목록
POST   /api/v1/plans/generate          - AI 계획 생성
GET    /api/v1/plans/:id               - 계획 상세
PUT    /api/v1/plans/:id               - 계획 수정
POST   /api/v1/plans/:id/approve       - 계획 승인
POST   /api/v1/plans/:id/sync          - Garmin 일괄 동기화
DELETE /api/v1/plans/:id               - 계획 삭제
```

---

## 7. 사용자 인터페이스

### 7.1 정보 아키텍처

```
RunningCoach
├── 로그인
├── 대시보드 (홈)
│   ├── 주간 요약 카드
│   ├── 최근 활동
│   ├── 건강 상태
│   └── 다음 워크아웃
├── 활동
│   ├── 활동 목록
│   └── 활동 상세
├── 분석
│   ├── 트렌드 차트
│   ├── 주간/월간 리포트
│   ├── 비교 분석
│   └── AI 분석용 복사
├── 훈련 계획
│   ├── 계획 생성
│   ├── 계획 목록
│   ├── 달력 뷰
│   └── 워크아웃 라이브러리
├── 설정
│   ├── Garmin 연결
│   ├── Strava 연결
│   ├── 프로필
│   └── 동기화 설정
└── 도움말
```

### 7.2 주요 화면 와이어프레임

#### 대시보드
```
┌─────────────────────────────────────────────────────────┐
│  RunningCoach                    [Sync] [Settings] [?] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ 이번 주   │ │ 총 거리   │ │ 평균 페이스│ │ 활동 수   │  │
│  │ 42.5 km  │ │ 3:25:00  │ │ 5:32/km  │ │ 5회      │  │
│  │ ▲12%     │ │ ▲8%      │ │ ▼3%      │ │ =        │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│                                                         │
│  최근 활동                                    [전체보기]│
│  ┌─────────────────────────────────────────────────┐   │
│  │ 🏃 오전 러닝    오늘 06:30   8.2km   42:15      │   │
│  │ 🏃 저녁 러닝    어제 19:00   5.5km   29:30      │   │
│  │ 🏃 장거리      2일전 07:00   15.0km  1:18:45   │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────┐  ┌──────────────────────┐   │
│  │ 건강 상태            │  │ 다음 워크아웃         │   │
│  │ Body Battery: 72    │  │ 내일: Tempo Run      │   │
│  │ 수면 점수: 85       │  │ 목표: 6km @ 5:00/km  │   │
│  │ HRV: 45ms          │  │ [상세보기]            │   │
│  └──────────────────────┘  └──────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## 8. 배포 및 운영

### 8.1 배포 환경

**Target**: Synology/QNAP NAS with Docker

```yaml
# docker-compose.yml 구조
services:
  api:
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [db, redis]
    volumes: [fit_data:/data/fit]

  worker:
    build: ./backend
    command: celery worker
    depends_on: [db, redis]
    volumes: [fit_data:/data/fit]

  scheduler:
    build: ./backend
    command: celery beat
    depends_on: [redis]

  frontend:
    build: ./frontend
    ports: ["3000:3000"]

  db:
    image: timescale/timescaledb:latest-pg15
    volumes: [db_data:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine
    volumes: [redis_data:/data]

  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes: [./nginx.conf:/etc/nginx/nginx.conf]

volumes:
  db_data:
  redis_data:
  fit_data:
```

### 8.2 모니터링

- **메트릭**: Prometheus + Grafana
- **로깅**: Loki + Grafana
- **알림**: Grafana Alerting → Telegram/Email
- **헬스체크**: /health 엔드포인트

### 8.3 백업 전략

```
Daily:
- PostgreSQL pg_dump → NAS backup folder
- Redis RDB snapshot

Weekly:
- Full backup → External drive (optional)
- Log rotation
```

### 8.4 초기 계정 생성

- 최초 실행 시 환경변수 기반 seed 계정 생성
- 셀프 가입 비활성, 지인 계정은 운영자가 seed/관리 스크립트로 추가
- 동일 이메일은 idempotent upsert로 중복 생성 방지

### 8.5 환경변수 (MVP)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| DATABASE_URL | postgresql+asyncpg://postgres:postgres@localhost:5432/runningcoach | PostgreSQL 연결 문자열 |
| REDIS_URL | redis://localhost:6379/0 | Redis 세션/캐시 |
| SESSION_SECRET | change-me-in-production | Redis 세션 키 prefix (서명 미사용, 향후 확장용 예약) |
| SESSION_TTL_SECONDS | 604800 | 세션 만료(초), 슬라이딩 만료 지원 |
| COOKIE_SECURE | false | HTTPS에서만 쿠키 전송 (운영: true 권장) |
| COOKIE_SAMESITE | Lax | SameSite 정책 |
| CORS_ORIGINS | localhost 개발서버 | CORS 허용 도메인 (쉼표 구분) |
| GARMIN_ENCRYPTION_KEY | - | Garmin 토큰 암호화 키 (v1.0 예정, 현재 미사용) |
| GARMIN_BACKFILL_DAYS | 0 | 초기 백필 범위 (0=전체 이력) |
| GARMIN_SAFETY_WINDOW_DAYS | 3 | 증분 재조회 윈도우 |
| FIT_STORAGE_PATH | /data/fit | FIT 파일 저장 경로 (도커 외 환경은 권한 확인 필요) |
| OPENAI_API_KEY | - | OpenAI API 키 |
| OPENAI_MODEL | gpt-4o-mini | 기본 모델 |
| OPENAI_BUDGET_USD | - | 월 예산 상한 |
| STRAVA_CLIENT_ID | - | Strava OAuth 클라이언트 ID |
| STRAVA_CLIENT_SECRET | - | Strava OAuth 클라이언트 시크릿 |
| STRAVA_REDIRECT_URI | - | Strava OAuth 리다이렉트 |
| SYNC_CRON | - | 자동 동기화 크론(미설정 시 비활성) |
| ADMIN_EMAIL | - | 초기 관리자 이메일 |
| ADMIN_PASSWORD | - | 초기 관리자 비밀번호 |
| ADMIN_DISPLAY_NAME | - | 초기 관리자 표시명(옵션) |

### 8.6 동기화 스케줄

- MVP: 수동 동기화만 지원 (`POST /api/v1/ingest/run`)
- v1.0: 스케줄러(Celery Beat/cron)로 6시간마다 자동 동기화
- 스케줄은 `SYNC_CRON`으로 조정, 미설정 시 비활성
- 최초 실행 시 전체 이력 백필 수행
- Strava 업로드는 Garmin 동기화 완료 후 자동 실행

---

## 9. 테스트 전략

### 9.1 테스트 유형

| 유형 | 도구 | 커버리지 목표 |
|------|------|--------------|
| Unit Test | pytest | 80% |
| Integration Test | pytest + testcontainers | 주요 흐름 |
| E2E Test | Playwright | 핵심 사용자 시나리오 |
| Load Test | Locust | API 성능 검증 |

### 9.2 테스트 시나리오

**Critical Path**:
1. Garmin 로그인 → 데이터 동기화 → 대시보드 표시
2. 워크아웃 생성 → Garmin 전송 → 스케줄링
3. AI 대화형 계획 생성 → 수정 → 워크아웃 반영
4. Strava 자동 동기화 → 업로드 확인
5. 수동 플랜 import → 워크아웃/스케줄 전송

---

## 10. 릴리스 계획

### 10.1 버전 로드맵

| 버전 | 목표 | 주요 기능 |
|------|------|----------|
| MVP | 기술 검증 | 로컬 인증, Garmin 연동, FIT 파싱, Runalyze+ 지표, AI 대화형 플랜, Strava 자동 동기화 |
| v1.0 | 핵심 가치 | 자동 동기화, 트렌드 분석, 계획 승인/수정 플로우 |
| v1.5 | 안정화 | 버그 수정, 성능 최적화, UX 개선 |
| v2.0 | 확장 | 다중 사용자, 피로도 경고, 모바일 최적화 |

### 10.2 MVP 타임라인

```
Week 1: Garmin POC (로그인, 데이터 수집, FIT 파싱, 전체 이력 백필)
Week 2: 데이터 파이프라인 (DB, 정규화, 파생 지표)
Week 3: REST API (CRUD, 대시보드, metrics)
Week 4: 프론트엔드 (기본 UI, 파생 지표 카드)
Week 5: Garmin 워크아웃 연동
Week 6: AI 대화형 플랜 + 로그/예산
Week 7: Strava 자동 동기화
Week 8: 통합 테스트, 버그 수정
```

---

## 11. 부록

### 11.1 용어 정의

| 용어 | 정의 |
|------|------|
| 활동 (Activity) | Garmin에서 기록된 단일 운동 세션 |
| 워크아웃 (Workout) | 계획된 훈련 세션 템플릿 |
| 훈련 계획 (Plan) | 특정 목표를 위한 주차별 워크아웃 집합 |
| 동기화 (Sync) | Garmin Connect와 데이터 교환 |
| Body Battery | Garmin의 에너지 수준 지표 (0-100) |
| HRV | 심박변이도, 회복 상태 지표 |

### 11.2 참고 자료

- [garminconnect 라이브러리](https://github.com/cyberjunky/python-garminconnect)
- [Garmin FIT SDK](https://developer.garmin.com/fit/overview/)
- [Jack Daniels' Running Formula](https://www.amazon.com/Daniels-Running-Formula-Jack/dp/1718203667)
- [Training Peaks 문서](https://www.trainingpeaks.com/learn/)

### 11.3 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0 | 2025-12-29 | 초안 작성 | JY Jeong |
