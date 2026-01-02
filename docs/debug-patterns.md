# Debug Patterns & Common Issues

이 문서는 RunningCoach 프로젝트에서 발견된 버그 패턴과 해결책을 기록합니다.
새로운 코드 리뷰나 디버깅 시 참고하세요.

---

## Frontend (React + TypeScript)

### 1. Math.round 60초 오버플로우

**문제**: 시간 포맷팅에서 `Math.round(seconds % 60)`가 60을 반환할 수 있음

```typescript
// ❌ 잘못된 패턴
const min = Math.floor(seconds / 60);
const sec = Math.round(seconds % 60);  // 59.6 % 60 = 59.6 → round → 60 😱
return `${min}:${sec}`;  // "5:60" 출력!

// ✅ 올바른 패턴
const totalSeconds = Math.round(seconds);  // 먼저 반올림
const min = Math.floor(totalSeconds / 60);
const sec = totalSeconds % 60;  // 항상 0-59 범위
return `${min}:${String(sec).padStart(2, '0')}`;
```

**적용 위치**: `formatPace`, `formatDuration`, `formatPaceFromDecimal`

---

### 2. Invalid Date 미처리

**문제**: `new Date()`에 잘못된 문자열을 넣으면 `Invalid Date` 반환, 이후 연산에서 NaN 발생

```typescript
// ❌ 잘못된 패턴
function formatDate(dateStr: string): string {
  const date = new Date(dateStr);  // Invalid Date 가능
  return date.toLocaleDateString();  // "Invalid Date" 출력
}

// ✅ 올바른 패턴
function parseDate(dateStr: string | Date): Date | null {
  if (dateStr instanceof Date) {
    return isNaN(dateStr.getTime()) ? null : dateStr;
  }
  const date = new Date(dateStr);
  return isNaN(date.getTime()) ? null : date;
}

function formatDate(dateStr: string | Date): string {
  const date = parseDate(dateStr);
  if (!date) return '--';  // 안전한 폴백
  return date.toLocaleDateString();
}
```

---

### 3. 날짜 비교 시 타임존 드리프트

**문제**: `toDateString()` 비교는 로컬 타임존에서만 정확함

```typescript
// ❌ 잘못된 패턴 (UTC 시간대에서 오늘/어제 판단 오류 가능)
if (date.toDateString() === today.toDateString()) {
  return '오늘';
}

// ✅ 올바른 패턴
function isSameLocalDate(date1: Date, date2: Date): boolean {
  return (
    date1.getFullYear() === date2.getFullYear() &&
    date1.getMonth() === date2.getMonth() &&
    date1.getDate() === date2.getDate()
  );
}

if (isSameLocalDate(date, today)) {
  return '오늘';
}
```

---

### 4. Intl.DateTimeFormat 성능 최적화

**문제**: 매번 새 formatter 인스턴스 생성은 비효율적

```typescript
// ❌ 비효율적 (매 호출마다 인스턴스 생성)
function formatDateTime(date: Date) {
  return date.toLocaleDateString('ko-KR', { year: 'numeric', ... });
}

// ✅ 효율적 (캐시된 인스턴스 재사용)
const dateTimeFormatters = {
  full: new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  }),
  time: new Intl.DateTimeFormat('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }),
};

function formatDateTime(date: Date) {
  return dateTimeFormatters.full.format(date);
}
```

---

### 5. Mock 데이터 플래그 불일치

**문제**: 여러 hook에서 mock 데이터 플래그가 다르게 설정됨

```typescript
// ❌ 불일치 (파일마다 다른 방식)
// useDashboard.ts
const USE_MOCK_DATA = false;  // 하드코딩

// useRunalyze.ts
const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === 'true';

// ✅ 일관된 패턴
// 모든 파일에서 동일하게:
const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === 'true';
```

---

### 6. React Query invalidation 누락

**문제**: 관련 쿼리를 invalidate하지 않아 stale 데이터 표시

```typescript
// ❌ 누락된 패턴
export function useConnectGarmin() {
  return useMutation({
    mutationFn: authApi.connectGarmin,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['garmin-status'] });
      // sync status 업데이트 누락!
    },
  });
}

// ✅ 완전한 패턴
export function useConnectGarmin() {
  return useMutation({
    mutationFn: authApi.connectGarmin,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['garmin-status'] });
      queryClient.invalidateQueries({ queryKey: garminSyncKeys.all });  // 추가
    },
  });
}
```

---

### 7. API 응답 타입 불일치

**문제**: 백엔드 Pydantic 모델과 프론트엔드 TypeScript 타입 불일치

