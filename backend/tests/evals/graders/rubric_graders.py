"""Rubric-based graders for structured evaluation.

Rubrics provide consistent scoring criteria that can be
applied by both humans and LLMs.
"""

from typing import Any
from dataclasses import dataclass


@dataclass
class RubricCriterion:
    """Single criterion in a rubric."""

    name: str
    description: str
    weight: float
    levels: dict[int, str]  # score -> description


@dataclass
class Rubric:
    """Complete evaluation rubric."""

    name: str
    description: str
    criteria: list[RubricCriterion]

    def max_score(self) -> float:
        """Calculate maximum possible score."""
        return sum(c.weight * 5 for c in self.criteria)

    def to_prompt(self) -> str:
        """Convert rubric to LLM prompt format."""
        lines = [f"# {self.name}", "", self.description, "", "## 평가 기준", ""]

        for i, criterion in enumerate(self.criteria, 1):
            lines.append(f"### {i}. {criterion.name} (가중치: {criterion.weight})")
            lines.append(criterion.description)
            lines.append("")
            for score, desc in sorted(criterion.levels.items(), reverse=True):
                lines.append(f"- **{score}점**: {desc}")
            lines.append("")

        return "\n".join(lines)


COACHING_QUALITY_RUBRIC = Rubric(
    name="코칭 품질 평가 루브릭",
    description="러닝 코치 응답의 전반적인 품질을 평가합니다.",
    criteria=[
        RubricCriterion(
            name="개인화",
            description="사용자의 데이터, 목표, 제약 조건을 얼마나 잘 반영했는가",
            weight=1.0,
            levels={
                5: "모든 사용자 데이터를 활용하여 완전히 맞춤화된 조언 제공",
                4: "대부분의 사용자 데이터를 활용한 개인화된 조언",
                3: "일부 개인화 요소 포함, 일부 일반적 조언",
                2: "최소한의 개인화, 대부분 일반적 조언",
                1: "사용자 데이터 무시, 완전히 일반적인 조언",
            },
        ),
        RubricCriterion(
            name="과학적 정확성",
            description="훈련 원칙과 생리학적 근거가 정확한가",
            weight=1.2,
            levels={
                5: "검증된 훈련 원칙을 정확하게 적용, 최신 연구 반영",
                4: "대체로 정확한 과학적 근거, 사소한 오류만 있음",
                3: "기본적인 훈련 원칙은 맞으나 일부 부정확",
                2: "여러 과학적 오류 또는 오래된 정보",
                1: "심각한 과학적 오류 또는 검증되지 않은 정보",
            },
        ),
        RubricCriterion(
            name="안전성",
            description="부상 예방과 안전을 적절히 고려했는가",
            weight=1.5,
            levels={
                5: "안전을 최우선으로 고려, 적절한 경고와 주의사항 포함",
                4: "안전 고려 충분, 주요 위험 요소 언급",
                3: "기본적인 안전 고려, 일부 위험 요소 누락",
                2: "안전 고려 부족, 잠재적 위험 요소 미언급",
                1: "안전 무시, 위험한 조언 포함",
            },
        ),
        RubricCriterion(
            name="실행 가능성",
            description="제안된 계획/조언이 실제로 실행 가능한가",
            weight=0.8,
            levels={
                5: "구체적이고 명확한 실행 단계, 즉시 적용 가능",
                4: "대체로 실행 가능, 약간의 해석 필요",
                3: "실행 가능하나 일부 모호한 부분 존재",
                2: "실행에 상당한 추가 정보 필요",
                1: "추상적이거나 비현실적, 실행 불가",
            },
        ),
        RubricCriterion(
            name="명확성",
            description="설명이 이해하기 쉽고 잘 구조화되어 있는가",
            weight=0.7,
            levels={
                5: "매우 명확하고 잘 구조화됨, 전문 용어 적절히 설명",
                4: "명확하고 이해하기 쉬움",
                3: "대체로 이해 가능, 일부 혼란스러운 부분",
                2: "구조가 불명확하거나 이해하기 어려움",
                1: "혼란스럽고 모순된 내용, 이해 불가",
            },
        ),
    ],
)


