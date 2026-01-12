# AI Coach Evaluation Roadmap

Anthropic "Demystifying Evals for AI Agents" 프레임워크 기반 평가 개발 로드맵입니다.

## Evaluation Philosophy

### Metric Selection Strategy

| Task Type | Metric | Rationale |
|-----------|--------|-----------|
| **VDOT Calculation** | Pass@1 | 결정론적, 동일 입력 = 동일 출력 |
| **Training Plan Generation** | Pass^3 | 고객 대면, 일관성이 핵심 |
| **Coaching Advice** | Pass^3 | 고객 대면, 안전/품질 일관성 필요 |
| **RAG Retrieval** | Pass@3 | 도구 특성, 하나라도 관련 문서 찾으면 OK |

### Why Pass^k for Customer-Facing Agents?

```
고객 경험 시나리오:
- 동일한 "서브4 마라톤 계획" 요청을 3번 함
- Pass@3 = 93% → 한 번이라도 성공할 확률 높음
- Pass^3 = 70% → 매번 일관되게 좋은 응답할 확률

고객 입장에서는 "항상 좋은 응답"이 중요
∴ Pass^k로 일관성 측정
```

---

## Priority Levels (P0 → P3)

### P0: Safety Critical (즉시 필요)

**목표**: 위험한 조언 100% 차단

| Eval | Description | Metric | Target |
|------|-------------|--------|--------|
| `safety_injury_detection` | 부상 관련 위험 조언 감지 | Pass^3 | >0.95 |
| `safety_medical_boundary` | 의료 진단 거부 | Pass@1 | 1.0 |
| `safety_overtraining` | 과훈련 조언 방지 | Pass^3 | >0.90 |

**Graders**: Code + LLM Safety Checker

### P1: Accuracy Critical (핵심 정확성)

**목표**: 핵심 계산/정보 정확

| Eval | Description | Metric | Target |
|------|-------------|--------|--------|
| `vdot_calculation` | VDOT 계산 정확도 | Pass@1 | >0.95 |
| `pace_recommendation` | 훈련 페이스 권장 | Pass@1 | >0.90 |
| `mileage_progression` | 주간 거리 증가율 안전 | Pass@1 | >0.95 |
| `taper_timing` | 테이퍼 기간/감량 정확 | Pass@1 | >0.85 |

**Graders**: Code-based (Deterministic)

### P2: Quality Critical (품질 핵심)

**목표**: 사용자 가치 제공

| Eval | Description | Metric | Target |
|------|-------------|--------|--------|
| `training_plan_quality` | 훈련 계획 전반 품질 | Pass^3 | >0.75 |
| `personalization` | 개인화 수준 | Pass^3 | >0.70 |
| `coaching_clarity` | 조언 명확성 | Pass^3 | >0.80 |
| `rag_relevance` | RAG 검색 품질 | Pass@3 | >0.85 |

**Graders**: LLM + Rubric-based

### P3: Experience Polish (경험 개선)

**목표**: 사용자 경험 최적화

| Eval | Description | Metric | Target |
|------|-------------|--------|--------|
| `response_latency` | 응답 속도 | Avg < 3s | <3000ms |
| `token_efficiency` | 토큰 효율성 | Avg tokens | <2000 |
| `conversation_flow` | 대화 자연스러움 | Human | >4.0/5 |

---

## Development Phases

### Phase 1: Foundation (Week 1-2) ✅ DONE

- [x] Evaluation framework setup
- [x] Basic code graders
- [x] Mock LLM graders
- [x] CI integration
- [x] Transcript logging

### Phase 2: Safety First (Week 3-4)

- [ ] Real LLM safety grader integration
- [ ] Safety regression tests
- [ ] Edge case coverage for injuries
- [ ] Medical boundary tests

**Exit Criteria**: P0 evals all passing with >95% consistency

### Phase 3: Accuracy (Week 5-6)

- [ ] VDOT test expansion (all tables)
- [ ] Pace recommendation validation
- [ ] Training plan structure validation
- [ ] Cross-validation with known plans

**Exit Criteria**: P1 evals all passing with >90%

### Phase 4: Quality (Week 7-8)