```typescript
// ❌ 백엔드에 있는 필드가 프론트엔드에 없음
// Backend (Pydantic)
class GarminConnectionStatus(BaseModel):
    connected: bool
    session_valid: bool  # 프론트엔드에 없음!
    last_login: str | None

// Frontend (TypeScript) - 누락된 필드
interface GarminConnectionStatus {
  connected: boolean;
  last_sync: string | null;
  // session_valid 누락!
}

// ✅ 일치하는 타입
interface GarminConnectionStatus {
  connected: boolean;
  session_valid: boolean;
  last_login: string | null;
  last_sync: string | null;
}
```

**점검 방법**:
1. Backend Pydantic 모델 확인
2. Frontend TypeScript 인터페이스와 비교
3. 누락된 필드 추가

---

## Backend (FastAPI + Python)

### 1. 라우터 문서 불일치

**문제**: router.py 상단 주석과 실제 엔드포인트 불일치

**점검 사항**:
- HTTP 메서드 (PUT vs PATCH)
- 경로 패턴 (`/{id}/schedule` vs `/schedules`)
- 존재하지 않는 엔드포인트 주석
- 문서화되지 않은 엔드포인트

**해결 방법**:
```bash
# 실제 라우트 추출
grep -r "@router\.(get|post|put|patch|delete)" backend/app/api/v1/endpoints/
```

---

### 2. HTTP 308 리다이렉트 호환성

**문제**: 일부 레거시 클라이언트가 308을 자동 추적하지 않음

```python
# aliases.py - 문서화 추가
"""
Note on 308 Redirects:
    HTTP 308 preserves the request method (POST stays POST, PUT stays PUT).
    Most modern HTTP clients (axios, fetch, requests) handle 308 automatically.
    If you encounter issues with older clients, consider using the canonical
    paths directly instead of relying on redirects.
"""
```

---

### 3. RFC 8594 Sunset Header 누락

**문제**: 폐기 예정 API에 Sunset 헤더가 없음

```python
# ❌ Sunset 헤더 누락
redirect.headers[DEPRECATION_HEADER] = "This endpoint is deprecated..."

# ✅ RFC 8594 준수
redirect.headers[DEPRECATION_HEADER] = "This endpoint is deprecated..."
redirect.headers[SUNSET_HEADER] = deprecation_date  # "2025-01-01"
```

---

### 4. CORS 빈 설정 시 무응답

**문제**: `CORS_ORIGINS`가 빈 문자열이면 모든 요청이 차단되지만 경고 없음

```python
# ❌ 조용한 실패
cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
# cors_origins = [] 이면 모든 CORS 요청 차단, 로그 없음

# ✅ 경고 로그 추가
if not cors_origins:
    logging.warning(
        "CORS_ORIGINS is empty or not configured. "
        "CORS will block all cross-origin requests."
    )
```

---

### 5. 보안 기본값 프로덕션 누출

**문제**: 환경변수 미설정 시 기본값이 프로덕션에서 그대로 사용됨

```python
# ❌ 경고만 출력하고 계속 실행
if settings.session_secret == "change-me-in-production":
    logger.warning("session_secret is using default value")
# 프로덕션에서 기본 시크릿으로 동작 - 보안 위험!

# ✅ 프로덕션에서는 에러 발생
_IS_PRODUCTION = os.environ.get("ENVIRONMENT", "").lower() in ("production", "prod")

if insecure_settings and _IS_PRODUCTION:
    raise InsecureConfigurationError(
        f"Insecure configuration detected: {insecure_settings}"
    )
# 프로덕션에서 앱 시작 자체가 차단됨
```

**적용 위치**: `config.py`, `get_settings()`

---

### 6. cookie_samesite 대소문자 오류

**문제**: Starlette는 소문자 `samesite` 값을 기대하는데 대문자로 설정됨

```python
# ❌ 잘못된 패턴 - Starlette에서 무시될 수 있음
cookie_samesite: str = "Lax"

# ✅ 올바른 패턴 - 소문자 사용
cookie_samesite: str = "lax"  # "lax", "strict", "none"
```

**적용 위치**: `config.py`

---

### 7. bcrypt 이벤트 루프 블로킹

**문제**: bcrypt 해시/검증이 CPU-intensive하여 async 엔드포인트에서 이벤트 루프 블로킹

```python
# ❌ 동기 함수가 이벤트 루프 블로킹
async def login(password: str):
    if bcrypt.checkpw(password, hash):  # 블로킹!
        ...

# ✅ threadpool에서 실행
async def verify_password_async(plain: str, hashed: str) -> bool:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _password_executor,
        verify_password,  # sync 함수
        plain,
        hashed,
    )

async def login(password: str):
    if await verify_password_async(password, hash):  # 논블로킹
        ...
```

