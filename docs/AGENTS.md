# Docs AGENTS.md - 문서화 규칙

문서 작성 및 유지보수 시 AI 에이전트가 따라야 할 규칙입니다.

---

## 문서 구조

```
docs/
├── AGENTS.md            # 이 파일 (문서화 규칙)
├── debug-patterns.md    # 버그 패턴 기록 (필수 업데이트)
├── api-reference.md     # API 상세 문서
├── PRD.md              # 제품 요구사항
├── MVP.md              # MVP 명세
├── CHANGELOG.md        # 변경 이력
├── ROADMAP.md          # 로드맵
├── ARCHITECTURE.md     # 아키텍처 문서
├── USER_GUIDE.md       # 사용자 가이드
├── blueprint.md        # 설계 청사진
└── feature-map.md      # 기능-파일 매핑
```

---

## 필수 규칙

### 1. 버그 수정 시 반드시 기록

`debug-patterns.md`에 모든 버그를 기록합니다:

```markdown
### N. [버그 제목]

**문제**: [간단한 설명]
**원인**: [왜 발생했는지]
**해결**: [어떻게 수정했는지]

\`\`\`python
# ❌ 잘못된 패턴
[버그 코드]

# ✅ 올바른 패턴
[수정된 코드]
\`\`\`

**적용 위치**: `파일명:함수명`
**날짜**: YYYY-MM-DD
```

### 2. API 변경 시 문서 업데이트

`api-reference.md`를 항상 최신 상태로 유지:

```markdown
### POST /api/v1/workouts

**요청**:
\`\`\`json
{
  "name": "인터벌 훈련",
  "steps": [...]
}
\`\`\`

**응답** (201):
\`\`\`json
{
  "id": 123,
  "name": "인터벌 훈련",
  ...
}
\`\`\`
```

### 3. 작업 완료 후 업데이트할 문서

| 문서 | 업데이트 시점 |
|------|-------------|
| `CHANGELOG.md` | 모든 변경 후 |
| `ROADMAP.md` | 기능 완료/추가 시 |
| `ARCHITECTURE.md` | 구조 변경 시 |
| `USER_GUIDE.md` | 사용자 기능 변경 시 |
| `debug-patterns.md` | 버그 수정 시 |

---

## 문서별 작성 규칙

### CHANGELOG.md

```markdown
# Changelog

## [YYYY-MM-DD]

### Added
- 새로운 기능 설명

### Changed
- 변경된 기능 설명

### Fixed
- 수정된 버그 설명

### Removed
- 제거된 기능 설명
```

**규칙**:
- 날짜별 역순 정렬 (최신이 위)
- 사용자 관점에서 작성
- 기술적 세부사항은 간략히

### ROADMAP.md

```markdown
# Roadmap

## 완료됨 ✅
- [x] Garmin 동기화
- [x] AI 코치 기본 기능

## 진행 중 🚧
- [ ] Strava 자동 업로드 개선
- [ ] 훈련 플랜 템플릿

## 계획됨 📋
- [ ] 소셜 기능
- [ ] 멀티 스포츠 지원
```

**규칙**:
- 완료/진행중/계획 섹션 구분
- 체크박스로 상태 표시
- 우선순위 순서로 정렬

### ARCHITECTURE.md

```markdown
# Architecture

## 시스템 개요
[다이어그램 또는 설명]

## 컴포넌트
### Backend
- FastAPI 앱 구조
- 데이터 흐름

### Frontend
- React 컴포넌트 구조
- 상태 관리

## 데이터베이스
- ERD 또는 주요 테이블 설명

## 외부 연동
- Garmin, Strava, AI 등
```

### USER_GUIDE.md

```markdown
# 사용자 가이드

## 시작하기
1. 계정 생성
2. Garmin 연동

## 주요 기능
### 대시보드
[스크린샷과 설명]

### AI 코치
[사용 방법]

## FAQ
Q: 질문
A: 답변
```

**규칙**:
- 비개발자도 이해할 수 있게 작성
- 스크린샷 포함 권장
- 단계별 설명

---

## 마크다운 스타일

### 제목 계층

```markdown
# 문서 제목 (H1 - 문서당 하나)
## 주요 섹션 (H2)
### 하위 섹션 (H3)
#### 세부 항목 (H4)
```

### 코드 블록

````markdown
```python
# Python 코드
def example():
    pass
```

```typescript
// TypeScript 코드
const example = () => {};
```

```bash
# 쉘 명령어
npm run dev
```
````

### 테이블

```markdown
| 열1 | 열2 | 열3 |
|-----|-----|-----|
| 값1 | 값2 | 값3 |
```

### 링크

```markdown
# 상대 경로 (같은 저장소 내)
[API 문서](api-reference.md)
[백엔드 모델](../backend/app/models/)

# 외부 링크
[FastAPI 문서](https://fastapi.tiangolo.com/)
```

---

## 버전 관리

### 문서 버전 헤더

```markdown
---
last_updated: 2026-01-07
version: 1.2.0
---
```

### 변경 이력 (선택)

```markdown
## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2026-01-07 | 1.2.0 | AI 코치 섹션 추가 |
| 2026-01-01 | 1.1.0 | 대시보드 섹션 업데이트 |
```

---

## 자동화

### API 문서 생성

백엔드 OpenAPI 스키마에서 자동 생성 가능:

```bash
# Swagger UI에서 확인
http://localhost:8000/api/v1/docs

# OpenAPI JSON 내보내기
http://localhost:8000/api/v1/openapi.json
```

### 타입 문서 생성

```bash
# TypeScript 타입에서 문서 생성
cd frontend
npx typedoc src/types
```

---

## 검토 체크리스트

문서 작성/수정 후 확인:

- [ ] 마크다운 문법 오류 없음
- [ ] 링크가 올바르게 작동함
- [ ] 코드 예제가 실행 가능함
- [ ] 최신 코드와 일치함
- [ ] 오타 및 문법 오류 없음
- [ ] 일관된 스타일 유지

---

## 참조

- **CLAUDE.md** - 프로젝트 전체 가이드
- **AGENTS.md** (루트) - 핵심 개발 규칙
- **debug-patterns.md** - 58개+ 버그 패턴 참조
