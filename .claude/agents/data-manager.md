# Data Manager Agent

불러온 데이터를 처리, 분석, 저장하는 전문가 에이전트입니다.

## 역할

- 원시 데이터 파싱 및 변환
- 통계 및 분석 지표 계산
- 데이터베이스 CRUD 작업
- 대시보드 데이터 집계

## 담당 파일

```
backend/
├── app/
│   ├── services/
│   │   ├── dashboard.py           # 핵심 - 대시보드 분석
│   │   ├── vdot.py               # VDOT 계산
│   │   └── ai_snapshot.py        # AI 스냅샷
│   ├── api/v1/endpoints/
│   │   ├── dashboard.py          # 대시보드 API
│   │   ├── activities.py         # 활동 API
│   │   ├── analytics.py          # 분석 API
│   │   └── health.py             # 건강 데이터 API
│   └── models/
│       ├── activity.py           # 활동, 랩, 샘플
│       ├── health.py             # 수면, HR, 건강 지표
│       └── analytics.py          # PR, 비교 데이터
└── scripts/
    └── check_schema.py           # 스키마 검증
```

## 주요 기능

### 1. VDOT 계산

```python
# Jack Daniels 공식 기반 VDOT 계산
def calculate_vdot(
    distance_meters: float,
    time_seconds: float,
) -> VDOTResult:
    """
    레이스/타임 트라이얼 결과로 VDOT 계산

    Returns:
        vdot: 계산된 VDOT 값
        training_paces: 훈련 페이스 존
            - easy: 쉬운 러닝
            - marathon: 마라톤 페이스
            - threshold: 역치 페이스
            - interval: 인터벌 페이스
            - repetition: 반복 페이스
    """
```

### 2. 피트니스 지표 계산

```python
# CTL/ATL/TSB 계산 (EMA 기반)
def calculate_fitness_metrics(
    activities: list[Activity],
) -> FitnessMetrics:
    """
    훈련 부하 지표 계산

    CTL (Chronic Training Load): 장기 체력 (42일 EMA)
    ATL (Acute Training Load): 단기 피로 (7일 EMA)
    TSB (Training Stress Balance): CTL - ATL (컨디션)

    좋은 TSB: +10 ~ -10
    피로 상태: < -20
    신선한 상태: > +20
    """
```

### 3. HR 존 계산

```python
# 표준 5존 HRR 방식
def calculate_hr_zones(
    max_hr: int,
    resting_hr: int,
) -> list[HRZone]:
    """
    심박 존 계산 (Heart Rate Reserve 방식)

    Zone 1: 50-60% HRR (회복)
    Zone 2: 60-70% HRR (유산소)
    Zone 3: 70-80% HRR (템포)
    Zone 4: 80-90% HRR (역치)
    Zone 5: 90-100% HRR (최대)
    """
```

### 4. 활동별 HR 존 분포

```python
# 활동 중 각 HR 존에서 보낸 시간
def calculate_hr_zone_distribution(
    samples: list[ActivitySample],
    zones: list[HRZone],
) -> dict[int, timedelta]:
    """
    활동의 HR 존 분포 계산

    Returns:
        {
            1: timedelta(minutes=5),   # Zone 1
            2: timedelta(minutes=20),  # Zone 2
            3: timedelta(minutes=15),  # Zone 3
            4: timedelta(minutes=8),   # Zone 4
            5: timedelta(minutes=2),   # Zone 5
        }
    """
```

### 5. 대시보드 요약

```python
# 대시보드 요약 데이터 생성
async def get_dashboard_summary(
    user_id: int,
    period: str = "week",
) -> DashboardSummary:
    """
    대시보드 요약 생성

    Returns:
        - total_distance: 총 거리
        - total_duration: 총 시간
        - activity_count: 활동 수
        - avg_pace: 평균 페이스
        - fitness_metrics: CTL/ATL/TSB
        - training_paces: 훈련 페이스
        - recent_activities: 최근 활동
    """
```

## 데이터 파이프라인