**적용 위치**: `security.py`, `auth.py`

---

### 8. get_db 자동 커밋 오버헤드

**문제**: 읽기 전용 요청에서도 트랜잭션 커밋이 발생

```python
# ❌ 모든 요청에서 커밋
async def get_db():
    async with async_session_maker() as session:
        yield session
        await session.commit()  # GET 요청에서도 불필요한 커밋

# ✅ 명시적 커밋 (엔드포인트에서 직접 호출)
async def get_db():
    async with async_session_maker() as session:
        yield session
        # 커밋 없음 - 엔드포인트에서 명시적으로 호출

# 엔드포인트에서:
async def create_user(db: AsyncSession = Depends(get_db)):
    db.add(user)
    await db.commit()  # 명시적 커밋
```

**적용 위치**: `database.py`

---

### 9. Redis 클라이언트 미정리

**문제**: 앱 종료 시 Redis 커넥션이 닫히지 않아 누수 발생

```python
# ❌ 종료 시 정리 없음
_redis_client: Optional[redis.Redis] = None

async def get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(...)
    return _redis_client
# 앱 재시작/테스트 시 커넥션 누수

# ✅ 종료 시 정리
async def close_redis():
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None

# main.py lifespan에서 호출
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()  # 정리
```

**적용 위치**: `session.py`, `main.py`

---

### 10. 지도 배율 고정 문제

**문제**: 지도 초기 zoom 레벨이 고정되어 긴 경로가 한눈에 보이지 않음

```typescript
// ❌ 잘못된 패턴 - 고정 zoom 값
<Map
  initialViewState={{
    latitude: center.lat,
    longitude: center.lng,
    zoom: 14,  // 경로 길이와 무관하게 고정
  }}
>

// ✅ 올바른 패턴 - fitBounds로 경로 전체 표시
const mapRef = useRef<MapRef>(null);

const bounds = useMemo(() => {
  const lats = gpsPoints.map((p) => p.lat);
  const lngs = gpsPoints.map((p) => p.lng);
  return {
    minLng: Math.min(...lngs),
    maxLng: Math.max(...lngs),
    minLat: Math.min(...lats),
    maxLat: Math.max(...lats),
  };
}, [gpsPoints]);

const onMapLoad = useCallback(() => {
  if (mapRef.current && bounds) {
    mapRef.current.fitBounds(
      [[bounds.minLng, bounds.minLat], [bounds.maxLng, bounds.maxLat]],
      { padding: { top: 50, bottom: 50, left: 50, right: 50 }, duration: 0 }
    );
  }
}, [bounds]);

<Map ref={mapRef} onLoad={onMapLoad} ...>
```

**적용 위치**: `ActivityMap.tsx`

---

### 11. 메트릭 라벨 카디널리티 폭증

**문제**: 동적 값(URL, operation 이름)이 메트릭 라벨에 그대로 들어가면 시리즈가 무한 증가

```python
# ❌ 동적 값 그대로 사용 - 카디널리티 폭증
def observe_external_api(provider: str, operation: str, ...):
    self._external_counts[(provider, operation, status)] += 1
# operation이 URL이면 무한 증가

# ✅ 허용 목록으로 정규화
ALLOWED_OPERATIONS = frozenset({"login", "get_activities", "download_fit", ...})

def normalize_external_operation(operation: str) -> str:
    normalized = operation.lower().replace("-", "_")
    return normalized if normalized in ALLOWED_OPERATIONS else "other"

def observe_external_api(provider: str, operation: str, ...):
    normalized_op = normalize_external_operation(operation)
    self._external_counts[(provider, normalized_op, status)] += 1
```

**적용 위치**: `observability.py`

---

### 12. 로그 경로 PII 노출

**문제**: 요청 경로에 사용자 ID, 이메일 등이 포함되어 로그에 PII 노출

```python
# ❌ 원본 경로 그대로 로그
log_payload = {
    "path": request.url.path,  # "/api/v1/users/12345/profile" - ID 노출
}

# ✅ 경로 정규화
_PATH_ID_PATTERNS = [
    (re.compile(r"/\d+"), "/{id}"),
    (re.compile(r"/[0-9a-f]{8}-...-[0-9a-f]{12}", re.I), "/{uuid}"),
]

def normalize_log_path(path: str) -> str:
    for pattern, replacement in _PATH_ID_PATTERNS:
        path = pattern.sub(replacement, path)
    return path[:200]  # 길이 제한

log_payload = {
    "path": normalize_log_path(request.url.path),  # "/api/v1/users/{id}/profile"
}
```

**적용 위치**: `observability.py`

---

### 13. setup_tracing 중복 호출

**문제**: 앱 리로드/테스트 시 tracing이 중복 설정되어 계측 중복 발생

