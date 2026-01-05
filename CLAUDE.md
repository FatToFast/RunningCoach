# CLAUDE.md - RunningCoach Project Guide

러닝 코치 앱 프로젝트를 위한 Claude Code 가이드입니다.

## 필수 규칙

### 디버그 패턴 기록 (MUST)

버그를 발견하고 수정할 때마다 반드시 [docs/debug-patterns.md](docs/debug-patterns.md)에 기록합니다:

1. **문제 설명**: 어떤 버그였는지
2. **잘못된 패턴**: 버그를 유발한 코드 예시
3. **올바른 패턴**: 수정된 코드 예시
4. **적용 위치**: 관련 파일/함수

```markdown
### N. [버그 제목]

**문제**: [간단한 설명]

\`\`\`typescript
// ❌ 잘못된 패턴
[버그 코드]

// ✅ 올바른 패턴
[수정된 코드]
\`\`\`

**적용 위치**: `파일명`, `함수명`
```

이렇게 하면 같은 유형의 버그가 다시 발생했을 때 빠르게 해결할 수 있습니다.

## 프로젝트 구조

```
RunningCoach/
├── backend/           # FastAPI 백엔드
│   ├── app/
│   │   ├── api/v1/   # API 엔드포인트
│   │   ├── adapters/ # 외부 서비스 어댑터 (Garmin, Strava)
│   │   ├── core/     # 설정, 보안
│   │   ├── models/   # SQLAlchemy 모델
│   │   └── services/ # 비즈니스 로직
│   └── .venv/        # Python 가상환경
├── frontend/          # React + TypeScript + Vite 프론트엔드
│   └── src/
│       ├── api/      # API 클라이언트
│       ├── components/
│       ├── hooks/    # React Query hooks
│       ├── pages/
│       ├── types/    # TypeScript 타입 정의
│       └── utils/    # 유틸리티 함수
└── docs/             # 문서
```

## git pull 후 필수 작업

**중요**: GitHub에서 pull 후 반드시 스키마 체크를 실행합니다.

```bash
git pull
cd backend && source .venv/bin/activate
python scripts/check_schema.py --fix
```

이 스크립트는 SQLAlchemy 모델과 실제 DB 스키마를 비교하여 누락된 컬럼을 자동으로 추가합니다.

## 개발 명령어

### 로컬 서버 시작

```bash
# 1. 백엔드 시작
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 2. 프론트엔드 시작 (별도 터미널)
cd frontend
npm run dev

# 3. 브라우저에서 http://localhost:5173 접속
```

### Backend

```bash
cd backend
source .venv/bin/activate   # 가상환경 활성화
uvicorn app.main:app --reload --port 8000

# 스키마 확인
python scripts/check_schema.py
python scripts/check_schema.py --fix  # 누락된 컬럼 자동 추가

# 테스트
pytest

# 타입 체크
mypy app/
```

### Frontend

```bash
cd frontend
npm run dev          # 개발 서버 (포트 5173)
npm run build        # 프로덕션 빌드
npx tsc --noEmit     # 타입 체크
npm run lint         # ESLint
```

## API 구조

- Base URL: `/api/v1`
- 인증: 세션 기반 (쿠키)
- 문서: `/api/v1/docs` (Swagger UI)

주요 엔드포인트는 [router.py](backend/app/api/v1/router.py) 상단 주석 참조.

## 핵심 문서

| 문서 | 설명 |
|------|------|
| [docs/debug-patterns.md](docs/debug-patterns.md) | 발견된 버그 패턴과 해결책 |
| [docs/api-reference.md](docs/api-reference.md) | API 상세 문서 |
| [docs/PRD.md](docs/PRD.md) | 제품 요구사항 |

## 자주 발생하는 이슈

### Frontend

1. **시간 포맷팅 오류**: `format.ts`에서 Math.round 60초 오버플로우 주의
2. **API 타입 불일치**: Backend Pydantic ↔ Frontend TypeScript 동기화 필요
3. **React Query**: mutation 후 관련 쿼리 invalidation 확인

### Backend

1. **라우터 문서**: `router.py` 주석과 실제 구현 일치 확인
2. **CORS**: `CORS_ORIGINS` 환경변수 설정 필수
3. **가상환경**: 항상 `.venv` 활성화 후 실행
4. **동기화 락**: 대용량 백필(500+ 활동) 시 3시간 TTL, 1000+ 활동 시 `extend_lock()` 사용 권장
5. **httpx base_url**: leading slash 사용 시 base_url 경로가 덮어써지므로 주의
6. **HR 존 계산**: 표준 5존 HRR 방식 사용 (50-60%, 60-70%, 70-80%, 80-90%, 90-100%)
7. **Strava OAuth**: 프로덕션 배포 시 Redis 기반 state 저장 필요 (현재는 단일 워커 OK)

자세한 내용은 [docs/debug-patterns.md](docs/debug-patterns.md) 참조.

## 환경 변수

```bash
# Backend (.env)
DATABASE_URL=postgresql+asyncpg://...
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
GARMIN_ENCRYPTION_KEY=...

# Frontend (.env)
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCK_DATA=false
```

## 코드 스타일

- **Python**: Black + Ruff, Type hints 필수
- **TypeScript**: ESLint + Prettier
- **커밋 메시지**: Conventional Commits (feat:, fix:, docs:, etc.)

---

*이 문서는 Claude Code가 프로젝트를 이해하는 데 사용됩니다.*
