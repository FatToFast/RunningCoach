# FIT 파일 DB 저장 가이드

## 개요
FIT 파일을 파일시스템 대신 PostgreSQL 데이터베이스에 직접 저장하는 기능입니다.

## 장점
- **백업 간소화**: DB 백업만으로 모든 데이터 보호
- **클라우드 친화적**: 파일시스템 의존성 제거
- **압축 효율**: gzip 압축으로 60-70% 공간 절약
- **무결성 보장**: SHA-256 해시로 데이터 검증
- **성능**: PostgreSQL의 TOAST 메커니즘으로 대용량 바이너리 효율적 처리

## 구조

### 데이터베이스 스키마
```sql
-- garmin_raw_files 테이블
file_content: BYTEA         -- 압축된 FIT 파일 내용
file_size: INTEGER         -- 원본 크기 (bytes)
compression_type: VARCHAR(10) -- 압축 방식 (gzip/zstd/none)

-- activities 테이블 (캐시용)
fit_file_content: BYTEA    -- 압축된 FIT 파일 (캐시)
fit_file_size: INTEGER     -- 원본 크기
```

### 압축 통계 (실제 데이터)
- 평균 파일 크기: 145KB → 압축 후 ~50KB
- 전체 330개 파일: 46.71MB → ~16MB (압축률 65%)
- 최대 파일: 598KB → ~200KB

## 사용법

### 1. 마이그레이션 실행
```bash
cd backend

# DB 스키마 업데이트
alembic upgrade head

# FIT 파일 마이그레이션 (원본 유지)
python scripts/migrate_fit_files_to_db.py

# FIT 파일 마이그레이션 + 원본 삭제
python scripts/migrate_fit_files_to_db.py --delete-originals

# 마이그레이션 검증
python scripts/migrate_fit_files_to_db.py --verify
```

### 2. 코드에서 사용
```python
from app.services.fit_storage_service import FitStorageService

service = FitStorageService()

# 파일 저장
await service.store_fit_file_to_db(db, garmin_file, file_content)

# 파일 조회
file_content = await service.retrieve_fit_file_from_db(db, garmin_file)

# 파일시스템 → DB 마이그레이션
await service.migrate_file_to_db(db, garmin_file, delete_original=True)
```

### 3. sync_service.py 업데이트 (예시)
```python
# 기존 코드
file_path = self.fit_storage_path / str(self.user.id) / f"{activity_id}.fit"
file_path.write_bytes(fit_data)
activity.fit_file_path = str(file_path)

# 새 코드
storage_service = FitStorageService()
garmin_file = GarminRawFile(
    user_id=self.user.id,
    activity_id=activity.id,
    file_type="fit"
)
db.add(garmin_file)
await storage_service.store_fit_file_to_db(db, garmin_file, fit_data)
```

## 성능 고려사항

### PostgreSQL TOAST
- 8KB 이상 데이터는 자동으로 별도 테이블 저장
- `deferred=True` 옵션으로 필요시에만 로드
- 인덱스로 빠른 조회 지원

### 압축 옵션
- **gzip** (기본): 균형잡힌 압축률과 속도
- **zstd**: 더 나은 압축률 (선택적)
- **none**: 압축 없음 (특수한 경우)

## 백업 및 복구

### 백업
```bash
# 전체 DB 백업 (FIT 파일 포함)
pg_dump -d running -f backup.sql

# 압축 백업
pg_dump -d running | gzip > backup.sql.gz
```

### 복구
```bash
# 복구
psql -d running < backup.sql

# 압축 파일 복구
gunzip -c backup.sql.gz | psql -d running
```

## 롤백 방법

파일시스템으로 되돌리려면:

```bash
# 1. DB에서 파일 추출
python scripts/extract_fit_files_from_db.py

# 2. 마이그레이션 롤백
alembic downgrade -1

# 3. 설정 변경 (.env)
USE_DB_STORAGE=false
```

## 모니터링

```sql
-- DB 저장된 FIT 파일 통계
SELECT
    COUNT(*) as file_count,
    SUM(file_size) / 1024 / 1024 as total_mb,
    AVG(file_size) / 1024 as avg_kb,
    SUM(LENGTH(file_content)) / 1024 / 1024 as compressed_mb
FROM garmin_raw_files
WHERE file_content IS NOT NULL;

-- 압축률 확인
SELECT
    compression_type,
    COUNT(*) as count,
    AVG(LENGTH(file_content)::float / file_size * 100) as avg_compression_ratio
FROM garmin_raw_files
WHERE file_content IS NOT NULL
GROUP BY compression_type;
```

## 주의사항
- 초기 마이그레이션 시 DB 크기 일시적 증가
- 대용량 활동 (1시간 이상)의 경우 FIT 파일이 1MB 넘을 수 있음
- PostgreSQL `max_allowed_packet` 설정 확인 필요