```python
# ❌ 중복 호출 시 계측 중복
def setup_tracing(app: FastAPI):
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
# 두 번 호출하면 중복 계측

# ✅ idempotent guard
_tracing_initialized = False

def setup_tracing(app: FastAPI):
    global _tracing_initialized
    if _tracing_initialized:
        return
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    _tracing_initialized = True
```

**적용 위치**: `observability.py`

---

### 14. X-Request-ID 신뢰 문제

**문제**: 클라이언트가 보낸 X-Request-ID를 검증 없이 신뢰하면 인젝션 위험

```python
# ❌ 검증 없이 신뢰
request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
# 악의적 값: "malicious\nX-Injection: true"

# ✅ 검증 후 사용
raw_id = request.headers.get("X-Request-ID")
if raw_id and len(raw_id) <= 64 and raw_id.replace("-", "").isalnum():
    request_id = raw_id
else:
    request_id = str(uuid.uuid4())
```

**적용 위치**: `observability.py`

---

### 15. SPA 404에서 anchor 태그 사용

**문제**: React Router의 `<a href="/">` 사용 시 SPA 네비게이션이 끊기고 전체 페이지 리로드 발생

```tsx
// ❌ 잘못된 패턴 - 전체 페이지 리로드
const NotFound = () => (
  <div>
    <a href="/" className="btn btn-primary">Go to Dashboard</a>
  </div>
);
// 상태 손실, basename 무시, 불필요한 네트워크 요청

// ✅ 올바른 패턴 - React Router Link 사용
import { Link } from 'react-router-dom';

const NotFound = () => (
  <div>
    <Link to="/" className="btn btn-primary">Go to Dashboard</Link>
  </div>
);
// SPA 네비게이션 유지, 상태 보존, basename 자동 적용
```

**적용 위치**: `App.tsx`

---

### 16. 공개/보호 404 미분리

**문제**: 404 페이지가 보호된 레이아웃 내부에만 있으면 `/login/typo` 같은 공개 경로 오타가 인증 레이아웃으로 떨어짐

```tsx
// ❌ 잘못된 패턴 - 모든 404가 Layout 내부
<Routes>
  <Route path="/login" element={<Login />} />
  <Route element={<Layout />}>  {/* 인증 필요 */}
    <Route path="/" element={<Dashboard />} />
    <Route path="*" element={<NotFound />} />  {/* /login/typo도 여기로 */}
  </Route>
</Routes>

// ✅ 올바른 패턴 - 공개/보호 404 분리
<Routes>
  <Route path="/login" element={<Login />} />
  <Route element={<Layout />}>
    <Route path="/" element={<Dashboard />} />
    <Route path="*" element={<NotFound />} />  {/* 인증된 사용자용 404 */}
  </Route>
  {/* 공개 404 (Layout 외부, 마지막에 배치) */}
  <Route path="*" element={<PublicNotFound />} />
</Routes>
```

**적용 위치**: `App.tsx`

---

### 17. React Query 401 재시도

**문제**: 인증 에러(401/403)에도 재시도하면 불필요한 요청과 UX 지연 발생

```tsx
// ❌ 잘못된 패턴 - 모든 에러에 재시도
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,  // 401에도 재시도 → 불필요한 요청
    },
  },
});

// ✅ 올바른 패턴 - 인증 에러 재시도 제외
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        // 인증 에러는 재시도하지 않음
        if (error && typeof error === 'object' && 'response' in error) {
          const status = (error as { response?: { status?: number } }).response?.status;
          if (status === 401 || status === 403) return false;
        }
        return failureCount < 1;
      },
    },
  },
});
```

**적용 위치**: `App.tsx`

---

### 18. 페이지 컴포넌트 즉시 로드

**문제**: 모든 페이지를 즉시 import하면 초기 번들 크기가 커지고 첫 로드가 느려짐

```tsx
// ❌ 잘못된 패턴 - 모든 페이지 즉시 import
import { Dashboard } from './pages/Dashboard';
import { Activities } from './pages/Activities';
import { Settings } from './pages/Settings';
// ... 10개 이상의 페이지

// ✅ 올바른 패턴 - React.lazy로 코드 스플리팅
import { Suspense, lazy } from 'react';

const Dashboard = lazy(() =>
  import('./pages/Dashboard').then(m => ({ default: m.Dashboard }))
);
const Activities = lazy(() =>
  import('./pages/Activities').then(m => ({ default: m.Activities }))
);

// Suspense로 감싸기
<Suspense fallback={<PageLoader />}>
  <Routes>
    <Route path="/" element={<Dashboard />} />
    ...
  </Routes>
</Suspense>
```

