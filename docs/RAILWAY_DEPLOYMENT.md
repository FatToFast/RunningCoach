# Railway 배포 가이드

RunningCoach를 Railway에 배포하는 방법입니다.

## 아키텍처

```
Railway Project
├── Backend Service (FastAPI)
│   ├── Neon DB (External)
│   ├── Clerk Auth (External)
│   └── R2 Storage (External)
├── Frontend Service (React/Vite)
└── Redis Service (Railway Add-on)
```

## 1. Railway 프로젝트 생성

1. [Railway](https://railway.app) 로그인
2. "New Project" → "Empty Project"
3. 프로젝트 이름: `runningcoach`

## 2. Backend 서비스 배포

### GitHub 연결
1. "New Service" → "GitHub Repo"
2. `runningcoach` 리포지토리 선택
3. **Root Directory**: `backend` 설정

### 환경 변수 설정
Settings → Variables에서 `.env.production.template` 참고하여 설정:

```bash
# 필수 환경 변수
DATABASE_URL=postgresql+asyncpg://...?ssl=require
REDIS_URL=redis://...
SESSION_SECRET=<64자 hex>
SECRET_KEY=<64자 hex>
CLERK_PUBLISHABLE_KEY=pk_live_...
CLERK_SECRET_KEY=sk_live_...
R2_ACCOUNT_ID=...
R2_ACCESS_KEY=...
R2_SECRET_KEY=...
R2_BUCKET_NAME=runningcoach
GARMIN_ENCRYPTION_KEY=<Fernet key>
GOOGLE_AI_API_KEY=...
CORS_ORIGINS=https://frontend-xxx.railway.app
ENVIRONMENT=production
COOKIE_SECURE=true
COOKIE_SAMESITE=none
```

### 보안 키 생성
```bash
# SESSION_SECRET, SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# GARMIN_ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 3. Frontend 서비스 배포

### GitHub 연결
1. "New Service" → "GitHub Repo"
2. 같은 리포지토리 선택
3. **Root Directory**: `frontend` 설정

### 환경 변수 설정
```bash
VITE_API_BASE_URL=https://backend-xxx.railway.app
VITE_CLERK_PUBLISHABLE_KEY=pk_live_...
```

## 4. Redis 추가 (옵션)

1. "New Service" → "Database" → "Redis"
2. 자동으로 `REDIS_URL` 환경변수 주입됨
3. Backend 서비스에서 Redis 참조 설정

또는 [Upstash](https://upstash.com)의 무료 Redis 사용 가능

## 5. 도메인 설정

### 자동 생성 도메인
Railway가 자동으로 `*.railway.app` 도메인 제공

### 커스텀 도메인 (옵션)
1. Settings → Domains → "Add Domain"
2. DNS에 CNAME 레코드 추가

## 6. CORS 설정 업데이트

Frontend 도메인이 확정되면 Backend의 `CORS_ORIGINS` 업데이트:
```bash
CORS_ORIGINS=https://frontend-production-xxx.up.railway.app,https://your-domain.com
```

## 7. Clerk Webhook 설정 (옵션)

사용자 동기화가 필요한 경우:
1. Clerk Dashboard → Webhooks
2. Endpoint: `https://backend-xxx.railway.app/api/v1/webhooks/clerk`
3. Events: `user.created`, `user.updated`, `user.deleted`
4. Signing Secret을 `CLERK_WEBHOOK_SECRET`에 설정

## 8. 배포 확인

```bash
# Health check
curl https://backend-xxx.railway.app/api/v1/health

# API 문서
open https://backend-xxx.railway.app/api/v1/docs
```

## 트러블슈팅

### 502 Bad Gateway
- Backend 로그 확인: Railway Dashboard → Logs
- 환경 변수 누락 확인

### CORS 에러
- `CORS_ORIGINS`에 Frontend 도메인 포함 확인
- `COOKIE_SAMESITE=none`, `COOKIE_SECURE=true` 설정 확인

### DB 연결 실패
- `DATABASE_URL`에 `?ssl=require` 포함 확인
- Neon 대시보드에서 IP allowlist 확인

### Redis 연결 실패
- `REDIS_URL` 형식 확인
- Railway Redis 서비스 상태 확인

## 비용 예상

Railway Hobby Plan ($5/month):
- Backend: ~$3-5/month
- Frontend: ~$1-2/month
- Redis: ~$1-2/month

외부 서비스:
- Neon: Free tier (0.5GB storage)
- R2: Free tier (10GB storage, 10M requests)
- Clerk: Free tier (10,000 MAU)
