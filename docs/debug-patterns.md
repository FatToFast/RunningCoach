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

**적용 위치**:
- `utils/format.ts`: `formatPace`, `formatDuration`, `formatPaceFromDecimal`
- `pages/Records.tsx`: 로컬 `formatPace` (utils 사용 권장)
- `pages/Trends.tsx`: 로컬 `formatPace` (utils 사용 권장)
- `hooks/useActivities.ts`: 로컬 `formatPace` (utils 사용 권장)

⚠️ **주의**: 여러 파일에 중복 정의된 함수가 있으므로 `utils/format.ts`의 공통 함수 사용을 권장합니다.

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
| HR 존 계산 | `backend/app/api/v1/endpoints/activities.py:754-788` |
| Runalyze API 호출 | `backend/app/api/v1/endpoints/dashboard.py:43-104` |
| 동기화 락 관리 | `backend/app/core/session.py:134-244`, `backend/app/api/v1/endpoints/ingest.py:32` |
| Strava OAuth | `backend/app/api/v1/endpoints/strava.py:25-89` |

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

### 30. HR 존 계산 - 주석과 코드 불일치

**문제**: 함수 docstring과 실제 상수 값이 다름

```python
# ❌ 잘못된 패턴 - 주석과 실제 값 불일치
# 주석에는 "Zone 1: 50-60% HRR"이라고 했지만...
HR_ZONE_DEFINITIONS = [
    {"zone": 1, "min_pct": 0.304, "max_pct": 0.44},  # 실제: 30-44%
    {"zone": 2, "min_pct": 0.448, "max_pct": 0.576},  # 실제: 45-58%
]

def get_hr_zones(...):
    """
    Zones are calculated based on percentage of HRR:
    - Zone 1: 50-60% HRR  # 실제 코드와 다름!
    - Zone 2: 60-70% HRR
    """

# ✅ 올바른 패턴 - 주석과 실제 값 일치
HR_ZONE_DEFINITIONS = [
    {"zone": 1, "min_pct": 0.50, "max_pct": 0.60},  # Zone 1: 50-60% HRR
    {"zone": 2, "min_pct": 0.60, "max_pct": 0.70},  # Zone 2: 60-70% HRR
    {"zone": 3, "min_pct": 0.70, "max_pct": 0.80},  # Zone 3: 70-80% HRR
]

def get_hr_zones(...):
    """
    Uses industry-standard 5-zone HRR method:
    - Zone 1: 50-60% HRR (Recovery)
    - Zone 2: 60-70% HRR (Aerobic)
    - Zone 3: 70-80% HRR (Tempo)
    """
```

**적용 위치**: `activities.py:754-788`

**관련 이슈**:
- max_hr 기본값 설명도 부정확 ("220-age"라고 했지만 실제로는 샘플 최대값 사용)
- Query 파라미터 description에 실제 동작 명시 필요

---

### 31. httpx base_url + leading slash 오류

**문제**: leading slash가 base_url 경로를 덮어씀

```python
# ❌ 잘못된 패턴 - leading slash가 base_url 경로를 덮어씀
async with httpx.AsyncClient(
    base_url="https://runalyze.com/api/v1"
) as client:
    # /metrics/calculations → https://runalyze.com/metrics/calculations
    # /api/v1이 사라짐!
    response = await client.get("/metrics/calculations")

# ✅ 올바른 패턴 - leading slash 제거
async with httpx.AsyncClient(
    base_url="https://runalyze.com/api/v1"
) as client:
    # metrics/calculations → https://runalyze.com/api/v1/metrics/calculations
    response = await client.get("metrics/calculations")

# 또는 base_url을 도메인만 사용
async with httpx.AsyncClient(
    base_url="https://runalyze.com"
) as client:
    # /api/v1/metrics/calculations → 의도한 URL
    response = await client.get("/api/v1/metrics/calculations")
```

**적용 위치**: `dashboard.py:71-99`, 모든 httpx.AsyncClient base_url 사용 코드

**원인**: httpx는 WHATWG URL 표준을 따라 leading slash가 있으면 base_url의 경로를 무시함

---

### 32. 동기화 락 TTL 부족 및 연장 로직 누락

**문제**: 대용량 백필(500+ 활동) 시 1시간 TTL로 부족하고, 연장 로직도 없음

```python
# ❌ 잘못된 패턴 - 고정 TTL, 연장 불가
SYNC_LOCK_TTL = 3600  # 1시간
lock_owner = await acquire_lock(lock_name, ttl_seconds=SYNC_LOCK_TTL)

# 1000개 활동 동기화 시 1.5시간 걸림 → 중간에 락 만료!

# ✅ 올바른 패턴 1 - TTL 증가
SYNC_LOCK_TTL = 10800  # 3시간 (500개 활동 대응)

# ✅ 올바른 패턴 2 - 주기적 연장 (대용량)
async def extend_lock(lock_name: str, owner: str, ttl_seconds: int) -> bool:
    """Extend lock TTL atomically."""
    redis_client = await get_redis()
    lock_key = f"lock:{lock_name}"

    # Lua script로 소유권 확인 후 연장
    lua_script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("expire", KEYS[1], ARGV[2])
    else
        return 0
    end
    """

    result = await redis_client.eval(lua_script, 1, lock_key, owner, ttl_seconds)
    return result == 1

# 사용 예시
lock_owner = await acquire_lock(lock_name, ttl_seconds=SYNC_LOCK_TTL)
try:
    for batch in batches:
        await process_batch(batch)
        # 매 배치마다 락 연장 (10분마다)
        await extend_lock(lock_name, lock_owner, SYNC_LOCK_TTL)
finally:
    await release_lock(lock_name, lock_owner)
```

**적용 위치**:
- `ingest.py:32` - SYNC_LOCK_TTL 증가
- `session.py:212-244` - extend_lock() 함수 추가

**예상 동기화 시간**:
- 100개 활동: ~8분
- 500개 활동: ~40분
- 1000개 활동: ~1.5시간 (3시간 TTL 권장)

---

### 33. Strava OAuth state가 프로세스 메모리에만 저장

**문제**: 멀티워커/멀티인스턴스 환경에서 OAuth state가 공유되지 않아 콜백 실패

