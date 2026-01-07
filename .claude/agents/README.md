# RunningCoach AI Agents

RunningCoach의 전문가 에이전트 시스템입니다.

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Orchestrator                               │
│                    (전체 작업 조율 및 위임)                          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
       ┌───────────────┬───────┴───────┬───────────────┐
       │               │               │               │
       ▼               ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   Garmin    │ │    Data     │ │   Strava    │ │  AI Coach   │
│  Connector  │ │   Manager   │ │  Connector  │ │             │
├─────────────┤ ├─────────────┤ ├─────────────┤ ├─────────────┤
│ - 동기화   │ │ - VDOT     │ │ - 업로드   │ │ - 훈련계획 │
│ - 워크아웃 │ │ - 분석     │ │ - OAuth    │ │ - RAG      │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

**에이전트 협업**:
- 동기화: Garmin Connector → Data Manager → Strava Connector
- 훈련 계획: Data Manager → AI Coach
- 워크아웃 푸시: AI Coach → Garmin Connector

## 에이전트 목록

| 에이전트 | 파일 | 역할 |
|---------|------|------|
| **Orchestrator** | [orchestrator.md](orchestrator.md) | 전체 작업 조율 |
| **Garmin Connector** | [garmin-connector.md](garmin-connector.md) | Garmin 연동 |
| **Data Manager** | [data-manager.md](data-manager.md) | 데이터 처리/분석 |
| **Strava Connector** | [strava-connector.md](strava-connector.md) | Strava 연동 |
| **AI Coach** | [ai-coach.md](ai-coach.md) | 훈련 계획 생성 |

## 작업 흐름 예시

### 1. 데이터 동기화

```
User: "Garmin 동기화해줘"
  │
  ▼
Orchestrator
  │
  ├─1→ Garmin Connector: 데이터 가져오기
  │
  ├─2→ Data Manager: 파싱 및 저장
  │
  └─3→ Strava Connector: 자동 업로드 (설정 시)
```

### 2. 훈련 계획 생성

```
User: "12주 마라톤 훈련 계획 세워줘"
  │
  ▼
Orchestrator
  │
  ├─1→ Data Manager: 사용자 데이터 조회
  │
  └─2→ AI Coach: 훈련 계획 생성
```

### 3. 워크아웃 푸시

```
User: "인터벌 워크아웃 만들어서 Garmin으로 보내줘"
  │
  ▼
Orchestrator
  │
  ├─1→ AI Coach: 워크아웃 설계
  │
  └─2→ Garmin Connector: Garmin 전송
```

## 에이전트 활용 방법

### Claude Code Slash Commands

에이전트 기능은 slash command로 구현되어 있습니다:

```bash
/sync          # Garmin 동기화 (garmin-connector)
/plan          # 훈련 계획 생성 (ai-coach)
/workout       # 워크아웃 설계 (ai-coach + garmin-connector)
/upload        # Strava 업로드 (strava-connector)
```

### AI 에이전트 참조

Claude Code가 작업할 때 해당 에이전트 문서를 참조합니다:

```
"Garmin 동기화해줘"
  → garmin-connector.md 참조하여 작업 수행

"12주 마라톤 훈련 계획 세워줘"
  → ai-coach.md 참조하여 작업 수행
```

## 에이전트 간 통신

### 요청 형식

```json
{
  "agent": "garmin-connector",
  "action": "sync_activities",
  "params": {
    "user_id": 1,
    "days": 7
  }
}
```

### 응답 형식

```json
{
  "status": "success",
  "agent": "garmin-connector",
  "result": {
    "activities_synced": 5
  },
  "next_action": {
    "agent": "data-manager",
    "action": "process_activities"
  }
}
```

## 담당 영역

### Garmin Connector

- `backend/app/adapters/garmin_adapter.py`
- `backend/app/services/sync_service.py`
- `backend/app/api/v1/endpoints/ingest.py`

### Data Manager

- `backend/app/services/dashboard.py`
- `backend/app/services/vdot.py`
- `backend/app/api/v1/endpoints/dashboard.py`
- `backend/app/api/v1/endpoints/activities.py`

### Strava Connector

- `backend/app/api/v1/endpoints/strava.py`
- `backend/app/services/strava_upload.py`
- `backend/app/workers/strava_worker.py`

### AI Coach

- `backend/app/api/v1/endpoints/ai.py`
- `backend/app/knowledge/`
- `backend/app/core/ai_constants.py`

## 추가 정보

각 에이전트의 상세 문서를 참조하세요:

- [Orchestrator](orchestrator.md) - 작업 흐름, 의사결정 로직
- [Garmin Connector](garmin-connector.md) - API, 인증, 동기화
- [Data Manager](data-manager.md) - VDOT, 피트니스 지표, 분석
- [Strava Connector](strava-connector.md) - OAuth, 업로드, 재시도
- [AI Coach](ai-coach.md) - RAG, 훈련 계획, 프롬프트
