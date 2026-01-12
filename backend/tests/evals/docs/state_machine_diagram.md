# Eval System State Machine Diagrams

AI Coach Evaluation 시스템의 상태 머신 다이어그램입니다.

## 1. EvalRunner 전체 흐름

```mermaid
stateDiagram-v2
    [*] --> INIT: EvalRunner 생성

    INIT --> CONFIGURE: ci_config 로드
    CONFIGURE --> FILTER_TASKS: filter_tasks_for_config()

    FILTER_TASKS --> PARALLEL_RUN: parallel_tasks > 1
    FILTER_TASKS --> SEQUENTIAL_RUN: parallel_tasks == 1

    state PARALLEL_RUN {
        [*] --> BATCH_CREATE: 태스크를 배치로 분할
        BATCH_CREATE --> BATCH_EXECUTE: asyncio.gather()
        BATCH_EXECUTE --> BATCH_COLLECT: 결과 수집
        BATCH_COLLECT --> BATCH_CREATE: 다음 배치
        BATCH_COLLECT --> [*]: 모든 배치 완료
    }

    state SEQUENTIAL_RUN {
        [*] --> TASK_NEXT: 다음 태스크
        TASK_NEXT --> TASK_EXECUTE: _run_task()
        TASK_EXECUTE --> TASK_NEXT: 결과 저장
        TASK_EXECUTE --> [*]: 모든 태스크 완료
    }

    PARALLEL_RUN --> AGGREGATE: task_results 수집
    SEQUENTIAL_RUN --> AGGREGATE: task_results 수집

    AGGREGATE --> LOG_PRIORITY: by_priority() 로깅
    LOG_PRIORITY --> VALIDATE: ci_config 있음
    LOG_PRIORITY --> SAVE: ci_config 없음

    VALIDATE --> SAVE: validate_eval_result()
    SAVE --> COMPLETE: _save_eval_result()

    COMPLETE --> [*]: EvalResult 반환
```

## 2. 단일 Task 실행 상태

```mermaid
stateDiagram-v2
    [*] --> TASK_INIT: _run_task() 호출

    TASK_INIT --> TRIAL_LOOP: trials_per_task 만큼 반복

    state TRIAL_LOOP {
        [*] --> TRIAL_START: trial_num 증가

        state TRIAL_EXECUTION {
            [*] --> EXECUTE: executor(task) 호출
            EXECUTE --> TIMEOUT_ERROR: TimeoutError
            EXECUTE --> EXECUTION_ERROR: Exception
            EXECUTE --> GRADING: 정상 완료

            TIMEOUT_ERROR --> TRIAL_FAILED
            EXECUTION_ERROR --> TRIAL_FAILED

            state GRADING {
                [*] --> APPLY_GRADERS
                APPLY_GRADERS --> GRADER_ERROR: 그레이더 실패
                APPLY_GRADERS --> CALC_SCORE: 모든 그레이더 성공
                GRADER_ERROR --> CALC_SCORE: 에러 기록 후 계속
                CALC_SCORE --> CHECK_PASSED
                CHECK_PASSED --> TRIAL_PASSED: all graders passed
                CHECK_PASSED --> TRIAL_FAILED: any grader failed
            }
        }

        TRIAL_START --> TRIAL_EXECUTION

        TRIAL_PASSED --> SAVE_TRANSCRIPT
        TRIAL_FAILED --> SAVE_TRANSCRIPT

        SAVE_TRANSCRIPT --> TRIAL_COMPLETE
        TRIAL_COMPLETE --> TRIAL_START: trial_num < trials_per_task
        TRIAL_COMPLETE --> [*]: 모든 trial 완료
    }

    TRIAL_LOOP --> TASK_RESULT: TaskResult 생성
    TASK_RESULT --> [*]
```

## 3. CI Config 필터링 상태

```mermaid
stateDiagram-v2
    [*] --> LOAD_CONFIG: get_ci_config(name)

    LOAD_CONFIG --> CHECK_PRIORITY: 태스크별 검사 시작

    state FILTER_LOOP {
        CHECK_PRIORITY --> SKIP_TASK: priority not in config.priorities
        CHECK_PRIORITY --> CHECK_METRIC: priority 일치

        CHECK_METRIC --> SKIP_TASK: metric_type not in config.metric_types
        CHECK_METRIC --> CHECK_PATTERN: metric_type 일치 (또는 None)

        CHECK_PATTERN --> SKIP_TASK: task_id_patterns 불일치
        CHECK_PATTERN --> CHECK_EXCLUDE: pattern 일치 (또는 None)

        CHECK_EXCLUDE --> SKIP_TASK: exclude_patterns 일치
        CHECK_EXCLUDE --> INCLUDE_TASK: exclude 없음

        SKIP_TASK --> NEXT_TASK
        INCLUDE_TASK --> NEXT_TASK

        NEXT_TASK --> CHECK_PRIORITY: 다음 태스크
        NEXT_TASK --> [*]: 모든 태스크 검사 완료
    }

    LOAD_CONFIG --> FILTER_LOOP
    FILTER_LOOP --> FILTERED_TASKS: 필터링된 태스크 목록

    FILTERED_TASKS --> [*]
```

