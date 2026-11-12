"""FastAPI Route Endpoints for ContextMind Conversational Context Engine.

QueryMind AI 2.0 - Phase 5: ContextMind Multi-Turn State Management.
Exposes context resolution, context frame inspection, and explicit session reset endpoints.
"""

import uuid
from fastapi import APIRouter, HTTPException, Path, status

from app.schemas.context import (
    ContextFrameResponse,
    ContextResetResponse,
    ContextResolveRequest,
    ContextResolveResponse,
)
from app.services.context_engine import get_context_engine

router = APIRouter()


def _validate_uuid_path(session_id: str) -> str:
    """Validates session_id path parameter as a valid RFC 4122 UUID."""
    try:
        val = uuid.UUID(session_id)
        return str(val)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid session UUID format: '{session_id}'. Must be a valid RFC 4122 UUID string.",
        )


@router.post(
    "/resolve",
    response_model=ContextResolveResponse,
    summary="Resolve Query or Follow-Up Against Session Context",
    description="Resolves anaphora, merges context slots, updates conversational turn state, and refreshes sliding TTL.",
)
def resolve_context_endpoint(request: ContextResolveRequest) -> ContextResolveResponse:
    """Resolves an incoming query or follow-up question within the specified session context."""
    context_engine = get_context_engine()
    try:
        return context_engine.resolve_turn(
            session_id=request.session_id,
            query=request.query,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.get(
    "/frame/{session_id}",
    response_model=ContextFrameResponse,
    summary="Retrieve Active Session Context Frame",
    description="Retrieves the active structured Context Frame for a session. Returns 404 if not found or expired.",
)
def get_context_frame_endpoint(
    session_id: str = Path(..., description="Valid RFC 4122 session UUID string")
) -> ContextFrameResponse:
    """Returns the current active context frame for the given session ID."""
    canonical_id = _validate_uuid_path(session_id)
    context_engine = get_context_engine()

    frame = context_engine.get_frame(canonical_id)
    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session context '{canonical_id}' not found or has expired.",
        )

    return ContextFrameResponse(
        status="success",
        session_id=canonical_id,
        active_frame=frame,
        is_expired=False,
    )


@router.post(
    "/reset/{session_id}",
    response_model=ContextResetResponse,
    summary="Reset Active Session Context",
    description="Immediately deletes the active context frame for the specified session ID without affecting other sessions.",
)
def reset_context_endpoint(
    session_id: str = Path(..., description="Valid RFC 4122 session UUID string to reset")
) -> ContextResetResponse:
    """Resets and purges conversational context for the given session ID."""
    canonical_id = _validate_uuid_path(session_id)
    context_engine = get_context_engine()

    context_engine.reset_session(canonical_id)
    return ContextResetResponse(
        status="success",
        session_id=canonical_id,
        message=f"Context for session '{canonical_id}' has been reset successfully.",
    )

