from pydantic import BaseModel
from datetime import datetime
from typing import Optional


# Activity Schemas
class ActivityBase(BaseModel):
    garmin_activity_id: str
    activity_type: str
    start_time: datetime
    duration_seconds: float
    distance_meters: float
    avg_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None
    avg_pace_seconds: Optional[float] = None
    calories: Optional[int] = None
    elevation_gain: Optional[float] = None
    avg_cadence: Optional[float] = None
    training_effect_aerobic: Optional[float] = None
    training_effect_anaerobic: Optional[float] = None
    vo2max: Optional[float] = None


class ActivityResponse(ActivityBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityListResponse(BaseModel):
    activities: list[ActivityResponse]
    total: int


# Training Schedule Schemas
class WorkoutBase(BaseModel):
    date: datetime
    workout_type: str
    title: str
    description: Optional[str] = None
    target_distance_meters: Optional[float] = None
    target_duration_seconds: Optional[float] = None
    target_pace: Optional[str] = None
    intervals: Optional[str] = None


class WorkoutResponse(WorkoutBase):
    id: int
    schedule_id: int
    is_completed: bool
    garmin_workout_id: Optional[str] = None

    class Config:
        from_attributes = True


class ScheduleCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_date: datetime
    end_date: Optional[datetime] = None
    goal: Optional[str] = None
    workouts: list[WorkoutBase] = []


class ScheduleResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    start_date: datetime
    end_date: Optional[datetime] = None
    goal: Optional[str] = None
    is_synced_to_garmin: bool
    workouts: list[WorkoutResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Chat Schemas
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    include_garmin_context: bool = True


class ChatResponse(BaseModel):
    response: str
    suggested_schedule: Optional[ScheduleCreate] = None


# Dashboard Schemas
class WeeklySummary(BaseModel):
    total_distance_km: float
    total_duration_minutes: float
    total_activities: int
    avg_pace: Optional[str] = None
    avg_heart_rate: Optional[float] = None
    total_calories: int


class TrainingLoadData(BaseModel):
    date: str
    load: float
    acute_load: float
    chronic_load: float


class DashboardSummary(BaseModel):
    weekly_summary: WeeklySummary
    current_vo2max: Optional[float] = None
    recovery_time_hours: Optional[int] = None
    training_status: Optional[str] = None
    recent_activities: list[ActivityResponse]


# Garmin Auth
class GarminLoginRequest(BaseModel):
    email: str
    password: str


class GarminAuthStatus(BaseModel):
    is_authenticated: bool
    email: Optional[str] = None
