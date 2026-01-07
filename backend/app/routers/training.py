from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
import json

from app.models import (
    get_db,
    TrainingSchedule,
    Workout,
    ChatHistory,
    ChatRequest,
    ChatResponse,
    ScheduleCreate,
    ScheduleResponse,
    WorkoutBase,
)
from app.services import get_training_ai, get_garmin_client

router = APIRouter(prefix="/api/training", tags=["training"])


@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest, db: Session = Depends(get_db)):
    """AI 코치와 대화"""
    ai = get_training_ai()

    # 대화 기록 저장
    user_msg = ChatHistory(role="user", content=request.message)
    db.add(user_msg)

    result = ai.chat(request.message, include_garmin_context=request.include_garmin_context)

    # AI 응답 저장
    ai_msg = ChatHistory(role="assistant", content=result["response"])
    db.add(ai_msg)
    db.commit()

    return ChatResponse(
        response=result["response"],
        suggested_schedule=result.get("suggested_schedule"),
    )


@router.get("/chat/history")
async def get_chat_history(limit: int = 50, db: Session = Depends(get_db)):
    """대화 기록 조회"""
    messages = (
        db.query(ChatHistory)
        .order_by(ChatHistory.created_at.desc())
        .limit(limit)
        .all()
    )
    return [{"role": m.role, "content": m.content, "created_at": m.created_at} for m in reversed(messages)]


@router.delete("/chat/history")
async def clear_chat_history(db: Session = Depends(get_db)):
    """대화 기록 삭제"""
    db.query(ChatHistory).delete()
    db.commit()

    ai = get_training_ai()
    ai.clear_history()

    return {"message": "Chat history cleared"}


@router.get("/schedules", response_model=list[ScheduleResponse])
async def get_schedules(db: Session = Depends(get_db)):
    """저장된 스케줄 목록 조회"""
    schedules = db.query(TrainingSchedule).order_by(TrainingSchedule.created_at.desc()).all()
    return [ScheduleResponse.model_validate(s) for s in schedules]


@router.post("/schedules", response_model=ScheduleResponse)
async def create_schedule(schedule: ScheduleCreate, db: Session = Depends(get_db)):
    """훈련 스케줄 저장"""
    db_schedule = TrainingSchedule(
        title=schedule.title,
        description=schedule.description,
        start_date=schedule.start_date,
        end_date=schedule.end_date,
        goal=schedule.goal,
    )
    db.add(db_schedule)
    db.flush()

    # 워크아웃 추가
    for workout_data in schedule.workouts:
        workout = Workout(
            schedule_id=db_schedule.id,
            date=workout_data.date,
            workout_type=workout_data.workout_type,
            title=workout_data.title,
            description=workout_data.description,
            target_distance_meters=workout_data.target_distance_meters,
            target_duration_seconds=workout_data.target_duration_seconds,
            target_pace=workout_data.target_pace,
            intervals=workout_data.intervals,
        )
        db.add(workout)

    db.commit()
    db.refresh(db_schedule)

    return ScheduleResponse.model_validate(db_schedule)