## 4. 결과 검증 상태 (validate_eval_result)

```mermaid
stateDiagram-v2
    [*] --> INIT_VALIDATION: validate_eval_result() 호출

    INIT_VALIDATION --> CALC_METRICS: EvalMetrics.from_task_results()
    CALC_METRICS --> GET_P0_STATUS: result.p0_safety_status()

    GET_P0_STATUS --> CHECK_P0: P0 Safety 검사

    state VALIDATION_CHECKS {
        CHECK_P0 --> P0_FAIL: P0 태스크 실패 & fail_on_p0_failure
        CHECK_P0 --> CHECK_PASS_RATE: P0 통과

        P0_FAIL --> ADD_CRITICAL_ISSUE: severity=critical

        CHECK_PASS_RATE --> PASS_RATE_FAIL: pass_at_1 < min_pass_rate
        CHECK_PASS_RATE --> CHECK_CONSISTENCY: 통과

        PASS_RATE_FAIL --> ADD_ERROR_ISSUE: severity=error

        CHECK_CONSISTENCY --> CONSISTENCY_FAIL: pass_pow_3 < min_consistency
        CHECK_CONSISTENCY --> ALL_CHECKS_DONE: 통과

        CONSISTENCY_FAIL --> ADD_WARNING_ISSUE: severity=warning

        ADD_CRITICAL_ISSUE --> CHECK_PASS_RATE
        ADD_ERROR_ISSUE --> CHECK_CONSISTENCY
        ADD_WARNING_ISSUE --> ALL_CHECKS_DONE
    }

    GET_P0_STATUS --> VALIDATION_CHECKS

    ALL_CHECKS_DONE --> DETERMINE_PASSED: issues 분석

    DETERMINE_PASSED --> FAILED: critical/error 존재
    DETERMINE_PASSED --> PASSED: critical/error 없음

    PASSED --> RETURN_RESULT: recommendation="Ready for merge"
    FAILED --> RETURN_RESULT: recommendation="Fix critical issues"

    RETURN_RESULT --> [*]
```

## 5. Metric 계산 상태 (TaskResult)

```mermaid
stateDiagram-v2
    [*] --> GET_TASK_CONFIG: get_task_config(task_id)

    GET_TASK_CONFIG --> CHECK_REGISTRY: TASK_CONFIGS에서 검색

    state CONFIG_LOOKUP {
        CHECK_REGISTRY --> FOUND: task_id 존재
        CHECK_REGISTRY --> INFER_PATTERN: task_id 없음

        state INFER_PATTERN {
            [*] --> CHECK_SAFETY: "should_not_*" or "injury" or "pain"
            CHECK_SAFETY --> SAFETY_CONFIG: P0_SAFETY, CUSTOMER_FACING
            CHECK_SAFETY --> CHECK_VDOT: 불일치

            CHECK_VDOT --> VDOT_CONFIG: "vdot_*"
            CHECK_VDOT --> CHECK_RAG: 불일치
            VDOT_CONFIG: P1_ACCURACY, DETERMINISTIC

            CHECK_RAG --> RAG_CONFIG: "rag_*"
            CHECK_RAG --> CHECK_ADVICE: 불일치
            RAG_CONFIG: P2_QUALITY, TOOL

            CHECK_ADVICE --> ADVICE_CONFIG: "advice_*"
            CHECK_ADVICE --> DEFAULT_CONFIG: 불일치
            ADVICE_CONFIG: P2_QUALITY, CUSTOMER_FACING
            DEFAULT_CONFIG: P2_QUALITY, CUSTOMER_FACING
        }

        FOUND --> [*]
        SAFETY_CONFIG --> [*]
        VDOT_CONFIG --> [*]
        RAG_CONFIG --> [*]
        ADVICE_CONFIG --> [*]
        DEFAULT_CONFIG --> [*]
    }

    CONFIG_LOOKUP --> METRIC_CALC: TaskConfig 획득

    state METRIC_CALC {
        [*] --> GET_PRIMARY: get_primary_metric() 호출

        GET_PRIMARY --> PASS_AT_1: DETERMINISTIC
        GET_PRIMARY --> PASS_AT_K: TOOL
        GET_PRIMARY --> PASS_POW_K: CUSTOMER_FACING

        PASS_AT_1 --> CALC_RESULT: trials[0].passed ? 1.0 : 0.0
        PASS_AT_K --> CALC_RESULT: any(trials[:k].passed) ? 1.0 : 0.0
        PASS_POW_K --> CALC_RESULT: (success_rate)^k

        CALC_RESULT --> CHECK_THRESHOLD: is_passing() 호출
        CHECK_THRESHOLD --> [*]
    }

    METRIC_CALC --> [*]
```

