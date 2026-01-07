from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.models import get_db, Activity, DashboardSummary, WeeklySummary, ActivityResponse, TrainingLoadData
from app.services import get_garmin_client, TrainingAnalyzer

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """대시보드 요약 데이터"""
    garmin = get_garmin_client()

    # 주간 통계
    week_ago = datetime.now() - timedelta(days=7)
    weekly_activities = (
        db.query(Activity)
        .filter(Activity.start_time >= week_ago)
        .all()
    )

    total_distance = sum(a.distance_meters or 0 for a in weekly_activities)
    total_duration = sum(a.duration_seconds or 0 for a in weekly_activities)
    total_calories = sum(a.calories or 0 for a in weekly_activities)

    heart_rates = [a.avg_heart_rate for a in weekly_activities if a.avg_heart_rate]
    avg_hr = sum(heart_rates) / len(heart_rates) if heart_rates else None

    # 평균 페이스 계산
    running_activities = [a for a in weekly_activities if a.activity_type == "running"]
    avg_pace = None
    if running_activities:
        total_run_dist = sum(a.distance_meters or 0 for a in running_activities)
        total_run_dur = sum(a.duration_seconds or 0 for a in running_activities)
        if total_run_dist > 0:
            pace_sec = total_run_dur / (total_run_dist / 1000)
            avg_pace = f"{int(pace_sec // 60)}:{int(pace_sec % 60):02d}"

    weekly_summary = WeeklySummary(
        total_distance_km=round(total_distance / 1000, 2),
        total_duration_minutes=round(total_duration / 60, 1),
        total_activities=len(weekly_activities),
        avg_pace=avg_pace,
        avg_heart_rate=round(avg_hr, 1) if avg_hr else None,
        total_calories=total_calories,
    )

    # 현재 VO2max (최근 활동에서)
    recent_with_vo2 = (
        db.query(Activity)
        .filter(Activity.vo2max.isnot(None))
        .order_by(Activity.start_time.desc())
        .first()
    )
    current_vo2max = recent_with_vo2.vo2max if recent_with_vo2 else None

    # 훈련 상태
    training_status = None
    recovery_time = None
    if garmin.is_authenticated():
        try:
            status = garmin.get_training_status()
            if status.get("vo2max"):
                current_vo2max = status["vo2max"]
        except Exception:
            pass

    # 최근 활동
    recent_activities = (
        db.query(Activity)
        .order_by(Activity.start_time.desc())
        .limit(5)
        .all()
    )

    return DashboardSummary(
        weekly_summary=weekly_summary,
        current_vo2max=current_vo2max,
        recovery_time_hours=recovery_time,
        training_status=training_status,
        recent_activities=[ActivityResponse.model_validate(a) for a in recent_activities],
    )


@router.get("/charts/load")
async def get_training_load_chart(days: int = 28, db: Session = Depends(get_db)):
    """훈련 부하 차트 데이터"""
    analyzer = TrainingAnalyzer(db)
    load_data = analyzer.get_training_load_trend(days)

    return {
        "data": load_data,
        "fitness_status": analyzer.get_fitness_trend(),
    }


@router.get("/charts/pace")
async def get_pace_chart(days: int = 28, db: Session = Depends(get_db)):
    """페이스 추이 차트 데이터"""
    cutoff = datetime.now() - timedelta(days=days)
    activities = (
        db.query(Activity)
        .filter(Activity.start_time >= cutoff, Activity.activity_type == "running")
        .order_by(Activity.start_time)
        .all()
    )

    data = []
    for a in activities:
        if a.avg_pace_seconds and a.distance_meters and a.distance_meters >= 1000:
            pace_min = a.avg_pace_seconds / 60
            data.append({
                "date": a.start_time.strftime("%Y-%m-%d"),
                "pace_min_per_km": round(pace_min, 2),
                "distance_km": round(a.distance_meters / 1000, 2),
                "avg_hr": a.avg_heart_rate,
            })

    return {"data": data}


@router.get("/charts/distance")
async def get_distance_chart(weeks: int = 8, db: Session = Depends(get_db)):
    """주간 거리 추이 차트"""
    result = []
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for week in range(weeks, 0, -1):
        week_end = today - timedelta(days=(week - 1) * 7)
        week_start = week_end - timedelta(days=7)

        activities = (
            db.query(Activity)
            .filter(Activity.start_time >= week_start, Activity.start_time < week_end)
            .all()
        )

        total_distance = sum(a.distance_meters or 0 for a in activities)
        total_duration = sum(a.duration_seconds or 0 for a in activities)

        result.append({
            "week": week_start.strftime("%m/%d"),
            "distance_km": round(total_distance / 1000, 2),
            "duration_hours": round(total_duration / 3600, 2),
            "activities": len(activities),
        })

    return {"data": result}


@router.get("/charts/zones")
async def get_zone_distribution(days: int = 7, db: Session = Depends(get_db)):
    """훈련 존 분포"""
    analyzer = TrainingAnalyzer(db)
    zones = analyzer.get_training_zones_distribution(days)

    return {
        "zones": zones,
        "labels": {
            "zone1_recovery": "Zone 1 (회복)",
            "zone2_easy": "Zone 2 (이지)",
            "zone3_aerobic": "Zone 3 (유산소)",
            "zone4_threshold": "Zone 4 (역치)",
            "zone5_vo2max": "Zone 5 (VO2max)",
        },
    }
