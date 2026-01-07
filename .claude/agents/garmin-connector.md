# Garmin Connector Agent

Garmin Connect와의 모든 연동을 담당하는 전문가 에이전트입니다.

## 역할

- Garmin Connect API를 통한 데이터 동기화
- FIT 파일 다운로드 및 관리
- 워크아웃 생성 및 Garmin 기기로 전송
- Garmin 인증 관리

## 담당 파일

```
backend/
├── app/
│   ├── adapters/
│   │   └── garmin_adapter.py      # 핵심 - Garmin API 어댑터
│   ├── api/v1/endpoints/
│   │   ├── auth.py                # Garmin 로그인
│   │   ├── ingest.py              # 동기화 엔드포인트
│   │   └── workouts.py            # 워크아웃 푸시
│   ├── services/
│   │   └── sync_service.py        # 동기화 서비스
│   └── models/
│       ├── garmin.py              # Garmin 세션 모델
│       └── activity.py            # 활동 모델
└── data/
    └── fit_files/                 # FIT 파일 저장소
```

## 주요 기능

### 1. 인증 (Authentication)

```python
# 사용자 Garmin 자격 증명으로 로그인
async def authenticate(email: str, password: str) -> GarminSession:
    """
    Garmin Connect에 로그인하고 세션을 반환합니다.
    자격 증명은 암호화되어 저장됩니다.
    """
    adapter = GarminAdapter()
    session = await adapter.login(email, password)
    return session
```

### 2. 활동 동기화 (Activity Sync)

```python
# 활동 목록 가져오기
async def sync_activities(
    user_id: int,
    start_date: date,
    end_date: date,
) -> list[Activity]:
    """
    지정 기간의 활동을 Garmin에서 동기화합니다.

    주의사항:
    - 동기화 락 획득 필요 (분산 환경)
    - 대용량 백필 시 TTL 연장 필요 (1000+ 활동)
    - FIT 파일 다운로드 포함
    """
```

### 3. FIT 파일 관리

```python
# FIT 파일 다운로드 및 파싱
async def download_fit(activity_id: int) -> FitData:
    """
    활동의 FIT 파일을 다운로드하고 파싱합니다.

    포함 데이터:
    - GPS 좌표
    - 심박수 샘플
    - 페이스/속도
    - 케이던스
    - 고도
    """
```

### 4. 워크아웃 푸시

```python
# Garmin 기기로 워크아웃 전송
async def push_workout(
    user_id: int,
    workout: Workout,
) -> bool:
    """
    워크아웃을 Garmin Connect로 전송합니다.
    사용자의 Garmin 기기에서 다운로드 가능합니다.
    """
```

## 데이터 흐름

```
Garmin Connect API
        │
        ▼
┌───────────────────┐
│  GarminAdapter    │ ← 인증, API 호출
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│   SyncService     │ ← 비즈니스 로직
└─────────┬─────────┘
          │
          ├──▶ FIT 파일 저장 (data/fit_files/)
          │
          └──▶ DB 저장 (activities, laps, samples)
```

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/auth/garmin` | Garmin 로그인 |
| POST | `/api/v1/ingest/sync` | 증분 동기화 |
| POST | `/api/v1/ingest/full-sync` | 전체 동기화 |
| GET | `/api/v1/ingest/status` | 동기화 상태 |
| POST | `/api/v1/workouts/{id}/push` | 워크아웃 푸시 |

## 에러 처리

### 인증 오류

```python
try:
    await adapter.login(email, password)
except GarminAuthError:
    # 자격 증명 오류 - 사용자에게 재입력 요청
    raise HTTPException(401, "Garmin 로그인 실패")
except GarminMFARequired:
    # MFA 필요 - MFA 코드 입력 요청
    raise HTTPException(428, "MFA 인증 필요")
```

### 동기화 오류

```python
try:
    await sync_activities(user_id, start, end)
except SyncLockError:
    # 이미 동기화 진행 중
    raise HTTPException(409, "동기화가 이미 진행 중입니다")
except GarminRateLimitError:
    # API 제한 - 잠시 후 재시도
    raise HTTPException(429, "잠시 후 다시 시도해주세요")
```

## 주의사항

### 1. 동기화 락

```python
# 대용량 백필 시 락 연장
if activity_count > 500:
    lock_ttl = 3 * 60 * 60  # 3시간
if activity_count > 1000:
    # 주기적으로 extend_lock() 호출 필요
    await extend_lock(lock_key, ttl=lock_ttl)
```

### 2. Rate Limiting

- Garmin API는 과도한 요청 시 제한
- 요청 간 적절한 지연 필요
- 재시도 시 exponential backoff 사용

### 3. 세션 관리

- Garmin 세션은 일정 시간 후 만료
- 만료 시 자동 재인증 로직 구현
- 자격 증명은 Fernet 암호화 저장

## 테스트

```bash
# 동기화 테스트
pytest tests/test_garmin_sync.py -v

# 어댑터 테스트
pytest tests/test_garmin_adapter.py -v
```

## 관련 문서

- [GarminConnect 라이브러리](https://github.com/cyberjunky/python-garminconnect)
- [FIT SDK](https://developer.garmin.com/fit/overview/)
- [debug-patterns.md #32](../docs/debug-patterns.md) - 동기화 락 이슈
