from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from app.models.database import Activity


class TrainingAnalyzer:
    """훈련 부하 분석"""

    def __init__(self, db: Session):
        self.db = db

    def calculate_acute_load(self, days: int = 7) -> float:
        """급성 훈련 부하 (7일)"""
        cutoff = datetime.now() - timedelta(days=days)
        activities = self.db.query(Activity).filter(Activity.start_time >= cutoff).all()

        total_load = 0.0
        for activity in activities:
            load = self._calculate_activity_load(activity)
            total_load += load

        return round(total_load, 1)

    def calculate_chronic_load(self, days: int = 28) -> float:
        """만성 훈련 부하 (28일)"""
        cutoff = datetime.now() - timedelta(days=days)
        activities = self.db.query(Activity).filter(Activity.start_time >= cutoff).all()

        total_load = 0.0
        for activity in activities:
            load = self._calculate_activity_load(activity)
            total_load += load

        # 주간 평균으로 환산
        return round(total_load / (days / 7), 1)

    def _calculate_activity_load(self, activity: Activity) -> float:
        """개별 활동의 훈련 부하 계산 (TRIMP 기반)"""
        duration_min = activity.duration_seconds / 60 if activity.duration_seconds else 0
        avg_hr = activity.avg_heart_rate or 0

        # 훈련 효과 기반 부하 (가민 데이터 활용)
        if activity.training_effect_aerobic or activity.training_effect_anaerobic:
            aerobic = activity.training_effect_aerobic or 0
            anaerobic = activity.training_effect_anaerobic or 0
            return (aerobic + anaerobic) * duration_min / 10

        # 심박수 기반 TRIMP 계산 (대안)
        if avg_hr > 0:
            # 간단한 TRIMP 공식
            max_hr = 220 - 30  # 대략적인 최대 심박수 (30세 기준)
            hr_reserve_fraction = (avg_hr - 60) / (max_hr - 60)
            hr_reserve_fraction = max(0, min(1, hr_reserve_fraction))
            return duration_min * hr_reserve_fraction * 0.8

        # 거리 기반 대안
        distance_km = activity.distance_meters / 1000 if activity.distance_meters else 0
        return distance_km * 5  # km당 5 포인트

    def calculate_acwr(self) -> Optional[float]:
        """Acute:Chronic Workload Ratio 계산"""
        acute = self.calculate_acute_load(7)
        chronic = self.calculate_chronic_load(28)

        if chronic == 0:
            return None

        return round(acute / chronic, 2)

    def get_training_load_trend(self, days: int = 28) -> list[dict]:
        """훈련 부하 추이 데이터"""
        result = []
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        for i in range(days, -1, -1):
            date = today - timedelta(days=i)
            next_date = date + timedelta(days=1)

            # 해당 날짜의 활동
            day_activities = (
                self.db.query(Activity)
                .filter(Activity.start_time >= date, Activity.start_time < next_date)
                .all()
            )

            day_load = sum(self._calculate_activity_load(a) for a in day_activities)

            # 7일 평균 (급성 부하)
            week_ago = date - timedelta(days=6)
            week_activities = (
                self.db.query(Activity)
                .filter(Activity.start_time >= week_ago, Activity.start_time < next_date)
                .all()
            )
            acute_load = sum(self._calculate_activity_load(a) for a in week_activities) / 7

            # 28일 평균 (만성 부하)
            month_ago = date - timedelta(days=27)
            month_activities = (
                self.db.query(Activity)
                .filter(Activity.start_time >= month_ago, Activity.start_time < next_date)
                .all()
            )
            chronic_load = sum(self._calculate_activity_load(a) for a in month_activities) / 28

            result.append({
                "date": date.strftime("%Y-%m-%d"),
                "load": round(day_load, 1),
                "acute_load": round(acute_load, 1),
                "chronic_load": round(chronic_load, 1),
            })

        return result

    def get_training_zones_distribution(self, days: int = 7) -> dict:
        """훈련 강도 존 분포"""
        cutoff = datetime.now() - timedelta(days=days)
        activities = self.db.query(Activity).filter(Activity.start_time >= cutoff).all()

        zones = {
            "zone1_recovery": 0,  # < 60% max HR
            "zone2_easy": 0,  # 60-70% max HR
            "zone3_aerobic": 0,  # 70-80% max HR
            "zone4_threshold": 0,  # 80-90% max HR
            "zone5_vo2max": 0,  # > 90% max HR
        }

        total_duration = 0
        for activity in activities:
            duration = activity.duration_seconds or 0
            total_duration += duration
            avg_hr = activity.avg_heart_rate or 0

            if avg_hr == 0:
                zones["zone2_easy"] += duration
                continue

            # 대략적인 존 분류 (최대 심박수 190 기준)
            max_hr = 190
            hr_percent = avg_hr / max_hr * 100

            if hr_percent < 60:
                zones["zone1_recovery"] += duration
            elif hr_percent < 70:
                zones["zone2_easy"] += duration
            elif hr_percent < 80:
                zones["zone3_aerobic"] += duration
            elif hr_percent < 90:
                zones["zone4_threshold"] += duration
            else:
                zones["zone5_vo2max"] += duration

        # 퍼센트로 변환
        if total_duration > 0:
            return {k: round(v / total_duration * 100, 1) for k, v in zones.items()}

        return zones

    def get_fitness_trend(self) -> dict:
        """피트니스 추세 분석"""
        acwr = self.calculate_acwr()

        if acwr is None:
            status = "데이터 부족"
            recommendation = "더 많은 훈련 데이터가 필요합니다."
        elif acwr < 0.8:
            status = "언더트레이닝"
            recommendation = "훈련량을 점진적으로 늘려보세요."
        elif acwr <= 1.3:
            status = "최적"
            recommendation = "현재 훈련 부하가 적절합니다."
        elif acwr <= 1.5:
            status = "주의"
            recommendation = "훈련 부하가 높습니다. 회복에 신경 쓰세요."
        else:
            status = "위험"
            recommendation = "과훈련 위험이 있습니다. 휴식이 필요합니다."

        return {
            "acwr": acwr,
            "status": status,
            "recommendation": recommendation,
            "acute_load": self.calculate_acute_load(7),
            "chronic_load": self.calculate_chronic_load(28),
        }