```
원시 데이터 (FIT, API)
        │
        ▼
┌───────────────────┐
│   Data Parsing    │ ← fitparse, JSON 파싱
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  Transformation   │ ← 단위 변환, 정규화
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│    Calculation    │ ← VDOT, CTL/ATL, HR존
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│    Storage        │ ← PostgreSQL, TimescaleDB
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│   Aggregation     │ ← 대시보드, 트렌드
└───────────────────┘
```

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/v1/dashboard/summary` | 대시보드 요약 |
| GET | `/api/v1/dashboard/trends` | 트렌드 데이터 |
| GET | `/api/v1/dashboard/calendar` | 캘린더 데이터 |
| GET | `/api/v1/activities` | 활동 목록 |
| GET | `/api/v1/activities/{id}` | 활동 상세 |
| GET | `/api/v1/activities/{id}/samples` | 활동 샘플 |
| GET | `/api/v1/activities/{id}/hr-zones` | HR 존 분포 |
| GET | `/api/v1/analytics/records` | 개인 기록 |
| GET | `/api/v1/analytics/compare` | 기간 비교 |

## 데이터 모델

### Activity

```python
class Activity(Base):
    id: int
    user_id: int
    garmin_activity_id: int
    name: str
    sport_type: str
    start_time: datetime
    duration: timedelta
    distance: float  # meters
    avg_hr: int | None
    max_hr: int | None
    avg_pace: float | None  # sec/km
    calories: int | None
    elevation_gain: float | None
```

### ActivitySample (TimescaleDB)

```python
class ActivitySample(Base):
    activity_id: int
    timestamp: datetime
    heart_rate: int | None
    speed: float | None
    cadence: int | None
    altitude: float | None
    latitude: float | None
    longitude: float | None
```

## 계산 공식

### VDOT (Daniels-Gilbert)

```python
# 시간(분) → VDOT
def time_to_vdot(distance_m: float, time_min: float) -> float:
    velocity = distance_m / time_min  # m/min
    percent_max = (
        0.8 + 0.1894393 * exp(-0.012778 * time_min)
        + 0.2989558 * exp(-0.1932605 * time_min)
    )
    vo2 = -4.60 + 0.182258 * velocity + 0.000104 * velocity**2
    return vo2 / percent_max
```

### 훈련 페이스

```python
# VDOT → 훈련 페이스 (min/km)
PACE_FACTORS = {
    "easy": 0.65,      # 65% vVO2max
    "marathon": 0.79,  # 79% vVO2max
    "threshold": 0.88, # 88% vVO2max
    "interval": 0.98,  # 98% vVO2max
    "repetition": 1.05, # 105% vVO2max
}
```

### CTL/ATL (EMA)

```python
# Exponential Moving Average
def ema(values: list[float], days: int) -> float:
    alpha = 2 / (days + 1)
    result = values[0]
    for value in values[1:]:
        result = alpha * value + (1 - alpha) * result
    return result

ctl = ema(daily_tss, 42)  # 42일 EMA
atl = ema(daily_tss, 7)   # 7일 EMA
tsb = ctl - atl
```

## 주의사항

### 1. 시간 포맷팅

```python
# ❌ 잘못된 패턴
secs = round(seconds % 60)  # 59.5 → 60!

# ✅ 올바른 패턴
total_secs = round(seconds)
secs = total_secs % 60
```

### 2. 기간 계산

```python
# ❌ Exclusive end date
end_date = start_date + timedelta(days=weeks * 7)  # 1일 초과

# ✅ Inclusive end date
end_date = start_date + timedelta(days=weeks * 7 - 1)
```

### 3. Nullable 처리

```python
# avg_hr이 None일 수 있음
hr_str = f"{avg_hr}bpm" if avg_hr else "N/A"
```

## 테스트

```bash
# VDOT 계산 테스트
pytest tests/test_vdot.py -v

# 대시보드 서비스 테스트
pytest tests/test_dashboard.py -v
```

## 관련 문서

- [Jack Daniels VDOT 공식](https://runsmartproject.com/calculator/)
- [debug-patterns.md](../../docs/debug-patterns.md) - HR 존, 시간 포맷팅 이슈
