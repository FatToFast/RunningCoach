# AI Coach Agent

데이터와 문서 기반으로 훈련 스케줄을 생성하는 전문가 에이전트입니다.

## 역할

- 사용자 데이터 기반 맞춤형 훈련 계획 생성
- 러닝 관련 질문 답변 (RAG 기반)
- 워크아웃 설계 및 추천
- 훈련 피드백 및 조언 제공

## 담당 파일

```
backend/
├── app/
│   ├── api/v1/endpoints/
│   │   └── ai.py                  # 핵심 - AI 엔드포인트
│   ├── services/
│   │   └── ai_snapshot.py         # AI 스냅샷 서비스
│   ├── knowledge/                 # RAG 시스템
│   │   ├── embeddings.py          # Google Embeddings
│   │   ├── retriever.py           # 문서 검색
│   │   ├── loader.py              # 문서 로더
│   │   └── models.py              # 지식 모델
│   ├── core/
│   │   └── ai_constants.py        # 시스템 프롬프트
│   └── models/
│       └── ai.py                  # AI 대화 모델
└── scripts/
    └── build_knowledge_index.py   # RAG 인덱스 빌드
```

## 주요 기능

### 1. 대화형 코칭

```python
# AI 코치와 대화
async def chat(
    user_id: int,
    conversation_id: int | None,
    message: str,
) -> AIResponse:
    """
    사용자 메시지에 대한 AI 응답 생성

    Context:
    - 사용자 훈련 데이터 (최근 활동, VDOT, CTL/ATL/TSB)
    - 대회 목표 (설정된 경우)
    - 이전 대화 내역
    - RAG 검색 결과 (관련 러닝 지식)
    """
```

### 2. 훈련 계획 생성

```python
# 훈련 계획 생성
async def generate_training_plan(
    user_id: int,
    goal: TrainingGoal,
) -> TrainingPlan:
    """
    맞춤형 훈련 계획 생성

    Input:
    - goal.race_distance: 목표 거리 (5K, 10K, Half, Full)
    - goal.target_time: 목표 기록
    - goal.race_date: 대회 날짜
    - goal.weeks: 훈련 주수

    Output:
    - 주별 훈련 스케줄
    - 각 세션 상세 (거리, 페이스, 목적)
    - 주기화 (Base, Build, Peak, Taper)
    """
```

### 3. 워크아웃 설계

```python
# 개별 워크아웃 설계
async def design_workout(
    user_id: int,
    workout_type: str,
    target_distance: float | None = None,
) -> Workout:
    """
    워크아웃 설계

    Types:
    - easy: 쉬운 러닝
    - long: 장거리 러닝
    - tempo: 템포 러닝
    - interval: 인터벌 훈련
    - fartlek: 파틀렉
    - recovery: 회복 러닝
    """
```

### 4. RAG 기반 지식 검색

```python
# 러닝 지식 검색
async def search_knowledge(
    query: str,
    top_k: int = 3,
) -> list[KnowledgeResult]:
    """
    RAG 시스템으로 관련 문서 검색

    Sources:
    - 러닝 가이드북
    - 훈련 원칙 문서
    - FAQ

    Returns:
    - 관련 문서 청크
    - 신뢰도 점수 (min_score=0.3 필터)
    """
```

## 시스템 프롬프트 구성

```python
# ai_constants.py
SYSTEM_PROMPT = """
당신은 전문 러닝 코치입니다.

## 사용자 정보
- VDOT: {vdot}
- 최근 CTL: {ctl} / ATL: {atl} / TSB: {tsb}
- 주간 평균 거리: {weekly_distance}km

## 대회 목표 (설정된 경우)
- 대회명: {race_name}
- 날짜: {race_date} (D-{days_until})
- 목표 기록: {goal_time}

## 훈련 페이스 (VDOT 기반)
- Easy: {easy_pace}
- Marathon: {marathon_pace}
- Threshold: {threshold_pace}
- Interval: {interval_pace}

## 지침
1. 사용자의 현재 체력 수준에 맞는 조언 제공
2. 대회 목표가 있으면 역산하여 계획 수립
3. 점진적 부하 증가 원칙 준수 (주당 10% 이내)
4. TSB 상태에 따른 휴식/훈련 강도 조절
"""
```

## 데이터 흐름