- [ ] LLM grader calibration
- [ ] Human evaluation baseline
- [ ] Personalization depth testing
- [ ] RAG quality optimization

**Exit Criteria**: P2 evals all passing with >75%

### Phase 5: Polish (Week 9+)

- [ ] Performance optimization
- [ ] Human-in-the-loop feedback
- [ ] A/B test integration
- [ ] Production monitoring

---

## Grader Strategy

### Code-Based Graders (Fast, Deterministic)

```python
# 적합한 케이스:
- 숫자 검증 (VDOT, 페이스, 거리)
- 구조 검증 (필수 필드, 주간 구성)
- 규칙 검증 (10% 규칙, 80/20 규칙)
- 키워드 포함/제외

# 장점:
- 빠름 (~1ms)
- 결정론적
- 비용 없음
```

### LLM-Based Graders (Nuanced, Flexible)

```python
# 적합한 케이스:
- 품질 평가 (명확성, 유용성)
- 안전성 판단 (맥락 고려)
- 개인화 수준
- 과학적 정확성

# 장점:
- 뉘앙스 이해
- 맥락 고려
- 새로운 케이스 대응

# 주의점:
- 비용 발생
- 비결정론적 → Pass^k 사용
- Grader의 grader 필요 (calibration)
```

### Human Graders (Gold Standard)

```python
# 적합한 케이스:
- LLM 채점기 캘리브레이션
- 엣지 케이스 판단
- 새로운 평가 기준 개발
- 분쟁 해결

# 워크플로우:
1. 샘플링 (전체의 5-10%)
2. Rubric 기반 평가
3. LLM 채점기와 비교
4. 불일치 분석 및 개선
```

---

## CI/CD Integration

### PR Checks (Fast, Required)

```yaml
on: pull_request
jobs:
  - unit-tests      # 코드 채점기 테스트 (~30s)
  - vdot-tests      # VDOT 정확도 (~1m)
  - safety-tests    # 안전성 기본 (~1m)
```

### Nightly Evals (Comprehensive)

```yaml
on: schedule [0 3 * * *]
jobs:
  - full-eval-suite     # 전체 태스크 (~30m)
  - llm-grader-tests    # LLM 채점기 (~10m)
  - regression-check    # 회귀 분석
```

### Release Evals (Thorough)

```yaml
on: release
jobs:
  - extended-eval       # 확장 태스크셋
  - human-review        # 인간 검토 트리거
  - performance-test    # 성능 벤치마크
```

---

## Metric Thresholds by Environment

| Metric | Dev | Staging | Production |
|--------|-----|---------|------------|
| P0 Safety Pass^3 | >0.85 | >0.92 | >0.95 |
| P1 Accuracy Pass@1 | >0.80 | >0.88 | >0.95 |
| P2 Quality Pass^3 | >0.60 | >0.70 | >0.75 |
| P3 Latency (p95) | <5s | <4s | <3s |

---

## Failure Analysis Protocol

### When Evals Fail

1. **Transcript 확인**: `tests/evals/transcripts/{task_id}/`
2. **Grader 분석**: 어느 채점기가 실패했는지
3. **패턴 분석**: 반복되는 실패 패턴
4. **근본 원인**: 모델? 프롬프트? 데이터?

### Root Cause Categories

| Category | Indicator | Action |
|----------|-----------|--------|
| Prompt Issue | 일관된 특정 실패 | 프롬프트 개선 |
| Data Issue | RAG 관련 실패 | 지식베이스 보강 |
| Model Limitation | 복잡한 추론 실패 | 모델 업그레이드/체인 |
| Eval Issue | 불합리한 기대 | 평가 기준 수정 |

---

## Next Actions

### Immediate (This Week)

1. **Task별 메트릭 타입 추가** ← 핵심 개선
2. **실제 LLM 채점기 연동**
3. **Human evaluation 샘플링 도구**

### Short-term (This Month)

1. Phase 2 (Safety) 완료
2. LLM 채점기 캘리브레이션
3. CI nightly eval 설정

### Medium-term (This Quarter)

1. Phase 3-4 완료
2. Production 모니터링 연동
3. A/B 테스트 연동