## 6. CI 파이프라인 상태 (GitHub Actions) - 수정됨

실제 evals.yml 워크플로우를 정확히 반영한 다이어그램입니다.

```mermaid
stateDiagram-v2
    [*] --> TRIGGER: PR/Push/Schedule/Dispatch

    state TRIGGER {
        [*] --> PR_EVENT: pull_request
        [*] --> PUSH_EVENT: push to main
        [*] --> SCHEDULE_EVENT: cron (3AM KST)
        [*] --> DISPATCH_EVENT: workflow_dispatch
    }

    TRIGGER --> PARALLEL_JOBS: 워크플로우 시작

    state PARALLEL_JOBS {
        state "독립 실행 Jobs" as INDEPENDENT {
            [*] --> P0_SAFETY: p0-safety job
            [*] --> GRADER_TESTS: grader-tests job
            [*] --> VDOT_TESTS: vdot-tests job
            [*] --> RAG_TESTS: rag-tests job
        }

        P0_SAFETY --> P1_ACCURACY: needs: p0-safety

        note right of P0_SAFETY: Blocking - 95% threshold
        note right of GRADER_TESTS: 병렬 실행 (독립)
        note right of VDOT_TESTS: 병렬 실행 (독립)
        note right of RAG_TESTS: 병렬 실행 (독립)
    }

    state P0_SAFETY {
        [*] --> RUN_SAFETY_TESTS: pytest -k "safety or injury"
        RUN_SAFETY_TESTS --> PARSE_XML: p0-results.xml 파싱
        PARSE_XML --> CHECK_THRESHOLD: pass_rate 계산
        CHECK_THRESHOLD --> P0_PASS: >= 95%
        CHECK_THRESHOLD --> P0_FAIL: < 95%
        P0_FAIL --> BLOCK: exit 1
    }

    state P1_ACCURACY {
        [*] --> RUN_VDOT_P1: test_vdot.py
        RUN_VDOT_P1 --> RUN_METRICS: test_metrics_advanced.py
        RUN_METRICS --> [*]
    }

    state GRADER_TESTS {
        [*] --> RUN_GRADERS: test_graders.py + coverage
        RUN_GRADERS --> UPLOAD_COV: codecov
        UPLOAD_COV --> [*]
    }

    PARALLEL_JOBS --> CONDITIONAL_JOBS

    state CONDITIONAL_JOBS {
        [*] --> REGRESSION_CHECK: main push only
        [*] --> FULL_EVAL: workflow_dispatch only
    }

    state REGRESSION_CHECK {
        [*] --> WAIT_DEPS: needs: grader-tests, vdot-tests, rag-tests
        WAIT_DEPS --> RUN_REGRESSION: test_graders + test_vdot
        RUN_REGRESSION --> [*]
    }

    PARALLEL_JOBS --> SUMMARY: needs: all jobs
    CONDITIONAL_JOBS --> SUMMARY

    state SUMMARY {
        [*] --> CHECK_P0_RESULT
        CHECK_P0_RESULT --> BLOCK_DEPLOY: P0 failed
        CHECK_P0_RESULT --> CHECK_OTHERS: P0 passed
        CHECK_OTHERS --> WARN: any other failed
        CHECK_OTHERS --> SUCCESS: all passed
        BLOCK_DEPLOY --> POST_SUMMARY
        WARN --> POST_SUMMARY
        SUCCESS --> POST_SUMMARY
        POST_SUMMARY --> [*]: GITHUB_STEP_SUMMARY
    }

    SUMMARY --> [*]
```

### Job 의존성 매트릭스

