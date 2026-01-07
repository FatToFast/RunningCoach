Garmin Connect 데이터 동기화를 수행합니다.

## 작업 내용

1. `.claude/agents/garmin-connector.md` 참조
2. `backend/app/services/sync_service.py` 확인
3. 동기화 수행 또는 관련 코드 수정

## 관련 파일

- `backend/app/adapters/garmin_adapter.py` - Garmin API 어댑터
- `backend/app/api/v1/endpoints/ingest.py` - 동기화 엔드포인트
- `backend/app/services/sync_service.py` - 동기화 서비스

## 주의사항

- 동기화 락 TTL: 3시간 (대용량 백필 시)
- 1000+ 활동 시 `extend_lock()` 호출 필요
