# Strava Connector Agent

Strava와의 연동을 담당하는 전문가 에이전트입니다.

## 역할

- Strava OAuth 인증 관리
- 활동 업로드 (자동/수동)
- 업로드 실패 시 재시도 관리
- Strava 토큰 갱신

## 담당 파일

```
backend/
├── app/
│   ├── api/v1/endpoints/
│   │   └── strava.py              # 핵심 - Strava API
│   ├── services/
│   │   └── strava_upload.py       # 업로드 서비스
│   ├── workers/
│   │   └── strava_worker.py       # Arq 비동기 워커
│   └── models/
│       └── strava.py              # Strava OAuth 모델
└── alembic/versions/
    └── 014_add_strava_upload_jobs.py
```

## 주요 기능

### 1. OAuth 인증

```python
# OAuth 흐름
async def initiate_oauth() -> str:
    """
    Strava OAuth 시작
    Returns: authorization_url (사용자 리다이렉트용)
    """

async def handle_callback(code: str, state: str) -> StravaToken:
    """
    OAuth 콜백 처리
    - 인증 코드로 토큰 교환
    - 토큰 저장 (암호화)
    """

async def refresh_token(user_id: int) -> StravaToken:
    """
    만료된 토큰 갱신
    - 자동으로 refresh_token 사용
    """
```

### 2. 활동 업로드

```python
# 활동 업로드
async def upload_activity(
    user_id: int,
    activity_id: int,
) -> StravaUploadResult:
    """
    활동을 Strava에 업로드

    Process:
    1. FIT 파일 로드
    2. Strava API 호출
    3. 업로드 상태 추적
    4. 실패 시 재시도 큐 등록
    """
```

### 3. 자동 업로드

```python
# 새 활동 동기화 시 자동 업로드
async def auto_upload_new_activities(
    user_id: int,
    activities: list[Activity],
) -> list[StravaUploadResult]:
    """
    STRAVA_AUTO_UPLOAD=true 설정 시
    새로 동기화된 활동 자동 업로드
    """
```

### 4. 재시도 큐

```python
# Arq 기반 재시도
async def enqueue_upload(
    activity_id: int,
    retry_count: int = 0,
) -> str:
    """
    업로드 작업을 큐에 등록

    재시도 전략:
    - 1차 실패: 1분 후 재시도
    - 2차 실패: 5분 후 재시도
    - 3차 실패: 30분 후 재시도
    - 4차 실패: 2시간 후 재시도
    - 5차 실패: 실패 처리
    """
```

## 데이터 흐름

```
활동 동기화 완료
        │
        ▼
┌───────────────────┐
│  Auto Upload?     │ ← STRAVA_AUTO_UPLOAD 설정 확인
└─────────┬─────────┘
          │ Yes
          ▼
┌───────────────────┐
│   Enqueue Job     │ ← Arq 큐에 작업 등록
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Strava Worker    │ ← 백그라운드 워커
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Strava API       │ ← 파일 업로드
└─────────┬─────────┘
          │
    ┌─────┴─────┐
    ▼           ▼
Success      Failure
    │           │
    ▼           ▼
Update DB   Retry Queue
```

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/v1/strava/auth` | OAuth 시작 |
| GET | `/api/v1/strava/callback` | OAuth 콜백 |
| GET | `/api/v1/strava/status` | 연결 상태 |
| POST | `/api/v1/strava/disconnect` | 연결 해제 |
| POST | `/api/v1/strava/upload/{activity_id}` | 수동 업로드 |
| GET | `/api/v1/strava/uploads` | 업로드 이력 |
| GET | `/api/v1/strava/uploads/pending` | 대기 중 업로드 |

## 데이터 모델

### StravaToken

```python
class StravaToken(Base):
    user_id: int
    access_token: str      # 암호화 저장
    refresh_token: str     # 암호화 저장
    expires_at: datetime
    athlete_id: int
```

### StravaUploadJob

```python
class StravaUploadJob(Base):
    id: int
    activity_id: int
    status: str            # pending, processing, completed, failed
    strava_activity_id: int | None
    error_message: str | None
    retry_count: int
    created_at: datetime
    completed_at: datetime | None
```

## 설정

### 환경 변수

```bash
# Strava API 자격 증명
STRAVA_CLIENT_ID=12345
STRAVA_CLIENT_SECRET=xxxxx

# 자동 업로드 설정
STRAVA_AUTO_UPLOAD=true

# 워커 설정
ARQ_REDIS_URL=redis://localhost:6379/0
```

### 재시도 설정

```python
RETRY_DELAYS = [
    60,      # 1분
    300,     # 5분
    1800,    # 30분
    7200,    # 2시간
]
MAX_RETRIES = 4
```

## OAuth 흐름

```
사용자                  RunningCoach              Strava
  │                         │                       │
  │ "Strava 연결"           │                       │
  │─────────────────────────>                       │
  │                         │                       │
  │  redirect to Strava     │                       │
  │<─────────────────────────                       │
  │                         │                       │
  │ 로그인 & 권한 승인     │                       │
  │─────────────────────────────────────────────────>
  │                         │                       │
  │         callback with code                      │
  │<─────────────────────────────────────────────────
  │                         │                       │
  │ code                    │                       │
  │─────────────────────────>                       │
  │                         │                       │
  │                         │  exchange code        │
  │                         │──────────────────────>│
  │                         │                       │
  │                         │     tokens            │
  │                         │<──────────────────────│
  │                         │                       │
  │ "연결 완료"             │                       │
  │<─────────────────────────                       │
```

## 에러 처리

### OAuth 오류

```python
try:
    token = await exchange_code(code)
except StravaAuthError as e:
    if e.error == "invalid_grant":
        # 인증 코드 만료 또는 이미 사용됨
        raise HTTPException(400, "인증이 만료되었습니다. 다시 시도해주세요.")
```

### 업로드 오류

```python
try:
    await upload_to_strava(activity_id)
except StravaRateLimitError:
    # API 제한 - 재시도 큐 등록
    await enqueue_upload(activity_id, delay=300)
except StravaDuplicateError:
    # 이미 업로드된 활동
    job.status = "completed"
    job.error_message = "이미 Strava에 존재하는 활동입니다"
```

## 주의사항

### 1. OAuth State 저장

```python
# ❌ 단일 워커에서만 동작
_pending_states = {}  # 메모리 저장

# ✅ 프로덕션 - Redis 사용
async def store_state(state: str, data: dict):
    await redis.setex(f"strava_state:{state}", 600, json.dumps(data))
```

### 2. 토큰 만료 처리

```python
# 토큰 사용 전 만료 확인
async def get_valid_token(user_id: int) -> str:
    token = await get_token(user_id)
    if token.expires_at < datetime.utcnow():
        token = await refresh_token(user_id)
    return token.access_token
```

### 3. 동시 업로드 제한

```python
# 동시 업로드 수 제한
MAX_CONCURRENT_UPLOADS = 3
```

## 워커 실행

```bash
# Strava 업로드 워커 실행
cd backend
source .venv/bin/activate
arq app.workers.strava_worker.WorkerSettings
```

## 테스트

```bash
# Strava 연동 테스트
pytest tests/test_strava.py -v

# 업로드 서비스 테스트
pytest tests/test_strava_upload.py -v
```

## 관련 문서

- [Strava API 문서](https://developers.strava.com/docs/reference/)
- [stravalib 라이브러리](https://github.com/stravalib/stravalib)
- [debug-patterns.md #33](../../docs/debug-patterns.md) - OAuth state 이슈
