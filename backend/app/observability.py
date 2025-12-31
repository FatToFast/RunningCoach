"""Lightweight observability helpers (logging + metrics)."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict
from contextvars import ContextVar
from threading import Lock
from typing import Iterable, Protocol

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import get_settings

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
logger = logging.getLogger(__name__)


def get_request_id() -> str | None:
    """Return the current request id if set by middleware."""
    return request_id_ctx.get()


class MetricsBackend(Protocol):
    """Metrics backend interface."""

    def observe_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        ...

    def observe_sync_job(
        self,
        endpoint: str,
        success: bool,
        duration_ms: float,
        items_fetched: int | None = None,
        items_created: int | None = None,
        items_updated: int | None = None,
    ) -> None:
        ...

    def observe_external_api(
        self,
        provider: str,
        operation: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        ...

    def observe_fit_download(self, size_bytes: int, success: bool) -> None:
        ...

    def render_prometheus(self) -> str:
        ...


class MetricsCollector:
    """In-process metrics collector with Prometheus text output."""

    def __init__(self, buckets_ms: Iterable[int] | None = None) -> None:
        self._lock = Lock()
        self._request_counts: dict[tuple[str, str, str], int] = defaultdict(int)
        self._duration_sum_ms: dict[tuple[str, str], float] = defaultdict(float)
        self._duration_count: dict[tuple[str, str], int] = defaultdict(int)
        self._duration_buckets: dict[tuple[str, str], dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._sync_counts: dict[tuple[str, str], int] = defaultdict(int)
        self._sync_duration_sum_ms: dict[tuple[str, str], float] = defaultdict(float)
        self._sync_duration_count: dict[tuple[str, str], int] = defaultdict(int)
        self._sync_duration_buckets: dict[tuple[str, str], dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._sync_items: dict[tuple[str, str], int] = defaultdict(int)
        self._external_counts: dict[tuple[str, str, str], int] = defaultdict(int)
        self._external_duration_sum_ms: dict[tuple[str, str], float] = defaultdict(float)
        self._external_duration_count: dict[tuple[str, str], int] = defaultdict(int)
        self._external_duration_buckets: dict[tuple[str, str], dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._fit_bytes_total: dict[str, int] = defaultdict(int)
        self._fit_downloads_total: dict[str, int] = defaultdict(int)
        self._buckets_ms = list(buckets_ms or [50, 100, 250, 500, 1000, 2500, 5000, 10000])

    def observe_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Record a single request observation."""
        count_key = (method, path, str(status_code))
        duration_key = (method, path)
        bucket_key = self._bucket_for(duration_ms)

        with self._lock:
            self._request_counts[count_key] += 1
            self._duration_sum_ms[duration_key] += duration_ms
            self._duration_count[duration_key] += 1
            self._duration_buckets[duration_key][bucket_key] += 1

    def observe_sync_job(
        self,
        endpoint: str,
        success: bool,
        duration_ms: float,
        items_fetched: int | None = None,
        items_created: int | None = None,
        items_updated: int | None = None,
    ) -> None:
        """Record a sync job observation."""
        status = "success" if success else "error"
        duration_key = (endpoint, status)
        bucket_key = self._bucket_for(duration_ms)

        with self._lock:
            self._sync_counts[(endpoint, status)] += 1
            self._sync_duration_sum_ms[duration_key] += duration_ms
            self._sync_duration_count[duration_key] += 1
            self._sync_duration_buckets[duration_key][bucket_key] += 1

            if items_fetched is not None:
                self._sync_items[(endpoint, "fetched")] += items_fetched
            if items_created is not None:
                self._sync_items[(endpoint, "created")] += items_created
            if items_updated is not None:
                self._sync_items[(endpoint, "updated")] += items_updated

    def observe_external_api(
        self,
        provider: str,
        operation: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Record an external API call observation."""
        duration_key = (provider, operation)
        bucket_key = self._bucket_for(duration_ms)
        status = str(status_code)

        with self._lock:
            self._external_counts[(provider, operation, status)] += 1
            self._external_duration_sum_ms[duration_key] += duration_ms
            self._external_duration_count[duration_key] += 1
            self._external_duration_buckets[duration_key][bucket_key] += 1

    def observe_fit_download(self, size_bytes: int, success: bool) -> None:
        """Record FIT download metrics."""
        status = "success" if success else "error"
        with self._lock:
            self._fit_downloads_total[status] += 1
            if success and size_bytes > 0:
                self._fit_bytes_total[status] += size_bytes

    def render_prometheus(self) -> str:
        """Render metrics in Prometheus text format."""
        lines: list[str] = [
            "# HELP http_requests_total Total HTTP requests",
            "# TYPE http_requests_total counter",
        ]
        with self._lock:
            for (method, path, status), count in sorted(self._request_counts.items()):
                lines.append(
                    f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
                )

            lines.extend(
                [
                    "# HELP http_request_duration_ms Request duration in milliseconds",
                    "# TYPE http_request_duration_ms histogram",
                ]
            )
            for (method, path), total in sorted(self._duration_sum_ms.items()):
                buckets = self._duration_buckets[(method, path)]
                cumulative = 0
                for bound in self._buckets_ms:
                    cumulative += buckets.get(str(bound), 0)
                    lines.append(
                        "http_request_duration_ms_bucket"
                        f'{{method="{method}",path="{path}",le="{bound}"}} {cumulative}'
                    )
                cumulative += buckets.get("+Inf", 0)
                lines.append(
                    "http_request_duration_ms_bucket"
                    f'{{method="{method}",path="{path}",le="+Inf"}} {cumulative}'
                )
                count = self._duration_count[(method, path)]
                lines.append(
                    f'http_request_duration_ms_sum{{method="{method}",path="{path}"}} {total:.2f}'
                )
                lines.append(
                    f'http_request_duration_ms_count{{method="{method}",path="{path}"}} {count}'
                )

            lines.extend(
                [
                    "# HELP sync_jobs_total Total sync jobs",
                    "# TYPE sync_jobs_total counter",
                ]
            )
            for (endpoint, status), count in sorted(self._sync_counts.items()):
                lines.append(
                    f'sync_jobs_total{{endpoint="{endpoint}",status="{status}"}} {count}'
                )

            lines.extend(
                [
                    "# HELP sync_job_duration_ms Sync job duration in milliseconds",
                    "# TYPE sync_job_duration_ms histogram",
                ]
            )
            for (endpoint, status), total in sorted(self._sync_duration_sum_ms.items()):
                buckets = self._sync_duration_buckets[(endpoint, status)]
                cumulative = 0
                for bound in self._buckets_ms:
                    cumulative += buckets.get(str(bound), 0)
                    lines.append(
                        "sync_job_duration_ms_bucket"
                        f'{{endpoint="{endpoint}",status="{status}",le="{bound}"}} {cumulative}'
                    )
                cumulative += buckets.get("+Inf", 0)
                lines.append(
                    "sync_job_duration_ms_bucket"
                    f'{{endpoint="{endpoint}",status="{status}",le="+Inf"}} {cumulative}'
                )
                count = self._sync_duration_count[(endpoint, status)]
                lines.append(
                    "sync_job_duration_ms_sum"
                    f'{{endpoint="{endpoint}",status="{status}"}} {total:.2f}'
                )
                lines.append(
                    "sync_job_duration_ms_count"
                    f'{{endpoint="{endpoint}",status="{status}"}} {count}'
                )

            lines.extend(
                [
                    "# HELP sync_items_total Items processed during sync",
                    "# TYPE sync_items_total counter",
                ]
            )
            for (endpoint, item_type), count in sorted(self._sync_items.items()):
                lines.append(
                    f'sync_items_total{{endpoint="{endpoint}",type="{item_type}"}} {count}'
                )

            lines.extend(
                [
                    "# HELP external_api_requests_total External API requests",
                    "# TYPE external_api_requests_total counter",
                ]
            )
            for (provider, operation, status), count in sorted(self._external_counts.items()):
                lines.append(
                    "external_api_requests_total"
                    f'{{provider="{provider}",operation="{operation}",status="{status}"}} {count}'
                )

            lines.extend(
                [
                    "# HELP external_api_duration_ms External API duration in milliseconds",
                    "# TYPE external_api_duration_ms histogram",
                ]
            )
            for (provider, operation), total in sorted(self._external_duration_sum_ms.items()):
                buckets = self._external_duration_buckets[(provider, operation)]
                cumulative = 0
                for bound in self._buckets_ms:
                    cumulative += buckets.get(str(bound), 0)
                    lines.append(
                        "external_api_duration_ms_bucket"
                        f'{{provider="{provider}",operation="{operation}",le="{bound}"}} {cumulative}'
                    )
                cumulative += buckets.get("+Inf", 0)
                lines.append(
                    "external_api_duration_ms_bucket"
                    f'{{provider="{provider}",operation="{operation}",le="+Inf"}} {cumulative}'
                )
                count = self._external_duration_count[(provider, operation)]
                lines.append(
                    "external_api_duration_ms_sum"
                    f'{{provider="{provider}",operation="{operation}"}} {total:.2f}'
                )
                lines.append(
                    "external_api_duration_ms_count"
                    f'{{provider="{provider}",operation="{operation}"}} {count}'
                )

            lines.extend(
                [
                    "# HELP fit_downloads_total FIT file download attempts",
                    "# TYPE fit_downloads_total counter",
                ]
            )
            for status, count in sorted(self._fit_downloads_total.items()):
                lines.append(f'fit_downloads_total{{status="{status}"}} {count}')

            lines.extend(
                [
                    "# HELP fit_download_bytes_total FIT file download bytes",
                    "# TYPE fit_download_bytes_total counter",
                ]
            )
            for status, total_bytes in sorted(self._fit_bytes_total.items()):
                lines.append(f'fit_download_bytes_total{{status="{status}"}} {total_bytes}')
        return "\n".join(lines) + "\n"

    def _bucket_for(self, duration_ms: float) -> str:
        for bound in self._buckets_ms:
            if duration_ms <= bound:
                return str(bound)
        return "+Inf"


class PrometheusMetrics:
    """Prometheus client-based metrics backend."""

    def __init__(self, buckets_ms: Iterable[int]) -> None:
        from prometheus_client import Counter, Histogram, CollectorRegistry

        self._registry = CollectorRegistry()
        self._buckets_ms = list(buckets_ms)

        self._http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "path", "status"],
            registry=self._registry,
        )
        self._http_request_duration_ms = Histogram(
            "http_request_duration_ms",
            "Request duration in milliseconds",
            ["method", "path"],
            buckets=self._buckets_ms,
            registry=self._registry,
        )
        self._sync_jobs_total = Counter(
            "sync_jobs_total",
            "Total sync jobs",
            ["endpoint", "status"],
            registry=self._registry,
        )
        self._sync_job_duration_ms = Histogram(
            "sync_job_duration_ms",
            "Sync job duration in milliseconds",
            ["endpoint", "status"],
            buckets=self._buckets_ms,
            registry=self._registry,
        )
        self._sync_items_total = Counter(
            "sync_items_total",
            "Items processed during sync",
            ["endpoint", "type"],
            registry=self._registry,
        )
        self._external_api_requests_total = Counter(
            "external_api_requests_total",
            "External API requests",
            ["provider", "operation", "status"],
            registry=self._registry,
        )
        self._external_api_duration_ms = Histogram(
            "external_api_duration_ms",
            "External API duration in milliseconds",
            ["provider", "operation"],
            buckets=self._buckets_ms,
            registry=self._registry,
        )
        self._fit_downloads_total = Counter(
            "fit_downloads_total",
            "FIT file download attempts",
            ["status"],
            registry=self._registry,
        )
        self._fit_download_bytes_total = Counter(
            "fit_download_bytes_total",
            "FIT file download bytes",
            ["status"],
            registry=self._registry,
        )

    def observe_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        self._http_requests_total.labels(method, path, str(status_code)).inc()
        self._http_request_duration_ms.labels(method, path).observe(duration_ms)

    def observe_sync_job(
        self,
        endpoint: str,
        success: bool,
        duration_ms: float,
        items_fetched: int | None = None,
        items_created: int | None = None,
        items_updated: int | None = None,
    ) -> None:
        status = "success" if success else "error"
        self._sync_jobs_total.labels(endpoint, status).inc()
        self._sync_job_duration_ms.labels(endpoint, status).observe(duration_ms)

        if items_fetched is not None:
            self._sync_items_total.labels(endpoint, "fetched").inc(items_fetched)
        if items_created is not None:
            self._sync_items_total.labels(endpoint, "created").inc(items_created)
        if items_updated is not None:
            self._sync_items_total.labels(endpoint, "updated").inc(items_updated)

    def observe_external_api(
        self,
        provider: str,
        operation: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        self._external_api_requests_total.labels(
            provider, operation, str(status_code)
        ).inc()
        self._external_api_duration_ms.labels(provider, operation).observe(duration_ms)

    def observe_fit_download(self, size_bytes: int, success: bool) -> None:
        status = "success" if success else "error"
        self._fit_downloads_total.labels(status).inc()
        if success and size_bytes > 0:
            self._fit_download_bytes_total.labels(status).inc(size_bytes)

    def render_prometheus(self) -> str:
        from prometheus_client import generate_latest

        return generate_latest(self._registry).decode("utf-8")


_metrics_backend: MetricsBackend | None = None


def get_metrics_backend() -> MetricsBackend:
    """Return a cached metrics backend instance."""
    global _metrics_backend
    if _metrics_backend is None:
        settings = get_settings()
        _metrics_backend = _build_metrics_backend(settings.metrics_backend)
    return _metrics_backend


def _build_metrics_backend(backend: str) -> MetricsBackend:
    buckets_ms = [50, 100, 250, 500, 1000, 2500, 5000, 10000]
    if backend == "prometheus":
        try:
            from prometheus_client import Counter  # noqa: F401

            return PrometheusMetrics(buckets_ms)
        except Exception:
            logger.warning(
                "Prometheus backend requested but prometheus_client is not available. "
                "Falling back to in-memory metrics."
            )
    return MetricsCollector(buckets_ms)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attach request_id, log request/response, and emit metrics."""

    def __init__(
        self,
        app: ASGIApp,
        metrics: MetricsBackend | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(app)
        self.metrics = metrics or get_metrics_backend()
        self.logger = logger or logging.getLogger("app.request")

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx.set(request_id)
        request.state.request_id = request_id

        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            status_code = response.status_code if response else 500

            if response is not None:
                response.headers["X-Request-ID"] = request_id

            route = request.scope.get("route")
            route_path = getattr(route, "path", None)
            # Normalize unmatched paths to avoid label cardinality explosion
            path = route_path or "/__unknown__"

            if self.metrics:
                self.metrics.observe_request(
                    request.method,
                    path,
                    status_code,
                    duration_ms,
                )

            log_payload = {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "route": route_path,
                "status_code": status_code,
                "elapsed_ms": round(duration_ms, 2),
                "client": request.client.host if request.client else None,
            }
            self.logger.info(json.dumps(log_payload))
            request_id_ctx.reset(token)


def setup_tracing(app: FastAPI, settings=None) -> None:
    """Configure OpenTelemetry tracing if enabled."""
    settings = settings or get_settings()
    if not settings.otel_enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception:
        logger.warning(
            "OpenTelemetry enabled but required packages are not installed."
        )
        return

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    exporter_kwargs = {}
    if settings.otel_exporter_otlp_endpoint:
        exporter_kwargs["endpoint"] = settings.otel_exporter_otlp_endpoint
    exporter = OTLPSpanExporter(**exporter_kwargs)
    provider.add_span_processor(BatchSpanProcessor(exporter))

    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