```python
# ❌ 잘못된 패턴 - 단일 워커에서만 동작
_oauth_states: dict[str, tuple[int, float]] = {}

def _generate_oauth_state(user_id: int) -> str:
    state_token = secrets.token_urlsafe(32)
    _oauth_states[state_token] = (user_id, time.time() + 600)
    return state_token
# Worker A에서 생성 → Worker B로 콜백 → state 찾을 수 없음!

# ✅ 올바른 패턴 - Redis 사용
async def generate_oauth_state(user_id: int, redis: Redis) -> str:
    state_token = secrets.token_urlsafe(32)
    await redis.setex(
        f"oauth:state:{state_token}",
        600,  # 10분 TTL
        user_id
    )
    return state_token

async def validate_oauth_state(state: str, user_id: int, redis: Redis) -> bool:
    stored_user_id = await redis.get(f"oauth:state:{state}")
    if not stored_user_id:
        return False

    if int(stored_user_id) != user_id:
        return False

    # 일회용 삭제
    await redis.delete(f"oauth:state:{state}")
    return True
```

**적용 위치**: `strava.py:25-89`

**배포 시나리오**:
- 단일 워커 (`uvicorn ... --workers 1`): 현재 방식 OK
- 멀티 워커 (`--workers 4+`) 또는 멀티 인스턴스: Redis 필수

**현재 상태**: MVP 단계이므로 TODO 주석 추가하고 프로덕션 배포 시 마이그레이션

---

### 34. garmin_id가 전역 고유로 설정되어 멀티유저 충돌

**문제**: Garmin activity ID는 사용자별로만 고유한데, 전역 unique 제약으로 인해 다른 사용자가 같은 ID를 가질 수 없음

```python
# ❌ 잘못된 패턴 - 전역 고유
class Activity(BaseModel):
    garmin_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
# 사용자 A가 garmin_id=12345 저장 → 사용자 B도 12345 저장 시 UniqueViolation!

# ✅ 올바른 패턴 - 사용자별 고유 (복합 유니크)
class Activity(BaseModel):
    __table_args__ = (
        UniqueConstraint("user_id", "garmin_id", name="uq_activities_user_garmin_id"),
    )
    garmin_id: Mapped[int] = mapped_column(BigInteger, index=True)  # unique=True 제거
```

**적용 위치**: `models/activity.py`

**마이그레이션**: `012_fix_garmin_schema_drift.py`에서 이미 DB 제약 변경됨, 모델 파일만 동기화 필요

---

### 35. 다운샘플링 시 첫/마지막 샘플 누락

**문제**: 균등 간격 다운샘플링이 마지막 샘플을 포함하지 않아 경계값 손실

```python
# ❌ 잘못된 패턴 - 마지막 샘플 누락 가능
step = total_count // downsample
sample_query = (
    select(subq)
    .where((subq.c.row_num - 1) % step == 0)  # 마지막 row가 step 배수가 아니면 누락
    .limit(downsample)
)

# ✅ 올바른 패턴 - 첫/마지막 보장
sample_query = (
    select(subq)
    .where(
        (subq.c.row_num == 1)  # 첫 샘플 항상 포함
        | (subq.c.row_num == total_count)  # 마지막 샘플 항상 포함
        | (  # 중간은 균등 분포
            (subq.c.row_num > 1) & (subq.c.row_num < total_count)
            & ((subq.c.row_num - 2) % step < 1)
        )
    )
    .limit(downsample)
)
```

**적용 위치**: `activities.py:527-586`

---

### 36. HR 필드 이름 불일치 (hr vs heart_rate)

**문제**: FIT 파서에 따라 `hr` 또는 `heart_rate` 필드가 채워지는데 한쪽만 읽음

```python
# ❌ 잘못된 패턴 - hr 필드만 사용
result = await db.execute(
    select(ActivitySample.hr, ActivitySample.timestamp)
    .where(ActivitySample.hr.isnot(None))
)
# heart_rate 필드에만 값이 있으면 빈 결과!

# ✅ 올바른 패턴 - coalesce로 양쪽 확인
from sqlalchemy.sql.functions import coalesce

hr_value = coalesce(ActivitySample.hr, ActivitySample.heart_rate)
result = await db.execute(
    select(hr_value.label("hr"), ActivitySample.timestamp)
    .where(hr_value.isnot(None))
)
```

**적용 위치**: `activities.py:848-859`

**관련 테이블**: `activity_samples` - `hr`, `heart_rate` 두 컬럼 모두 존재

---

### 37. FIT 파일 존재 여부와 has_fit_file 플래그 불일치

**문제**: DB에 `has_fit_file=True`지만 실제 파일이 삭제/이동된 경우 처리 안됨

```python
# ❌ 잘못된 패턴 - 플래그만 확인
if not activity.has_fit_file:
    await self._download_fit_file(activity, garmin_id)
# 파일 삭제됐어도 has_fit_file=True면 다시 다운로드 안 함

# ✅ 올바른 패턴 - 실제 파일 존재 확인
need_download = not activity.has_fit_file
if activity.fit_file_path:
    if not Path(activity.fit_file_path).exists():
        logger.info(f"FIT file missing for activity {garmin_id}, re-downloading")
        need_download = True
if need_download:
    await self._download_fit_file(activity, garmin_id)
```

**적용 위치**: `sync_service.py:352-360`

**시나리오**: 디스크 정리, 백업 복원 후 파일 누락, 스토리지 마이그레이션

---

### 13. Runalyze 데이터 누락 시 Fallback 처리

**문제**: Runalyze API/스크래핑 실패 시 `effective_vo2max`, `marathon_shape`가 None으로 표시됨

```python
# ❌ 잘못된 패턴 - Runalyze 데이터만 사용
fitness_status = FitnessStatus(
    effective_vo2max=(runalyze_calc.get("effective_vo2max") if runalyze_calc else None),
    marathon_shape=runalyze_calc.get("marathon_shape") if runalyze_calc else None,
)
# Runalyze 접속 불가 시 VO2max가 None

# ✅ 올바른 패턴 - 활동 데이터에서 Fallback
# 1. 먼저 활동에서 최신 VO2max 조회
activity_vo2max_result = await db.execute(
    select(Activity.vo2max)
    .where(Activity.user_id == user_id, Activity.vo2max.isnot(None))
    .order_by(Activity.start_time.desc())
    .limit(1)
)
activity_vo2max = activity_vo2max_result.scalar_one_or_none()

# 2. Runalyze 우선, 없으면 활동 데이터 사용
fitness_status = FitnessStatus(
    effective_vo2max=(
        (runalyze_calc.get("effective_vo2max") or runalyze_calc.get("vo2max")) if runalyze_calc else None
    ) or (round(activity_vo2max, 1) if activity_vo2max else None),
    # marathon_shape는 Runalyze 전용 (fallback 없음)
    marathon_shape=runalyze_calc.get("marathon_shape") if runalyze_calc else None,
)
```

