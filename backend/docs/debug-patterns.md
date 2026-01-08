# Debug Patterns - RunningCoach

이 문서는 프로젝트에서 발견한 버그 패턴과 해결책을 기록합니다.

## 목차
- [설정 관리](#설정-관리)
- [성능 최적화](#성능-최적화)
- [외부 API 통합](#외부-api-통합)

---

## 설정 관리

### 1. 하드코딩된 설정값을 config로 이동

**문제**: 설정값이 코드 곳곳에 하드코딩되어 환경별 설정 불가능

**잘못된 패턴**:
```python
# ❌ 하드코딩
DEFAULT_MAX_DISTANCE_METERS = 800_000  # gear.py
SAMPLE_LIMIT = 5000  # ai_coach.py
ALL_TIME_START_YEAR = 2006  # ai_snapshot.py
timeout=60.0  # strava_upload.py
```

**올바른 패턴**:
```python
# ✅ config.py에 중앙화
class Settings(BaseSettings):
    gear_default_max_distance_meters: int = 800_000
    ai_sample_limit: int = 5000
    ai_snapshot_all_time_start_year: int = 2006
    strava_http_timeout_seconds: int = 60

# 사용
settings = get_settings()
max_distance = settings.gear_default_max_distance_meters
```

**적용 위치**:
- `backend/app/core/config.py`
- `backend/app/api/v1/endpoints/gear.py`
- `backend/app/api/v1/endpoints/ai_coach.py`
- `backend/app/services/ai_snapshot.py`
- `backend/app/services/strava_upload.py`
- `backend/.env.example`

---

## 성능 최적화

### 2. RAG 검색 결과 캐싱

**문제**: 동일한 쿼리 반복 시 임베딩 API 호출 및 벡터 검색 반복

**올바른 패턴**:
```python
# ✅ TTL 기반 캐싱
def __init__(self):
    self._cache: dict = {}

async def search(query: str, top_k: int = 3):
    cache_key = (query, top_k, min_score)
    if cache_key in self._cache:
        timestamp, results = self._cache[cache_key]
        if time.time() - timestamp < TTL:
            return results
    results = await self._do_search(query, top_k)
    self._cache[cache_key] = (time.time(), results)
    return results
```

**적용 위치**: `backend/app/knowledge/retriever.py`

---

### 3. N+1 쿼리 해결 (Gear)

**문제**: 리스트 조회 시 각 항목마다 개별 쿼리

**올바른 패턴**:
```python
# ✅ 배치 쿼리
async def get_gear_stats_batch(gear_ids):
    result = await db.execute(
        select(gear_id, func.sum(distance), func.count())
        .where(gear_id.in_(gear_ids))
        .group_by(gear_id)
    )
    return {row.gear_id: (row.sum, row.count) for row in result}
```

**적용 위치**: `backend/app/api/v1/endpoints/gear.py`

---

## 외부 API 통합

### 4. Strava 토큰 자동 갱신

**문제**: 토큰 만료 시 수동 재로그인 필요

**올바른 패턴**:
```python
# ✅ 자동 갱신 (만료 5분 전)
async def _ensure_token_valid(session, db):
    buffer = timedelta(seconds=300)
    if datetime.now() >= session.expires_at - buffer:
        tokens = await refresh_token(session.refresh_token)
        session.access_token = tokens["access_token"]
        await db.commit()
```

**적용 위치**: `backend/app/api/v1/endpoints/strava.py`

---

### 5. Exponential Backoff 폴링

**문제**: 고정 간격 폴링으로 인한 네트워크 부하

**올바른 패턴**:
```python
# ✅ Exponential backoff
for attempt in range(max_attempts):
    if attempt > 0:
        delay = initial_delay * (2 ** (attempt - 1))
        await asyncio.sleep(delay)
    status = await check_status()
    if status == "complete":
        break
```

**적용 위치**: `backend/app/api/v1/endpoints/strava.py`

---

### 6. AI 응답 검증 강화

**문제**: AI 잘못된 응답 형식 에러 처리 없음

**올바른 패턴**:
```python
# ✅ 명확한 검증
status = data.get("status")
if not status:
    raise HTTPException(502, "Missing status field")
if status not in ("plan", "need_info"):
    raise HTTPException(502, f"Invalid status: {status}")
if status == "plan" and "plan" not in data:
    raise HTTPException(502, "Missing plan field")
```

**적용 위치**: `backend/app/api/v1/endpoints/ai.py`

---

*이 문서는 지속적으로 업데이트됩니다.*
