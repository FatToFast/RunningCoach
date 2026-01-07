AI 기반 훈련 계획을 생성합니다.

## 작업 내용

1. `.claude/agents/ai-coach.md` 참조
2. `.claude/agents/data-manager.md` 참조 (VDOT, 피트니스 지표)
3. 훈련 계획 생성 또는 관련 코드 수정

## 관련 파일

- `backend/app/api/v1/endpoints/ai.py` - AI 엔드포인트
- `backend/app/core/ai_constants.py` - 시스템 프롬프트
- `backend/app/knowledge/` - RAG 시스템
- `backend/app/services/vdot.py` - VDOT 계산

## 훈련 계획 구성

- Base Phase (기초): 유산소 기반 구축
- Build Phase (강화): 훈련 강도 증가
- Peak Phase (피크): 레이스 페이스 훈련
- Taper Phase (조정): 훈련량 감소, 휴식