**적용 위치**: `dashboard.py:504-532`

**시나리오**: Runalyze 429 에러, API 토큰 만료, 로그인 실패

---

### 14. Runalyze 스크래핑 시 marathon_shape 누락

**문제**: `_fetch_runalyze_data()`에서 `marathon_shape` 필드를 calculations에 포함하지 않음

```python
# ❌ 잘못된 패턴 - marathon_shape 누락
calculations = {
    "ctl": metrics.ctl,
    "atl": metrics.atl,
    "effective_vo2max": metrics.vo2max,
    # marathon_shape 빠짐!
}

# ✅ 올바른 패턴 - 모든 필드 포함
calculations = {
    "ctl": metrics.ctl,
    "atl": metrics.atl,
    "effective_vo2max": metrics.vo2max,
    "marathon_shape": metrics.marathon_shape,  # 추가!
    "monotony": metrics.monotony,
    "training_strain": metrics.training_strain,
}
```

**적용 위치**: `dashboard.py:47-59`

---

### 38. 페이지네이션 tie-breaker 누락

**문제**: 정렬 기준 컬럼만으로 ORDER BY 하면 동일 값일 때 페이지 이동 시 중복/누락 발생

```python
# ❌ 잘못된 패턴 - 단일 컬럼 정렬
query = query.order_by(Activity.start_time.desc())
# start_time이 같은 10개 활동이 있으면 page 1,2 간에 중복/누락 발생

# ✅ 올바른 패턴 - tie-breaker 추가
query = query.order_by(Activity.start_time.desc(), Activity.id.desc())
# id는 항상 고유하므로 안정적인 순서 보장
```

**적용 위치**: `activities.py:241-244`, 모든 페이지네이션 쿼리

---

### 39. 목록 쿼리 전체 컬럼 로드

**문제**: 요약 목록에서 전체 Activity 컬럼을 로드하면 불필요한 메모리/네트워크 사용

```python
# ❌ 잘못된 패턴 - 모든 컬럼 로드
query = select(Activity).where(Activity.user_id == user_id)
# 50+ 컬럼 모두 로드 (samples, fit_file_path 등 불필요)

# ✅ 올바른 패턴 - 필요한 컬럼만 로드
from sqlalchemy.orm import load_only

query = (
    select(Activity)
    .where(Activity.user_id == user_id)
    .options(load_only(
        Activity.id,
        Activity.garmin_id,
        Activity.activity_type,
        Activity.name,
        Activity.start_time,
        Activity.duration_seconds,
        Activity.distance_meters,
        Activity.avg_hr,
        Activity.avg_pace_seconds,
        Activity.calories,
    ))
)
```

**적용 위치**: `activities.py:218-234`, 목록 조회 쿼리

---

### 40. 날짜 필터링 시 타임존 무시

**문제**: 사용자 타임존 없이 날짜 필터링하면 UTC 기준으로 처리되어 예상과 다른 결과

```python
# ❌ 잘못된 패턴 - naive datetime 그대로 사용
if start_date:
    query = query.where(Activity.start_time >= start_date)
# 사용자가 "2024-01-15" 입력 시 UTC 00:00 기준이 되어
# 한국 시간(+9)에서는 1월 14일 15:00 이후 활동만 조회됨

# ✅ 올바른 패턴 - 사용자 타임존 적용
from zoneinfo import ZoneInfo

user_tz = ZoneInfo(current_user.timezone or "Asia/Seoul")

if start_date:
    if start_date.tzinfo is None:
        start_datetime = start_date.replace(tzinfo=user_tz)
    else:
        start_datetime = start_date
    query = query.where(Activity.start_time >= start_datetime)
```

**적용 위치**: `activities.py:220-241`, 날짜 필터 사용하는 모든 엔드포인트

---

### 41. activity_type 기본값 "running"으로 강제

**문제**: Garmin에서 타입 정보가 없을 때 "running"으로 강제하면 데이터 왜곡

```python
# ❌ 잘못된 패턴 - 기본값 running
activity_type=data.get("activityType", {}).get("typeKey", "running")
# 수영, 사이클, 걷기도 "running"으로 저장됨

# ✅ 올바른 패턴 - 기본값 unknown
activity_type=data.get("activityType", {}).get("typeKey", "unknown")
# 타입 정보 없으면 "unknown"으로 명시적 표시
# 프론트엔드에서 별도 아이콘/필터링 가능
```

**적용 위치**: `sync_service.py:957`

---

### 42. recent_activities로 마일리지 차트 집계 시 과소/누락

**문제**: Dashboard의 `recent_activities`는 최근 5개만 반환되어 8주/6개월 집계에 부적합

```typescript
// ❌ 잘못된 패턴 - recent_activities만 사용
const mileageData = useMemo(() => {
  const activities = dashboard?.recent_activities;  // 최대 5개!
  if (!activities) return [];

  // 8주 데이터 생성 시도 → 대부분 0으로 표시됨
  for (let i = 7; i >= 0; i--) {
    const weekDistance = activities
      .filter(a => /* 해당 주 필터 */)
      .reduce((sum, a) => sum + a.distance_km, 0);  // 대부분 0
  }
}, [dashboard?.recent_activities]);

// ✅ 올바른 패턴 - Trends API 사용
const { data: trends } = useTrends(8);  // 8주 데이터

const mileageData = useMemo(() => {
  if (!trends?.weekly_distance) return [];

  return trends.weekly_distance.map((d, index) => ({
    label: /* 라벨 */,
    distance: d.value,  // 실제 주간 집계 데이터
    isCurrent: index === trends.weekly_distance.length - 1,
  }));
}, [trends?.weekly_distance]);
```

**적용 위치**: `Dashboard.tsx:13-58`

---

### 43. Model과 Migration 간 스키마 드리프트

**문제**: SQLAlchemy 모델과 실제 DB 스키마(migration)가 불일치하면 런타임 오류 발생

