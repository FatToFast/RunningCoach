# State Machine 분석 및 개선 제안

## 1. 다이어그램 vs 실제 코드 비교

### 발견된 불일치 및 문제점

#### 1.1 CI 파이프라인 다이어그램 (다이어그램 #6)

**문제**: 실제 GitHub Actions 워크플로우와 불일치

| 다이어그램 | 실제 코드 (evals.yml) | 문제 |
|-----------|---------------------|------|
| P1 → GRADER_TESTS (순차) | grader-tests는 p0-safety와 병렬 | 의존성 잘못 표현 |
| P1 → RAG_TESTS (순차) | rag-tests는 독립 실행 | 의존성 없음 |
| PUSH_MAIN → NIGHTLY | push는 regression-check로 연결 | 잘못된 매핑 |

**실제 워크플로우 의존성**:
```yaml
p0-safety: 독립
p1-accuracy: needs: [p0-safety]
grader-tests: 독립 (p0-safety와 병렬)
vdot-tests: 독립
rag-tests: 독립
eval-summary: needs: [p0-safety, p1-accuracy, grader-tests, vdot-tests, rag-tests]
regression-check: needs: [unit-tests, vdot-tests, rag-tests]  # unit-tests는 정의되지 않음!
```

#### 1.2 컴포넌트 관계도 (다이어그램 #8)

**누락된 컴포넌트**:
- `run_vdot_eval()` - 실제 존재하나 다이어그램에 없음
- `run_training_plan_eval()` - 실제 존재하나 다이어그램에 없음
- `TranscriptLogger` - 트랜스크립트 저장에 사용됨
- `EvalTranscript` - 개별 trial 기록

**잘못된 연결**:
- `FILTER → TASK_CONFIGS`: 실제로는 `filter_tasks_for_config → get_task_config → TASK_CONFIGS`
- `VALIDATE → P0_STATUS`: validate는 result.p0_safety_status()를 호출, 직접 연결 아님

#### 1.3 Regression 검사 다이어그램 (다이어그램 #7)

**문제**: `check_regression()` 함수의 실제 흐름과 불일치

```python
# 실제 코드 (runner.py:672-732)
def check_regression(...):
    comparison = compare_eval_results(baseline, current)  # 먼저 비교

    # CI 계산은 comparison 이후
    current_ci = calculate_confidence_interval(...)
    baseline_ci = calculate_confidence_interval(...)

    # P0 체크
    current_p0 = current.p0_safety_status()
    baseline_p0 = baseline.p0_safety_status()
```

다이어그램은 `COMPARE → CALC_CI → CHECK_OVERLAP`으로 표현했지만,
실제로는 `COMPARE`와 `CALC_CI`가 독립적으로 실행됨.

---

## 2. 불필요한/중복된 흐름 식별

### 2.1 중복된 Entry Points

**현재 상태** (runner.py):
```python
run_pr_eval()      # PR_FAST_CONFIG 사용
run_nightly_eval() # NIGHTLY_FULL_CONFIG 사용
run_release_eval() # RELEASE_FULL_CONFIG 사용
run_vdot_eval()    # config 없이 직접 실행
run_training_plan_eval()  # config 없이 직접 실행
```

**문제점**:
- `run_vdot_eval()`과 `run_training_plan_eval()`은 CI config를 사용하지 않음
- 5개의 entry point가 각각 다른 패턴을 따름
- mock executor/grader 코드가 3곳에서 중복

### 2.2 CI Config 구조 중복

**ci_config.py**에서:
```python
PR_FAST_CONFIG = CIEvalConfig(
    priorities=[TaskPriority.P0_SAFETY, TaskPriority.P1_ACCURACY],
    ...
)

PR_SAFETY_CONFIG = CIEvalConfig(
    priorities=[TaskPriority.P0_SAFETY],
    task_id_patterns=["should_not_*", "advice_*_pain", "edge_injury_*"],
    ...
)
```

**문제점**:
- `PR_SAFETY_CONFIG`는 `PR_FAST_CONFIG`의 부분집합처럼 보이지만, 다른 설정 사용
- `task_id_patterns`은 P0 태스크 ID와 중복 (이미 TASK_CONFIGS에 정의됨)

### 2.3 Metric 계산 경로 중복

**TaskResult에서**:
```python
def pass_at_1(self) -> float:
def pass_at_k(self, k: int = 3) -> float:
def pass_pow_k(self, k: int = 3) -> float:
```

