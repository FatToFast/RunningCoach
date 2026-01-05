"""Database models for RunningCoach."""

from app.models.user import User
from app.models.garmin import GarminSession, GarminSyncState, GarminRawEvent, GarminRawFile
from app.models.activity import Activity, ActivitySample, ActivityLap, ActivityMetric
from app.models.health import Sleep, HRRecord, HealthMetric, FitnessMetricDaily, HeartRateZone, BodyComposition
from app.models.workout import Workout, WorkoutSchedule
from app.models.plan import Plan, PlanWeek
from app.models.analytics import AnalyticsSummary
from app.models.ai import AIConversation, AIMessage, AIImport
from app.models.ai_snapshot import AITrainingSnapshot
from app.models.strava import StravaSession, StravaSyncState, StravaActivityMap, StravaUploadJob, StravaUploadStatus
from app.models.gear import Gear, ActivityGear, GearType, GearStatus
from app.models.strength import StrengthSession, StrengthExercise
from app.models.calendar_note import CalendarNote
from app.models.race import Race

__all__ = [
    # User
    "User",
    # Garmin
    "GarminSession",
    "GarminSyncState",
    "GarminRawEvent",
    "GarminRawFile",
    # Activity
    "Activity",
    "ActivitySample",
    "ActivityLap",
    "ActivityMetric",
    # Health
    "Sleep",
    "HRRecord",
    "HealthMetric",
    "FitnessMetricDaily",
    "HeartRateZone",
    "BodyComposition",
    # Workout
    "Workout",
    "WorkoutSchedule",
    # Plan
    "Plan",
    "PlanWeek",
    # Analytics
    "AnalyticsSummary",
    # AI
    "AIConversation",
    "AIMessage",
    "AIImport",
    "AITrainingSnapshot",
    # Strava
    "StravaSession",
    "StravaSyncState",
    "StravaActivityMap",
    "StravaUploadJob",
    "StravaUploadStatus",
    # Gear
    "Gear",
    "ActivityGear",
    "GearType",
    "GearStatus",
    # Strength
    "StrengthSession",
    "StrengthExercise",
    # Calendar
    "CalendarNote",
    # Race
    "Race",
]