**적용 위치**: `App.tsx`

---

### 19. API prefix 버전 파싱 오류

**문제**: api_prefix에서 버전 추출 시 `v{숫자}` 형식이 아니면 `int()` 변환에서 500 에러

```python
# ❌ 잘못된 패턴 - 숫자가 아닌 입력에서 크래시
def _parse_version(version_str: str) -> tuple[int, int]:
    version_str = version_str.lstrip("v")
    parts = version_str.split(".")
    major = int(parts[0])  # "api" -> int("api") -> ValueError!
    return (major, 0)

# api_prefix="/api" 일 때 → int("api") → 500 에러

# ✅ 올바른 패턴 - 안전한 파싱
def _parse_version(version_str: str) -> tuple[int, int]:
    version_str = version_str.lstrip("v")
    parts = version_str.split(".")
    try:
        major = int(parts[0]) if parts and parts[0].isdigit() else 0
        minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    except (ValueError, IndexError):
        return (0, 0)
    return (major, minor)

def _get_current_api_version() -> str:
    last_segment = prefix.rstrip("/").split("/")[-1]
    # 버전 형식인지 확인
    if last_segment.startswith("v") and len(last_segment) > 1 and last_segment[1].isdigit():
        return last_segment
    return "v1"  # 기본값
```

**적용 위치**: `aliases.py`

---

### 20. API prefix trailing slash

**문제**: api_prefix에 trailing slash가 있으면 URL 결합 시 이중 슬래시 발생

```python
# ❌ 잘못된 패턴
api_prefix = "/api/v1/"
openapi_url = f"{api_prefix}/openapi.json"
# 결과: "/api/v1//openapi.json"

# ✅ 올바른 패턴 - 정규화 속성 제공
api_prefix: str = "/api/v1"  # 주석: trailing slash 금지

@property
def normalized_api_prefix(self) -> str:
    """Return api_prefix with trailing slash removed."""
    return self.api_prefix.rstrip("/")

# 사용 시
openapi_url = f"{settings.normalized_api_prefix}/openapi.json"
```

**적용 위치**: `config.py`

---

### 21. 프론트/백엔드 응답 타입 불일치

**문제**: 프론트엔드 TypeScript 타입이 백엔드 Pydantic 응답과 맞지 않아 런타임 오류 발생

```typescript
// ❌ 잘못된 패턴 - 백엔드 응답과 불일치
export interface GarminConnectResponse {
  message: string;  // 백엔드는 connected, last_login도 반환
}

const response = await connectGarmin(creds);
console.log(response.connected);  // undefined!

// ✅ 올바른 패턴 - 백엔드 Pydantic 모델과 일치
export interface GarminConnectResponse {
  connected: boolean;
  message: string;
  last_login: string | null;
}

// 백엔드 (auth.py)
class GarminConnectResponse(BaseModel):
    connected: bool
    message: str
    last_login: datetime | None = None
```

**적용 위치**: `auth.ts`, `auth.py`

---

### 22. 세션 쿠키 이름 하드코딩

**문제**: 쿠키 이름이 코드에 하드코딩되어 환경별 변경이 어렵고 불일치 위험

```python
# ❌ 잘못된 패턴 - 하드코딩
SESSION_COOKIE_NAME = "session_id"

response.set_cookie(
    key=SESSION_COOKIE_NAME,  # 변경하려면 코드 수정 필요
    ...
)

# ✅ 올바른 패턴 - 설정에서 관리
# config.py
session_cookie_name: str = "session_id"

# auth.py
SESSION_COOKIE_NAME = settings.session_cookie_name
```

**적용 위치**: `config.py`, `auth.py`

---

### 23. In-memory 상태가 멀티워커에서 실패

**문제**: 백그라운드 작업 상태를 `dict`로 추적하면 단일 워커에서만 동작하고, 멀티워커/멀티인스턴스 배포에서 실패

```python
# ❌ 잘못된 패턴 - 단일 워커에서만 동작
_running_jobs: dict[int, bool] = {}

async def run_ingest(...):
    if _running_jobs.get(user_id, False):
        return "Already running"  # Worker 2에서는 Worker 1의 상태를 모름
    _running_jobs[user_id] = True
    ...

# ✅ 올바른 패턴 (MVP) - 제한사항 명시
# WARNING: This only works for single-worker deployments.
# For multi-worker/multi-instance, use Redis-based locking instead.
# See: https://redis.io/docs/manual/patterns/distributed-locks/
_running_jobs: dict[int, bool] = {}

# ✅ 올바른 패턴 (Production) - Redis 분산 락
import redis
lock_key = f"sync_lock:{user_id}"
if redis_client.set(lock_key, "1", nx=True, ex=300):  # 5분 TTL
    try:
        # do work
    finally:
        redis_client.delete(lock_key)
```

