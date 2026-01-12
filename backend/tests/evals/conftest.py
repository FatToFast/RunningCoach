"""Pytest configuration and fixtures for AI evaluation tests."""

import asyncio
from datetime import datetime
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client for testing."""
    client = AsyncMock()

    # Default response for coaching quality grading
    client.generate.return_value = '''{
        "scores": {
            "personalization": 4,
            "scientific": 4,
            "feasibility": 4,
            "safety": 5,
            "clarity": 4
        },
        "overall": 4.2,
        "strengths": ["Good personalization", "Safety-focused"],
        "weaknesses": ["Could be more specific"],
        "reasoning": "Overall good quality coaching response"
    }'''

    return client


@pytest.fixture
def mock_rag_retriever():
    """Create a mock RAG retriever for testing."""
    retriever = AsyncMock()

    retriever.search.return_value = [
        MagicMock(
            chunk=MagicMock(
                title="인터벌 훈련 가이드",
                source="training_guide.md",
                content="인터벌 훈련은 VO2max 향상에 효과적입니다...",
            ),
            score=0.85,
        ),
        MagicMock(
            chunk=MagicMock(
                title="마라톤 페이스 전략",
                source="race_strategy.md",
                content="마라톤 페이스 전략의 핵심은...",
            ),
            score=0.78,
        ),
    ]

    return retriever


@pytest.fixture
def sample_user_context():
    """Sample user context for testing."""
    return {
        "user_profile": {
            "weekly_mileage_km": 40,
            "recent_5k_time": "22:00",
            "recent_10k_time": "46:00",
            "experience_level": "intermediate",
            "age": 35,
            "max_hr": 185,
            "resting_hr": 55,
        },
        "goal": {
            "race_name": "서울마라톤",
            "race_date": "2026-03-15",
            "distance": "full_marathon",
            "target_time": "3:45:00",
        },
        "constraints": {
            "available_days_per_week": 4,
            "max_long_run_hours": 3,
        },
        "fitness_status": {
            "ctl": 45.5,
            "atl": 52.3,
            "tsb": -6.8,
        },
    }


@pytest.fixture
def sample_training_plan_response():
    """Sample AI coach training plan response."""
    return """## 16주 마라톤 훈련 계획

목표: 서울마라톤 3:45 완주
현재 주간 거리: 40km
VDOT 추정: 45 (10K 46:00 기준)

### 추천 훈련 페이스
- 이지런: 5:50-6:20/km
- 마라톤 페이스: 5:20/km
- 템포: 5:00/km
- 인터벌: 4:35/km

### 1주차 (베이스)

| 요일 | 훈련 | 거리/시간 | 페이스/강도 | 목적 |
|------|------|----------|------------|------|
| 월 | 휴식 | - | - | 회복 |
| 화 | 이지런 | 8km | 6:00/km | 기초 지구력 |
| 수 | 휴식 | - | - | 회복 |
| 목 | 템포런 | 10km | 5:00/km (중간 4km) | 유산소 역치 |
| 금 | 휴식 | - | - | 회복 |
| 토 | 이지런 | 6km | 6:10/km | 회복 |
| 일 | 장거리 | 16km | 6:00/km | 지구력 |

주간 총 거리: 40km

### 주의사항
- 점진적으로 거리를 늘려가세요 (주당 10% 이내)
- 통증이 있으면 즉시 휴식하세요
- 충분한 수분 섭취와 수면이 중요합니다

### 테이퍼링 (15-16주차)
- 15주차: 평소의 60-70% 거리
- 16주차 (대회 주): 평소의 40% 거리, 가벼운 조깅만
"""


@pytest.fixture
def sample_coaching_advice_response():
    """Sample AI coach advice response."""
    return """정강이 통증에 대해 걱정되시는군요. 러닝 후 정강이 앞쪽 통증은
일반적으로 '정강이통(shin splints)'이라고 불리는 증상일 수 있습니다.

### 원인 분석
주간 거리를 30% 증가시킨 것이 주요 원인일 수 있습니다.
일반적으로 주당 10% 이내로 거리를 늘리는 것이 안전합니다.
또한 신발이 800km를 넘었다면 쿠션이 약해져 충격 흡수가 부족할 수 있습니다.

### 권장 사항
1. **휴식**: 2-3일간 러닝을 쉬세요
2. **아이싱**: 통증 부위에 15-20분씩 얼음찜질
3. **신발 교체**: 800km 이상 사용한 신발은 교체를 권장합니다
4. **점진적 복귀**: 통증이 사라진 후 이전 거리의 50%부터 시작

### 주의 사항
통증이 1주일 이상 지속되거나 악화된다면
**반드시 정형외과 또는 스포츠의학 전문의 상담**을 받으세요.

절대로 통증을 무시하고 계속 뛰지 마세요.
부상 예방이 기록 향상보다 훨씬 중요합니다!
"""


@pytest.fixture
def eval_runner_config():
    """Default eval runner configuration."""
    return {
        "trials_per_task": 3,
        "parallel_tasks": 1,
        "timeout_seconds": 60,
        "save_transcripts": False,  # Disable for unit tests
    }


# Markers for test categories
def pytest_configure(config):
    """Add custom markers."""
    config.addinivalue_line(
        "markers", "vdot: VDOT calculation tests"
    )
    config.addinivalue_line(
        "markers", "training_plan: Training plan evaluation tests"
    )
    config.addinivalue_line(
        "markers", "coaching: Coaching advice evaluation tests"
    )
    config.addinivalue_line(
        "markers", "rag: RAG retrieval quality tests"
    )
    config.addinivalue_line(
        "markers", "slow: Slow tests (LLM calls, etc.)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests requiring services"
    )
