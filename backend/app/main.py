"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.core.config import get_settings
from app.core.session import close_redis
from app.api.v1.router import api_router
from app.observability import RequestLoggingMiddleware, get_metrics_backend, setup_tracing

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan events."""
    # Startup
    # Initialize RAG knowledge retriever if enabled
    if settings.rag_enabled:
        try:
            from app.knowledge.retriever import initialize_knowledge_retriever

            await initialize_knowledge_retriever()
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(
                f"Failed to initialize knowledge retriever: {e}. RAG will be disabled."
            )

    yield
    # Shutdown - cleanup resources
    await close_redis()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    openapi_url=f"{settings.api_prefix}/openapi.json",
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    lifespan=lifespan,
)

metrics_backend = get_metrics_backend()

# CORS middleware
# Note: When allow_credentials=True, allow_origins cannot be ["*"]
# Must specify explicit origins for credentials to work
# Configure via CORS_ORIGINS env var (comma-separated list)
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

if not cors_origins:
    import logging
    logging.getLogger(__name__).warning(
        "CORS_ORIGINS is empty or not configured. "
        "CORS will block all cross-origin requests. "
        "Set CORS_ORIGINS env var (e.g., 'http://localhost:5173,http://localhost:3000')."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware, metrics=metrics_backend)
setup_tracing(app, settings)

# Include API router
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


@app.get("/metrics", include_in_schema=False)
async def metrics() -> PlainTextResponse:
    """Prometheus-style metrics endpoint."""
    return PlainTextResponse(metrics_backend.render_prometheus())
