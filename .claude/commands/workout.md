워크아웃을 설계하고 Garmin에 전송합니다.

## 작업 내용

1. `.claude/agents/ai-coach.md` 참조 (워크아웃 설계)
2. `.claude/agents/garmin-connector.md` 참조 (Garmin 전송)
3. 워크아웃 생성 또는 관련 코드 수정

## 관련 파일

- `backend/app/api/v1/endpoints/workouts.py` - 워크아웃 API
- `backend/app/models/workout.py` - 워크아웃 모델
- `backend/app/adapters/garmin_adapter.py` - Garmin 푸시

## 워크아웃 타입

- easy: 쉬운 러닝
- long: 장거리 러닝
- tempo: 템포 러닝
- interval: 인터벌 훈련
- fartlek: 파틀렉
- recovery: 회복 러닝