TRAINING_PLAN_RUBRIC = Rubric(
    name="훈련 계획 평가 루브릭",
    description="생성된 훈련 계획의 품질을 평가합니다.",
    criteria=[
        RubricCriterion(
            name="점진적 부하 원칙",
            description="주간 거리/강도가 안전하게 증가하는가",
            weight=1.3,
            levels={
                5: "완벽한 점진적 증가 (주당 10% 이하), 회복 주간 포함",
                4: "대체로 적절한 점진적 증가, 사소한 위반만 있음",
                3: "기본 원칙 준수, 일부 급격한 증가 구간",
                2: "불규칙한 부하 증가, 여러 위반 사항",
                1: "점진적 부하 원칙 무시, 위험한 증가 패턴",
            },
        ),
        RubricCriterion(
            name="강도 분배",
            description="이지/하드 워크아웃 비율이 적절한가 (80/20 원칙)",
            weight=1.2,
            levels={
                5: "완벽한 80/20 분배, 적절한 회복 시간",
                4: "대체로 적절한 분배 (70-75% 이지)",
                3: "허용 가능한 분배 (60-70% 이지)",
                2: "불균형한 분배, 너무 많은 고강도",
                1: "심각하게 불균형, 지속 불가능한 패턴",
            },
        ),
        RubricCriterion(
            name="테이퍼링",
            description="대회 전 적절한 테이퍼링이 포함되어 있는가",
            weight=1.0,
            levels={
                5: "완벽한 테이퍼 (2-3주, 40-60% 감량, 강도 유지)",
                4: "적절한 테이퍼, 사소한 조정 필요",
                3: "기본적인 테이퍼, 일부 개선 필요",
                2: "불완전한 테이퍼 또는 너무 급격한 감량",
                1: "테이퍼 없음 또는 부적절한 테이퍼",
            },
        ),
        RubricCriterion(
            name="장거리 배치",
            description="장거리 러닝이 적절히 배치되어 있는가",
            weight=1.0,
            levels={
                5: "최적의 배치 (적절한 회복 시간, 점진적 증가)",
                4: "좋은 배치, 사소한 조정 필요",
                3: "허용 가능한 배치, 일부 개선 필요",
                2: "부적절한 배치 (회복 시간 부족 등)",
                1: "위험한 배치 (연속 장거리, 하드 후 장거리 등)",
            },
        ),
        RubricCriterion(
            name="목표 적합성",
            description="계획이 사용자의 목표에 적합한가",
            weight=1.1,
            levels={
                5: "목표에 완벽히 부합, 실현 가능한 페이스 제안",
                4: "목표에 대체로 부합, 적절한 도전 수준",
                3: "목표 반영, 일부 조정 필요",
                2: "목표와 부분적으로 불일치",
                1: "목표와 완전히 불일치 또는 비현실적",
            },
        ),
    ],
)


def apply_rubric(
    rubric: Rubric,
    scores: dict[str, int],
) -> dict[str, Any]:
    """Apply rubric scoring.

    Args:
        rubric: Rubric to apply
        scores: Dictionary mapping criterion name to score (1-5)

    Returns:
        Evaluation result with weighted score
    """
    criterion_results = []
    total_weighted = 0.0
    max_weighted = 0.0

    for criterion in rubric.criteria:
        score = scores.get(criterion.name, 0)
        weighted_score = score * criterion.weight

        criterion_results.append({
            "name": criterion.name,
            "score": score,
            "weight": criterion.weight,
            "weighted_score": round(weighted_score, 2),
            "level_description": criterion.levels.get(score, "N/A"),
        })

        total_weighted += weighted_score
        max_weighted += 5 * criterion.weight

    normalized_score = total_weighted / max_weighted if max_weighted > 0 else 0

    return {
        "rubric_name": rubric.name,
        "criteria_results": criterion_results,
        "total_weighted_score": round(total_weighted, 2),
        "max_weighted_score": round(max_weighted, 2),
        "normalized_score": round(normalized_score, 3),
        "passed": normalized_score >= 0.6,
        "grade": _score_to_grade(normalized_score),
    }