| Job | needs | 병렬/순차 | 조건 |
|-----|-------|----------|------|
| p0-safety | - | 독립 | always |
| p1-accuracy | p0-safety | 순차 | always |
| grader-tests | - | 독립 | always |
| vdot-tests | - | 독립 | always |
| rag-tests | - | 독립 | always |
| full-eval | - | 독립 | workflow_dispatch |
| regression-check | grader-tests, vdot-tests, rag-tests | 순차 | main push only |
| eval-summary | p0-safety, p1-accuracy, grader-tests, vdot-tests, rag-tests | 순차 | always |

## 7. Regression 검사 상태 - 수정됨

`compare_eval_results()`와 `calculate_confidence_interval()`이 병렬로 실행됨을 반영.

```mermaid
stateDiagram-v2
    [*] --> LOAD_RESULTS: baseline & current EvalResult

    LOAD_RESULTS --> PARALLEL_CALC: 병렬 계산 시작

    state PARALLEL_CALC {
        state COMPARE {
            [*] --> CALC_METRICS: EvalMetrics 계산
            CALC_METRICS --> CALC_DELTA: 차이 계산
            CALC_DELTA --> [*]
        }

        state CALC_CI {
            [*] --> CURRENT_CI: current confidence interval
            [*] --> BASELINE_CI: baseline confidence interval
            CURRENT_CI --> [*]
            BASELINE_CI --> [*]
        }

        state GET_P0 {
            [*] --> CURRENT_P0: current.p0_safety_status()
            [*] --> BASELINE_P0: baseline.p0_safety_status()
            CURRENT_P0 --> [*]
            BASELINE_P0 --> [*]
        }
    }

    PARALLEL_CALC --> ANALYSIS: 모든 계산 완료

    state ANALYSIS {
        [*] --> CHECK_P0_REGRESSION: baseline 통과 → current 실패?
        CHECK_P0_REGRESSION --> P0_REGRESSED: Yes
        CHECK_P0_REGRESSION --> CHECK_CI_OVERLAP: No

        CHECK_CI_OVERLAP --> SIGNIFICANT_CHANGE: 구간 겹치지 않음
        CHECK_CI_OVERLAP --> NO_CHANGE: 구간 겹침

        SIGNIFICANT_CHANGE --> CHECK_DELTA_DIRECTION
        CHECK_DELTA_DIRECTION --> SIGNIFICANT_REGRESSION: delta < -threshold
        CHECK_DELTA_DIRECTION --> REVIEW_NEEDED: delta >= -threshold
    }

    ANALYSIS --> DETERMINE_ACTION

    state DETERMINE_ACTION {
        P0_REGRESSED --> BLOCK: "BLOCK: P0 safety regression"
        SIGNIFICANT_REGRESSION --> BLOCK: "BLOCK: Significant regression"
        REVIEW_NEEDED --> REVIEW: "REVIEW: Statistical change"
        NO_CHANGE --> PASS: "PASS: No significant change"
    }

    DETERMINE_ACTION --> [*]: Recommendation 반환
```

## 8. 전체 컴포넌트 관계도 - 수정됨

통합 entry point(`run_eval_suite`)와 레거시 entry point 모두 표시.

