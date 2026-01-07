from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Activity(Base):
    """활동 데이터 - Runalyze/Stryd 호환"""
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    garmin_activity_id = Column(String, unique=True, index=True)
    activity_type = Column(String)
    activity_type_id = Column(Integer, nullable=True)
    start_time = Column(DateTime)
    start_time_gmt = Column(DateTime, nullable=True)

    # 기본 메트릭
    duration_seconds = Column(Float)
    elapsed_duration_seconds = Column(Float, nullable=True)
    moving_duration_seconds = Column(Float, nullable=True)
    distance_meters = Column(Float)
    calories = Column(Integer, nullable=True)

    # 페이스 & 속도
    avg_pace_seconds = Column(Float, nullable=True)
    max_pace_seconds = Column(Float, nullable=True)
    avg_speed = Column(Float, nullable=True)  # m/s
    max_speed = Column(Float, nullable=True)

    # 심박수
    avg_heart_rate = Column(Integer, nullable=True)
    max_heart_rate = Column(Integer, nullable=True)
    min_heart_rate = Column(Integer, nullable=True)

    # 케이던스
    avg_cadence = Column(Float, nullable=True)
    max_cadence = Column(Float, nullable=True)
    avg_running_cadence = Column(Float, nullable=True)
    max_running_cadence = Column(Float, nullable=True)
    total_strides = Column(Integer, nullable=True)

    # 고도
    elevation_gain = Column(Float, nullable=True)
    elevation_loss = Column(Float, nullable=True)
    min_elevation = Column(Float, nullable=True)
    max_elevation = Column(Float, nullable=True)

    # Stryd 러닝 파워
    avg_power = Column(Float, nullable=True)  # watts
    max_power = Column(Float, nullable=True)
    normalized_power = Column(Float, nullable=True)
    avg_power_20min = Column(Float, nullable=True)  # FTP 추정용

    # Stryd 러닝 다이나믹스
    avg_ground_contact_time = Column(Float, nullable=True)  # ms
    avg_ground_contact_balance = Column(Float, nullable=True)  # %
    avg_vertical_oscillation = Column(Float, nullable=True)  # cm
    avg_vertical_ratio = Column(Float, nullable=True)  # %
    avg_stride_length = Column(Float, nullable=True)  # m
    avg_leg_spring_stiffness = Column(Float, nullable=True)  # kN/m

    # Stryd 추가 메트릭
    form_power = Column(Float, nullable=True)  # watts
    air_power = Column(Float, nullable=True)  # watts (공기저항)

    # 훈련 효과 & 부하
    training_effect_aerobic = Column(Float, nullable=True)
    training_effect_anaerobic = Column(Float, nullable=True)
    training_load = Column(Float, nullable=True)
    training_stress_score = Column(Float, nullable=True)
    intensity_factor = Column(Float, nullable=True)

    # 생리학적 메트릭
    vo2max = Column(Float, nullable=True)
    lactate_threshold_hr = Column(Integer, nullable=True)
    lactate_threshold_speed = Column(Float, nullable=True)

    # 환경
    avg_temperature = Column(Float, nullable=True)  # celsius
    max_temperature = Column(Float, nullable=True)
    min_temperature = Column(Float, nullable=True)

    # 위치
    start_latitude = Column(Float, nullable=True)
    start_longitude = Column(Float, nullable=True)
    end_latitude = Column(Float, nullable=True)
    end_longitude = Column(Float, nullable=True)

    # 장비
    device_id = Column(String, nullable=True)

    # 심박존 시간 (초)
    hr_zone_1_seconds = Column(Float, nullable=True)
    hr_zone_2_seconds = Column(Float, nullable=True)
    hr_zone_3_seconds = Column(Float, nullable=True)
    hr_zone_4_seconds = Column(Float, nullable=True)
    hr_zone_5_seconds = Column(Float, nullable=True)

    # 파워존 시간 (초) - Stryd
    power_zone_1_seconds = Column(Float, nullable=True)
    power_zone_2_seconds = Column(Float, nullable=True)
    power_zone_3_seconds = Column(Float, nullable=True)
    power_zone_4_seconds = Column(Float, nullable=True)
    power_zone_5_seconds = Column(Float, nullable=True)

    # 원본 데이터
    raw_data = Column(Text, nullable=True)
    splits_data = Column(Text, nullable=True)  # JSON

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DailyStats(Base):
    """일일 통계 - 수면, 스트레스, HRV, Body Battery 등"""
    __tablename__ = "daily_stats"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, index=True)

    # 걸음 수
    total_steps = Column(Integer, nullable=True)
    daily_step_goal = Column(Integer, nullable=True)
    total_distance_meters = Column(Float, nullable=True)

    # 심박수
    resting_heart_rate = Column(Integer, nullable=True)
    min_heart_rate = Column(Integer, nullable=True)
    max_heart_rate = Column(Integer, nullable=True)
    avg_heart_rate = Column(Integer, nullable=True)

    # HRV (Heart Rate Variability)
    hrv_weekly_avg = Column(Float, nullable=True)
    hrv_last_night = Column(Float, nullable=True)
    hrv_status = Column(String, nullable=True)  # balanced, low, high
    hrv_baseline_low = Column(Float, nullable=True)
    hrv_baseline_high = Column(Float, nullable=True)

    # 스트레스
    avg_stress_level = Column(Integer, nullable=True)
    max_stress_level = Column(Integer, nullable=True)
    stress_duration_seconds = Column(Integer, nullable=True)
    rest_stress_duration_seconds = Column(Integer, nullable=True)

    # Body Battery
    body_battery_high = Column(Integer, nullable=True)
    body_battery_low = Column(Integer, nullable=True)
    body_battery_charged = Column(Integer, nullable=True)
    body_battery_drained = Column(Integer, nullable=True)

    # 수면
    sleep_start_time = Column(DateTime, nullable=True)
    sleep_end_time = Column(DateTime, nullable=True)
    sleep_duration_seconds = Column(Integer, nullable=True)
    deep_sleep_seconds = Column(Integer, nullable=True)
    light_sleep_seconds = Column(Integer, nullable=True)
    rem_sleep_seconds = Column(Integer, nullable=True)
    awake_seconds = Column(Integer, nullable=True)
    sleep_score = Column(Integer, nullable=True)
    sleep_quality = Column(String, nullable=True)
    avg_sleep_stress = Column(Float, nullable=True)
    avg_spo2 = Column(Float, nullable=True)
    avg_respiration_rate = Column(Float, nullable=True)

    # 칼로리
    total_calories = Column(Integer, nullable=True)
    active_calories = Column(Integer, nullable=True)
    bmr_calories = Column(Integer, nullable=True)

    # 활동
    floors_climbed = Column(Integer, nullable=True)
    floors_descended = Column(Integer, nullable=True)
    intensity_minutes_moderate = Column(Integer, nullable=True)
    intensity_minutes_vigorous = Column(Integer, nullable=True)

    # 훈련 상태
    training_readiness_score = Column(Integer, nullable=True)
    training_readiness_status = Column(String, nullable=True)

    # 호흡
    avg_respiration = Column(Float, nullable=True)
    min_respiration = Column(Float, nullable=True)
    max_respiration = Column(Float, nullable=True)

    # SpO2
    avg_spo2_value = Column(Float, nullable=True)
    min_spo2_value = Column(Float, nullable=True)

    # 원본 데이터
    raw_data = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BodyComposition(Base):
    """체성분 데이터"""
    __tablename__ = "body_composition"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, index=True)
    timestamp = Column(DateTime, nullable=True)

    weight = Column(Float, nullable=True)  # kg
    bmi = Column(Float, nullable=True)
    body_fat_percentage = Column(Float, nullable=True)
    body_water_percentage = Column(Float, nullable=True)
    bone_mass = Column(Float, nullable=True)  # kg
    muscle_mass = Column(Float, nullable=True)  # kg
    visceral_fat = Column(Float, nullable=True)
    metabolic_age = Column(Integer, nullable=True)

    raw_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TrainingStatus(Base):
    """훈련 상태 이력"""
    __tablename__ = "training_status"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, index=True)

    # VO2max
    vo2max_running = Column(Float, nullable=True)
    vo2max_cycling = Column(Float, nullable=True)

    # 훈련 부하
    training_load_7day = Column(Float, nullable=True)
    training_load_28day = Column(Float, nullable=True)
    training_load_balance = Column(String, nullable=True)  # optimal, high, low

    # 회복
    recovery_time_hours = Column(Integer, nullable=True)
    recovery_heart_rate = Column(Integer, nullable=True)

    # Lactate Threshold
    lactate_threshold_hr = Column(Integer, nullable=True)
    lactate_threshold_speed = Column(Float, nullable=True)  # m/s
    lactate_threshold_power = Column(Float, nullable=True)  # watts

    # 레이스 예측
    race_prediction_5k = Column(String, nullable=True)
    race_prediction_10k = Column(String, nullable=True)
    race_prediction_half = Column(String, nullable=True)
    race_prediction_marathon = Column(String, nullable=True)

    # 지구력 점수
    endurance_score = Column(Integer, nullable=True)

    # 피트니스 연령
    fitness_age = Column(Integer, nullable=True)

    raw_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PersonalRecord(Base):
    """개인 기록"""
    __tablename__ = "personal_records"

    id = Column(Integer, primary_key=True, index=True)
    activity_id = Column(String, nullable=True)
    activity_type = Column(String)
    record_type = Column(String)  # distance, time, pace, etc.

    value = Column(Float)
    value_unit = Column(String)  # meters, seconds, etc.

    achieved_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)


