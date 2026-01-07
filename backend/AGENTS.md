# Backend AGENTS.md - 백엔드 개발 규칙

FastAPI 백엔드 개발 시 AI 에이전트가 따라야 할 규칙입니다.

---

## 디렉토리 구조

```
backend/
├── app/
│   ├── api/v1/
│   │   ├── router.py          # 메인 라우터 (모든 엔드포인트 등록)
│   │   └── endpoints/         # 개별 엔드포인트 모듈
│   │       ├── activities.py  # 활동 API
│   │       ├── ai.py          # AI 대화 API
│   │       ├── auth.py        # 인증 API
│   │       ├── dashboard.py   # 대시보드 API
│   │       ├── workouts.py    # 워크아웃 API
│   │       └── ...
│   ├── models/                # SQLAlchemy 모델 (DB 스키마 정의)
│   │   ├── user.py
│   │   ├── activity.py
│   │   ├── ai.py
│   │   └── ...
│   ├── schemas/               # Pydantic 스키마 (API 요청/응답)
│   ├── services/              # 비즈니스 로직
│   │   ├── sync_service.py    # Garmin 동기화
│   │   ├── dashboard.py       # 대시보드 분석
│   │   ├── vdot.py           # VDOT 계산
│   │   └── ...
│   ├── adapters/              # 외부 서비스 어댑터
│   │   └── garmin_adapter.py  # Garmin Connect API
│   ├── knowledge/             # RAG 시스템
│   ├── workers/               # Arq 비동기 워커
│   └── core/                  # 핵심 설정
│       ├── config.py          # Pydantic Settings
│       ├── database.py        # SQLAlchemy 설정
│       ├── security.py        # 인증/암호화
│       └── session.py         # Redis 세션
├── alembic/                   # DB 마이그레이션
├── scripts/                   # 유틸리티 스크립트
└── tests/                     # 테스트
```

---

## 필수 규칙

### 1. 모델 변경 시

```bash
# 1. 모델 수정 후 마이그레이션 생성
alembic revision --autogenerate -m "설명"

# 2. 마이그레이션 적용
alembic upgrade head

# 3. 스키마 검증
python scripts/check_schema.py --fix
```

**주의**: 모델과 마이그레이션이 불일치하면 런타임 오류 발생

### 2. API 엔드포인트 추가 시

```python
# 1. schemas/에 요청/응답 스키마 정의
class CreateWorkoutRequest(BaseModel):
    name: str
    steps: list[WorkoutStepCreate]

class WorkoutResponse(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)

# 2. endpoints/에 라우터 정의
@router.post("/", response_model=WorkoutResponse)
async def create_workout(
    request: CreateWorkoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkoutResponse:
    ...

# 3. router.py에 라우터 등록
api_router.include_router(workouts.router, prefix="/workouts", tags=["workouts"])
```

### 3. 서비스 로직 작성 시

```python
# services/는 순수 비즈니스 로직만 포함
# HTTP 관련 코드 금지 (Request, Response 등)

async def calculate_vdot(
    db: AsyncSession,
    user_id: int,
    race_distance: float,
    race_time: timedelta,
) -> VDOTResult:
    """VDOT 계산 서비스"""
    # 비즈니스 로직만
    ...
```

---

## 타입 규칙

### 필수 타입 힌트

```python
# ✅ 올바른 패턴
async def get_user_activities(
    db: AsyncSession,
    user_id: int,
    limit: int = 10,
    offset: int = 0,
) -> list[Activity]:
    ...

# ❌ 잘못된 패턴
async def get_user_activities(db, user_id, limit=10, offset=0):
    ...
```

### Nullable 처리

```python
# ✅ 올바른 패턴
async def get_user(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()

# 호출 시 None 체크
user = await get_user(db, user_id)
if user is None:
    raise HTTPException(status_code=404, detail="User not found")
```

---

## 데이터베이스 패턴

### 쿼리 작성

```python
# ✅ SQLAlchemy 2.0 스타일
from sqlalchemy import select
from sqlalchemy.orm import selectinload

stmt = (
    select(Activity)
    .where(Activity.user_id == user_id)
    .options(selectinload(Activity.laps))
    .order_by(Activity.start_time.desc())
    .limit(limit)
)
result = await db.execute(stmt)
activities = result.scalars().all()

# ❌ 1.x 스타일 (사용 금지)
activities = db.query(Activity).filter(Activity.user_id == user_id).all()
```

### 트랜잭션 처리

```python
# 자동 커밋 (대부분의 경우)
async with db.begin():
    db.add(new_activity)
    # 블록 종료 시 자동 커밋

# 명시적 커밋이 필요한 경우
db.add(new_activity)
await db.commit()
await db.refresh(new_activity)
```

---

## 외부 API 연동

### httpx 사용 시 주의사항

```python
# ❌ 잘못된 패턴 - leading slash가 base_url을 덮어씀
async with httpx.AsyncClient(base_url="https://api.example.com/v1") as client:
    response = await client.get("/users")  # https://api.example.com/users 로 요청됨!

# ✅ 올바른 패턴
async with httpx.AsyncClient(base_url="https://api.example.com/v1/") as client:
    response = await client.get("users")  # 슬래시 없이
```

### 재시도 로직

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def fetch_garmin_data(...):
    ...
```

---

## 인증 패턴

### 현재 사용자 가져오기

```python
from app.core.session import get_current_user

@router.get("/me")
async def get_me(user: User = Depends(get_current_user)) -> UserResponse:
    return user
```

### 선택적 인증

```python
from app.core.session import get_current_user_optional

@router.get("/public")
async def public_endpoint(
    user: User | None = Depends(get_current_user_optional),
) -> Response:
    if user:
        # 로그인된 사용자
    else:
        # 비로그인 사용자
```

---

## 자주 발생하는 실수

### 1. AI 모델 필드명 불일치

```python
# ❌ 잘못된 필드명 (구버전)
class AIConversation(Base):
    language: str
    model: str
    tokens: int

# ✅ 올바른 필드명 (현재)
class AIConversation(Base):
    context_type: str
    context_data: dict

class AIMessage(Base):
    token_count: int  # tokens가 아님
```

### 2. 동기화 락 TTL

```python
# 대용량 백필 시 락 연장 필요
if activity_count > 1000:
    await extend_lock(lock_key, ttl=10800)  # 3시간
```

### 3. HR 존 계산

```python
# 표준 5존 HRR 방식
ZONE_PERCENTAGES = [
    (0.50, 0.60),  # Zone 1
    (0.60, 0.70),  # Zone 2
    (0.70, 0.80),  # Zone 3
    (0.80, 0.90),  # Zone 4
    (0.90, 1.00),  # Zone 5
]
```

---

## 테스트

```bash
# 전체 테스트
pytest

# 특정 테스트
pytest tests/test_vdot.py -v

# 커버리지
pytest --cov=app tests/
```

---

## 환경 설정

```bash
# 가상환경 활성화 필수
source .venv/bin/activate

# 개발 서버
uvicorn app.main:app --reload --port 8000

# 타입 체크
mypy app/

# 린팅
ruff check .
black app/
```

---

## 참조

- `core/config.py` - 모든 설정값
- `core/ai_constants.py` - AI 시스템 프롬프트
- `../docs/debug-patterns.md` - 버그 패턴 기록
- `../docs/api-reference.md` - API 문서