```python
# ❌ 잘못된 패턴 - Model이 migration과 불일치
class AnalyticsSummary(BaseModel):
    period_type: Mapped[str] = mapped_column(String(10))  # Migration은 String(20)
    # period_end 컬럼 누락 (Migration에는 존재)
    # total_calories 컬럼 누락
    # summary_data JSONB 컬럼 누락
    elevation_gain: Mapped[float] = mapped_column(Float)  # Migration에 없음!

# ✅ 올바른 패턴 - Model과 Migration 동기화
class AnalyticsSummary(BaseModel):
    period_type: Mapped[str] = mapped_column(String(20))  # Migration과 일치
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)  # Migration에 있는 컬럼 추가
    total_calories: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    summary_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # elevation_gain은 summary_data JSONB에 저장
```

**확인 방법**: `alembic/versions/*.py`와 `models/*.py` 비교
**적용 위치**: `analytics.py`, 새 모델 생성 시 항상 migration 확인

---

### 44. UTC vs 사용자 타임존 주/월 경계 계산

**문제**: 주간/월간 summary 계산 시 UTC 기준 경계 사용하면 사용자 시간대와 불일치

```python
# ❌ 잘못된 패턴 - UTC 기준 "오늘"
target_date = target_date or date.today()  # UTC 기준!
# 한국(+9)에서 오전 8시 = UTC 전날 23시 → 잘못된 주/월 배정

# ✅ 올바른 패턴 - 사용자 타임존 기준
from zoneinfo import ZoneInfo
from datetime import datetime

user_tz = ZoneInfo(self.user.timezone or "Asia/Seoul")
if target_date is None:
    now_local = datetime.now(user_tz)
    target_date = now_local.date()

# 주/월 경계도 사용자 타임존 기준으로 계산
start, end = self._get_period_boundaries(period, target_date)
```

**적용 위치**: `dashboard.py:get_summary()`, `get_trends()`, `compare_periods()`

---

### 45. CTL/ATL/TSB 트렌드 계산 O(weeks × history)

**문제**: 12주 트렌드 조회 시 매주 전체 히스토리 재계산 → 성능 저하

```python
# ❌ 잘못된 패턴 - 매주 전체 재계산
while current <= end_date:
    # 매번 전체 히스토리 로드 + EMA 계산 (O(n) per week)
    metrics = self._calculate_fitness_metrics(current)
    result.append({"date": current, **metrics})
    current += timedelta(weeks=1)
# 총 복잡도: O(weeks × history_days) = O(12 × 1000) = O(12,000)

# ✅ 올바른 패턴 - 한 번의 순회로 모든 샘플 수집
def _batch_calculate_fitness_metrics(self, sample_dates, max_date):
    # 전체 히스토리 한 번만 로드
    activities = self._get_activities_in_range(earliest, max_date)
    daily_loads = build_daily_loads(activities)

    sample_set = set(sample_dates)
    results = {}

    # 한 번 순회하며 필요한 날짜에서 샘플링
    current = earliest_load
    while current <= latest_sample:
        ctl = ctl + decay_42 * (load - ctl)
        atl = atl + decay_7 * (load - atl)

        if current in sample_set:
            results[current] = {"ctl": ctl, "atl": atl, "tsb": ctl - atl}
        current += timedelta(days=1)

    return results
# 총 복잡도: O(history_days) = O(1,000) — 12배 개선!
```

**적용 위치**: `dashboard.py:_get_fitness_trend()`, `_batch_calculate_fitness_metrics()`

---

### 43. CSS 유틸리티 클래스 누락

**문제**: 컴포넌트에서 사용하는 `bg-info`, `bg-muted` 등이 CSS에 정의되지 않음

```css
/* ❌ 잘못된 패턴 - 정의 없이 사용 */
.activity-indicator {
  @apply bg-info;  /* 에러 또는 무시됨 */
}

/* ✅ 올바른 패턴 - index.css에 유틸리티 클래스 추가 */
.bg-info { background: var(--color-info, #3b82f6); }
.bg-muted { background: var(--color-text-muted); }
```

**적용 위치**: `index.css:282-283`, `CompactActivities.tsx:23-32`

---

### 46. 앱 레벨 중복 체크 vs DB 유니크 제약

**문제**: 앱 레벨에서 SELECT 후 INSERT하면 race condition으로 중복 발생 가능

```python
# ❌ 잘못된 패턴 - race condition 취약
existing = await db.execute(
    select(Schedule).where(
        Schedule.workout_id == workout_id,
        Schedule.scheduled_date == date,
    )
)
if existing.scalar_one_or_none():
    raise HTTPException(409, "Already scheduled")

schedule = Schedule(workout_id=workout_id, scheduled_date=date)
db.add(schedule)
await db.commit()
# 두 요청이 동시에 SELECT → 둘 다 없음 → 둘 다 INSERT → 중복!

# ✅ 올바른 패턴 - DB 유니크 제약 + IntegrityError 처리
class Schedule(BaseModel):
    __table_args__ = (
        UniqueConstraint("workout_id", "scheduled_date", name="uq_schedule"),
    )

from sqlalchemy.exc import IntegrityError

schedule = Schedule(workout_id=workout_id, scheduled_date=date)
db.add(schedule)
try:
    await db.commit()
except IntegrityError:
    await db.rollback()
    raise HTTPException(409, "Already scheduled")
```

**적용 위치**: `workouts.py:schedule_workout()`, 중복 방지가 필요한 모든 엔드포인트

---

### 47. 페이지네이션 정렬 시 tie-breaker 누락

**문제**: 정렬 기준 컬럼 값이 동일할 때 순서가 불안정하여 페이지 이동 시 중복/누락 발생

```python
# ❌ 잘못된 패턴 - 단일 컬럼 정렬
query = query.order_by(Schedule.scheduled_date.asc())
# 같은 날짜에 3개 스케줄이 있으면 page 1,2 이동 시 순서 달라짐

# ✅ 올바른 패턴 - tie-breaker 추가
query = query.order_by(Schedule.scheduled_date.asc(), Schedule.id.asc())
# id는 항상 고유하므로 안정적인 순서 보장
```

**적용 위치**: `workouts.py:list_schedules()`, 모든 페이지네이션 쿼리

---

### 48. Status 값 문자열 하드코딩 vs Enum

**문제**: status 값이 여러 곳에 문자열로 흩어지면 오타 및 일관성 문제 발생

