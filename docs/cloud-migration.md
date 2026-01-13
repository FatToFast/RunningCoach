# Cloud Migration Guide

RunningCoach 클라우드 배포를 위한 마이그레이션 가이드입니다.

## 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Vercel)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ React + Vite │  │ Clerk React  │  │ Direct R2 Upload     │  │
│  │ TanStack Query│ │ @clerk/clerk │  │ (Presigned URLs)     │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (Fly.io / Railway)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ FastAPI      │  │ Hybrid Auth  │  │ R2 Storage Service   │  │
│  │ Uvicorn      │  │ Clerk + Session│ │ boto3 S3-compatible │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐
│  Neon DB     │    │ Clerk API    │    │ Cloudflare R2        │
│  PostgreSQL  │    │ JWKS + Users │    │ FIT File Storage     │
│  Serverless  │    │              │    │ 10GB Free Tier       │
└──────────────┘    └──────────────┘    └──────────────────────┘
```

## 구성 요소

### 1. Clerk 인증

Clerk은 사용자 인증을 위한 클라우드 서비스입니다.

**특징:**
- JWT 기반 인증
- 소셜 로그인 (Google, GitHub 등)
- Webhook 기반 사용자 동기화
- JWKS를 통한 토큰 검증

**설정 환경변수:**
```bash
# Backend
CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
CLERK_WEBHOOK_SECRET=whsec_...

# Frontend
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
VITE_AUTH_MODE=clerk  # or 'hybrid' for both Clerk and session
```

### 2. Cloudflare R2 스토리지

FIT 파일을 저장하기 위한 S3 호환 오브젝트 스토리지입니다.

**특징:**
- 10GB 무료 티어
- S3 호환 API
- Presigned URL로 직접 업로드
- gzip 압축 지원

**설정 환경변수:**
```bash
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY=your_access_key
R2_SECRET_KEY=your_secret_key
R2_BUCKET_NAME=fit-files
```

### 3. Neon PostgreSQL

서버리스 PostgreSQL 데이터베이스입니다.

**설정:**
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.region.aws.neon.tech/running?sslmode=require
```

## 마이그레이션 단계

### Step 1: 데이터베이스 스키마 업데이트

```bash
cd backend
alembic upgrade head
```

또는 스키마 검증 스크립트 실행:
```bash
python scripts/check_schema.py --fix
```

### Step 2: 환경변수 설정

Backend `.env`:
```bash
# Database (Neon)
DATABASE_URL=postgresql+asyncpg://...

# Clerk
CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
CLERK_WEBHOOK_SECRET=whsec_...

# R2
R2_ACCOUNT_ID=...
R2_ACCESS_KEY=...
R2_SECRET_KEY=...
R2_BUCKET_NAME=fit-files
```

Frontend `.env`:
```bash
VITE_API_BASE_URL=https://your-api.fly.dev
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
VITE_AUTH_MODE=clerk
```

### Step 3: Clerk Webhook 설정

1. Clerk Dashboard에서 Webhooks 설정
2. Endpoint URL: `https://your-api.fly.dev/api/v1/webhooks/clerk`
3. 이벤트 선택: `user.created`, `user.updated`, `user.deleted`
4. Webhook Secret 복사하여 `CLERK_WEBHOOK_SECRET`에 설정

### Step 4: 검증

```bash
# Backend 검증 스크립트 실행
python scripts/verify_cloud_migration.py --verbose

# 테스트 실행
pytest tests/test_cloud_services.py -v
```

## API 엔드포인트

### 업로드 API

```
POST /api/v1/upload/url         - Presigned 업로드 URL 생성
POST /api/v1/upload/complete    - 업로드 완료 확인
GET  /api/v1/upload/activity/{id}/download-url - 다운로드 URL
GET  /api/v1/upload/stats       - 스토리지 사용량
DELETE /api/v1/upload/activity/{id}/fit - FIT 파일 삭제
GET  /api/v1/upload/health      - 서비스 상태
```

### Webhook API

```
POST /api/v1/webhooks/clerk     - Clerk 이벤트 수신
GET  /api/v1/webhooks/health    - 서비스 상태
```

### Debug API (개발 환경만)

```
GET  /api/v1/debug/logs         - 최근 로그 조회
GET  /api/v1/debug/errors       - 최근 에러 조회
GET  /api/v1/debug/timing       - 성능 통계
POST /api/v1/debug/clear        - 로그 삭제
```

## 하이브리드 인증

로컬 개발과 클라우드 배포를 모두 지원하는 하이브리드 인증 시스템입니다.

**인증 순서:**
1. Bearer 토큰이 있으면 Clerk JWT 검증
2. Clerk 검증 실패 또는 토큰 없으면 세션 쿠키 확인
3. 둘 다 없으면 401 Unauthorized

**사용:**
```python
from app.core.hybrid_auth import get_current_user

@router.get("/protected")
async def protected_endpoint(user: User = Depends(get_current_user)):
    return {"user_id": user.id}
```

## 디버깅

### Debug Utilities

```python
from app.core.debug_utils import DebugLogger, CloudMigrationDebug

# 일반 로깅
DebugLogger.info("component", "message", context={"key": "value"})

# 클라우드 마이그레이션 특화 로깅
CloudMigrationDebug.log_clerk_token_verification(
    token_preview="eyJ...",
    success=True,
    user_id="user_123"
)

CloudMigrationDebug.log_r2_operation(
    operation="upload",
    user_id=1,
    activity_id=100,
    success=True,
    details={"size": 10000}
)
```

### 로그 조회 (개발 환경)

```bash
# API로 조회
curl http://localhost:8000/api/v1/debug/logs?component=clerk_auth

# 에러만 조회
curl http://localhost:8000/api/v1/debug/errors

# 성능 통계
curl http://localhost:8000/api/v1/debug/timing
```

## 테스트

```bash
# 전체 클라우드 테스트
./scripts/run_cloud_tests.sh

# 개별 테스트
pytest tests/test_cloud_services.py::TestClerkAuth -v
pytest tests/test_cloud_services.py::TestR2Storage -v
pytest tests/test_cloud_services.py::TestWebhooks -v
```

## 트러블슈팅

### Clerk 인증 실패

1. JWKS URL 확인: `https://{frontend_api}.clerk.accounts.dev/.well-known/jwks.json`
2. Publishable Key 형식 확인: `pk_test_` 또는 `pk_live_` 시작
3. Secret Key가 Backend에 설정되어 있는지 확인

### R2 업로드 실패

1. R2 credential 확인
2. 버킷 이름 및 권한 확인
3. CORS 설정 확인 (Presigned URL 사용 시)

### Webhook 서명 검증 실패

1. `CLERK_WEBHOOK_SECRET` 정확히 설정
2. Request body가 수정되지 않았는지 확인
3. Svix 헤더 (`svix-id`, `svix-timestamp`, `svix-signature`) 존재 확인

## 참고 자료

- [Clerk Documentation](https://clerk.com/docs)
- [Cloudflare R2 Documentation](https://developers.cloudflare.com/r2/)
- [Neon Documentation](https://neon.tech/docs)