```mermaid
flowchart TB
    subgraph "Unified Entry Point (권장)"
        RUN_SUITE[run_eval_suite]
        SUITE_TYPE[EvalSuiteType]
    end

    subgraph "Legacy Entry Points (Deprecated)"
        PR_CHECK[run_pr_eval]
        NIGHTLY[run_nightly_eval]
        RELEASE[run_release_eval]
        VDOT_EVAL[run_vdot_eval]
        TRAINING_EVAL[run_training_plan_eval]
    end

    subgraph "Configuration Layer"
        CI_CONFIG[CIEvalConfig]
        PR_FAST[PR_FAST_CONFIG]
        PR_SAFETY[PR_SAFETY_CONFIG]
        NIGHTLY_FULL[NIGHTLY_FULL_CONFIG]
        NIGHTLY_LLM[NIGHTLY_LLM_GRADER_CONFIG]
        RELEASE_FULL[RELEASE_FULL_CONFIG]
        RELEASE_REG[RELEASE_REGRESSION_CONFIG]
    end

    subgraph "Runner Layer"
        EVAL_RUNNER[EvalRunner]
        FILTER[filter_tasks_for_config]
        VALIDATE[validate_eval_result]
    end

    subgraph "Execution Layer"
        RUN_TASK[_run_task]
        RUN_TRIAL[_run_trial]
        EXECUTOR[executor callable]
        GRADERS[graders list]
    end

    subgraph "Transcript Layer"
        TRANSCRIPT_LOGGER[TranscriptLogger]
        EVAL_TRANSCRIPT[EvalTranscript]
    end

    subgraph "Metrics Layer"
        TASK_CONFIG[TaskConfig]
        TASK_CONFIGS[TASK_CONFIGS registry]
        GET_TASK_CONFIG[get_task_config]
        EVAL_METRICS[EvalMetrics]
    end

    subgraph "Data Models"
        EVAL_RESULT[EvalResult]
        TASK_RESULT[TaskResult]
        TRIAL_RESULT[TrialResult]
    end

    subgraph "Analysis"
        BY_PRIORITY[by_priority]
        BY_METRIC[by_metric_type]
        P0_STATUS[p0_safety_status]
        COMPARE[compare_eval_results]
        REGRESSION[check_regression]
        CONF_INT[calculate_confidence_interval]
    end

    %% Unified Entry Point connections (권장 경로)
    RUN_SUITE --> SUITE_TYPE
    SUITE_TYPE --> CI_CONFIG
    RUN_SUITE --> EVAL_RUNNER

    %% Legacy Entry Point connections (deprecated)
    PR_CHECK -.-> PR_FAST
    NIGHTLY -.-> NIGHTLY_FULL
    RELEASE -.-> RELEASE_FULL
    VDOT_EVAL -.-> EVAL_RUNNER
    TRAINING_EVAL -.-> EVAL_RUNNER

    PR_FAST --> EVAL_RUNNER
    NIGHTLY_FULL --> EVAL_RUNNER
    RELEASE_FULL --> EVAL_RUNNER

    %% Runner connections
    EVAL_RUNNER --> FILTER
    FILTER --> GET_TASK_CONFIG
    GET_TASK_CONFIG --> TASK_CONFIGS

    EVAL_RUNNER --> RUN_TASK
    RUN_TASK --> RUN_TRIAL
    RUN_TRIAL --> EXECUTOR
    RUN_TRIAL --> GRADERS

    %% Transcript connections
    RUN_TRIAL --> EVAL_TRANSCRIPT
    EVAL_TRANSCRIPT --> TRANSCRIPT_LOGGER
    TRANSCRIPT_LOGGER -.-> EVAL_RUNNER

    %% Result connections
    RUN_TRIAL --> TRIAL_RESULT
    RUN_TASK --> TASK_RESULT
    EVAL_RUNNER --> EVAL_RESULT

    %% Validation connections
    EVAL_RESULT --> VALIDATE
    VALIDATE --> EVAL_METRICS
    EVAL_METRICS --> P0_STATUS

    %% Analysis connections
    EVAL_RESULT --> BY_PRIORITY
    EVAL_RESULT --> BY_METRIC
    BY_PRIORITY --> GET_TASK_CONFIG
    BY_METRIC --> GET_TASK_CONFIG

    EVAL_RESULT --> COMPARE
    COMPARE --> REGRESSION
    CONF_INT --> REGRESSION
```

## Priority 및 Metric Type 매핑

| Priority | Metric Type | Pass Metric | Threshold | 예시 Task |
|----------|-------------|-------------|-----------|-----------|
| P0_SAFETY | CUSTOMER_FACING | Pass^k | 95% | should_not_*, advice_*_pain |
| P1_ACCURACY | DETERMINISTIC | Pass@1 | 95% | vdot_* |
| P1_ACCURACY | CUSTOMER_FACING | Pass^k | 85% | marathon_*, half_* |
| P2_QUALITY | CUSTOMER_FACING | Pass^k | 75% | advice_* |
| P2_QUALITY | TOOL | Pass@k | 80% | rag_* |
| P3_EXPERIENCE | CUSTOMER_FACING | Pass^k | 70% | personalization_*, edge_* |

## CI Config별 필터링

| Config | Priorities | Metric Types | Max Trials | Timeout | LLM |
|--------|------------|--------------|------------|---------|-----|
| PR_FAST | P0, P1 | DETERMINISTIC | 1 | 120s | No |
| PR_SAFETY | P0 | All | 3 | 180s | No |
| NIGHTLY_FULL | P0, P1, P2 | All | 3 | 600s | Yes |
| NIGHTLY_LLM | P2 | CUSTOMER_FACING | 2 | 900s | Yes |
| RELEASE_FULL | P0, P1, P2, P3 | All | 5 | 1800s | Yes |
| RELEASE_REGRESSION | P0, P1 | All | 3 | 600s | No |
