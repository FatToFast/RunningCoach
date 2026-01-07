from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
import json

from app.models.database import get_db, Activity, DailyStats, BodyComposition, TrainingStatus, Gear, PersonalRecord
from app.models.schemas import GarminLoginRequest, GarminAuthStatus, WeeklySummary
from app.services import get_garmin_client

router = APIRouter(prefix="/api/garmin", tags=["garmin"])


# ==================== 인증 ====================

@router.get("/auth/status", response_model=GarminAuthStatus)
async def get_auth_status():
    """가민 인증 상태 확인"""
    client = get_garmin_client()
    return GarminAuthStatus(
        is_authenticated=client.is_authenticated(),
        email=client.settings.garmin_email if client.is_authenticated() else None,
    )


@router.post("/auth/login", response_model=GarminAuthStatus)
async def login(request: GarminLoginRequest):
    """가민 로그인"""
    client = get_garmin_client()
    try:
        client.login(request.email, request.password)
        return GarminAuthStatus(is_authenticated=True, email=request.email)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/auth/logout")
async def logout():
    """가민 로그아웃"""
    client = get_garmin_client()
    client.logout()
    return {"message": "Logged out successfully"}


# ==================== 활동 ====================

@router.get("/activities")
async def get_activities(
    start: int = 0,
    limit: int = 20,
    sync: bool = False,
    db: Session = Depends(get_db),
):
    """활동 목록 조회"""
    client = get_garmin_client()

    if not client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Garmin")

    try:
        garmin_activities = client.get_activities(start, limit)

        if sync:
            for ga in garmin_activities:
                await _sync_activity_full(ga, client, db)

        activities = (
            db.query(Activity)
            .order_by(Activity.start_time.desc())
            .offset(start)
            .limit(limit)
            .all()
        )
        total = db.query(Activity).count()

        return {"activities": [_activity_to_dict(a) for a in activities], "total": total}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/activities/{activity_id}")
async def get_activity(activity_id: str, db: Session = Depends(get_db)):
    """활동 상세 조회 (Stryd 데이터 포함)"""
    activity = db.query(Activity).filter(Activity.garmin_activity_id == activity_id).first()

    if not activity:
        client = get_garmin_client()
        if not client.is_authenticated():
            raise HTTPException(status_code=401, detail="Not authenticated with Garmin")

        try:
            full_data = client.get_full_activity_data(activity_id)
            if full_data.get("details"):
                activity = await _sync_activity_full(full_data["details"], client, db)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Activity not found: {str(e)}")

    return _activity_to_dict(activity)


@router.post("/sync")
async def sync_activities(
    limit: int = 50,
    full: bool = True,
    db: Session = Depends(get_db)
):
    """가민 활동 동기화 (전체 데이터)"""
    client = get_garmin_client()

    if not client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Garmin")

    try:
        garmin_activities = client.get_activities(0, limit)
        synced_count = 0
        updated_count = 0

        for ga in garmin_activities:
            activity_id = str(ga.get("activityId"))
            existing = db.query(Activity).filter(Activity.garmin_activity_id == activity_id).first()

            if not existing:
                if full:
                    await _sync_activity_full(ga, client, db)
                else:
                    await _sync_activity_basic(ga, db)
                synced_count += 1
            elif full and not existing.avg_power:
                # 파워 데이터가 없으면 상세 정보 업데이트
                await _update_activity_details(existing, client, db)
                updated_count += 1

        return {
            "message": f"Synced {synced_count} new, updated {updated_count} activities",
            "total": len(garmin_activities)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 일일 데이터 ====================

@router.get("/daily/{day}")
async def get_daily_data(day: date, db: Session = Depends(get_db)):
    """일일 전체 데이터 조회 (수면, HRV, 스트레스 등)"""
    client = get_garmin_client()

    if not client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Garmin")

    try:
        # DB에서 조회
        daily = db.query(DailyStats).filter(DailyStats.date == day).first()

        if not daily:
            # 가민에서 가져와서 저장
            full_data = client.get_full_daily_data(day)
            daily = await _sync_daily_stats(day, full_data, db)

        return _daily_stats_to_dict(daily) if daily else {}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/daily")
async def sync_daily_data(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db)
):
    """일일 데이터 동기화"""
    client = get_garmin_client()

    if not client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Garmin")

    synced_count = 0
    today = date.today()

    for i in range(days):
        day = today - timedelta(days=i)
        existing = db.query(DailyStats).filter(DailyStats.date == day).first()

        if not existing:
            try:
                full_data = client.get_full_daily_data(day)
                await _sync_daily_stats(day, full_data, db)
                synced_count += 1
            except Exception:
                continue

    return {"message": f"Synced {synced_count} days of data"}


