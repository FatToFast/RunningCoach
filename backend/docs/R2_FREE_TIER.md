# Cloudflare R2 무료 티어 활용 가이드

## 🎉 R2 무료 티어 (2025년 기준)

```
✅ 저장: 10GB 무료 (매월)
✅ Class A 작업: 100만 요청/월 무료 (PUT, POST, LIST)
✅ Class B 작업: 1,000만 요청/월 무료 (GET, HEAD)
✅ 전송료(Egress): 완전 무료 (무제한!)
```

## 💡 FIT 파일 저장 계산

### 현재 상황
- FIT 파일 평균: 145KB
- 현재 보유: 330개 파일 (46.71MB)

### R2 무료 티어로 가능한 용량
```
10GB = 10,240MB

가능한 FIT 파일 수:
10,240MB ÷ 0.145MB = 약 70,000개

사용자당 연간 300개 활동 가정:
70,000 ÷ 300 = 약 230명 지원 가능!
```

## 🏆 최적 조합: Neon + R2 (완전 무료!)

```yaml
구성:
  Database: Neon (3GB 무료)
  Storage: Cloudflare R2 (10GB 무료)
  비용: $0/월

지원 규모:
  - 사용자: 200명+
  - FIT 파일: 70,000개
  - DB 데이터: 3GB
```

## 구현 코드

### 1. R2 설정
```python
# app/services/r2_storage.py
import boto3
from typing import Optional
from datetime import datetime

class R2StorageService:
    def __init__(self):
        self.client = boto3.client(
            's3',
            endpoint_url=f'https://{ACCOUNT_ID}.r2.cloudflarestorage.com',
            aws_access_key_id=R2_ACCESS_KEY,
            aws_secret_access_key=R2_SECRET_KEY
        )
        self.bucket = 'fit-files'  # 10GB 무료!

    async def upload_fit(
        self,
        user_id: int,
        activity_id: int,
        fit_data: bytes
    ) -> dict:
        """FIT 파일 업로드 (무료 티어 내)"""

        # 연도별 폴더 구조로 정리
        year = datetime.now().year
        key = f"users/{user_id}/{year}/{activity_id}.fit"

        # 압축하면 더 많이 저장 가능
        compressed = gzip.compress(fit_data)

        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=compressed,
            ContentType='application/gzip'
        )

        return {
            'key': key,
            'original_size': len(fit_data),
            'compressed_size': len(compressed),
            'compression_ratio': f"{(1 - len(compressed)/len(fit_data))*100:.1f}%"
        }

    def generate_presigned_url(
        self,
        user_id: int,
        activity_id: int,
        expires_in: int = 3600
    ) -> str:
        """다운로드용 임시 URL 생성"""

        year = datetime.now().year
        key = f"users/{user_id}/{year}/{activity_id}.fit"

        return self.client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket, 'Key': key},
            ExpiresIn=expires_in
        )
```

### 2. Neon DB 연결
```python
# app/core/database.py
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine

# Neon 무료 티어 (3GB)
DATABASE_URL = "postgresql+asyncpg://user:pass@xxx.neon.tech/db"

engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,  # Neon 무료 티어 connection limit
    max_overflow=0
)
```

### 3. 스토리지 모니터링
```python
# app/api/v1/endpoints/storage.py
@router.get("/storage/stats")
async def get_storage_stats(
    current_user: User = Depends(get_current_user),
    r2: R2StorageService = Depends(get_r2_service)
):
    """R2 사용량 확인 (무료 티어: 10GB)"""

    # List all objects
    response = r2.client.list_objects_v2(
        Bucket='fit-files',
        Prefix=f'users/{current_user.id}/'
    )

    total_size = sum(obj['Size'] for obj in response.get('Contents', []))
    file_count = len(response.get('Contents', []))

    return {
        'user_usage_mb': total_size / 1024 / 1024,
        'file_count': file_count,
        'free_tier_limit_gb': 10,
        'free_tier_remaining_gb': 10 - (total_size / 1024 / 1024 / 1024),
        'percentage_used': (total_size / (10 * 1024 * 1024 * 1024)) * 100
    }
```

## 비용 비교표

| 조합 | DB | Storage | 월 비용 | 지원 규모 |
|------|-----|---------|---------|-----------|
| **Neon + R2** ⭐ | 3GB 무료 | 10GB 무료 | **$0** | 200명 |
| Supabase | 500MB 무료 | 1GB 무료 | $0 | 20명 |
| Railway + R2 | $5 | 10GB 무료 | $5 | 200명 |
| AWS RDS + S3 | $15 | $2.3 | $17.3 | 무제한 |

## 마이그레이션 전략

### Phase 1: R2 버킷 생성 (5분)
```bash
# Cloudflare Dashboard에서
1. R2 > Create Bucket
2. Name: fit-files
3. Location: Automatic (가장 가까운 리전)
```

### Phase 2: 기존 파일 마이그레이션
```python
# scripts/migrate_to_r2.py
async def migrate_to_r2():
    """기존 FIT 파일을 R2로 마이그레이션"""

    r2 = R2StorageService()

    # 로컬 또는 DB에서 파일 읽기
    activities = await db.query(
        "SELECT * FROM activities WHERE fit_file_path IS NOT NULL"
    )

    for activity in activities:
        # 파일 읽기
        if activity.fit_file_content:
            fit_data = decompress(activity.fit_file_content)
        else:
            fit_data = Path(activity.fit_file_path).read_bytes()

        # R2 업로드
        result = await r2.upload_fit(
            activity.user_id,
            activity.id,
            fit_data
        )

        # DB 업데이트
        activity.r2_key = result['key']
        activity.storage_provider = 'r2'

    print(f"✅ {len(activities)}개 파일 마이그레이션 완료")
    print(f"📊 R2 무료 티어 사용량: {total_size/1024/1024:.2f}MB / 10,240MB")
```

## 성능 최적화

### 압축으로 2배 저장
```python
# gzip 압축 시
원본: 145KB → 압축: 50KB (65% 절감)
10GB로 저장 가능: 70,000개 → 200,000개!
```

### CDN 연동 (선택사항)
```nginx
# Cloudflare CDN 자동 적용
https://fit-files.your-domain.com/{key}
# 전 세계 엣지 로케이션에서 빠른 다운로드
```

## 모니터링 대시보드

```sql
-- 사용량 통계
SELECT
    COUNT(*) as total_files,
    SUM(file_size) / 1024 / 1024 as total_mb,
    (SUM(file_size) / (10 * 1024 * 1024 * 1024)) * 100 as free_tier_usage_percent
FROM activities
WHERE storage_provider = 'r2';

-- 사용자별 통계
SELECT
    user_id,
    COUNT(*) as file_count,
    SUM(file_size) / 1024 / 1024 as user_mb
FROM activities
WHERE storage_provider = 'r2'
GROUP BY user_id
ORDER BY user_mb DESC;
```

## 결론

**R2 10GB 무료 티어**는 생각보다 매우 관대합니다!

- 현재 46MB → **10,240MB까지 무료** (200배 여유!)
- 200명 이상 사용자 지원 가능
- 전송료 완전 무료 (큰 장점!)
- **Neon + R2 조합으로 완전 무료 운영 가능**

초기 프로젝트나 중소 규모 서비스에 완벽한 솔루션입니다! 🚀