```python
# ❌ 잘못된 패턴 - 문자열 하드코딩
schedule.status = "scheduled"  # 파일 A
schedule.status = "scheudled"  # 파일 B - 오타!
if status == "Scheduled":  # 대소문자 불일치

# ✅ 올바른 패턴 - Enum 정의 및 사용
class WorkoutScheduleStatus(str, Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"

# Model에서
status: Mapped[str] = mapped_column(
    String(20),
    default=WorkoutScheduleStatus.SCHEDULED.value,
)

# Endpoint에서 - FastAPI가 자동 검증
status_filter: WorkoutScheduleStatus | None = None
```

**적용 위치**: `workout.py`, `workouts.py` - status 사용하는 모든 곳

---

### 49. SQLAlchemy 모델과 Migration 스키마 드리프트

**문제**: Migration에는 컬럼이 있지만 Model에 없으면 ORM에서 해당 필드 접근 불가

```python
# Migration (001_initial_schema.py)
sa.Column("completed_activity_id", sa.Integer(), nullable=True),
sa.ForeignKeyConstraint(["completed_activity_id"], ["activities.id"]),

# ❌ 잘못된 패턴 - Model에 컬럼 누락
class WorkoutSchedule(BaseModel):
    workout_id: Mapped[int]
    scheduled_date: Mapped[date]
    status: Mapped[str]
    # completed_activity_id 없음! DB에는 있는데...

# ✅ 올바른 패턴 - Model과 Migration 동기화
class WorkoutSchedule(BaseModel):
    workout_id: Mapped[int]
    scheduled_date: Mapped[date]
    status: Mapped[str]
    completed_activity_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("activities.id", ondelete="SET NULL"),
        nullable=True,
    )
```

**확인 방법**: `alembic/versions/*.py`의 CREATE TABLE과 `models/*.py` 비교
**적용 위치**: `workout.py`, 새 모델 작성 시 항상 migration 확인

---

### 44. Pydantic 스키마와 반환 타입 불일치

**문제**: API 스키마가 `int`를 기대하는데 서비스에서 `str`을 반환

```python
# Pydantic Schema
class TrainingPaces(BaseModel):
    vdot: float
    easy_min: int  # seconds per km (정수)
    easy_max: int

# ❌ 잘못된 패턴 - 문자열 반환
def calculate_training_paces(self):
    easy_min = f"{pace // 60}:{pace % 60:02d}/km"  # "5:30/km" 문자열!
    return {"easy_min": easy_min}  # ValidationError!

# ✅ 올바른 패턴 - 스키마와 일치하는 타입 반환
def calculate_training_paces(self):
    easy_min = int(round(pace_seconds))  # 330 (정수, 초 단위)
    return {"easy_min": easy_min}  # OK
```

**적용 위치**: `services/dashboard.py`, `endpoints/dashboard.py`

---

### 50. SQLAlchemy 모델과 Migration 컬럼명 불일치

**문제**: Migration에서 정의한 컬럼명과 Model에서 사용하는 필드명이 다르면 DB 접근 시 오류 발생

```python
# Migration (001_initial_schema.py)
sa.Column("token_count", sa.Integer(), nullable=True),

# ❌ 잘못된 패턴 - 컬럼명 불일치
class AIMessage(BaseModel):
    tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # DB에는 token_count가 있는데 tokens로 접근하려고 함!

# ✅ 올바른 패턴 - DB 컬럼명과 일치
class AIMessage(BaseModel):
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 또는 명시적 컬럼명 지정:
    tokens: Mapped[Optional[int]] = mapped_column("token_count", Integer, nullable=True)
```

**적용 위치**: `models/ai.py` - AIMessage.token_count, AIConversation.context_type/context_data

---

### 51. 외부 API JSON 파싱 예외 미처리

**문제**: 외부 서비스(AI 등)에서 반환한 JSON이 스키마와 맞지 않을 때 500 에러 발생

```python
# ❌ 잘못된 패턴 - ValidationError 미처리
plan_data = ai_response.get("plan")
plan_request = PlanImportRequest.model_validate(plan_data)  # ValidationError → 500!

# ✅ 올바른 패턴 - 명시적 예외 처리
from pydantic import ValidationError as PydanticValidationError

try:
    plan_request = PlanImportRequest.model_validate(plan_data)
except PydanticValidationError as e:
    logger.warning(f"AI generated invalid plan JSON: {e}")
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,  # 외부 서비스 오류
        detail=f"Invalid format: {e.error_count()} validation errors",
    )
```

**적용 위치**: `endpoints/ai.py` - AI plan 생성/import 로직

---

### 52. 기간 계산 시 inclusive/exclusive 혼동

**문제**: end_date를 inclusive로 볼지 exclusive로 볼지 일관성 없으면 1일 오차 발생

```python
# ❌ 잘못된 패턴 - weeks * 7일 그대로 더함 (exclusive)
plan_duration = timedelta(weeks=4)  # 28일
end_date = start_date + plan_duration  # 1일 길어짐!
# 1주차: 1-7일, 2주차: 8-14일, 3주차: 15-21일, 4주차: 22-28일
# end_date는 29일째가 됨 (exclusive)

# ✅ 올바른 패턴 - inclusive end_date 계산
plan_duration_days = num_weeks * 7 - 1  # 27일 (마지막 날 포함)
end_date = start_date + timedelta(days=plan_duration_days)
# 4주차 마지막 날(28일째)이 end_date
```

**적용 위치**: `endpoints/ai.py:import_plan()` - 플랜 기간 계산

---

### 53. 날짜 검증 누락

**문제**: goal_date가 start_date보다 이른 경우 논리적 오류 발생하지만 검증 없이 통과

```python
# ❌ 잘못된 패턴 - 검증 없이 날짜 사용
plan_start_date = start_date_parsed
plan_end_date = goal_date_parsed or (plan_start_date + duration)
# goal_date가 start_date보다 이르면 음수 기간의 플랜 생성!

# ✅ 올바른 패턴 - 명시적 검증
if goal_date_parsed and goal_date_parsed < plan_start_date:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"goal_date ({goal_date_parsed}) cannot be before start_date ({plan_start_date})",
    )
```

**적용 위치**: `endpoints/ai.py:import_plan()`, 날짜 범위 검증이 필요한 모든 곳

---

