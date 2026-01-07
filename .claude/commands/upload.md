활동을 Strava에 업로드합니다.

## 작업 내용

1. `.claude/agents/strava-connector.md` 참조
2. Strava 업로드 수행 또는 관련 코드 수정

## 관련 파일

- `backend/app/api/v1/endpoints/strava.py` - Strava API
- `backend/app/services/strava_upload.py` - 업로드 서비스
- `backend/app/workers/strava_worker.py` - Arq 워커

## 재시도 전략

- 1차 실패: 1분 후 재시도
- 2차 실패: 5분 후 재시도
- 3차 실패: 30분 후 재시도
- 4차 실패: 2시간 후 재시도

## 주의사항

- OAuth state는 프로덕션에서 Redis 저장 필요
- 동시 업로드 제한: 3개