class Gear(Base):
    """장비 정보"""
    __tablename__ = "gear"

    id = Column(Integer, primary_key=True, index=True)
    garmin_gear_id = Column(String, unique=True, index=True)

    gear_type = Column(String)  # shoes, bike, etc.
    name = Column(String)
    brand = Column(String, nullable=True)
    model = Column(String, nullable=True)

    total_distance_meters = Column(Float, default=0)
    total_activities = Column(Integer, default=0)
    max_distance_meters = Column(Float, nullable=True)  # 최대 수명

    is_active = Column(Boolean, default=True)
    date_begin = Column(Date, nullable=True)
    date_end = Column(Date, nullable=True)

    raw_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TrainingSchedule(Base):
    __tablename__ = "training_schedules"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(Text, nullable=True)
    start_date = Column(DateTime)
    end_date = Column(DateTime, nullable=True)
    goal = Column(String, nullable=True)
    is_synced_to_garmin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    workouts = relationship("Workout", back_populates="schedule", cascade="all, delete-orphan")


class Workout(Base):
    __tablename__ = "workouts"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("training_schedules.id"))
    date = Column(DateTime)
    workout_type = Column(String)
    title = Column(String)
    description = Column(Text, nullable=True)
    target_distance_meters = Column(Float, nullable=True)
    target_duration_seconds = Column(Float, nullable=True)
    target_pace = Column(String, nullable=True)
    target_power = Column(Float, nullable=True)  # Stryd power target
    intervals = Column(Text, nullable=True)
    is_completed = Column(Boolean, default=False)
    garmin_workout_id = Column(String, nullable=True)

    schedule = relationship("TrainingSchedule", back_populates="workouts")


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