**EvalMetrics에서**:
```python
pass_at_1=statistics.mean(tr.pass_at_1() for tr in results),
pass_at_3=statistics.mean(tr.pass_at_k(3) for tr in results),
pass_pow_3=statistics.mean(tr.pass_pow_k(3) for tr in results),
```

**TaskConfig에서**:
```python
def get_primary_metric(self, task_result: "TaskResult") -> float:
    if self.metric_type == MetricType.DETERMINISTIC:
        return task_result.pass_at_1()
    ...
```

같은 metric 계산이 3가지 경로로 호출 가능 → 일관성 유지 어려움

---

## 3. 개선 제안

### 3.1 Entry Point 통합

**Before** (5개 함수):
```python
run_pr_eval()
run_nightly_eval()
run_release_eval()
run_vdot_eval()
run_training_plan_eval()
```

**After** (1개 함수 + config):
```python
async def run_eval_suite(
    suite_type: str,  # "vdot", "training_plan", "full"
    ci_config: CIEvalConfig | None = None,
    executor: Callable | None = None,
    graders: list[Callable] | None = None,
) -> EvalResult:
    """Unified entry point for all evaluation runs."""

    # Suite별 기본 executor/graders 제공
    if suite_type == "vdot":
        executor = executor or vdot_executor
        graders = graders or [vdot_grader]
        tasks = VDOT_TASKS
    elif suite_type == "training_plan":
        ...
```

### 3.2 CI 파이프라인 단순화

**현재** (evals.yml):
```yaml
jobs:
  p0-safety:
  p1-accuracy:
  grader-tests:
  vdot-tests:    # p1-accuracy와 중복?
  rag-tests:
  full-eval:
  regression-check:
  eval-summary:
```

**제안**:
```yaml
jobs:
  # Phase 1: Safety (blocking)
  safety-gate:
    - P0 safety tests
    - Verify 95% threshold

  # Phase 2: Core (parallel, after safety)
  core-tests:
    needs: [safety-gate]
    strategy:
      matrix:
        suite: [vdot, grader, rag]

  # Phase 3: Summary
  summary:
    needs: [safety-gate, core-tests]
```

### 3.3 Metric 계산 단일 경로

**제안**: TaskConfig를 유일한 metric 계산 진입점으로

```python
class TaskResult:
    def get_metric(self, metric_type: MetricType | None = None) -> float:
        """Get metric based on task config or explicit type."""
        if metric_type is None:
            config = get_task_config(self.task_id)
            return config.get_primary_metric(self)

        if metric_type == MetricType.DETERMINISTIC:
            return self._pass_at_1()
        elif metric_type == MetricType.TOOL:
            return self._pass_at_k(3)
        else:
            return self._pass_pow_k(3)

    # Private methods (implementation)
    def _pass_at_1(self) -> float: ...
    def _pass_at_k(self, k: int) -> float: ...
    def _pass_pow_k(self, k: int) -> float: ...
```

### 3.4 다이어그램 수정 필요 항목

| 다이어그램 | 수정 필요 사항 |
|-----------|---------------|
| #6 CI 파이프라인 | 실제 needs 의존성 반영, regression-check의 unit-tests 오류 수정 |
| #7 Regression | COMPARE와 CALC_CI 병렬 실행 표현 |
| #8 컴포넌트 | run_vdot_eval, TranscriptLogger 추가 |

---

## 4. 우선순위별 개선 로드맵

### P0: 즉시 수정 필요
1. **evals.yml의 regression-check**: `unit-tests` job이 정의되지 않음 → 실행 실패
2. **다이어그램 #6**: 실제 워크플로우와 심각한 불일치

### P1: 권장 개선
1. Entry point 통합 (run_eval_suite)
2. CI config 정리 (PR_SAFETY_CONFIG 필요성 검토)
3. Metric 계산 단일 경로화

### P2: 선택적 개선
1. TranscriptLogger를 컴포넌트 다이어그램에 추가
2. 누락된 함수들 다이어그램에 반영

---

## 5. 요약

### 불필요한 흐름
- 5개의 분리된 entry point (통합 가능)
- PR_FAST_CONFIG와 PR_SAFETY_CONFIG의 중복된 우선순위 필터링
- 3곳에서 중복된 mock executor/grader 코드

### 누락된 흐름
- run_vdot_eval(), run_training_plan_eval() 다이어그램에 없음
- TranscriptLogger, EvalTranscript 관계 미표현
- GitHub Actions의 실제 job 의존성

### 잘못된 흐름
- CI 파이프라인 다이어그램의 의존성
- Regression 검사의 순차/병렬 구분
- regression-check job의 존재하지 않는 의존성 (unit-tests)