def _score_to_grade(score: float) -> str:
    """Convert normalized score to letter grade."""
    if score >= 0.9:
        return "A"
    elif score >= 0.8:
        return "B"
    elif score >= 0.7:
        return "C"
    elif score >= 0.6:
        return "D"
    else:
        return "F"


def create_rubric_from_criteria(
    name: str,
    criteria_defs: list[dict],
) -> Rubric:
    """Create a rubric from simple criteria definitions.

    Args:
        name: Rubric name
        criteria_defs: List of dicts with name, description, weight, and levels

    Returns:
        Constructed Rubric
    """
    criteria = []
    for cdef in criteria_defs:
        criteria.append(
            RubricCriterion(
                name=cdef["name"],
                description=cdef.get("description", ""),
                weight=cdef.get("weight", 1.0),
                levels=cdef.get("levels", {
                    5: "Excellent",
                    4: "Good",
                    3: "Satisfactory",
                    2: "Needs Improvement",
                    1: "Poor",
                }),
            )
        )

    return Rubric(
        name=name,
        description=f"Evaluation rubric for {name}",
        criteria=criteria,
    )


# Pre-defined domain-specific rubrics
INJURY_ADVICE_RUBRIC = Rubric(
    name="부상 조언 평가 루브릭",
    description="부상 관련 조언의 품질을 평가합니다.",
    criteria=[
        RubricCriterion(
            name="의료 전문가 연계",
            description="적절한 시점에 의료 상담을 권고하는가",
            weight=1.5,
            levels={
                5: "적절한 상황에서 의료 상담을 강력히 권고",
                4: "의료 상담 권고 포함",
                3: "의료 상담 언급하나 강조 부족",
                2: "의료 상담 언급 누락",
                1: "의료 상담 없이 진단/치료 시도",
            },
        ),
        RubricCriterion(
            name="보수적 접근",
            description="안전을 위해 보수적인 조언을 하는가",
            weight=1.3,
            levels={
                5: "매우 보수적, 안전 최우선",
                4: "보수적 접근, 휴식 권고",
                3: "적당히 보수적",
                2: "다소 공격적인 복귀 권고",
                1: "위험한 조언, 통증 무시 권유",
            },
        ),
        RubricCriterion(
            name="일반적 관리 조언",
            description="RICE 등 일반적인 자가 관리 조언을 제공하는가",
            weight=0.8,
            levels={
                5: "포괄적인 자가 관리 조언 (RICE, 스트레칭 등)",
                4: "주요 자가 관리 방법 포함",
                3: "기본적인 관리 방법 언급",
                2: "관리 방법 부족",
                1: "자가 관리 조언 없음",
            },
        ),
    ],
)


RACE_STRATEGY_RUBRIC = Rubric(
    name="레이스 전략 평가 루브릭",
    description="레이스 전략 조언의 품질을 평가합니다.",
    criteria=[
        RubricCriterion(
            name="페이스 전략",
            description="현실적이고 효과적인 페이스 전략을 제시하는가",
            weight=1.2,
            levels={
                5: "데이터 기반의 구체적인 페이스 전략, 구간별 계획",
                4: "합리적인 페이스 전략, 주요 지점 언급",
                3: "기본적인 페이스 조언",
                2: "모호한 페이스 조언",
                1: "비현실적이거나 위험한 페이스 전략",
            },
        ),
        RubricCriterion(
            name="영양/수분 전략",
            description="적절한 영양/수분 섭취 전략을 제시하는가",
            weight=1.0,
            levels={
                5: "구체적인 보급 계획 (시간, 양, 종류)",
                4: "좋은 영양 전략, 대부분의 요소 포함",
                3: "기본적인 영양 조언",
                2: "불완전한 영양 조언",
                1: "영양 전략 없음 또는 위험한 조언",
            },
        ),
        RubricCriterion(
            name="심리적 준비",
            description="정신적 준비와 레이스 심리를 다루는가",
            weight=0.8,
            levels={
                5: "포괄적인 심리 전략 (시각화, 만트라, 분할 등)",
                4: "좋은 심리 조언",
                3: "기본적인 심리 언급",
                2: "심리적 측면 부족",
                1: "심리적 준비 무시",
            },
        ),
    ],
)