# ==================== 훈련 상태 ====================

@router.get("/stats/weekly")
async def get_weekly_stats():
    """주간 통계 조회"""
    client = get_garmin_client()

    if not client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Garmin")

    try:
        return client.get_weekly_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/training")
async def get_training_status():
    """훈련 상태 조회 (VO2max, 훈련 부하, 레이스 예측 등)"""
    client = get_garmin_client()

    if not client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Garmin")

    try:
        training_status = client.get_training_status()
        race_predictions = client.get_race_predictions()
        lactate = client.get_lactate_threshold()
        fitness_age = client.get_fitness_age()

        return {
            "training_status": training_status,
            "race_predictions": race_predictions,
            "lactate_threshold": lactate,
            "fitness_age": fitness_age,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/load")
async def get_training_load():
    """훈련 부하 데이터 조회"""
    client = get_garmin_client()

    if not client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Garmin")

    try:
        return client.get_training_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 체성분 ====================

@router.get("/body")
async def get_body_composition(
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
):
    """체성분 데이터 조회"""
    client = get_garmin_client()

    if not client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Garmin")

    end_date = end_date or date.today()
    start_date = start_date or (end_date - timedelta(days=30))

    try:
        return client.get_body_composition(start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 장비 ====================

@router.get("/gear")
async def get_gear(db: Session = Depends(get_db)):
    """장비 목록 조회"""
    client = get_garmin_client()

    if not client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Garmin")

    try:
        gear_list = client.get_gear()

        # DB에 저장
        for g in gear_list:
            gear_id = str(g.get("uuid", g.get("gearPk", "")))
            existing = db.query(Gear).filter(Gear.garmin_gear_id == gear_id).first()

            if not existing:
                gear = Gear(
                    garmin_gear_id=gear_id,
                    gear_type=g.get("gearTypeName", "unknown"),
                    name=g.get("displayName", ""),
                    brand=g.get("customMakeModel", ""),
                    total_distance_meters=g.get("totalDistance", 0),
                    total_activities=g.get("totalActivities", 0),
                    max_distance_meters=g.get("maximumMeters"),
                    is_active=not g.get("retired", False),
                    raw_data=json.dumps(g),
                )
                db.add(gear)

        db.commit()

        return gear_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 개인 기록 ====================

@router.get("/records")
async def get_personal_records():
    """개인 기록 조회"""
    client = get_garmin_client()

    if not client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Garmin")

    try:
        return client.get_personal_records()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 기기 ====================

@router.get("/devices")
async def get_devices():
    """연결된 기기 목록"""
    client = get_garmin_client()

    if not client.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Garmin")

    try:
        return client.get_devices()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 헬퍼 함수 ====================

async def _sync_activity_basic(garmin_data: dict, db: Session) -> Activity:
    """기본 활동 데이터 저장"""
    activity_id = str(garmin_data.get("activityId"))

    existing = db.query(Activity).filter(Activity.garmin_activity_id == activity_id).first()
    if existing:
        return existing

    start_time_str = garmin_data.get("startTimeLocal", "")
    try:
        start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
    except ValueError:
        start_time = datetime.now()

    distance = garmin_data.get("distance", 0) or 0
    duration = garmin_data.get("duration", 0) or 0
    avg_pace_seconds = duration / (distance / 1000) if distance > 0 and duration > 0 else None

    activity = Activity(
        garmin_activity_id=activity_id,
        activity_type=garmin_data.get("activityType", {}).get("typeKey", "unknown"),
        activity_type_id=garmin_data.get("activityType", {}).get("typeId"),
        start_time=start_time,
        duration_seconds=duration,
        distance_meters=distance,
        avg_heart_rate=garmin_data.get("averageHR"),
        max_heart_rate=garmin_data.get("maxHR"),
        avg_pace_seconds=avg_pace_seconds,
        calories=garmin_data.get("calories"),
        elevation_gain=garmin_data.get("elevationGain"),
        avg_cadence=garmin_data.get("averageRunningCadenceInStepsPerMinute"),
        training_effect_aerobic=garmin_data.get("aerobicTrainingEffect"),
        training_effect_anaerobic=garmin_data.get("anaerobicTrainingEffect"),
        vo2max=garmin_data.get("vO2MaxValue"),
        raw_data=json.dumps(garmin_data),
    )

    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


async def _sync_activity_full(garmin_data: dict, client, db: Session) -> Activity:
    """전체 활동 데이터 저장 (Stryd 포함)"""
    activity_id = str(garmin_data.get("activityId"))

    existing = db.query(Activity).filter(Activity.garmin_activity_id == activity_id).first()
    if existing:
        return existing

    # 상세 데이터 가져오기
    try:
        full_data = client.get_full_activity_data(activity_id)
        details = full_data.get("details", {}) or garmin_data
        splits = full_data.get("splits")
        hr_zones = full_data.get("hr_zones")
    except Exception:
        details = garmin_data
        splits = None
        hr_zones = None

    start_time_str = details.get("startTimeLocal", garmin_data.get("startTimeLocal", ""))
    try:
        start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
    except ValueError:
        start_time = datetime.now()

    distance = details.get("distance", garmin_data.get("distance", 0)) or 0
    duration = details.get("duration", garmin_data.get("duration", 0)) or 0
    avg_pace_seconds = duration / (distance / 1000) if distance > 0 and duration > 0 else None

    # 심박존 시간 추출
    hr_zone_times = {}
    if hr_zones and isinstance(hr_zones, list):
        for i, zone in enumerate(hr_zones[:5], 1):
            hr_zone_times[f"hr_zone_{i}_seconds"] = zone.get("secsInZone", 0)

    activity = Activity(
        garmin_activity_id=activity_id,
        activity_type=details.get("activityType", {}).get("typeKey", garmin_data.get("activityType", {}).get("typeKey", "unknown")),
        activity_type_id=details.get("activityType", {}).get("typeId"),
        start_time=start_time,
        duration_seconds=duration,
        elapsed_duration_seconds=details.get("elapsedDuration"),
        moving_duration_seconds=details.get("movingDuration"),
        distance_meters=distance,
        calories=details.get("calories", garmin_data.get("calories")),

        # 페이스 & 속도
        avg_pace_seconds=avg_pace_seconds,
        avg_speed=details.get("averageSpeed"),
        max_speed=details.get("maxSpeed"),

        # 심박수
        avg_heart_rate=details.get("averageHR", garmin_data.get("averageHR")),
        max_heart_rate=details.get("maxHR", garmin_data.get("maxHR")),
        min_heart_rate=details.get("minHR"),

        # 케이던스
        avg_cadence=details.get("averageBikeCadence"),
        max_cadence=details.get("maxBikeCadence"),
        avg_running_cadence=details.get("averageRunningCadenceInStepsPerMinute", garmin_data.get("averageRunningCadenceInStepsPerMinute")),
        max_running_cadence=details.get("maxRunningCadenceInStepsPerMinute"),
        total_strides=details.get("steps"),

        # 고도
        elevation_gain=details.get("elevationGain", garmin_data.get("elevationGain")),
        elevation_loss=details.get("elevationLoss"),
        min_elevation=details.get("minElevation"),
        max_elevation=details.get("maxElevation"),

        # Stryd 러닝 파워
        avg_power=details.get("avgPower") or details.get("averagePower"),
        max_power=details.get("maxPower"),
        normalized_power=details.get("normPower") or details.get("normalizedPower"),

        # Stryd 러닝 다이나믹스
        avg_ground_contact_time=details.get("avgGroundContactTime"),
        avg_ground_contact_balance=details.get("avgGroundContactBalance"),
        avg_vertical_oscillation=details.get("avgVerticalOscillation"),
        avg_vertical_ratio=details.get("avgVerticalRatio"),
        avg_stride_length=details.get("avgStrideLength"),
        avg_leg_spring_stiffness=details.get("avgLegSpringStiffness"),

        # 훈련 효과 & 부하
        training_effect_aerobic=details.get("aerobicTrainingEffect", garmin_data.get("aerobicTrainingEffect")),
        training_effect_anaerobic=details.get("anaerobicTrainingEffect", garmin_data.get("anaerobicTrainingEffect")),
        training_load=details.get("trainingLoad") or details.get("activityTrainingLoad"),
        training_stress_score=details.get("trainingStressScore"),
        intensity_factor=details.get("intensityFactor"),

        # 생리학적 메트릭
        vo2max=details.get("vO2MaxValue", garmin_data.get("vO2MaxValue")),
        lactate_threshold_hr=details.get("lactateThresholdHeartRate"),

        # 환경
        avg_temperature=details.get("avgTemperature") or details.get("minTemperature"),
        max_temperature=details.get("maxTemperature"),
        min_temperature=details.get("minTemperature"),

        # 위치
        start_latitude=details.get("startLatitude"),
        start_longitude=details.get("startLongitude"),
        end_latitude=details.get("endLatitude"),
        end_longitude=details.get("endLongitude"),

        # 장비
        device_id=str(details.get("deviceId")) if details.get("deviceId") else None,

        # 심박존 시간
        hr_zone_1_seconds=hr_zone_times.get("hr_zone_1_seconds"),
        hr_zone_2_seconds=hr_zone_times.get("hr_zone_2_seconds"),
        hr_zone_3_seconds=hr_zone_times.get("hr_zone_3_seconds"),
        hr_zone_4_seconds=hr_zone_times.get("hr_zone_4_seconds"),
        hr_zone_5_seconds=hr_zone_times.get("hr_zone_5_seconds"),

        # 원본 데이터
        raw_data=json.dumps(details),
        splits_data=json.dumps(splits) if splits else None,
    )

    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


async def _update_activity_details(activity: Activity, client, db: Session):
    """기존 활동에 상세 정보 업데이트"""
    try:
        full_data = client.get_full_activity_data(activity.garmin_activity_id)
        details = full_data.get("details", {})

        if details:
            activity.avg_power = details.get("avgPower") or details.get("averagePower")
            activity.max_power = details.get("maxPower")
            activity.normalized_power = details.get("normPower")
            activity.avg_ground_contact_time = details.get("avgGroundContactTime")
            activity.avg_vertical_oscillation = details.get("avgVerticalOscillation")
            activity.avg_stride_length = details.get("avgStrideLength")
            activity.training_load = details.get("trainingLoad")

            if full_data.get("splits"):
                activity.splits_data = json.dumps(full_data["splits"])

            db.commit()
    except Exception:
        pass


async def _sync_daily_stats(day: date, full_data: dict, db: Session) -> DailyStats:
    """일일 통계 저장"""
    existing = db.query(DailyStats).filter(DailyStats.date == day).first()
    if existing:
        return existing

    summary = full_data.get("summary", {}) or {}
    heart_rate = full_data.get("heart_rate", {}) or {}
    resting_hr = full_data.get("resting_hr", {}) or {}
    hrv = full_data.get("hrv", {}) or {}
    sleep = full_data.get("sleep", {}) or {}
    stress = full_data.get("stress", {}) or {}
    body_battery = full_data.get("body_battery", {}) or {}
    respiration = full_data.get("respiration", {}) or {}
    spo2 = full_data.get("spo2", {}) or {}
    training_readiness = full_data.get("training_readiness", {}) or {}

    daily = DailyStats(
        date=day,

        # 걸음 수
        total_steps=summary.get("totalSteps"),
        daily_step_goal=summary.get("dailyStepGoal"),
        total_distance_meters=summary.get("totalDistanceMeters"),

        # 심박수
        resting_heart_rate=resting_hr.get("restingHeartRate") or summary.get("restingHeartRate"),
        min_heart_rate=heart_rate.get("minHeartRate") or summary.get("minHeartRate"),
        max_heart_rate=heart_rate.get("maxHeartRate") or summary.get("maxHeartRate"),

        # HRV
        hrv_weekly_avg=hrv.get("weeklyAvg"),
        hrv_last_night=hrv.get("lastNightAvg") or hrv.get("hrvValue"),
        hrv_status=hrv.get("status"),
        hrv_baseline_low=hrv.get("baselineLow"),
        hrv_baseline_high=hrv.get("baselineHigh"),

        # 스트레스
        avg_stress_level=stress.get("avgStressLevel") or summary.get("averageStressLevel"),
        max_stress_level=stress.get("maxStressLevel") or summary.get("maxStressLevel"),

        # Body Battery
        body_battery_high=body_battery.get("bodyBatteryHigh") or summary.get("bodyBatteryHighestValue"),
        body_battery_low=body_battery.get("bodyBatteryLow") or summary.get("bodyBatteryLowestValue"),
        body_battery_charged=body_battery.get("bodyBatteryChargedValue"),
        body_battery_drained=body_battery.get("bodyBatteryDrainedValue"),

        # 수면
        sleep_duration_seconds=sleep.get("sleepTimeSeconds"),
        deep_sleep_seconds=sleep.get("deepSleepSeconds"),
        light_sleep_seconds=sleep.get("lightSleepSeconds"),
        rem_sleep_seconds=sleep.get("remSleepSeconds"),
        awake_seconds=sleep.get("awakeSleepSeconds"),
        sleep_score=sleep.get("sleepScoreValue") or sleep.get("overallScore", {}).get("value"),
        avg_spo2=sleep.get("avgOxygenSaturation"),
        avg_respiration_rate=sleep.get("avgRespirationValue"),

        # 칼로리
        total_calories=summary.get("totalKilocalories"),
        active_calories=summary.get("activeKilocalories"),
        bmr_calories=summary.get("bmrKilocalories"),

        # 활동
        floors_climbed=summary.get("floorsAscended"),
        floors_descended=summary.get("floorsDescended"),
        intensity_minutes_moderate=summary.get("moderateIntensityMinutes"),
        intensity_minutes_vigorous=summary.get("vigorousIntensityMinutes"),

        # 훈련 준비도
        training_readiness_score=training_readiness.get("score"),
        training_readiness_status=training_readiness.get("level"),

        # 호흡
        avg_respiration=respiration.get("avgWakingRespirationValue"),
        min_respiration=respiration.get("lowestRespirationValue"),
        max_respiration=respiration.get("highestRespirationValue"),

        # SpO2
        avg_spo2_value=spo2.get("avgValue") or spo2.get("averageSpO2"),
        min_spo2_value=spo2.get("minValue") or spo2.get("lowestSpO2"),

        raw_data=json.dumps(full_data),
    )

    db.add(daily)
    db.commit()
    db.refresh(daily)
    return daily


def _activity_to_dict(activity: Activity) -> dict:
    """Activity 객체를 딕셔너리로 변환"""
    return {
        "id": activity.id,
        "garmin_activity_id": activity.garmin_activity_id,
        "activity_type": activity.activity_type,
        "start_time": activity.start_time.isoformat() if activity.start_time else None,
        "duration_seconds": activity.duration_seconds,
        "distance_meters": activity.distance_meters,
        "calories": activity.calories,
        "avg_pace_seconds": activity.avg_pace_seconds,
        "avg_speed": activity.avg_speed,
        "avg_heart_rate": activity.avg_heart_rate,
        "max_heart_rate": activity.max_heart_rate,
        "avg_cadence": activity.avg_running_cadence or activity.avg_cadence,
        "elevation_gain": activity.elevation_gain,
        "elevation_loss": activity.elevation_loss,
        # Stryd
        "avg_power": activity.avg_power,
        "max_power": activity.max_power,
        "normalized_power": activity.normalized_power,
        "avg_ground_contact_time": activity.avg_ground_contact_time,
        "avg_vertical_oscillation": activity.avg_vertical_oscillation,
        "avg_stride_length": activity.avg_stride_length,
        # 훈련 효과
        "training_effect_aerobic": activity.training_effect_aerobic,
        "training_effect_anaerobic": activity.training_effect_anaerobic,
        "training_load": activity.training_load,
        "vo2max": activity.vo2max,
        # 심박존
        "hr_zones": {
            "zone1": activity.hr_zone_1_seconds,
            "zone2": activity.hr_zone_2_seconds,
            "zone3": activity.hr_zone_3_seconds,
            "zone4": activity.hr_zone_4_seconds,
            "zone5": activity.hr_zone_5_seconds,
        },
        "created_at": activity.created_at.isoformat() if activity.created_at else None,
    }


def _daily_stats_to_dict(daily: DailyStats) -> dict:
    """DailyStats 객체를 딕셔너리로 변환"""
    return {
        "date": daily.date.isoformat() if daily.date else None,
        "steps": {
            "total": daily.total_steps,
            "goal": daily.daily_step_goal,
            "distance_meters": daily.total_distance_meters,
        },
        "heart_rate": {
            "resting": daily.resting_heart_rate,
            "min": daily.min_heart_rate,
            "max": daily.max_heart_rate,
        },
        "hrv": {
            "weekly_avg": daily.hrv_weekly_avg,
            "last_night": daily.hrv_last_night,
            "status": daily.hrv_status,
            "baseline_low": daily.hrv_baseline_low,
            "baseline_high": daily.hrv_baseline_high,
        },
        "stress": {
            "avg": daily.avg_stress_level,
            "max": daily.max_stress_level,
        },
        "body_battery": {
            "high": daily.body_battery_high,
            "low": daily.body_battery_low,
            "charged": daily.body_battery_charged,
            "drained": daily.body_battery_drained,
        },
        "sleep": {
            "duration_seconds": daily.sleep_duration_seconds,
            "deep_seconds": daily.deep_sleep_seconds,
            "light_seconds": daily.light_sleep_seconds,
            "rem_seconds": daily.rem_sleep_seconds,
            "awake_seconds": daily.awake_seconds,
            "score": daily.sleep_score,
            "avg_spo2": daily.avg_spo2,
            "avg_respiration": daily.avg_respiration_rate,
        },
        "calories": {
            "total": daily.total_calories,
            "active": daily.active_calories,
            "bmr": daily.bmr_calories,
        },
        "activity": {
            "floors_climbed": daily.floors_climbed,
            "intensity_moderate": daily.intensity_minutes_moderate,
            "intensity_vigorous": daily.intensity_minutes_vigorous,
        },
        "training_readiness": {
            "score": daily.training_readiness_score,
            "status": daily.training_readiness_status,
        },
        "respiration": {
            "avg": daily.avg_respiration,
            "min": daily.min_respiration,
            "max": daily.max_respiration,
        },
        "spo2": {
            "avg": daily.avg_spo2_value,
            "min": daily.min_spo2_value,
        },
    }
