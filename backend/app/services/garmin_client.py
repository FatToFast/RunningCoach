import json
from datetime import datetime, timedelta, date
from typing import Optional
from pathlib import Path

from garminconnect import Garmin

from app.config import get_settings


class GarminClient:
    """가민 커넥트 API 클라이언트 - Runalyze/Stryd 호환 전체 데이터 수집"""

    def __init__(self):
        self.settings = get_settings()
        self.client: Optional[Garmin] = None
        self.token_path = Path("./data/.garmin_tokens")

    def _get_token_store(self) -> Path:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        return self.token_path

    def is_authenticated(self) -> bool:
        return self.client is not None

    def login(self, email: Optional[str] = None, password: Optional[str] = None) -> bool:
        email = email or self.settings.garmin_email
        password = password or self.settings.garmin_password

        if not email or not password:
            raise ValueError("Garmin credentials not provided")

        try:
            self.client = Garmin(email, password)
            token_file = self._get_token_store()

            if token_file.exists():
                try:
                    self.client.login(token_file)
                    return True
                except Exception:
                    pass

            self.client.login()
            self.client.garth.dump(str(token_file))
            return True

        except Exception as e:
            self.client = None
            raise Exception(f"Garmin login failed: {str(e)}")

    def logout(self):
        self.client = None
        if self._get_token_store().exists():
            self._get_token_store().unlink()

    # ==================== 활동 데이터 ====================

    def get_activities(self, start: int = 0, limit: int = 20) -> list[dict]:
        """활동 목록 조회"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.get_activities(start, limit)

    def get_activities_by_date(self, start_date: date, end_date: date) -> list[dict]:
        """날짜 범위로 활동 조회"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.get_activities_by_date(
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d")
        )

    def get_activity_details(self, activity_id: str) -> dict:
        """활동 상세 정보 - Stryd 데이터 포함"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.get_activity(activity_id)

    def get_activity_splits(self, activity_id: str) -> list[dict]:
        """활동 스플릿/랩 데이터"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.get_activity_splits(activity_id)

    def get_activity_hr_zones(self, activity_id: str) -> dict:
        """심박존 시간 분포"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.get_activity_hr_in_timezones(activity_id)

    def get_activity_weather(self, activity_id: str) -> dict:
        """활동 중 날씨 정보"""
        if not self.client:
            raise Exception("Not authenticated")
        try:
            return self.client.get_activity_weather(activity_id)
        except Exception:
            return {}

    # ==================== 일일 통계 ====================

    def get_daily_summary(self, day: date) -> dict:
        """일일 활동 요약"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.get_user_summary(day.strftime("%Y-%m-%d"))

    def get_steps_data(self, day: date) -> dict:
        """걸음 수 상세"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.get_steps_data(day.strftime("%Y-%m-%d"))

    # ==================== 심박수 & HRV ====================

    def get_heart_rates(self, day: date) -> dict:
        """일일 심박수 데이터"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.get_heart_rates(day.strftime("%Y-%m-%d"))

    def get_resting_heart_rate(self, day: date) -> dict:
        """안정시 심박수"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.get_rhr_day(day.strftime("%Y-%m-%d"))

    def get_hrv_data(self, day: date) -> dict:
        """HRV (심박 변이도) 데이터"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.get_hrv_data(day.strftime("%Y-%m-%d"))

    # ==================== 수면 ====================

    def get_sleep_data(self, day: date) -> dict:
        """수면 데이터"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.get_sleep_data(day.strftime("%Y-%m-%d"))

    # ==================== 스트레스 & Body Battery ====================

    def get_stress_data(self, day: date) -> dict:
        """스트레스 레벨"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.get_stress_data(day.strftime("%Y-%m-%d"))

    def get_body_battery(self, day: date) -> dict:
        """Body Battery"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.get_body_battery(day.strftime("%Y-%m-%d"))

    # ==================== 호흡 & SpO2 ====================

    def get_respiration_data(self, day: date) -> dict:
        """호흡수 데이터"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.get_respiration_data(day.strftime("%Y-%m-%d"))

    def get_spo2_data(self, day: date) -> dict:
        """혈중 산소 포화도"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.get_spo2_data(day.strftime("%Y-%m-%d"))

    # ==================== 체성분 ====================

    def get_body_composition(self, start_date: date, end_date: date) -> dict:
        """체성분 데이터"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.get_body_composition(
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d")
        )

    def get_weigh_ins(self, day: date) -> list[dict]:
        """체중 측정 기록"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.get_daily_weigh_ins(day.strftime("%Y-%m-%d"))

    # ==================== 훈련 상태 ====================

    def get_training_status(self) -> dict:
        """훈련 상태 (VO2max, 훈련 부하 등)"""
        if not self.client:
            raise Exception("Not authenticated")
        try:
            return self.client.get_training_status(None)
        except Exception:
            # 폴백: 활동에서 추출
            activities = self.client.get_activities(0, 5)
            vo2max = None
            for activity in activities:
                if activity.get("vO2MaxValue"):
                    vo2max = activity["vO2MaxValue"]
                    break
            return {
                "vo2max": vo2max,
                "training_load_7day": self._calculate_training_load(7),
                "training_load_28day": self._calculate_training_load(28),
            }

    def get_training_readiness(self, day: date) -> dict:
        """훈련 준비도"""
        if not self.client:
            raise Exception("Not authenticated")
        try:
            return self.client.get_training_readiness(day.strftime("%Y-%m-%d"))
        except Exception:
            return {}

    def get_race_predictions(self) -> dict:
        """레이스 예측 시간"""
        if not self.client:
            raise Exception("Not authenticated")
        try:
            return self.client.get_race_predictions()
        except Exception:
            return {}

    def get_lactate_threshold(self) -> dict:
        """젖산 역치 데이터"""
        if not self.client:
            raise Exception("Not authenticated")
        try:
            return self.client.get_lactate_threshold()
        except Exception:
            return {}

    def get_endurance_score(self, day: date) -> dict:
        """지구력 점수"""
        if not self.client:
            raise Exception("Not authenticated")
        try:
            return self.client.get_endurance_score(day.strftime("%Y-%m-%d"))
        except Exception:
            return {}

    def get_fitness_age(self) -> dict:
        """피트니스 연령"""
        if not self.client:
            raise Exception("Not authenticated")
        try:
            return self.client.get_fitnessage_data()
        except Exception:
            return {}

    # ==================== 개인 기록 & 뱃지 ====================

    def get_personal_records(self) -> list[dict]:
        """개인 기록"""
        if not self.client:
            raise Exception("Not authenticated")
        try:
            return self.client.get_personal_record()
        except Exception:
            return []

    def get_earned_badges(self) -> list[dict]:
        """획득 뱃지"""
        if not self.client:
            raise Exception("Not authenticated")
        try:
            return self.client.get_earned_badges()
        except Exception:
            return []

    # ==================== 장비 ====================

    def get_gear(self) -> list[dict]:
        """모든 장비"""
        if not self.client:
            raise Exception("Not authenticated")
        try:
            return self.client.get_gear()
        except Exception:
            return []

    def get_gear_stats(self, gear_id: str) -> dict:
        """장비 사용 통계"""
        if not self.client:
            raise Exception("Not authenticated")
        try:
            return self.client.get_gear_stats(gear_id)
        except Exception:
            return {}

    # ==================== 기기 ====================

    def get_devices(self) -> list[dict]:
        """연결된 기기 목록"""
        if not self.client:
            raise Exception("Not authenticated")
        try:
            return self.client.get_devices()
        except Exception:
            return []

    # ==================== 워크아웃 ====================

    def get_workouts(self, start: int = 0, limit: int = 20) -> list[dict]:
        """워크아웃 목록"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.get_workouts(start, limit)

    def create_workout(self, workout_data: dict) -> dict:
        """워크아웃 생성"""
        if not self.client:
            raise Exception("Not authenticated")
        return self.client.upload_workout(workout_data)

    def schedule_workout(self, workout_id: str, day: date) -> dict:
        """워크아웃 스케줄링"""
        if not self.client:
            raise Exception("Not authenticated")
        try:
            return self.client.schedule_workout(workout_id, day.strftime("%Y-%m-%d"))
        except AttributeError:
            raise Exception("Workout scheduling not supported")

    # ==================== 종합 수집 ====================

    def get_full_daily_data(self, day: date) -> dict:
        """하루 전체 데이터 수집 (Runalyze 호환)"""
        if not self.client:
            raise Exception("Not authenticated")

        data = {
            "date": day.isoformat(),
            "summary": None,
            "heart_rate": None,
            "resting_hr": None,
            "hrv": None,
            "sleep": None,
            "stress": None,
            "body_battery": None,
            "respiration": None,
            "spo2": None,
            "steps": None,
            "training_readiness": None,
        }

        try:
            data["summary"] = self.get_daily_summary(day)
        except Exception:
            pass

        try:
            data["heart_rate"] = self.get_heart_rates(day)
        except Exception:
            pass

        try:
            data["resting_hr"] = self.get_resting_heart_rate(day)
        except Exception:
            pass

        try:
            data["hrv"] = self.get_hrv_data(day)
        except Exception:
            pass

        try:
            data["sleep"] = self.get_sleep_data(day)
        except Exception:
            pass

        try:
            data["stress"] = self.get_stress_data(day)
        except Exception:
            pass

        try:
            data["body_battery"] = self.get_body_battery(day)
        except Exception:
            pass

        try:
            data["respiration"] = self.get_respiration_data(day)
        except Exception:
            pass

        try:
            data["spo2"] = self.get_spo2_data(day)
        except Exception:
            pass

        try:
            data["steps"] = self.get_steps_data(day)
        except Exception:
            pass

        try:
            data["training_readiness"] = self.get_training_readiness(day)
        except Exception:
            pass

        return data

    def get_full_activity_data(self, activity_id: str) -> dict:
        """활동 전체 데이터 수집 (Stryd 포함)"""
        if not self.client:
            raise Exception("Not authenticated")

        data = {
            "activity_id": activity_id,
            "details": None,
            "splits": None,
            "hr_zones": None,
            "weather": None,
        }

        try:
            data["details"] = self.get_activity_details(activity_id)
        except Exception:
            pass

        try:
            data["splits"] = self.get_activity_splits(activity_id)
        except Exception:
            pass

        try:
            data["hr_zones"] = self.get_activity_hr_zones(activity_id)
        except Exception:
            pass

        try:
            data["weather"] = self.get_activity_weather(activity_id)
        except Exception:
            pass

        return data

    def _calculate_training_load(self, days: int) -> float:
        """훈련 부하 계산"""
        if not self.client:
            return 0.0

        try:
            activities = self.client.get_activities(0, 50)
            cutoff_date = datetime.now() - timedelta(days=days)
            total_load = 0.0

            for activity in activities:
                start_time_str = activity.get("startTimeLocal", "")
                if start_time_str:
                    try:
                        start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                        if start_time.replace(tzinfo=None) >= cutoff_date:
                            aerobic = activity.get("aerobicTrainingEffect", 0) or 0
                            anaerobic = activity.get("anaerobicTrainingEffect", 0) or 0
                            duration_min = (activity.get("duration", 0) or 0) / 60
                            load = (aerobic + anaerobic) * duration_min / 10
                            total_load += load
                    except ValueError:
                        continue

            return round(total_load, 1)
        except Exception:
            return 0.0

    def get_weekly_stats(self) -> dict:
        """주간 통계"""
        if not self.client:
            raise Exception("Not authenticated")

        activities = self.get_activities(0, 50)
        week_ago = datetime.now() - timedelta(days=7)

        weekly_activities = []
        for activity in activities:
            start_time_str = activity.get("startTimeLocal", "")
            if start_time_str:
                try:
                    start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                    if start_time.replace(tzinfo=None) >= week_ago:
                        weekly_activities.append(activity)
                except ValueError:
                    continue

        total_distance = sum(a.get("distance", 0) or 0 for a in weekly_activities)
        total_duration = sum(a.get("duration", 0) or 0 for a in weekly_activities)
        total_calories = sum(a.get("calories", 0) or 0 for a in weekly_activities)
        total_power_activities = [a for a in weekly_activities if a.get("avgPower")]

        heart_rates = [a.get("averageHR", 0) for a in weekly_activities if a.get("averageHR")]
        avg_hr = sum(heart_rates) / len(heart_rates) if heart_rates else None

        powers = [a.get("avgPower", 0) for a in total_power_activities if a.get("avgPower")]
        avg_power = sum(powers) / len(powers) if powers else None

        running_activities = [a for a in weekly_activities if a.get("activityType", {}).get("typeKey") == "running"]
        avg_pace = None
        if running_activities:
            running_duration = sum(a.get("duration", 0) or 0 for a in running_activities)
            running_distance = sum(a.get("distance", 0) or 0 for a in running_activities)
            if running_distance > 0:
                avg_pace_sec = running_duration / (running_distance / 1000)
                avg_pace_min = int(avg_pace_sec // 60)
                avg_pace_sec_rem = int(avg_pace_sec % 60)
                avg_pace = f"{avg_pace_min}:{avg_pace_sec_rem:02d}"

        return {
            "total_distance_km": round(total_distance / 1000, 2),
            "total_duration_minutes": round(total_duration / 60, 1),
            "total_activities": len(weekly_activities),
            "avg_pace": avg_pace,
            "avg_heart_rate": round(avg_hr, 1) if avg_hr else None,
            "avg_power": round(avg_power, 1) if avg_power else None,
            "total_calories": total_calories,
        }


# 싱글톤 인스턴스
_garmin_client: Optional[GarminClient] = None


def get_garmin_client() -> GarminClient:
    global _garmin_client
    if _garmin_client is None:
        _garmin_client = GarminClient()
    return _garmin_client
