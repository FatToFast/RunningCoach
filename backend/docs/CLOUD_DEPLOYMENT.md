# RunningCoach 클라우드 배포 가이드

## 🎯 추천: Supabase (DB + Storage 통합)

### 아키텍처
```
[Frontend - Vercel]
    ↓
[Backend API - Railway/Fly.io]
    ↓
[Supabase]
  ├─ PostgreSQL (활동 데이터)
  └─ Storage (FIT 파일)
```

## Supabase 설정 (15분)

### 1. 프로젝트 생성
```bash
# supabase.com에서 프로젝트 생성 후
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJxxx...
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.xxx.supabase.co:5432/postgres
```

### 2. Storage Bucket 설정
```sql
-- Supabase Dashboard SQL Editor
INSERT INTO storage.buckets (id, name, public)
VALUES ('fit-files', 'fit-files', false);

-- RLS 정책 (사용자별 접근 제한)
CREATE POLICY "Users can upload their own FIT files"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'fit-files' AND
            auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can view their own FIT files"
ON storage.objects FOR SELECT
TO authenticated
USING (bucket_id = 'fit-files' AND
       auth.uid()::text = (storage.foldername(name))[1]);
```

### 3. 서비스 통합 코드

```python
# app/services/supabase_storage.py
from supabase import create_client, Client
from typing import Optional, Dict
import os

class SupabaseStorageService:
    def __init__(self):
        self.client: Client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_KEY")  # Service key for backend
        )
        self.bucket = "fit-files"

    async def upload_fit(
        self,
        user_id: int,
        activity_id: int,
        fit_data: bytes
    ) -> Dict[str, str]:
        """Upload FIT file to Supabase Storage."""

        # Path: user_id/activity_id.fit
        path = f"{user_id}/{activity_id}.fit"

        # Upload
        response = self.client.storage.from_(self.bucket).upload(
            path,
            fit_data,
            {"content-type": "application/octet-stream"}
        )

        # Generate signed URL (1 hour)
        signed_url = self.client.storage.from_(self.bucket)\
            .create_signed_url(path, 3600)

        return {
            "path": path,
            "signed_url": signed_url["signedURL"],
            "size": len(fit_data)
        }

    async def get_fit(
        self,
        user_id: int,
        activity_id: int
    ) -> Optional[bytes]:
        """Download FIT file from Supabase Storage."""

        path = f"{user_id}/{activity_id}.fit"

        # Download
        response = self.client.storage.from_(self.bucket)\
            .download(path)

        return response

    def get_public_url(self, path: str) -> str:
        """Get public URL (if bucket is public)."""
        return self.client.storage.from_(self.bucket)\
            .get_public_url(path)
```

### 4. 마이그레이션 스크립트

```python
# scripts/migrate_to_supabase.py
import asyncio
from pathlib import Path
from supabase import create_client

async def migrate_to_supabase():
    """Migrate existing FIT files to Supabase Storage."""

    # Initialize clients
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    # Get all activities with FIT files
    activities = await db.query("""
        SELECT id, user_id, fit_file_path, fit_file_content
        FROM activities
        WHERE fit_file_path IS NOT NULL
           OR fit_file_content IS NOT NULL
    """)

    for activity in activities:
        # Get FIT data
        if activity.fit_file_content:
            # From DB
            fit_data = decompress(activity.fit_file_content)
        else:
            # From filesystem
            fit_data = Path(activity.fit_file_path).read_bytes()

        # Upload to Supabase
        path = f"{activity.user_id}/{activity.id}.fit"
        supabase.storage.from_("fit-files").upload(path, fit_data)

        # Update record
        await db.execute("""
            UPDATE activities
            SET storage_path = %s, storage_provider = 'supabase'
            WHERE id = %s
        """, (path, activity.id))

        print(f"✓ Migrated activity {activity.id}")

if __name__ == "__main__":
    asyncio.run(migrate_to_supabase())
```

## Railway/Fly.io 배포 (Backend)

### Railway (추천)
```bash
# railway.toml
[build]
  builder = "DOCKERFILE"

[deploy]
  startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"

# 배포
railway login
railway link
railway up
```

### Fly.io
```toml
# fly.toml
app = "runningcoach-api"

[env]
  PORT = "8080"

[[services]]
  internal_port = 8080
  protocol = "tcp"

  [[services.ports]]
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443

# 배포
fly launch
fly deploy
```

## Vercel 배포 (Frontend)

```json
// vercel.json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://runningcoach-api.railway.app/api/:path*"
    }
  ]
}
```

```bash
# 배포
vercel
```

## 환경 변수 설정

### Backend (.env.production)
```bash
# Supabase
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.xxx.supabase.co:5432/postgres
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJxxx...  # Service role key
SUPABASE_ANON_KEY=eyJxxx...     # Public anon key

# Redis (Upstash)
REDIS_URL=redis://default:xxx@xxx.upstash.io:6379

# Auth
SESSION_SECRET=xxx
SECRET_KEY=xxx
COOKIE_SECURE=true
COOKIE_SAMESITE=none

# CORS
CORS_ORIGINS=https://runningcoach.vercel.app
```

### Frontend (.env.production)
```bash
VITE_API_BASE_URL=https://runningcoach-api.railway.app
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJxxx...
```

## 비용 분석 (월)

### Option 1: Supabase + Railway
- Supabase Free: $0
- Railway (API): $5
- **총: $5/월**

### Option 2: Supabase Pro + Vercel
- Supabase Pro: $25
- Vercel Pro: $20
- **총: $45/월** (프로덕션급)

### Option 3: All-in-One PaaS
- Render.com: $7 (DB) + $7 (API) = $14/월
- Fly.io: $7 (DB) + $0 (API) = $7/월

## 모니터링

### Supabase Dashboard
- 실시간 DB 쿼리 모니터링
- Storage 사용량 추적
- API 요청 통계

### Uptime 모니터링
```javascript
// UptimeRobot 또는 Better Uptime 설정
const endpoints = [
  'https://api.runningcoach.com/health',
  'https://runningcoach.com'
];
```

## 백업 전략

### 자동 백업 (Supabase)
- 일일 자동 백업 (7일 보관)
- Point-in-time recovery (Pro)

### 수동 백업
```bash
# DB 백업
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Storage 백업 (rclone)
rclone sync supabase:fit-files ./backups/fit-files
```

## 보안 체크리스트

- [x] HTTPS 강제
- [x] 환경 변수 분리
- [x] RLS (Row Level Security) 활성화
- [x] API Rate Limiting
- [x] CORS 설정
- [x] SQL Injection 방지
- [x] File Upload 크기 제한
- [x] Auth Token 만료 설정

## 결론

**추천 스택:**
1. **Supabase** (DB + Storage) - 통합 관리
2. **Railway/Fly.io** (Backend API) - 간편 배포
3. **Vercel** (Frontend) - 빠른 CDN

**장점:**
- 어디서든 접근 가능
- 자동 백업
- 무료 시작 → 성장 시 업그레이드
- 5분 내 배포 가능

이제 로컬이 아닌 클라우드에서 완전히 구동됩니다!