### 54. Clipboard API await 누락

**문제**: `navigator.clipboard.writeText()`는 Promise를 반환하지만 await 없이 호출하면 에러 감지 불가

```typescript
// ❌ 잘못된 패턴 - await 없이 호출
navigator.clipboard.writeText(text);  // Promise 반환, 에러 무시됨
alert('복사 완료!');  // 실제 실패해도 성공 메시지 표시

// ✅ 올바른 패턴 - await + 에러 처리
try {
  await navigator.clipboard.writeText(text);
  alert('복사 완료!');
} catch (error) {
  console.error('Clipboard write failed:', error);
  alert('클립보드 복사에 실패했습니다.');
}
```

**적용 위치**: `pages/Coach.tsx:handleExportSummary()`, 모든 clipboard 작업

---

### 55. API 응답 객체 vs 필드 추출 혼동

**문제**: API가 객체를 반환하는데 string으로 기대하거나, 필요한 필드만 추출하지 않고 전체 객체 사용

```typescript
// ❌ 잘못된 패턴 - 응답 타입 불일치
const summary = await exportSummary.mutateAsync('markdown');
// summary는 { format, content, generated_at } 객체인데
navigator.clipboard.writeText(typeof summary === 'string' ? summary : JSON.stringify(summary));
// JSON.stringify된 전체 객체가 복사됨!

// ✅ 올바른 패턴 - 필요한 필드만 추출
const response = await exportSummary.mutateAsync('markdown');
const content = response.content;  // content 필드만 추출
await navigator.clipboard.writeText(content);
```

**적용 위치**: `pages/Coach.tsx:handleExportSummary()`, 모든 API 응답 처리

---

### 56. None/null 값의 문자열 연결 (f-string)

**문제**: Python f-string에서 None 값이 "None" 문자열로 변환됨

```python
# ❌ 잘못된 패턴 - None 체크 없이 f-string
avg_hr = None  # 데이터 없음
markdown = f"- 평균 심박수: {avg_hr}bpm"  # "- 평균 심박수: Nonebpm" 출력!

# ✅ 올바른 패턴 - 조건부 문자열
avg_hr = data.get('avg_hr')
line = f"- 평균 심박수: {avg_hr}bpm" if avg_hr else "- 평균 심박수: N/A"
```

**적용 위치**: `endpoints/ai.py:_format_markdown_summary()`, 모든 선택적 필드 포맷팅

---

### 57. Python 임포트 모듈명과 지역 변수명 충돌 (Variable Shadowing)

**문제**: `from fastapi import status` 후 함수 내에서 `status = ...`로 지역 변수 선언 시, 임포트한 모듈이 가려져서 `UnboundLocalError` 발생

```python
from fastapi import status, HTTPException

async def my_endpoint():
    try:
        # ... some code
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,  # ← 에러!
            detail="Error"
        )

    # ❌ 잘못된 패턴 - 임포트된 모듈명과 동일한 변수명
    status = payload.get("status")  # 이 할당이 위의 status를 가림
    if status == "plan":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,  # UnboundLocalError!
            detail="Error"
        )

# ✅ 올바른 패턴 - 다른 변수명 사용
async def my_endpoint():
    try:
        # ...
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,  # 정상 작동
            detail="Error"
        )

    response_status = payload.get("status")  # 다른 이름 사용
    if response_status == "plan":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,  # 정상 작동
            detail="Error"
        )
```

**원인**: Python은 함수 내에서 변수가 할당되면 해당 변수를 지역 변수로 취급합니다 (함수 전체에 적용). 따라서 `status = ...`가 함수 끝에 있어도, 함수 시작 부분에서 `status.HTTP_503`을 참조하면 "아직 할당되지 않은 지역 변수"로 인식되어 `UnboundLocalError`가 발생합니다.

**적용 위치**: `endpoints/ai.py:quick_chat()`, `endpoints/ai.py:conversation_chat()`, 모든 FastAPI 엔드포인트

---

### 58. SQLAlchemy 모델 필드 변경 후 응답 스키마 미동기화

**문제**: SQLAlchemy 모델 컬럼명을 변경했지만, API 응답 생성 코드에서 여전히 이전 컬럼명을 참조

```python
# SQLAlchemy 모델이 변경됨:
# 이전: language, model
# 현재: context_type, context_data

# ❌ 잘못된 패턴 - 모델은 변경했지만 응답 코드는 그대로
return ConversationDetailResponse(
    id=conversation.id,
    title=conversation.title,
    language=conversation.language,  # AttributeError!
    model=conversation.model,        # AttributeError!
    ...
)

# ✅ 올바른 패턴 - 응답 스키마와 모델 필드 동기화
return ConversationDetailResponse(
    id=conversation.id,
    title=conversation.title,
    context_type=conversation.context_type,
    context_data=conversation.context_data,
    ...
)
```

**체크리스트**: 모델 필드 변경 시
1. SQLAlchemy 모델 수정
2. Pydantic 응답 스키마 수정
3. **API 엔드포인트 응답 생성 코드 수정** (이 부분 누락 가능성 높음)
4. 프론트엔드 타입 정의 수정

**적용 위치**: `endpoints/ai.py:get_conversation()`, 모든 모델 필드 변경 작업

---

## Backend - Data Parsing

### 23. Garmin RepeatGroupDTO 중첩 스텝 미파싱

**문제**: Garmin 워크아웃에서 인터벌 구간은 `RepeatGroupDTO` 내부에 중첩된 `workoutSteps` 배열로 저장됨. 단순 반복문은 이 중첩 구조를 파싱하지 못해 페이스 타겟 정보가 누락됨.

```python
# ❌ 잘못된 패턴 - 최상위 스텝만 파싱
def _parse_garmin_workout_steps(workout_data: dict) -> list[dict]:
    steps = []
    for segment in workout_data.get("workoutSegments", []):
        for step in segment.get("workoutSteps", []):
            # RepeatGroupDTO 내부 스텝 누락!
            parsed_step = _parse_single_step(step)
            steps.append(parsed_step)
    return steps

# ✅ 올바른 패턴 - RepeatGroupDTO 중첩 처리
def _parse_garmin_workout_steps(workout_data: dict) -> list[dict]:
    steps = []
    for segment in workout_data.get("workoutSegments", []):
        for step in segment.get("workoutSteps", []):
            step_type = step.get("type", "")

            if step_type == "RepeatGroupDTO":
                repeat_count = step.get("numberOfIterations", 1)
                nested_steps = step.get("workoutSteps", [])

                # 반복 마커 추가
                steps.append({
                    "type": "main",
                    "description": f"🔄 {repeat_count}회 반복",
                    "is_repeat_marker": True,
                    "repeat_count": repeat_count,
                })

                # 중첩 스텝 파싱
                for nested_step in nested_steps:
                    parsed = _parse_single_step(nested_step)
                    if parsed:
                        steps.append(parsed)
            else:
                parsed = _parse_single_step(step)
                if parsed:
                    steps.append(parsed)
    return steps
```