**적용 위치**: `ingest.py`

---

### 24. 사용하지 않는 응답 필드 반환

**문제**: 응답 스키마에 필드가 있지만 실제로 저장/조회되지 않아 클라이언트 혼란 유발

```python
# ❌ 잘못된 패턴 - sync_id가 저장되지 않음
class IngestRunResponse(BaseModel):
    started: bool
    message: str
    sync_id: str  # 생성되지만 DB에 저장 안 됨 → 조회 불가

return IngestRunResponse(
    started=True,
    sync_id=str(uuid.uuid4()),  # 의미 없는 값
)

# ✅ 올바른 패턴 - 사용하지 않는 필드 제거
class IngestRunResponse(BaseModel):
    started: bool
    message: str
    endpoints: list[str]
    # Note: sync_id was removed as it was not persisted or queryable.
    # Use /ingest/status to check if sync is running.
```

**적용 위치**: `ingest.py`

---

### 25. 동기 API에서 동시성 가드 누락

**문제**: 비동기(백그라운드) API에는 동시성 체크가 있지만, 동기(블로킹) API에는 없어서 동시 요청 시 충돌

```python
# ❌ 잘못된 패턴 - /run/sync에 동시성 가드 없음
@router.post("/run/sync")
async def run_ingest_sync(...):
    # 백그라운드 sync가 실행 중이어도 중복 실행됨
    sync_service = await create_sync_service(...)
    return await sync_service.sync_endpoint(...)

# ✅ 올바른 패턴 - 일관된 동시성 체크
@router.post("/run/sync")
async def run_ingest_sync(...):
    if _running_jobs.get(current_user.id, False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sync already in progress. Use /ingest/status to check progress.",
        )

    _running_jobs[current_user.id] = True
    try:
        # sync logic
        return results
    finally:
        _running_jobs[current_user.id] = False
```

**적용 위치**: `ingest.py`

---

### 26. HR 존 시간 계산이 샘플링 주기를 가정

**문제**: "1 샘플 = 1초"로 가정하면 5Hz나 불규칙 샘플링에서 시간/비율이 왜곡됨

```python
# ❌ 잘못된 패턴 - 샘플 개수로 시간 계산
hr_values = [row[0] for row in result.all()]
for hr in hr_values:
    for zone in zones:
        if zone["min_hr"] <= hr < zone["max_hr"]:
            zone["count"] += 1  # 1 sample = 1 second 가정
            break
total_time = sum(z["count"] for z in zones)  # 5Hz면 5배 왜곡

# ✅ 올바른 패턴 - 타임스탬프 델타 사용
samples = [(row[0], row[1]) for row in result.all()]  # (hr, timestamp)
for i, (hr, ts) in enumerate(samples):
    if i < len(samples) - 1:
        duration = (samples[i + 1][1] - ts).total_seconds()
        duration = min(duration, 60.0)  # 갭 방지 캡
    else:
        # 마지막 샘플: 평균 간격 추정
        avg_interval = total_span / (len(samples) - 1)
        duration = min(avg_interval, 60.0)

    for zone in zones:
        if zone["min_hr"] <= hr < zone["max_hr"]:
            zone["count"] += duration
            break
```

**적용 위치**: `activities.py`

---

### 27. FIT 다운로드 경로 순회 취약점

**문제**: DB에 저장된 file_path를 검증 없이 서빙하면 임의 파일 노출 가능

```python
# ❌ 잘못된 패턴 - DB 경로 그대로 사용
return FileResponse(
    path=fit_file.file_path,  # DB 오염 시 "/etc/passwd" 가능
    filename=f"activity_{activity.garmin_id}.fit",
)

# ✅ 올바른 패턴 - 허용 디렉토리 검증
settings = get_settings()
allowed_root = os.path.realpath(settings.fit_storage_path)
file_real_path = os.path.realpath(fit_file.file_path)

if not file_real_path.startswith(allowed_root + os.sep):
    logger.warning(f"Path traversal blocked: {fit_file.file_path}")
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="FIT file not found",  # 보안상 모호한 메시지
    )

return FileResponse(path=file_real_path, ...)
```

**적용 위치**: `activities.py`

---

### 28. 응답 스키마에 채워지지 않는 필드

**문제**: Pydantic 모델에 필드가 있지만 실제로 채워지지 않아 항상 null 반환

