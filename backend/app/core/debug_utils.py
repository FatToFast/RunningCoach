"""Debug utilities for cloud migration components.

This module provides comprehensive debugging tools for:
1. Request/Response logging
2. Clerk authentication tracing
3. R2 storage operation tracking
4. Performance monitoring
5. Error aggregation

Usage:
    from app.core.debug_utils import DebugLogger, debug_timer, trace_auth

    # Log authentication flow
    with trace_auth("clerk_jwt"):
        verify_token(token)

    # Time an operation
    with debug_timer("r2_upload"):
        await r2.upload_fit(...)
"""

import functools
import logging
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, TypeVar
from collections import deque

# Configure module logger
logger = logging.getLogger(__name__)


class DebugLogger:
    """Centralized debug logging with context tracking."""

    # Class-level storage for recent logs (circular buffer)
    _recent_logs: deque = deque(maxlen=1000)
    _error_logs: deque = deque(maxlen=100)
    _timing_stats: Dict[str, List[float]] = {}

    @classmethod
    def log(
        cls,
        level: str,
        component: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
    ) -> None:
        """Log a debug message with structured context.

        Args:
            level: Log level (debug, info, warning, error)
            component: Component name (clerk_auth, r2_storage, webhook, etc.)
            message: Log message
            context: Additional context data
            error: Exception if applicable
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "component": component,
            "message": message,
            "context": context or {},
        }

        if error:
            log_entry["error"] = {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            }

        cls._recent_logs.append(log_entry)

        if level == "error":
            cls._error_logs.append(log_entry)

        # Also log to standard logger
        log_func = getattr(logger, level, logger.info)
        log_msg = f"[{component}] {message}"
        if context:
            log_msg += f" | context={context}"
        if error:
            log_func(log_msg, exc_info=True)
        else:
            log_func(log_msg)

    @classmethod
    def debug(cls, component: str, message: str, **kwargs) -> None:
        """Log debug message."""
        cls.log("debug", component, message, **kwargs)

    @classmethod
    def info(cls, component: str, message: str, **kwargs) -> None:
        """Log info message."""
        cls.log("info", component, message, **kwargs)

    @classmethod
    def warning(cls, component: str, message: str, **kwargs) -> None:
        """Log warning message."""
        cls.log("warning", component, message, **kwargs)

    @classmethod
    def error(cls, component: str, message: str, **kwargs) -> None:
        """Log error message."""
        cls.log("error", component, message, **kwargs)

    @classmethod
    def record_timing(cls, operation: str, duration_ms: float) -> None:
        """Record timing for performance monitoring.

        Args:
            operation: Operation name
            duration_ms: Duration in milliseconds
        """
        if operation not in cls._timing_stats:
            cls._timing_stats[operation] = []
        cls._timing_stats[operation].append(duration_ms)

        # Keep only last 100 timings per operation
        if len(cls._timing_stats[operation]) > 100:
            cls._timing_stats[operation] = cls._timing_stats[operation][-100:]

    @classmethod
    def get_timing_stats(cls, operation: Optional[str] = None) -> Dict[str, Any]:
        """Get timing statistics.

        Args:
            operation: Specific operation or None for all

        Returns:
            Timing statistics dictionary
        """
        def calc_stats(timings: List[float]) -> Dict[str, float]:
            if not timings:
                return {"count": 0}
            return {
                "count": len(timings),
                "min_ms": min(timings),
                "max_ms": max(timings),
                "avg_ms": sum(timings) / len(timings),
                "p50_ms": sorted(timings)[len(timings) // 2],
                "p95_ms": sorted(timings)[int(len(timings) * 0.95)] if len(timings) >= 20 else max(timings),
            }

        if operation:
            return {operation: calc_stats(cls._timing_stats.get(operation, []))}
        return {op: calc_stats(timings) for op, timings in cls._timing_stats.items()}

    @classmethod
    def get_recent_logs(
        cls,
        component: Optional[str] = None,
        level: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get recent log entries.

        Args:
            component: Filter by component
            level: Filter by level
            limit: Maximum entries to return

        Returns:
            List of log entries
        """
        logs = list(cls._recent_logs)

        if component:
            logs = [l for l in logs if l["component"] == component]
        if level:
            logs = [l for l in logs if l["level"] == level]

        return logs[-limit:]

    @classmethod
    def get_recent_errors(cls, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent error entries.

        Args:
            limit: Maximum entries to return

        Returns:
            List of error log entries
        """
        return list(cls._error_logs)[-limit:]

    @classmethod
    def clear_logs(cls) -> None:
        """Clear all stored logs."""
        cls._recent_logs.clear()
        cls._error_logs.clear()
        cls._timing_stats.clear()


@contextmanager
def debug_timer(operation: str, component: str = "performance"):
    """Context manager for timing operations.

    Args:
        operation: Name of the operation being timed
        component: Component name for logging

    Usage:
        with debug_timer("r2_upload"):
            await upload_file(...)
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        DebugLogger.record_timing(operation, duration_ms)
        DebugLogger.debug(
            component,
            f"Operation '{operation}' completed",
            context={"duration_ms": round(duration_ms, 2)},
        )


@contextmanager
def trace_auth(auth_type: str = "clerk"):
    """Context manager for tracing authentication flow.

    Args:
        auth_type: Type of auth (clerk, session, hybrid)

    Usage:
        with trace_auth("clerk_jwt"):
            verify_token(token)
    """
    DebugLogger.debug("auth", f"Starting {auth_type} authentication")
    start = time.perf_counter()
    try:
        yield
        duration_ms = (time.perf_counter() - start) * 1000
        DebugLogger.info(
            "auth",
            f"{auth_type} authentication succeeded",
            context={"duration_ms": round(duration_ms, 2)},
        )
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        DebugLogger.error(
            "auth",
            f"{auth_type} authentication failed",
            context={"duration_ms": round(duration_ms, 2)},
            error=e,
        )
        raise


@contextmanager
def trace_storage(operation: str):
    """Context manager for tracing storage operations.

    Args:
        operation: Storage operation name (upload, download, delete, etc.)

    Usage:
        with trace_storage("upload"):
            await r2.upload_fit(...)
    """
    DebugLogger.debug("r2_storage", f"Starting storage operation: {operation}")
    start = time.perf_counter()
    try:
        yield
        duration_ms = (time.perf_counter() - start) * 1000
        DebugLogger.info(
            "r2_storage",
            f"Storage operation '{operation}' completed",
            context={"duration_ms": round(duration_ms, 2)},
        )
        DebugLogger.record_timing(f"r2_{operation}", duration_ms)
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        DebugLogger.error(
            "r2_storage",
            f"Storage operation '{operation}' failed",
            context={"duration_ms": round(duration_ms, 2)},
            error=e,
        )
        raise


F = TypeVar("F", bound=Callable[..., Any])


def debug_endpoint(component: str = "api"):
    """Decorator for debugging API endpoints.

    Args:
        component: Component name for logging

    Usage:
        @router.get("/endpoint")
        @debug_endpoint("upload")
        async def my_endpoint():
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            operation = func.__name__
            DebugLogger.debug(
                component,
                f"Endpoint called: {operation}",
                context={"kwargs": {k: str(v)[:100] for k, v in kwargs.items()}},
            )
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000
                DebugLogger.info(
                    component,
                    f"Endpoint succeeded: {operation}",
                    context={"duration_ms": round(duration_ms, 2)},
                )
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start) * 1000
                DebugLogger.error(
                    component,
                    f"Endpoint failed: {operation}",
                    context={"duration_ms": round(duration_ms, 2)},
                    error=e,
                )
                raise
        return wrapper  # type: ignore
    return decorator


# =============================================================================
# Debug API Endpoints (for development)
# =============================================================================

def get_debug_router():
    """Create FastAPI router for debug endpoints.

    Returns:
        FastAPI APIRouter with debug endpoints
    """
    from fastapi import APIRouter, Query
    from typing import Optional

    router = APIRouter()

    @router.get("/logs")
    async def get_logs(
        component: Optional[str] = Query(None, description="Filter by component"),
        level: Optional[str] = Query(None, description="Filter by level"),
        limit: int = Query(100, ge=1, le=1000, description="Max entries"),
    ):
        """Get recent debug logs."""
        return {
            "logs": DebugLogger.get_recent_logs(component, level, limit),
            "total_logs": len(DebugLogger._recent_logs),
            "total_errors": len(DebugLogger._error_logs),
        }

    @router.get("/errors")
    async def get_errors(
        limit: int = Query(50, ge=1, le=100, description="Max entries"),
    ):
        """Get recent error logs."""
        return {
            "errors": DebugLogger.get_recent_errors(limit),
            "total_errors": len(DebugLogger._error_logs),
        }

    @router.get("/timing")
    async def get_timing(
        operation: Optional[str] = Query(None, description="Filter by operation"),
    ):
        """Get timing statistics."""
        return DebugLogger.get_timing_stats(operation)

    @router.post("/clear")
    async def clear_logs():
        """Clear all debug logs."""
        DebugLogger.clear_logs()
        return {"status": "cleared"}

    return router


# =============================================================================
# Cloud Migration Specific Debugging
# =============================================================================


class CloudMigrationDebug:
    """Debug utilities specific to cloud migration."""

    @staticmethod
    def log_clerk_token_verification(
        token_preview: str,
        success: bool,
        user_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Log Clerk token verification attempt.

        Args:
            token_preview: First/last few chars of token
            success: Whether verification succeeded
            user_id: Clerk user ID if successful
            error: Error message if failed
        """
        context = {
            "token_preview": token_preview,
            "success": success,
        }
        if user_id:
            context["clerk_user_id"] = user_id
        if error:
            context["error"] = error

        if success:
            DebugLogger.info("clerk_auth", "Token verification succeeded", context=context)
        else:
            DebugLogger.warning("clerk_auth", "Token verification failed", context=context)

    @staticmethod
    def log_r2_operation(
        operation: str,
        user_id: int,
        activity_id: int,
        success: bool,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Log R2 storage operation.

        Args:
            operation: Operation type (upload, download, delete)
            user_id: User ID
            activity_id: Activity ID
            success: Whether operation succeeded
            details: Additional operation details
            error: Error message if failed
        """
        context = {
            "operation": operation,
            "user_id": user_id,
            "activity_id": activity_id,
            "success": success,
        }
        if details:
            context.update(details)
        if error:
            context["error"] = error

        if success:
            DebugLogger.info("r2_storage", f"R2 {operation} succeeded", context=context)
        else:
            DebugLogger.error("r2_storage", f"R2 {operation} failed", context=context)

    @staticmethod
    def log_webhook_event(
        event_type: str,
        clerk_user_id: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Log Clerk webhook event processing.

        Args:
            event_type: Webhook event type (user.created, etc.)
            clerk_user_id: Clerk user ID from event
            success: Whether processing succeeded
            details: Additional event details
            error: Error message if failed
        """
        context = {
            "event_type": event_type,
            "clerk_user_id": clerk_user_id,
            "success": success,
        }
        if details:
            context.update(details)
        if error:
            context["error"] = error

        if success:
            DebugLogger.info("webhook", f"Webhook {event_type} processed", context=context)
        else:
            DebugLogger.error("webhook", f"Webhook {event_type} failed", context=context)

    @staticmethod
    def log_hybrid_auth_flow(
        auth_method: str,
        user_id: Optional[int] = None,
        clerk_user_id: Optional[str] = None,
        fallback_used: bool = False,
        error: Optional[str] = None,
    ) -> None:
        """Log hybrid authentication flow.

        Args:
            auth_method: Auth method used (clerk, session)
            user_id: Database user ID
            clerk_user_id: Clerk user ID if using Clerk
            fallback_used: Whether fallback auth was used
            error: Error message if failed
        """
        context = {
            "auth_method": auth_method,
            "fallback_used": fallback_used,
        }
        if user_id:
            context["user_id"] = user_id
        if clerk_user_id:
            context["clerk_user_id"] = clerk_user_id
        if error:
            context["error"] = error

        DebugLogger.info("hybrid_auth", f"Auth flow completed via {auth_method}", context=context)