@router.get("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """스케줄 상세 조회"""
    schedule = db.query(TrainingSchedule).filter(TrainingSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return ScheduleResponse.model_validate(schedule)


@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(schedule_id: int, schedule: ScheduleCreate, db: Session = Depends(get_db)):
    """스케줄 수정"""
    db_schedule = db.query(TrainingSchedule).filter(TrainingSchedule.id == schedule_id).first()
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    db_schedule.title = schedule.title
    db_schedule.description = schedule.description
    db_schedule.start_date = schedule.start_date
    db_schedule.end_date = schedule.end_date
    db_schedule.goal = schedule.goal

    # 기존 워크아웃 삭제 후 새로 추가
    db.query(Workout).filter(Workout.schedule_id == schedule_id).delete()

    for workout_data in schedule.workouts:
        workout = Workout(
            schedule_id=db_schedule.id,
            date=workout_data.date,
            workout_type=workout_data.workout_type,
            title=workout_data.title,
            description=workout_data.description,
            target_distance_meters=workout_data.target_distance_meters,
            target_duration_seconds=workout_data.target_duration_seconds,
            target_pace=workout_data.target_pace,
            intervals=workout_data.intervals,
        )
        db.add(workout)

    db.commit()
    db.refresh(db_schedule)

    return ScheduleResponse.model_validate(db_schedule)


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """스케줄 삭제"""
    schedule = db.query(TrainingSchedule).filter(TrainingSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    db.delete(schedule)
    db.commit()

    return {"message": "Schedule deleted"}


@router.post("/schedules/{schedule_id}/sync-garmin")
async def sync_schedule_to_garmin(schedule_id: int, db: Session = Depends(get_db)):
    """스케줄을 가민으로 전송"""
    garmin = get_garmin_client()
    if not garmin.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated with Garmin")

    schedule = db.query(TrainingSchedule).filter(TrainingSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    synced_workouts = []
    errors = []

    for workout in schedule.workouts:
        if workout.workout_type == "rest":
            continue  # 휴식일은 스킵

        try:
            # 가민 워크아웃 형식으로 변환
            garmin_workout = _convert_to_garmin_format(workout)

            # 워크아웃 생성
            result = garmin.create_workout(garmin_workout)
            workout_id = result.get("workoutId")

            if workout_id:
                # 스케줄에 추가
                garmin.schedule_workout(workout_id, workout.date)
                workout.garmin_workout_id = str(workout_id)
                synced_workouts.append(workout.title)

        except Exception as e:
            errors.append(f"{workout.title}: {str(e)}")

    schedule.is_synced_to_garmin = len(errors) == 0
    db.commit()

    return {
        "synced": synced_workouts,
        "errors": errors,
        "message": f"Synced {len(synced_workouts)} workouts to Garmin",
    }


def _convert_to_garmin_format(workout: Workout) -> dict:
    """워크아웃을 가민 형식으로 변환"""
    # 기본 구조
    garmin_workout = {
        "workoutName": workout.title,
        "description": workout.description or "",
        "sportType": {"sportTypeId": 1, "sportTypeKey": "running"},
        "workoutSegments": [],
    }

    # 워크아웃 타입에 따른 세그먼트 구성
    if workout.workout_type == "easy" or workout.workout_type == "recovery":
        # 단순 러닝
        segment = {
            "segmentOrder": 1,
            "sportType": {"sportTypeId": 1, "sportTypeKey": "running"},
            "workoutSteps": [
                {
                    "stepOrder": 1,
                    "intensity": "WARMUP" if workout.workout_type == "easy" else "RECOVERY",
                    "durationType": "DISTANCE" if workout.target_distance_meters else "TIME",
                    "durationValue": workout.target_distance_meters or workout.target_duration_seconds,
                }
            ],
        }
        garmin_workout["workoutSegments"].append(segment)

    elif workout.workout_type == "interval" and workout.intervals:
        # 인터벌 훈련
        intervals = json.loads(workout.intervals) if isinstance(workout.intervals, str) else workout.intervals

        steps = []
        step_order = 1

        # 워밍업
        if intervals.get("warmup_meters"):
            steps.append({
                "stepOrder": step_order,
                "intensity": "WARMUP",
                "durationType": "DISTANCE",
                "durationValue": intervals["warmup_meters"],
            })
            step_order += 1

        # 인터벌 반복
        for repeat in intervals.get("repeats", []):
            for _ in range(repeat.get("reps", 1)):
                # 고강도
                steps.append({
                    "stepOrder": step_order,
                    "intensity": "INTERVAL",
                    "durationType": "DISTANCE",
                    "durationValue": repeat.get("distance_meters", 400),
                })
                step_order += 1

                # 휴식
                steps.append({
                    "stepOrder": step_order,
                    "intensity": "REST",
                    "durationType": "TIME",
                    "durationValue": repeat.get("rest_seconds", 60),
                })
                step_order += 1

        # 쿨다운
        if intervals.get("cooldown_meters"):
            steps.append({
                "stepOrder": step_order,
                "intensity": "COOLDOWN",
                "durationType": "DISTANCE",
                "durationValue": intervals["cooldown_meters"],
            })

        segment = {
            "segmentOrder": 1,
            "sportType": {"sportTypeId": 1, "sportTypeKey": "running"},
            "workoutSteps": steps,
        }
        garmin_workout["workoutSegments"].append(segment)

    else:
        # 템포, 롱런 등 기본 형식
        segment = {
            "segmentOrder": 1,
            "sportType": {"sportTypeId": 1, "sportTypeKey": "running"},
            "workoutSteps": [
                {
                    "stepOrder": 1,
                    "intensity": "ACTIVE",
                    "durationType": "DISTANCE" if workout.target_distance_meters else "TIME",
                    "durationValue": workout.target_distance_meters or workout.target_duration_seconds,
                }
            ],
        }
        garmin_workout["workoutSegments"].append(segment)

    return garmin_workout