```python
# ❌ 잘못된 패턴 - 필드 정의만 있고 채우는 로직 없음
class ActivityMetricResponse(BaseModel):
    trimp: float | None = None
    leg_spring_stiffness: float | None = None  # 절대 채워지지 않음
    form_power: int | None = None  # 절대 채워지지 않음

# ✅ 올바른 패턴 - 미구현 필드 문서화
class ActivityMetricResponse(BaseModel):
    trimp: float | None = None
    # Note: leg_spring_stiffness and form_power are planned but not yet populated.
    # They require Stryd pod (form_power) or calculation from GCT/mass (LSS).
    # Keeping in schema for forward compatibility. Always null until implemented.
    leg_spring_stiffness: float | None = None  # in kN/m (requires body weight + GCT)
    form_power: int | None = None  # from Stryd pod (not Garmin)
```

**적용 위치**: `activities.py`

---

### 29. 문서와 코드의 타입 불일치

**문제**: API 문서에 `date`로 기록되었지만 코드는 `datetime` 사용

```markdown
# ❌ 잘못된 문서 - 코드와 불일치
| Parameter | Type | 설명 |
|-----------|------|------|
| start_date | date | 시작 날짜 필터 |

# ✅ 올바른 문서 - 코드와 일치 + 예시 포함
| Parameter | Type | 설명 |
|-----------|------|------|
| start_date | datetime | 시작 날짜 필터 (ISO 8601, e.g., `2024-01-01` or `2024-01-01T00:00:00Z`) |
```

코드 확인:
```python
# activities.py - 실제 타입
start_date: datetime | None = Query(None, description="Filter start date (from)")
```

**적용 위치**: `api-reference.md`, `activities.py`

---

## 일반적인 디버깅 체크리스트

### 코드 리뷰 시 확인 사항

1. **숫자 포맷팅**
   - [ ] Math.round/floor/ceil 순서 확인
   - [ ] 60초/분/시간 경계 테스트

2. **날짜 처리**
   - [ ] Invalid Date 핸들링
   - [ ] 타임존 관련 비교 로직
   - [ ] ISO 8601 파싱 지원

3. **API 타입**
   - [ ] Backend Pydantic ↔ Frontend TypeScript 일치
   - [ ] Optional 필드 nullable 처리
   - [ ] Enum 값 일치

4. **상태 관리**
   - [ ] React Query invalidation 완전성
   - [ ] 관련 쿼리 키 그룹화
   - [ ] Stale 데이터 갱신

5. **환경 설정**
   - [ ] 환경변수 일관성
   - [ ] 빈 값/누락 시 기본값
   - [ ] 개발/프로덕션 분기

---

## 관련 파일 참조

| 이슈 | 관련 파일 |
|------|----------|
| 시간 포맷팅 | `frontend/src/utils/format.ts` |
| API 타입 | `frontend/src/types/api.ts` |
| React Query hooks | `frontend/src/hooks/` |
| 라우터 문서 | `backend/app/api/v1/router.py` |
| 레거시 별칭 | `backend/app/api/v1/aliases.py` |
| CORS 설정 | `backend/app/main.py`, `backend/app/core/config.py` |
| 지도 배율 | `frontend/src/components/activity/ActivityMap.tsx` |
| 보안 설정 | `backend/app/core/config.py` |
| 비밀번호 해시 | `backend/app/core/security.py`, `backend/app/api/v1/endpoints/auth.py` |
| DB 세션 | `backend/app/core/database.py` |
| Redis 세션 | `backend/app/core/session.py`, `backend/app/main.py` |
| 관측성/메트릭 | `backend/app/observability.py` |
| 라우팅/코드스플리팅 | `frontend/src/App.tsx` |
| 인증 가드 | `frontend/src/components/layout/Layout.tsx` |
| API prefix/버전 | `backend/app/core/config.py`, `backend/app/api/v1/aliases.py` |
| API 클라이언트 | `frontend/src/api/client.ts` |
| 인증 API 타입 | `frontend/src/api/auth.ts`, `backend/app/api/v1/endpoints/auth.py` |
| 데이터 수집/동기화 | `backend/app/api/v1/endpoints/ingest.py` |
| 활동 데이터 | `backend/app/api/v1/endpoints/activities.py` |
| API 문서 | `docs/api-reference.md` |

---

---

## 로컬 개발 환경 트러블슈팅

### 빠른 시작 가이드

```bash
# 1. 백엔드 시작
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 2. 프론트엔드 시작 (별도 터미널)
cd frontend
npm run dev

# 3. 브라우저에서 http://localhost:5173 접속
```

---

### CORS 에러

**증상**:
```
Access to XMLHttpRequest at 'http://localhost:8000/api/v1/...' from origin 'http://localhost:5173'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present
```

**원인**: `.env` 파일에 `CORS_ORIGINS` 환경변수가 없음

**해결**:
```bash
# backend/.env에 추가
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173
```

그 후 백엔드 서버 재시작.