```
사용자 질문
     │
     ▼
┌───────────────────┐
│  Context Builder  │ ← 사용자 데이터 수집
└─────────┬─────────┘
          │
          ├──▶ 최근 활동 요약
          ├──▶ 피트니스 지표 (CTL/ATL/TSB)
          ├──▶ VDOT & 훈련 페이스
          ├──▶ 대회 목표
          └──▶ 이전 대화 내역
          │
          ▼
┌───────────────────┐
│   RAG Retriever   │ ← 관련 문서 검색
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│    AI Provider    │ ← Gemini / OpenAI
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Response Parser  │ ← 워크아웃/플랜 파싱
└─────────┬─────────┘
          │
          ▼
     AI 응답
```

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/ai/chat` | 대화 메시지 전송 |
| POST | `/api/v1/ai/quick-chat` | 빠른 질문 (새 대화) |
| GET | `/api/v1/ai/conversations` | 대화 목록 |
| GET | `/api/v1/ai/conversations/{id}` | 대화 상세 |
| DELETE | `/api/v1/ai/conversations/{id}` | 대화 삭제 |
| POST | `/api/v1/ai/import` | 외부 플랜 가져오기 |
| GET | `/api/v1/ai/export` | 분석용 데이터 내보내기 |
| GET | `/api/v1/ai/coach/context` | 코치 컨텍스트 조회 |

## AI 제공자 설정

### Google Gemini (Primary)

```python
# config.py
GOOGLE_AI_API_KEY = "..."
GOOGLE_AI_MODEL = "gemini-2.5-flash-lite"
```

### OpenAI (Fallback)

```python
OPENAI_API_KEY = "..."
OPENAI_MODEL = "gpt-4o-mini"
```

### RAG 설정

```python
RAG_ENABLED = True
RAG_TOP_K = 3
RAG_MIN_SCORE = 0.3
```

## 응답 형식

### 일반 대화

```json
{
  "message": "오늘은 쉬운 러닝 8km를 권장합니다...",
  "suggestions": [
    "이번 주 훈련 스케줄 확인",
    "인터벌 훈련 추천받기"
  ]
}
```

### 훈련 계획

```json
{
  "plan": {
    "weeks": 12,
    "goal": "서브-4 마라톤",
    "phases": [
      {"name": "Base", "weeks": [1, 2, 3, 4]},
      {"name": "Build", "weeks": [5, 6, 7, 8]},
      {"name": "Peak", "weeks": [9, 10]},
      {"name": "Taper", "weeks": [11, 12]}
    ],
    "weekly_schedules": [...]
  }
}
```

### 워크아웃

```json
{
  "workout": {
    "name": "VO2max 인터벌",
    "type": "interval",
    "steps": [
      {"type": "warmup", "duration": "10min", "pace": "easy"},
      {"type": "repeat", "count": 5, "steps": [
        {"type": "run", "distance": "1km", "pace": "interval"},
        {"type": "recovery", "duration": "2min"}
      ]},
      {"type": "cooldown", "duration": "10min", "pace": "easy"}
    ]
  }
}
```

## 훈련 원칙

### 주기화 (Periodization)

```
Base Phase (4주)
├── 유산소 기반 구축
├── 쉬운 러닝 80%
└── 장거리 러닝 도입

Build Phase (4주)
├── 훈련 강도 증가
├── 템포/역치 훈련 추가
└── 주간 거리 점진적 증가

Peak Phase (2주)
├── 레이스 페이스 훈련
├── 최대 훈련 부하
└── 인터벌 훈련 강화

Taper Phase (2주)
├── 훈련량 감소 (40-60%)
├── 강도 유지
└── 충분한 휴식
```

### 80/20 원칙

- **80%**: 쉬운 러닝 (Zone 1-2)
- **20%**: 질 높은 훈련 (Zone 3-5)

### 10% 규칙

- 주간 거리 증가는 10% 이내
- 급격한 부하 증가 방지

## 주의사항

### 1. AI 모델 필드명

```python
# ❌ 구버전 필드명
conversation.language
conversation.model
message.tokens

# ✅ 현재 필드명
conversation.context_type
conversation.context_data
message.token_count
```

### 2. 변수 섀도잉

```python
# ❌ FastAPI status 모듈 섀도잉
from fastapi import status
status = payload.get("status")  # 오류!

# ✅ 다른 변수명 사용
response_status = payload.get("status")
```

### 3. RAG 스코어 필터링

```python
# 낮은 점수의 문서는 제외
results = [r for r in rag_results if r.score >= RAG_MIN_SCORE]
```

## RAG 인덱스 빌드

```bash
# 지식 베이스 인덱스 생성
cd backend
source .venv/bin/activate
python scripts/build_knowledge_index.py
```

## 테스트

```bash
# AI 엔드포인트 테스트
pytest tests/test_ai.py -v

# RAG 시스템 테스트
pytest tests/test_knowledge.py -v
```

## 관련 문서

- [Google AI 문서](https://ai.google.dev/docs)
- [Jack Daniels Running Formula](https://runsmartproject.com/)
- [debug-patterns.md #57-58](../docs/debug-patterns.md) - AI 관련 이슈
