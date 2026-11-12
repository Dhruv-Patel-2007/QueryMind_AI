"""QueryMind AI 2.0 - Main FastAPI Application Entry Point."""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api.endpoints.nlp import router as nlp_router
from app.api.endpoints.schema import router as schema_router
from app.api.endpoints.context import router as context_router
from app.services.context_engine import get_context_engine

settings = get_settings()

_cleanup_task: Optional[asyncio.Task] = None


async def _periodic_session_cleanup(interval_seconds: int) -> None:
    """Asynchronous background worker to prune expired conversational sessions periodically."""
    engine = get_context_engine()
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            engine.session_manager.clear_expired_sessions()
        except asyncio.CancelledError:
            break
        except Exception:
            # Prevent background loop crash on unexpected exception
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager handling startup and shutdown background tasks."""
    global _cleanup_task
    # Startup: Start periodic cleanup task if not already running
    if _cleanup_task is None or _cleanup_task.done():
        _cleanup_task = asyncio.create_task(
            _periodic_session_cleanup(settings.SESSION_CLEANUP_INTERVAL_SECONDS)
        )
    try:
        yield
    finally:
        # Shutdown: Graceful cancellation of background task
        if _cleanup_task and not _cleanup_task.done():
            _cleanup_task.cancel()
            try:
                await _cleanup_task
            except asyncio.CancelledError:
                pass
        _cleanup_task = None


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="NLP-Based Conversational Text-to-SQL System for Academic Institutions",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(nlp_router, prefix=f"{settings.API_V1_STR}/nlp", tags=["NLP"])
app.include_router(schema_router, prefix=f"{settings.API_V1_STR}/schema", tags=["Schema"])
app.include_router(context_router, prefix=f"{settings.API_V1_STR}/context", tags=["Context"])



@app.get("/", tags=["Root"])
def root_info():
    """Root endpoint providing service metadata."""
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health",
    }


@app.get(f"{settings.API_V1_STR}/health", tags=["Health"])
def health_check():
    """System health check endpoint verifying backend connectivity."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)

