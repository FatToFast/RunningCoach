from datetime import datetime
from typing import Optional
import json

from openai import OpenAI

from app.config import get_settings
from app.services.garmin_client import get_garmin_client


class TrainingAI:
    """AI 훈련 코치"""

    SYSTEM_PROMPT = """당신은 전문 러닝 코치입니다. 사용자의 훈련 데이터를 분석하고 개인화된 훈련 계획을 제안합니다.

주요 역할:
1. 사용자의 현재 체력 수준과 훈련 부하를 분석
2. 목표(마라톤, 하프마라톤, 10K 등)에 맞는 훈련 계획 수립
3. 회복과 부상 예방을 고려한 균형 잡힌 스케줄 제안
4. 주간/월간 훈련 주기화 적용

훈련 유형:
- easy: 편한 페이스의 회복/기초 러닝 (최대 심박수의 60-70%)
- tempo: 젖산 역치 페이스 러닝 (최대 심박수의 80-90%)
- interval: 고강도 인터벌 훈련
- long_run: 장거리 러닝 (주간 최장 거리)
- recovery: 가벼운 회복 러닝
- rest: 완전 휴식

응답 시 훈련 스케줄을 제안할 때는 다음 JSON 형식을 사용하세요:
```json
{
  "schedule": {
    "title": "훈련 계획 제목",
    "description": "계획 설명",
    "goal": "목표",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "workouts": [
      {
        "date": "YYYY-MM-DD",
        "workout_type": "easy|tempo|interval|long_run|recovery|rest",
        "title": "운동 제목",
        "description": "상세 설명",
        "target_distance_meters": 5000,
        "target_duration_seconds": 1800,
        "target_pace": "5:30",
        "intervals": null
      }
    ]
  }
}
```

인터벌 훈련의 경우 intervals 필드에 다음 형식 사용:
```json
{
  "intervals": {
    "warmup_meters": 1600,
    "cooldown_meters": 1600,
    "repeats": [
      {"distance_meters": 400, "pace": "4:00", "rest_seconds": 90, "reps": 8}
    ]
  }
}
```
"""

    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)
        self.conversation_history: list[dict] = []

    def _get_garmin_context(self) -> str:
        """가민 데이터로 컨텍스트 생성"""
        try:
            garmin = get_garmin_client()
            if not garmin.is_authenticated():
                return "가민 데이터 없음 (로그인 필요)"

            weekly_stats = garmin.get_weekly_stats()
            training_status = garmin.get_training_status()

            context = f"""
현재 훈련 상태:
- 주간 총 거리: {weekly_stats['total_distance_km']} km
- 주간 총 시간: {weekly_stats['total_duration_minutes']} 분
- 주간 활동 수: {weekly_stats['total_activities']} 회
- 평균 페이스: {weekly_stats['avg_pace'] or 'N/A'}
- 평균 심박수: {weekly_stats['avg_heart_rate'] or 'N/A'} bpm
- VO2max: {training_status.get('vo2max') or 'N/A'}
- 7일 훈련 부하: {training_status.get('training_load_7day', 0)}
- 28일 훈련 부하: {training_status.get('training_load_28day', 0)}
"""
            return context
        except Exception as e:
            return f"가민 데이터 조회 실패: {str(e)}"

    def chat(self, user_message: str, include_garmin_context: bool = True) -> dict:
        """AI와 대화"""
        # 컨텍스트 구성
        system_message = self.SYSTEM_PROMPT
        if include_garmin_context:
            garmin_context = self._get_garmin_context()
            system_message += f"\n\n사용자의 현재 훈련 데이터:\n{garmin_context}"

        # 대화 기록 관리 (최근 10개만 유지)
        self.conversation_history.append({"role": "user", "content": user_message})
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        messages = [{"role": "system", "content": system_message}] + self.conversation_history

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            )

            assistant_message = response.choices[0].message.content
            self.conversation_history.append({"role": "assistant", "content": assistant_message})

            # 스케줄 JSON 추출 시도
            schedule = self._extract_schedule(assistant_message)

            return {
                "response": assistant_message,
                "suggested_schedule": schedule,
            }

        except Exception as e:
            return {
                "response": f"AI 응답 생성 중 오류 발생: {str(e)}",
                "suggested_schedule": None,
            }

    def _extract_schedule(self, message: str) -> Optional[dict]:
        """응답에서 스케줄 JSON 추출"""
        try:
            # JSON 블록 찾기
            start_markers = ['```json', '{"schedule"']
            end_markers = ['```', '}}\n']

            json_str = None
            for start in start_markers:
                if start in message:
                    start_idx = message.find(start)
                    if start == '```json':
                        start_idx += len('```json')
                        end_idx = message.find('```', start_idx)
                    else:
                        # 중괄호 매칭으로 끝 찾기
                        depth = 0
                        for i, char in enumerate(message[start_idx:]):
                            if char == '{':
                                depth += 1
                            elif char == '}':
                                depth -= 1
                                if depth == 0:
                                    end_idx = start_idx + i + 1
                                    break

                    if end_idx > start_idx:
                        json_str = message[start_idx:end_idx].strip()
                        break

            if json_str:
                data = json.loads(json_str)
                if "schedule" in data:
                    return data["schedule"]
                return data

        except (json.JSONDecodeError, ValueError):
            pass

        return None

    def generate_schedule(
        self,
        goal: str,
        target_date: Optional[datetime] = None,
        current_weekly_km: float = 0,
        experience_level: str = "intermediate",
    ) -> dict:
        """훈련 스케줄 자동 생성"""
        prompt = f"""다음 조건에 맞는 주간 훈련 스케줄을 생성해주세요:

목표: {goal}
목표 대회 날짜: {target_date.strftime('%Y-%m-%d') if target_date else '미정'}
현재 주간 러닝 거리: {current_weekly_km} km
경험 수준: {experience_level}

오늘 날짜: {datetime.now().strftime('%Y-%m-%d')}

1주일 분량의 구체적인 훈련 계획을 JSON 형식으로 제공해주세요."""

        return self.chat(prompt, include_garmin_context=True)

    def clear_history(self):
        """대화 기록 초기화"""
        self.conversation_history = []


# 싱글톤 인스턴스
_training_ai: Optional[TrainingAI] = None


def get_training_ai() -> TrainingAI:
    global _training_ai
    if _training_ai is None:
        _training_ai = TrainingAI()
    return _training_ai