**Garmin 데이터 구조 예시**:
```json
{
  "workoutSegments": [{
    "workoutSteps": [
      { "type": "ExecutableStepDTO", "stepType": {"stepTypeKey": "warmup"} },
      {
        "type": "RepeatGroupDTO",
        "numberOfIterations": 5,
        "workoutSteps": [
          {
            "stepType": {"stepTypeKey": "interval"},
            "targetType": {"workoutTargetTypeKey": "pace.zone"},
            "targetValueOne": 3.5714286,  // m/s → 4:40/km
            "targetValueTwo": 3.508772
          }
        ]
      },
      { "type": "ExecutableStepDTO", "stepType": {"stepTypeKey": "cooldown"} }
    ]
  }]
}
```

**페이스 변환**: `1000 / speed_mps / 60` = 분:초/km

**적용 위치**: `endpoints/workouts.py:_parse_garmin_workout_steps()`

---

## Backend - AI Service Issues

### 59. quick_chat() updated_at 미업데이트

**문제**: `quick_chat()` 함수에서 새 대화 생성 후 `updated_at` 필드를 갱신하지 않아 대화 목록 정렬이 부정확해짐

```python
# ❌ 잘못된 패턴 - updated_at 미갱신
assistant_message = AIMessage(...)
db.add(assistant_message)
await db.commit()  # updated_at 갱신 누락!

# ✅ 올바른 패턴 - updated_at 명시적 갱신
assistant_message = AIMessage(...)
db.add(assistant_message)
conversation.updated_at = datetime.now(timezone.utc)  # 추가
await db.commit()
```

**적용 위치**: `endpoints/ai.py:quick_chat()`

---

### 60. Plan Import Docstring과 실제 코드 불일치

**문제**: `PlanImportRequest` docstring이 `weeks * 7`로 설명하지만 실제 코드는 `weeks * 7 - 1`을 사용 (end_date가 inclusive이므로)

```python
# ❌ 잘못된 docstring
"""
2. start_date not provided + goal_date provided: start_date = goal_date - (weeks * 7 days)
3. Neither provided: start_date = today, end_date = today + (weeks * 7 days)
"""

# ✅ 올바른 docstring - 실제 코드와 일치
"""
2. start_date not provided + goal_date provided: start_date = goal_date - (weeks * 7 - 1) days
3. Neither provided: start_date = today, end_date = today + (weeks * 7 - 1) days

Note: end_date is INCLUSIVE. For N weeks, the plan spans N*7 days (day 1 to day N*7),
so end_date = start_date + (N * 7 - 1) days.
"""
```

**적용 위치**: `endpoints/ai.py:PlanImportRequest`

---

### 61. Unicode-unsafe 제목 Truncation

**문제**: 한글 등 멀티바이트 문자 중간에서 문자열을 자르면 깨진 문자 발생 가능

```python
# ❌ 잘못된 패턴 - 문자 경계 무시
title = request.message[:50] + "..." if len(request.message) > 50 else request.message

# ✅ 올바른 패턴 - Unicode-safe truncation 함수 사용
def _truncate_unicode_safe(text: str, max_length: int, suffix: str = "...") -> str:
    if len(text) <= max_length:
        return text
    truncated = text[:max_length]
    # 가능하면 단어 경계에서 자르기
    last_space = truncated.rfind(" ")
    if last_space > max_length // 2:
        truncated = truncated[:last_space]
    return truncated + suffix

title = _truncate_unicode_safe(request.message, 50)
```

**적용 위치**: `endpoints/ai.py:quick_chat()`, `_truncate_unicode_safe()` 함수 추가

---

### 62. 하드코딩된 토큰 비용

**문제**: 토큰 비용이 `0.002` (GPT-4o 가격)로 하드코딩되어 있어 Gemini 사용 시 부정확한 비용 계산

```python
# ❌ 잘못된 패턴 - 하드코딩된 단일 provider 가격
cost_per_1k_tokens = 0.002

# ✅ 올바른 패턴 - 설정 기반 multi-provider 지원
if settings.ai_provider == "google":
    cost_per_1k_tokens = settings.ai_token_cost_google  # 0.00075
else:
    cost_per_1k_tokens = settings.ai_token_cost_openai  # 0.002
```

**설정 추가**: `config.py`에 `ai_token_cost_google`, `ai_token_cost_openai` 설정 추가

**적용 위치**: `endpoints/ai.py:get_token_usage()`, `core/config.py`

---

### 63. 하드코딩된 페이스 임계값 (ai_snapshot)

**문제**: AI 스냅샷의 인터벌/템포 페이스 임계값이 하드코딩되어 사용자 맞춤 불가

```python
# ❌ 잘못된 패턴 - 하드코딩
DEFAULT_INTERVAL_CUTOFF = 270  # 4:30/km
DEFAULT_TEMPO_CUTOFF = 300     # 5:00/km

# ✅ 올바른 패턴 - 설정에서 로드
DEFAULT_INTERVAL_CUTOFF = settings.ai_default_interval_pace
DEFAULT_TEMPO_CUTOFF = settings.ai_default_tempo_pace
```

**설정 추가**: `config.py`에 `ai_default_interval_pace`, `ai_default_tempo_pace` 설정 추가

**적용 위치**: `services/ai_snapshot.py`, `core/config.py`

---

### 64. 하드코딩된 All-time 시작 연도

**문제**: All-time 스냅샷 조회 시 시작일이 `datetime(2000, 1, 1)`로 하드코딩되어 의미 불분명

```python
# ❌ 잘못된 패턴 - 매직 넘버
window_start = datetime(2000, 1, 1).date()  # 왜 2000년?

# ✅ 올바른 패턴 - 명시적 상수 사용
ALL_TIME_START_YEAR = 2006  # GPS 러닝 워치가 대중화된 시기

if weeks is None:
    window_start = datetime(ALL_TIME_START_YEAR, 1, 1).date()
```

