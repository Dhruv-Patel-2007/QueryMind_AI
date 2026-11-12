"""Pydantic v2 Validation Schemas for ContextMind Conversational Context Engine.

QueryMind AI 2.0 - Phase 5: ContextMind Multi-Turn State Management.
Defines explicit structured models for Context Frames, Active Filters, Turn Records,
and Context API Request/Response contracts.
"""

from typing import Any, Dict, List, Literal, Optional
import uuid
from pydantic import BaseModel, Field, field_validator


class ActiveFilterSchema(BaseModel):
    """Represents an active SQL filter condition within the context frame."""
    column: str = Field(..., description="Canonical qualified column name (e.g., departments.code)")
    operator: str = Field("=", description="Comparison operator (=, >=, <=, >, <, !=, LIKE)")
    value: Any = Field(..., description="Target value for the filter condition")


class ActiveSortSchema(BaseModel):
    """Represents active sorting configuration within the context frame."""
    column: str = Field(..., description="Canonical attribute or column for ordering")
    direction: Literal["ASC", "DESC"] = Field("ASC", description="Sort direction (ASC or DESC)")


class TurnRecordSchema(BaseModel):
    """Audit record for a single conversation turn in the session history."""
    turn_id: int = Field(..., description="Monotonically increasing turn sequence index")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp when turn was resolved")
    user_query: str = Field(..., description="Raw user query received in this turn")
    resolved_query: str = Field(..., description="Unambiguous standalone query produced by ContextMind")
    intent: Optional[str] = Field(None, description="Classified intent category for this turn")
    was_follow_up: bool = Field(False, description="True if turn was resolved as follow-up to prior context")
    modifications: Dict[str, Any] = Field(default_factory=dict, description="Summary of slot mutations in this turn")


class ContextFrameSchema(BaseModel):
    """Explicit structured Context Frame representing conversational session state.
    
    Structure: <Entity References, Active Filters, Metric, Grouping, Sort Order, Limit, Intent, Turn History, TTL>
    """
    session_id: str = Field(..., description="Unique UUID session identifier")
    created_at: str = Field(..., description="ISO 8601 UTC creation timestamp")
    last_active: str = Field(..., description="ISO 8601 UTC last activity timestamp")
    expires_at: str = Field(..., description="ISO 8601 UTC expiration timestamp")
    ttl_seconds: int = Field(600, description="Configured sliding TTL window in seconds")
    turn_count: int = Field(0, description="Total number of conversational turns completed in this session")
    active_entities: Dict[str, Any] = Field(default_factory=dict, description="Referenced entity slots (e.g. primary_table, department_code)")
    active_filters: List[ActiveFilterSchema] = Field(default_factory=list, description="Currently active query filters")
    active_metric: Optional[str] = Field(None, description="Active analytical/aggregation metric (e.g., cgpa, attendance)")
    active_group_by: List[str] = Field(default_factory=list, description="Active grouping attributes (e.g. departments.name)")
    active_order_by: Optional[ActiveSortSchema] = Field(None, description="Active sorting attribute and direction")
    active_limit: Optional[int] = Field(None, description="Active result row limit")
    last_intent: Optional[str] = Field(None, description="Most recently classified query intent")
    last_query: Optional[str] = Field(None, description="Most recent raw user query")
    last_resolved_query: Optional[str] = Field(None, description="Most recent fully resolved query")
    turn_history: List[TurnRecordSchema] = Field(default_factory=list, description="Sequential history of conversational turns")


class ContextResolveRequest(BaseModel):
    """Request payload for resolving a query or follow-up against session context."""
    session_id: str = Field(..., description="Client-provided valid UUID session identifier")
    query: str = Field(..., min_length=1, max_length=500, description="Natural language query or follow-up question")

    @field_validator("session_id")
    @classmethod
    def validate_uuid_format(cls, v: str) -> str:
        """Enforces RFC 4122 UUID validation on session_id."""
        try:
            parsed = uuid.UUID(v)
            return str(parsed)
        except (ValueError, AttributeError, TypeError):
            raise ValueError("Invalid session UUID format. Must be a valid RFC 4122 UUID string.")

    @field_validator("query")
    @classmethod
    def validate_non_empty_query(cls, v: str) -> str:
        """Enforces non-empty, stripped query content."""
        cleaned = v.strip() if v else ""
        if not cleaned:
            raise ValueError("Query string cannot be empty or whitespace only.")
        return cleaned


class ContextResolveResponse(BaseModel):
    """Response payload returned by ContextMind query resolution."""
    status: Literal["success", "clarification", "reset"] = Field(..., description="Execution status")
    session_id: str = Field(..., description="Session UUID")
    original_query: str = Field(..., description="Original raw user input query")
    resolved_query: str = Field(..., description="Standalone unambiguous natural language query")
    was_follow_up: bool = Field(False, description="True if query was resolved as follow-up to previous turn")
    was_reset: bool = Field(False, description="True if query triggered context reset")
    active_frame: Optional[ContextFrameSchema] = Field(None, description="Active context frame after resolution")
    clarification_needed: bool = Field(False, description="True if anaphora could not be resolved without clarification")
    clarification_message: Optional[str] = Field(None, description="User-facing prompt requesting referent clarification")
    turn_number: int = Field(0, description="Turn index for this interaction")


class ContextFrameResponse(BaseModel):
    """Response payload for inspecting the active context frame of a session."""
    status: Literal["success", "expired", "not_found"] = Field(..., description="Lookup status")
    session_id: str = Field(..., description="Session UUID")
    active_frame: Optional[ContextFrameSchema] = Field(None, description="Active context frame if present and valid")
    is_expired: bool = Field(False, description="True if session was expired and evicted")


class ContextResetResponse(BaseModel):
    """Response payload confirming explicit session reset."""
    status: Literal["success"] = Field("success", description="Reset execution status")
    session_id: str = Field(..., description="Session UUID")
    message: str = Field("Context reset successfully", description="Confirmation message")

