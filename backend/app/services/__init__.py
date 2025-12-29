"""Service layer for RunningCoach.

Services contain business logic and data aggregation.
"""

from app.services.garmin_sync import GarminSyncService, get_sync_service
from app.services.dashboard import DashboardService, get_dashboard_service

__all__ = [
    "GarminSyncService",
    "get_sync_service",
    "DashboardService",
    "get_dashboard_service",
]
