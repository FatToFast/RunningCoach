# 🚀 Clerk + Neon + R2 마이그레이션 가이드

## 📋 목차
1. [개요](#개요)
2. [사전 준비](#사전-준비)
3. [Phase 1: Clerk 인증 설정](#phase-1-clerk-인증-설정)
4. [Phase 2: Neon DB 마이그레이션](#phase-2-neon-db-마이그레이션)
5. [Phase 3: R2 스토리지 설정](#phase-3-r2-스토리지-설정)
6. [Phase 4: 애플리케이션 통합](#phase-4-애플리케이션-통합)
7. [검증 및 테스트](#검증-및-테스트)
8. [트러블슈팅](#트러블슈팅)

## 개요

현재 로컬 환경에서 실행되는 RunningCoach를 완전한 클라우드 기반으로 전환합니다.

### 목표 아키텍처
```
[Frontend + Clerk Auth]
         ↓
    [FastAPI Backend]
      ↓         ↓
[Neon DB]    [R2 Storage]
```

### 비용
- **Clerk**: 10,000 MAU 무료
- **Neon**: 3GB 무료
- **R2**: 10GB 무료
- **총 비용**: $0/월 ✨

## 사전 준비

### 계정 생성
1. [Clerk](https://clerk.com) - 인증 서비스
2. [Neon](https://neon.tech) - Serverless PostgreSQL
3. [Cloudflare](https://cloudflare.com) - R2 스토리지

### 로컬 백업
```bash
# 1. 데이터베이스 백업
pg_dump runningcoach > backup_$(date +%Y%m%d).sql

# 2. FIT 파일 백업
tar -czf fit_files_backup.tar.gz backend/data/fit_files

# 3. 환경 변수 백업
cp backend/.env backend/.env.backup
```

## Phase 1: Clerk 인증 설정

### 1.1 Clerk 프로젝트 생성

1. Clerk Dashboard에서 새 애플리케이션 생성
2. 인증 방법 선택:
   - Email/Password
   - Google OAuth
   - Apple OAuth (선택)

3. API Keys 복사:
```bash
CLERK_PUBLISHABLE_KEY=pk_test_xxx
CLERK_SECRET_KEY=sk_test_xxx
```

### 1.2 Clerk 웹훅 설정

Clerk Dashboard > Webhooks:
```
Endpoint URL: https://api.runningcoach.com/webhooks/clerk
Events: user.created, user.updated, user.deleted
```

웹훅 Secret 저장:
```bash
CLERK_WEBHOOK_SECRET=whsec_xxx
```

### 1.3 Frontend 통합

```bash
cd frontend

# Clerk 패키지 설치
npm install @clerk/clerk-react

# 환경 변수 설정
echo "VITE_CLERK_PUBLISHABLE_KEY=pk_test_xxx" >> .env.local
```

App.tsx 수정:
```typescript
import { ClerkProvider } from '@clerk/clerk-react';

const clerkPubKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

function App() {
  return (
    <ClerkProvider publishableKey={clerkPubKey}>
      {/* Your app */}
    </ClerkProvider>
  );
}
```

## Phase 2: Neon DB 마이그레이션

### 2.1 Neon 프로젝트 생성

1. Neon Console에서 새 프로젝트 생성
2. Region: 가장 가까운 리전 선택 (ap-northeast-2 for Seoul)
3. Database 이름: `runningcoach`

### 2.2 Connection String

```bash
# Neon Dashboard에서 복사
DATABASE_URL=postgresql://user:pass@xxx.neon.tech:5432/runningcoach?sslmode=require
```

### 2.3 데이터 마이그레이션

```bash
# 1. 스키마 생성
psql $DATABASE_URL < backup.sql

# 2. Alembic 마이그레이션 실행
cd backend
alembic upgrade head

# 3. Clerk user ID 마이그레이션
python scripts/migrate_users_to_clerk.py
```

### 2.4 Connection Pooling 설정

Neon Console > Settings > Connection Pooling:
- Pool Mode: Transaction
- Pool Size: 25

## Phase 3: R2 스토리지 설정

### 3.1 R2 버킷 생성

1. Cloudflare Dashboard > R2
2. Create Bucket: `fit-files`
3. Settings:
   - Location: Automatic
   - Public Access: Disabled

### 3.2 API 토큰 생성

Cloudflare Dashboard > My Profile > API Tokens:
```
Token Name: RunningCoach R2
Permissions:
  - Account: Cloudflare R2:Edit
  - Zone: None
```

### 3.3 환경 변수 설정

```bash
R2_ACCOUNT_ID=xxx
R2_ACCESS_KEY=xxx
R2_SECRET_KEY=xxx
R2_BUCKET_NAME=fit-files
```

### 3.4 FIT 파일 마이그레이션

```bash
cd backend
python scripts/migrate_fits_to_r2.py

# 진행 상황 확인
python scripts/check_r2_migration.py
```

## Phase 4: 애플리케이션 통합

### 4.1 Backend 설정

```bash
cd backend

# 필요 패키지 설치
pip install pyjwt[crypto] boto3 httpx svix

# .env 파일 업데이트
cat >> .env <<EOF
# Clerk
CLERK_PUBLISHABLE_KEY=pk_test_xxx
CLERK_SECRET_KEY=sk_test_xxx
CLERK_WEBHOOK_SECRET=whsec_xxx

# Neon
DATABASE_URL=postgresql://user:pass@xxx.neon.tech:5432/runningcoach

# R2
R2_ACCOUNT_ID=xxx
R2_ACCESS_KEY=xxx
R2_SECRET_KEY=xxx
R2_BUCKET_NAME=fit-files
EOF
```

### 4.2 API 라우터 업데이트

app/api/v1/router.py:
```python
from app.api.v1.endpoints import upload
from app.core.clerk_auth import get_current_user

# Clerk 인증 사용
router.include_router(
    upload.router,
    prefix="/upload",
    tags=["upload"],
    dependencies=[Depends(get_current_user)]
)
```

### 4.3 Frontend API 클라이언트

hooks/useApi.ts:
```typescript
import { useAuth } from '@clerk/clerk-react';

export function useApi() {
  const { getToken } = useAuth();

  const apiCall = async (endpoint: string, options = {}) => {
    const token = await getToken();

    return fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers: {
        ...options.headers,
        'Authorization': `Bearer ${token}`
      }
    });
  };

  return { apiCall };
}
```

### 4.4 직접 업로드 구현

hooks/useFitUpload.ts:
```typescript
export function useFitUpload() {
  const { apiCall } = useApi();

  const uploadFit = async (file: File, activityId?: number) => {
    // 1. Presigned URL 요청
    const response = await apiCall('/upload/upload-url', {
      method: 'POST',
      body: JSON.stringify({
        activity_id: activityId,
        filename: file.name,
        file_size: file.size
      })
    });

    const { upload_url, key, activity_id } = await response.json();

    // 2. R2 직접 업로드
    const uploadResponse = await fetch(upload_url, {
      method: 'PUT',
      body: file,
      headers: {
        'Content-Type': 'application/octet-stream'
      }
    });

    if (!uploadResponse.ok) {
      throw new Error('Upload failed');
    }

    // 3. 업로드 완료 알림
    await apiCall('/upload/upload-complete', {
      method: 'POST',
      body: JSON.stringify({
        activity_id,
        file_size: file.size
      })
    });

    return { activity_id, key };
  };

  return { uploadFit };
}
```

## 검증 및 테스트

### 5.1 인증 테스트

```bash
# Clerk 토큰 검증
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/auth/me

# 응답 확인
{
  "id": 1,
  "clerk_user_id": "user_xxx",
  "email": "user@example.com"
}
```

### 5.2 DB 연결 테스트

```bash
# Neon 연결 확인
psql $DATABASE_URL -c "SELECT COUNT(*) FROM users;"

# Python에서 테스트
python -c "
from app.core.database import get_db_context
import asyncio

async def test():
    async with get_db_context() as db:
        result = await db.execute('SELECT 1')
        print('DB Connected:', result.scalar())

asyncio.run(test())
"
```

### 5.3 R2 업로드 테스트

```python
# scripts/test_r2_upload.py
from app.services.r2_storage import R2StorageService

async def test_upload():
    r2 = R2StorageService()

    # 테스트 파일 업로드
    test_data = b"Test FIT file content"
    result = await r2.upload_fit(
        user_id=1,
        activity_id=999,
        fit_data=test_data
    )

    print(f"Upload result: {result}")

    # 다운로드 테스트
    downloaded = await r2.download_fit(
        user_id=1,
        activity_id=999
    )

    assert downloaded == test_data
    print("✅ R2 upload/download test passed!")

asyncio.run(test_upload())
```

### 5.4 통합 테스트

```bash
# 전체 플로우 테스트
cd backend
pytest tests/integration/test_clerk_neon_r2.py -v
```

## 배포

### 6.1 Backend 배포 (Railway)

```bash
# railway.toml
[build]
  builder = "nixpacks"

[deploy]
  startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"

# 배포
railway login
railway link
railway up
```

### 6.2 Frontend 배포 (Vercel)

```bash
# vercel.json
{
  "env": {
    "VITE_CLERK_PUBLISHABLE_KEY": "@clerk_publishable_key",
    "VITE_API_URL": "@api_url"
  }
}

# 배포
vercel --prod
```

## 트러블슈팅

### Clerk 인증 오류

**문제**: "Invalid token" 오류
```bash
# JWKS URL 확인
curl https://YOUR_CLERK_DOMAIN/.well-known/jwks.json

# 토큰 디코딩 테스트
jwt decode $TOKEN --no-verify
```

### Neon 연결 오류

**문제**: "too many connections" 오류
```python
# Connection pool 설정
engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=0,
    pool_pre_ping=True
)
```

### R2 업로드 오류

**문제**: "SignatureDoesNotMatch" 오류
```bash
# 시간 동기화 확인
date
ntpdate -s time.nist.gov

# Access Key 확인
echo $R2_ACCESS_KEY | base64 -d
```

## 모니터링

### 대시보드 URL
- Clerk: https://dashboard.clerk.com
- Neon: https://console.neon.tech
- Cloudflare: https://dash.cloudflare.com

### 알림 설정
```bash
# Clerk 웹훅 알림
# Neon 사용량 알림 (80% 도달 시)
# R2 스토리지 알림 (9GB 도달 시)
```

## 롤백 계획

만약 문제가 발생하면:

```bash
# 1. 로컬 DB로 롤백
export DATABASE_URL=postgresql://localhost/runningcoach

# 2. 로컬 인증으로 롤백
git checkout pre-clerk-migration

# 3. 로컬 FIT 파일로 롤백
tar -xzf fit_files_backup.tar.gz
```

## 완료 체크리스트

- [ ] Clerk 계정 생성 및 설정
- [ ] Neon DB 생성 및 마이그레이션
- [ ] R2 버킷 생성 및 설정
- [ ] Backend 코드 업데이트
- [ ] Frontend 코드 업데이트
- [ ] 환경 변수 설정
- [ ] 테스트 실행
- [ ] 스테이징 배포
- [ ] 프로덕션 배포
- [ ] 모니터링 설정

---

🎉 **축하합니다!** RunningCoach가 이제 완전한 클라우드 기반으로 전환되었습니다.

문제가 있으면 GitHub Issues에 보고해주세요: https://github.com/runningcoach/issues