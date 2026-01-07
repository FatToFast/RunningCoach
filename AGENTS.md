# AGENTS.md - AI 에이전트 규칙

이 문서는 AI 에이전트가 RunningCoach 프로젝트에서 작업할 때 따라야 할 핵심 규칙을 정의합니다.

---

## 핵심 원칙

### 1. 코드 변경 전 확인

```
읽기 → 이해 → 수정
```

- **절대로** 읽지 않은 파일을 수정하지 마세요
- 기존 패턴과 컨벤션을 파악한 후 코드를 작성하세요
- 관련 파일들을 함께 확인하세요 (모델 ↔ 스키마 ↔ API)

### 2. 버그 수정 시 문서화

버그를 수정할 때마다 반드시 `docs/debug-patterns.md`에 기록:

```markdown
### N. [버그 제목]

**문제**: [설명]

\`\`\`typescript
// ❌ 잘못된 패턴
// ✅ 올바른 패턴
\`\`\`

**적용 위치**: `파일명`
```

### 3. 테스트 및 검증

- 타입 체크: `mypy app/` (backend), `npx tsc --noEmit` (frontend)
- 린팅: `ruff check .` (backend), `npm run lint` (frontend)
- 스키마 동기화: `python scripts/check_schema.py --fix`

---

## 프로젝트 지도

```
RunningCoach/
│
├── backend/                 # FastAPI 백엔드
│   ├── AGENTS.md           # 백엔드 규칙
│   └── app/
│       ├── api/v1/         # REST API 엔드포인트
│       ├── models/         # SQLAlchemy 모델 (진실의 원천)
│       ├── schemas/        # Pydantic 스키마 (API 계약)
│       ├── services/       # 비즈니스 로직
│       ├── adapters/       # 외부 서비스 연동
│       ├── knowledge/      # RAG 시스템
│       └── core/           # 설정, 보안, DB
│
├── frontend/                # React 프론트엔드
│   ├── AGENTS.md           # 프론트엔드 규칙
│   └── src/
│       ├── pages/          # 페이지 컴포넌트
│       ├── components/     # 재사용 컴포넌트
│       ├── hooks/          # React Query hooks
│       ├── api/            # API 클라이언트
│       └── types/          # TypeScript 타입
│
├── docs/                    # 문서
│   ├── AGENTS.md           # 문서화 규칙
│   ├── debug-patterns.md   # 버그 패턴 기록 (필독)
│   ├── api-reference.md    # API 문서
│   └── PRD.md              # 제품 요구사항
│
├── AGENTS.md               # 이 파일 (핵심 규칙)
└── CLAUDE.md               # 프로젝트 상세 가이드
```

---

## 영역별 담당

| 영역 | 주요 파일 | 변경 시 주의사항 |
|------|----------|-----------------|
| **데이터 모델** | `backend/app/models/` | 마이그레이션 필요, 스키마 동기화 |
| **API 엔드포인트** | `backend/app/api/v1/endpoints/` | 스키마 일치, 문서 업데이트 |
| **비즈니스 로직** | `backend/app/services/` | 단위 테스트 권장 |
| **UI 컴포넌트** | `frontend/src/components/` | 재사용성 고려 |
| **페이지** | `frontend/src/pages/` | 라우팅 확인 |
| **API 타입** | `frontend/src/types/` | Backend와 동기화 |

---

## 금지 사항

### 절대 하지 말 것

1. **추측으로 코드 작성** - 항상 기존 코드를 먼저 읽으세요
2. **타입 무시** - Python type hints, TypeScript 타입 필수
3. **테스트 없이 배포** - 최소한 타입 체크는 통과해야 함
4. **문서 업데이트 누락** - API 변경 시 문서도 함께 수정
5. **하드코딩** - 설정값은 환경변수 또는 config 사용

### 피해야 할 패턴

```python
# ❌ 잘못된 패턴
async def get_user(id):  # 타입 힌트 없음
    return await db.query(User).filter(id=id).first()  # None 처리 없음

# ✅ 올바른 패턴
async def get_user(user_id: int, db: AsyncSession) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
```

```typescript
// ❌ 잘못된 패턴
const data = await api.get('/users')  // any 타입

// ✅ 올바른 패턴
const { data } = await api.get<User[]>('/users')
```

---

## 작업 흐름

### 새 기능 추가 시

```
1. PRD.md 확인 → 요구사항 파악
2. 관련 코드 탐색 → 기존 패턴 파악
3. 모델 정의 (필요시) → 마이그레이션
4. 스키마 정의 → API 계약
5. 서비스 로직 → 비즈니스 구현
6. API 엔드포인트 → HTTP 인터페이스
7. 프론트엔드 연동 → UI 구현
8. 테스트 & 문서화
```

### 버그 수정 시

```
1. 버그 재현 → 정확한 상황 파악
2. 원인 분석 → 코드 추적
3. 수정 구현 → 최소한의 변경
4. 검증 → 타입 체크, 테스트
5. 문서화 → debug-patterns.md 기록
```

---

## 커밋 규칙

### 메시지 형식

```
<type>: <description>

[optional body]
```

### 타입

| 타입 | 용도 |
|------|------|
| `feat` | 새 기능 |
| `fix` | 버그 수정 |
| `docs` | 문서 변경 |
| `refactor` | 리팩토링 |
| `test` | 테스트 |
| `chore` | 빌드, 설정 |

### 예시

```
feat: VDOT 기반 훈련 페이스 계산 추가

- services/vdot.py: Jack Daniels 공식 구현
- dashboard.py: 훈련 페이스 존 계산 통합
- TrainingPacesCard 컴포넌트 추가
```

---

## 참조 문서

- **CLAUDE.md** - 프로젝트 상세 구조, 명령어, 환경 변수
- **docs/debug-patterns.md** - 이전 버그와 해결책
- **docs/api-reference.md** - API 상세 문서
- **docs/PRD.md** - 제품 요구사항 및 기능 명세

---

## 영역별 상세 규칙

각 영역의 세부 규칙은 해당 디렉토리의 AGENTS.md를 참조:

- `backend/AGENTS.md` - 백엔드 개발 규칙
- `frontend/AGENTS.md` - 프론트엔드 개발 규칙
- `docs/AGENTS.md` - 문서화 규칙