---

### 마이그레이션 버전 오류

**증상**:
```
Can't locate revision identified by 'XXXXXXXX'
```

**원인**:
- GitHub에서 마이그레이션 파일이 삭제/변경됨
- 로컬 DB의 `alembic_version`이 존재하지 않는 리비전을 가리킴

**해결**:
```bash
# 1. 현재 DB 버전 확인
/opt/homebrew/opt/postgresql@15/bin/psql -d runningcoach -c "SELECT version_num FROM alembic_version;"

# 2. 최신 마이그레이션 리비전 찾기
cd backend
source .venv/bin/activate
alembic history | head -5

# 3. DB 버전 수동 업데이트 (head 리비전으로)
/opt/homebrew/opt/postgresql@15/bin/psql -d runningcoach -c "UPDATE alembic_version SET version_num = '<HEAD_REVISION>';"

# 4. 스키마 드리프트 확인 및 자동 수정
python scripts/check_schema.py --fix
```

---

### 스키마 드리프트 (누락된 컬럼)

**증상**:
```
column activities.has_stryd does not exist
```
또는 500 Internal Server Error (CORS 에러처럼 보일 수 있음)

**원인**:
- git pull 후 새 모델 필드가 추가됨
- 마이그레이션이 이미 다른 환경에서 실행되어 로컬과 불일치

**해결**:
```bash
cd backend
source .venv/bin/activate

# 1. 스키마 확인 (체크만)
python scripts/check_schema.py

# 2. 누락된 컬럼 자동 추가
python scripts/check_schema.py --fix

# 3. 백엔드 재시작
```

**권장 워크플로우** - git pull 후 항상 실행:
```bash
git pull
cd backend && source .venv/bin/activate
python scripts/check_schema.py --fix
```

---

### Redis 연결 오류

**증상**:
```
redis.exceptions.ConnectionError: Error 61 connecting to localhost:6379
```

**해결**:
```bash
# macOS
brew services start redis

# 확인
redis-cli ping
# 응답: PONG
```

---

### PostgreSQL 연결 오류

**증상**:
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**해결**:
```bash
# macOS
brew services start postgresql@15

# 데이터베이스 존재 확인
/opt/homebrew/opt/postgresql@15/bin/psql -l | grep runningcoach

# 없으면 생성
/opt/homebrew/opt/postgresql@15/bin/createdb runningcoach
```

---

### 포트 충돌

**증상**:
```
Address already in use - bind(2) for "0.0.0.0" port 8000
```

**해결**:
```bash
# 해당 포트 사용 프로세스 종료
lsof -ti:8000 | xargs kill -9
lsof -ti:5173 | xargs kill -9
```

---

### 쿠키가 저장되지 않음

**증상**: 로그인 후 API 호출 시 401 Unauthorized

**원인**:
1. HTTPS에서 HTTP 쿠키 설정 (Secure=true 문제)
2. SameSite 설정 문제

**해결** (`backend/.env`):
```bash
# 로컬 개발 환경 설정
COOKIE_SECURE=false
COOKIE_SAMESITE=lax
```

---

### Garmin 세션 만료

**증상**: 동기화 버튼이 비활성화되고 "세션 갱신 필요" 표시

**해결**: Settings 페이지에서 Garmin 연동 해제 후 다시 연동

---

### 로그 확인

```bash
# 백엔드 로그 (실시간)
tail -f /tmp/claude/.../tasks/XXX.output

# 또는 터미널에서 직접 실행
cd backend && source .venv/bin/activate && uvicorn app.main:app --port 8000 --reload
```

---

### 유용한 디버깅 명령어

```bash
# API 헬스 체크
curl http://localhost:8000/health

# 세션 상태 확인 (쿠키 파일 필요)
curl -b cookies.txt http://localhost:8000/api/v1/auth/me

# DB 테이블 스키마 확인
/opt/homebrew/opt/postgresql@15/bin/psql -d runningcoach -c "\d+ activities"

# Redis 세션 확인
redis-cli keys "session:*"

# 마이그레이션 상태
cd backend && source .venv/bin/activate && alembic current
```

---

### 환경 변수 체크리스트

로컬 개발에 필요한 최소 설정 (`backend/.env`):

```bash
# 필수
DATABASE_URL=postgresql+asyncpg://<user>@localhost:5432/runningcoach
REDIS_URL=redis://localhost:6379/0
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# 보안 (개발용)
SESSION_SECRET=<랜덤 문자열>
COOKIE_SECURE=false
COOKIE_SAMESITE=lax

# Garmin 연동 (선택)
GARMIN_ENCRYPTION_KEY=<Fernet key>
```

---

*마지막 업데이트: 2026-01-02*