**적용 위치**: `services/ai_snapshot.py`

---

### 65. Backend/Frontend 스키마 불일치 - RaceCreate 필드 누락

**문제**: Frontend에서 대회 기록 생성 시 `is_completed`, `result_time_seconds`, `result_notes` 필드를 전달하지만 Backend `RaceCreate` 스키마에 해당 필드가 없어서 저장되지 않음

```typescript
// Frontend Records.tsx - RecordEditModal
onSave(null, {
  name,
  race_date: raceDate,
  is_completed: true,           // ❌ Backend RaceCreate에 없음
  result_time_seconds: 2685,    // ❌ Backend RaceCreate에 없음
  result_notes: "PB 달성!",     // ❌ Backend RaceCreate에 없음
});
```

```python
# ❌ 잘못된 패턴 - Backend RaceCreate에 결과 필드 누락
class RaceCreate(BaseModel):
    name: str
    race_date: date
    distance_km: Optional[float] = None
    is_primary: bool = False
    # is_completed, result_time_seconds, result_notes 없음!

# ✅ 올바른 패턴 - 완료된 대회 생성 지원
class RaceCreate(BaseModel):
    name: str
    race_date: date
    distance_km: Optional[float] = None
    is_primary: bool = False
    # Fields for creating completed races (e.g., from personal records)
    is_completed: bool = False
    result_time_seconds: Optional[int] = None
    result_notes: Optional[str] = None
```

**증상**:
- 수정 모달에서 저장 버튼 클릭 시 아무 반응 없음 (실제로는 새 대회가 생성되지만 result_time_seconds=null)
- DB에 중복 레코드 생성
- `findRaceForRecord`가 `is_completed=true AND result_time_seconds IS NOT NULL` 조건으로 조회하므로 기존 대회 찾지 못함

**적용 위치**:
- `backend/app/api/v1/endpoints/races.py`: `RaceCreate` 스키마
- `frontend/src/api/races.ts`: `RaceCreate` 인터페이스

---

### 66. Race Times 카드에서 공식 기록 대신 Garmin 기록 표시

**문제**: Race Times 섹션에서 연결된 레이스의 공식 기록(result_time_seconds)이 아닌 원래 Garmin 활동 시간(record.value)을 표시함

```typescript
// ❌ 잘못된 패턴 - 항상 Garmin 기록 표시
{records.distance_records.map((record) => {
  const existingRace = findRaceForRecord(record);
  return (
    <RecordCard
      value={record.value}  // 항상 Garmin 활동 시간 (46:00)
      activityName={record.activity_name}
      // ...
    />
  );
})}

// ✅ 올바른 패턴 - 공식 기록이 있으면 우선 표시
{records.distance_records.map((record) => {
  const existingRace = findRaceForRecord(record);
  // 연결된 레이스가 있고 공식 기록이 있으면 공식 기록 표시
  const displayValue = existingRace?.result_time_seconds ?? record.value;
  const displayName = existingRace?.name ?? record.activity_name;
  return (
    <RecordCard
      value={displayValue}  // 공식 기록 44:45 (있으면)
      activityName={displayName}  // 대회명 (있으면)
      // ...
    />
  );
})}
```

**증상**:
- DB에 공식 기록(44:45)이 저장되어 있지만 카드에는 Garmin 기록(46:00) 표시
- 수정 모달을 열면 올바른 44:45가 표시됨 (DB에서 읽어오므로)
- 화면과 DB 간의 표시 불일치

**적용 위치**:
- `frontend/src/pages/Records.tsx`: Race Times 섹션의 RecordCard 렌더링

---

### 67. 대회 기록 섹션에 Garmin PB가 누락됨

**문제**: "대회 기록" 섹션이 수동으로 등록된 `completedRaces`만 표시하고, Garmin에서 가져온 `distance_records`(PB)는 표시하지 않음

```typescript
// ❌ 잘못된 패턴 - completedRaces만 표시
const completedRaces = racesData?.races.filter((r) => r.is_completed) || [];

{completedRaces.length > 0 && (
  <section>
    <h2>대회 기록</h2>
    {completedRaces.map((race) => (
      <RaceCard race={race} variant="completed" />
    ))}
  </section>
)}

// ✅ 올바른 패턴 - completedRaces + Garmin-only distance_records 병합
const garminOnlyRecords = records.distance_records
  .filter((record) => !findRaceForRecord(record))  // 연결된 레이스 없는 것만
  .map((record) => ({
    id: `garmin-${record.category}`,
    name: record.activity_name || record.category,
    race_date: record.achieved_date,
    result_time_seconds: record.value,
    isGarminOnly: true,
    originalRecord: record,
    // ... 필요한 필드들
  }));

const allRaceRecords = [
  ...completedRaces.map(r => ({ ...r, isGarminOnly: false })),
  ...garminOnlyRecords,
].sort((a, b) => new Date(b.race_date).getTime() - new Date(a.race_date).getTime());

{allRaceRecords.map((record) => (
  record.isGarminOnly ? (
    <GarminPBCard record={record} onClick={() => setEditingRecord(...)} />
  ) : (
    <RaceCard race={record} variant="completed" />
  )
))}
```

**데이터 구조**:
- `distance_records`: Garmin에서 가져온 거리별 PB (5K, 10K, Half, Marathon 등)
- `completedRaces`: 사용자가 수동으로 등록한 완료된 대회
- `findRaceForRecord()`: distance_record와 매칭되는 completedRace 찾기

**증상**:
- "Race Times" 섹션에는 Garmin PB가 표시되지만
- "대회 기록" 섹션에는 수동 등록된 대회만 표시됨
- Garmin PB 중 대회로 등록되지 않은 기록이 누락됨

**해결**:
- 두 데이터 소스를 병합하여 "대회 기록" 섹션에 표시
- Garmin-only 기록은 "Garmin PB" 배지와 "클릭하여 대회로 등록" 안내 표시
- 클릭 시 RecordEditModal 열어서 대회로 변환 가능

**적용 위치**:
- `frontend/src/pages/Records.tsx`: "대회 기록" 섹션 렌더링 로직

---

*마지막 업데이트: 2026-01-08*
