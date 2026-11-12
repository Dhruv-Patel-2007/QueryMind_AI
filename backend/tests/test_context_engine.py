"""Comprehensive Automated Pytest Suite for ContextMind Conversational Context Engine.

QueryMind AI 2.0 - Phase 5: ContextMind Multi-Turn State Management.
Tests cover:
- Thread-safe session management & session isolation
- Sliding TTL expiration with deterministic simulated clock (zero sleep)
- Deterministic anaphora and reference resolution (Examples A, B, C)
- Slot merging, contradiction elimination, and filter preservation
- Ambiguity detection and unresolvable referent clarification
- Explicit context reset triggers and programmatic resets
- Concurrent multi-threaded execution safety
- FastAPI /api/context HTTP endpoints & validation error contracts
"""

from concurrent.futures import ThreadPoolExecutor
import uuid
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.schemas.context import ActiveFilterSchema, ContextFrameSchema
from app.services.context_engine import ContextMind, SessionManager, get_context_engine

settings = get_settings()
client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Session Manager & Isolation Tests
# ---------------------------------------------------------------------------

def test_session_manager_create_and_retrieve():
    """Verifies creation and retrieval of session frames."""
    mgr = SessionManager(ttl_seconds=600)
    sid = str(uuid.uuid4())

    frame = mgr.create_or_get_session(sid)
    assert frame.session_id == sid
    assert frame.turn_count == 0
    assert frame.ttl_seconds == 600
    assert len(frame.turn_history) == 0

    retrieved = mgr.get_session(sid)
    assert retrieved is not None
    assert retrieved.session_id == sid


def test_session_isolation_independent_frames():
    """Verifies that two different session IDs maintain strictly isolated context frames."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid_1 = str(uuid.uuid4())
    sid_2 = str(uuid.uuid4())

    # Session 1: AI department students
    r1 = ce.resolve_turn(sid_1, "Show students in the AI department.")
    assert r1.status == "success"
    assert r1.active_frame.active_entities.get("department_code") == "AI"
    assert len(r1.active_frame.active_filters) == 1
    assert r1.active_frame.active_filters[0].value == "AI"

    # Session 2: CS department courses
    r2 = ce.resolve_turn(sid_2, "Show courses in the CS department.")
    assert r2.status == "success"
    assert r2.active_frame.active_entities.get("department_code") == "CS"
    assert r2.active_frame.active_entities.get("primary_table") == "courses"

    # Verify Session 1 was not modified by Session 2
    f1 = ce.get_frame(sid_1)
    assert f1.active_entities.get("department_code") == "AI"
    assert f1.active_entities.get("primary_table") == "students"
    assert f1.active_filters[0].value == "AI"

    # Reset Session 1, verify Session 2 untouched
    ce.reset_session(sid_1)
    assert ce.get_frame(sid_1) is None
    assert ce.get_frame(sid_2) is not None
    assert ce.get_frame(sid_2).active_entities.get("department_code") == "CS"


def test_session_manager_sliding_ttl_with_injectable_clock():
    """Verifies sliding TTL expiration and refresh behavior deterministically without sleep."""
    current_time = [1000.0]

    def mock_clock() -> float:
        return current_time[0]

    mgr = SessionManager(ttl_seconds=600, time_provider=mock_clock)
    ce = ContextMind(session_manager=mgr, time_provider=mock_clock)
    sid = str(uuid.uuid4())

    # Turn 1 at t=1000 -> expires at t=1600
    r1 = ce.resolve_turn(sid, "Show students in the AI department.")
    assert r1.status == "success"
    assert mgr._parse_iso(r1.active_frame.expires_at) == 1600.0

    # Advance clock to t=1500 (within TTL)
    current_time[0] = 1500.0
    f = ce.get_frame(sid)
    assert f is not None
    assert f.turn_count == 1

    # Turn 2 at t=1500 -> sliding TTL refreshes expiration to t=2100
    r2 = ce.resolve_turn(sid, "Now show their attendance.")
    assert r2.status == "success"
    assert r2.was_follow_up is True
    assert mgr._parse_iso(r2.active_frame.expires_at) == 2100.0

    # Advance clock to t=2050 (still valid under refreshed TTL)
    current_time[0] = 2050.0
    f2 = ce.get_frame(sid)
    assert f2 is not None

    # Advance clock past expiration to t=2101
    current_time[0] = 2101.0
    f3 = ce.get_frame(sid)
    assert f3 is None  # Evicted due to TTL expiration


def test_session_manager_expiration_eviction():
    """Verifies that expired sessions cannot be reused or influence future turns."""
    current_time = [2000.0]

    def mock_clock() -> float:
        return current_time[0]

    mgr = SessionManager(ttl_seconds=300, time_provider=mock_clock)
    ce = ContextMind(session_manager=mgr, time_provider=mock_clock)
    sid = str(uuid.uuid4())

    # Turn 1
    ce.resolve_turn(sid, "Show students in the AI department.")

    # Advance past 300s TTL
    current_time[0] = 2305.0

    # Attempt follow-up after expiration: since session expired, pronoun 'their' cannot resolve
    res = ce.resolve_turn(sid, "Now show their attendance.")
    assert res.status == "clarification"
    assert res.clarification_needed is True
    assert "no prior conversational context" in res.clarification_message


def test_session_manager_cleanup_expired_sessions():
    """Verifies batch cleanup of multiple expired sessions."""
    current_time = [100.0]
    mgr = SessionManager(ttl_seconds=50, time_provider=lambda: current_time[0])

    sid_1 = str(uuid.uuid4())
    sid_2 = str(uuid.uuid4())
    mgr.create_or_get_session(sid_1)
    mgr.create_or_get_session(sid_2)
    assert mgr.session_count() == 2

    # Advance time past TTL
    current_time[0] = 160.0
    pruned = mgr.clear_expired_sessions()
    assert pruned == 2
    assert mgr.session_count() == 0


# ---------------------------------------------------------------------------
# 2. Anaphora & Follow-Up Resolution Tests (Examples A, B, C)
# ---------------------------------------------------------------------------

def test_context_engine_example_a_their_attendance():
    """Verifies Example A: 'Show students in the AI department' -> 'Now show their attendance'."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    # Turn 1
    r1 = ce.resolve_turn(sid, "Show students in the AI department.")
    assert r1.status == "success"
    assert r1.was_follow_up is False
    assert r1.resolved_query == "Show students in the AI department."
    assert r1.active_frame.active_entities.get("primary_table") == "students"
    assert r1.active_frame.active_entities.get("department_code") == "AI"

    # Turn 2: Follow-up with pronoun 'their'
    r2 = ce.resolve_turn(sid, "Now show their attendance.")
    assert r2.status == "success"
    assert r2.was_follow_up is True
    assert r2.resolved_query == "Show attendance of students in the AI department."
    assert r2.active_frame.active_metric == "attendance"
    assert r2.active_frame.active_entities.get("primary_table") == "students"
    assert r2.active_frame.active_entities.get("department_code") == "AI"
    assert len(r2.active_frame.active_filters) == 1
    assert r2.active_frame.active_filters[0].value == "AI"


def test_context_engine_example_b_sort_them_by_credits():
    """Verifies Example B: 'Show courses in the CS department' -> 'Sort them by credits'."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    # Turn 1
    r1 = ce.resolve_turn(sid, "Show courses in the CS department.")
    assert r1.status == "success"
    assert r1.active_frame.active_entities.get("primary_table") == "courses"
    assert r1.active_frame.active_entities.get("department_code") == "CS"

    # Turn 2: Follow-up with pronoun 'them' and sort instruction
    r2 = ce.resolve_turn(sid, "Sort them by credits.")
    assert r2.status == "success"
    assert r2.was_follow_up is True
    assert r2.resolved_query == "Show courses in the CS department sorted by credits."
    assert r2.active_frame.active_order_by is not None
    assert r2.active_frame.active_order_by.column == "courses.credits"
    assert r2.active_frame.active_order_by.direction == "ASC"
    assert r2.active_frame.active_entities.get("primary_table") == "courses"
    assert r2.active_frame.active_entities.get("department_code") == "CS"


def test_context_engine_example_c_cs_students_instead():
    """Verifies Example C: 'Show average CGPA of AI students' -> 'Now show CS students instead'."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    # Turn 1
    r1 = ce.resolve_turn(sid, "Show average CGPA of AI students.")
    assert r1.status == "success"
    assert r1.active_frame.active_metric == "cgpa"
    assert r1.active_frame.active_entities.get("department_code") == "AI"

    # Turn 2: Replacement with 'instead'
    r2 = ce.resolve_turn(sid, "Now show CS students instead.")
    assert r2.status == "success"
    assert r2.was_follow_up is True
    assert r2.resolved_query == "Show average CGPA of CS students."
    assert r2.active_frame.active_entities.get("department_code") == "CS"
    assert r2.active_frame.active_metric == "cgpa"  # Preserved metric

    # Critical contradiction invariant: Only CS filter remains, AI is deleted
    assert len(r2.active_frame.active_filters) == 1
    assert r2.active_frame.active_filters[0].column == "departments.code"
    assert r2.active_frame.active_filters[0].value == "CS"


def test_context_engine_contradiction_elimination_single_department():
    """Ensures contradictory department filters never silently coexist in the active frame."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    ce.resolve_turn(sid, "Show students in Electrical Engineering.")
    frame = ce.get_frame(sid)
    assert frame.active_entities.get("department_code") == "EE"
    assert len([f for f in frame.active_filters if f.column == "departments.code"]) == 1

    # Override with Mathematics
    ce.resolve_turn(sid, "Now show MATH students instead.")
    frame2 = ce.get_frame(sid)
    assert frame2.active_entities.get("department_code") == "MATH"
    dept_filters = [f for f in frame2.active_filters if f.column == "departments.code"]
    assert len(dept_filters) == 1
    assert dept_filters[0].value == "MATH"


def test_context_engine_filter_preservation_across_turns():
    """Verifies that non-conflicting filters and entities remain preserved across turns."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    # Turn 1
    ce.resolve_turn(sid, "Show courses in the CS department.")
    # Turn 2: Add sort
    r2 = ce.resolve_turn(sid, "Sort them by credits.")
    # Turn 3: Add limit
    r3 = ce.resolve_turn(sid, "Top 5.")

    assert r3.status == "success"
    assert r3.active_frame.active_limit == 5
    assert r3.active_frame.active_order_by.column == "courses.credits"
    assert r3.active_frame.active_entities.get("department_code") == "CS"
    assert r3.active_frame.turn_count == 3


def test_context_engine_those_courses_filter_addition():
    """Verifies resolution of 'those <entity> with <condition>'."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    ce.resolve_turn(sid, "Show courses in the CS department.")
    r2 = ce.resolve_turn(sid, "Show those courses with credits greater than 3.")
    assert r2.status == "success"
    assert r2.was_follow_up is True
    assert r2.resolved_query == "Show courses in the CS department with credits greater than 3."


def test_context_engine_the_same_department_resolution():
    """Verifies resolution of anaphoric reference 'the same department'."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    ce.resolve_turn(sid, "Show courses in the AI department.")
    r2 = ce.resolve_turn(sid, "Show instructors in the same department.")
    assert r2.status == "success"
    assert r2.was_follow_up is True
    assert "AI department" in r2.resolved_query


# ---------------------------------------------------------------------------
# 3. Ambiguity & Unresolvable Pronoun Tests
# ---------------------------------------------------------------------------

def test_context_engine_unresolvable_pronoun_triggers_clarification():
    """Verifies that anaphoric pronouns without prior context return structured clarification."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    res = ce.resolve_turn(sid, "Now show their attendance.")
    assert res.status == "clarification"
    assert res.clarification_needed is True
    assert res.was_follow_up is False
    assert "their" in res.clarification_message
    assert "no prior conversational context" in res.clarification_message


def test_context_engine_unresolvable_pronoun_them_without_context():
    """Verifies unresolvable 'them' returns clarification."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    res = ce.resolve_turn(sid, "Sort them by credits.")
    assert res.status == "clarification"
    assert res.clarification_needed is True
    assert "them" in res.clarification_message


# ---------------------------------------------------------------------------
# 4. Reset & History Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "reset_phrase",
    ["clear context", "Clear context.", "RESET", "reset context", "start over", "new query"],
)
def test_context_engine_explicit_reset_phrases(reset_phrase: str):
    """Verifies that explicit reset phrases immediately purge the session frame."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    # Active turn
    ce.resolve_turn(sid, "Show students in the AI department.")
    assert ce.get_frame(sid) is not None

    # Reset trigger
    r_reset = ce.resolve_turn(sid, reset_phrase)
    assert r_reset.status == "reset"
    assert r_reset.was_reset is True
    assert r_reset.active_frame is None

    # Verify frame purged from storage
    assert ce.get_frame(sid) is None


def test_context_engine_service_level_reset():
    """Verifies programmatic service-level reset method."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    ce.resolve_turn(sid, "Show students in the CS department.")
    assert ce.get_frame(sid) is not None

    success = ce.reset_session(sid)
    assert success is True
    assert ce.get_frame(sid) is None

    # Idempotent reset on non-existent session
    success_again = ce.reset_session(sid)
    assert success_again is False


def test_context_engine_turn_history_audit_stack():
    """Verifies turn history sequential stack and modification logging."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    ce.resolve_turn(sid, "Show students in the AI department.")
    ce.resolve_turn(sid, "Now show their attendance.")
    ce.resolve_turn(sid, "Now show CS students instead.")

    frame = ce.get_frame(sid)
    assert frame.turn_count == 3
    assert len(frame.turn_history) == 3

    assert frame.turn_history[0].turn_id == 1
    assert frame.turn_history[0].was_follow_up is False
    assert frame.turn_history[1].turn_id == 2
    assert frame.turn_history[1].was_follow_up is True
    assert frame.turn_history[2].turn_id == 3
    assert frame.turn_history[2].was_follow_up is True


# ---------------------------------------------------------------------------
# 5. Concurrency & Thread Safety Tests
# ---------------------------------------------------------------------------

def test_context_engine_thread_safe_concurrent_access():
    """Verifies thread-safe execution across multiple threads and sessions simultaneously."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    session_ids = [str(uuid.uuid4()) for _ in range(10)]

    def run_multi_turn_session(sid: str) -> bool:
        r1 = ce.resolve_turn(sid, "Show students in the AI department.")
        r2 = ce.resolve_turn(sid, "Now show their attendance.")
        f = ce.get_frame(sid)
        return (
            r1.status == "success"
            and r2.status == "success"
            and f is not None
            and f.turn_count == 2
            and f.active_metric == "attendance"
        )

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(run_multi_turn_session, session_ids))

    assert all(results)
    assert ce.session_manager.session_count() == 10


# ---------------------------------------------------------------------------
# 6. FastAPI Route & Validation Error Tests (/api/context)
# ---------------------------------------------------------------------------

def test_api_resolve_endpoint_success():
    """Verifies POST /api/context/resolve HTTP endpoint."""
    sid = str(uuid.uuid4())
    payload = {"session_id": sid, "query": "Show students in the AI department."}
    response = client.post("/api/context/resolve", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["session_id"] == sid
    assert data["resolved_query"] == "Show students in the AI department."
    assert data["was_follow_up"] is False
    assert data["turn_number"] == 1


def test_api_resolve_endpoint_follow_up_chain():
    """Verifies multi-turn follow-up chain via HTTP API."""
    sid = str(uuid.uuid4())

    # Turn 1
    r1 = client.post(
        "/api/context/resolve",
        json={"session_id": sid, "query": "Show courses in the CS department."},
    )
    assert r1.status_code == 200

    # Turn 2
    r2 = client.post(
        "/api/context/resolve",
        json={"session_id": sid, "query": "Sort them by credits."},
    )
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["was_follow_up"] is True
    assert data2["resolved_query"] == "Show courses in the CS department sorted by credits."
    assert data2["active_frame"]["turn_count"] == 2


def test_api_resolve_endpoint_reset_phrase():
    """Verifies that reset phrase sent to POST /api/context/resolve clears the frame."""
    sid = str(uuid.uuid4())
    client.post(
        "/api/context/resolve",
        json={"session_id": sid, "query": "Show students in the AI department."},
    )

    r_reset = client.post(
        "/api/context/resolve",
        json={"session_id": sid, "query": "clear context"},
    )
    assert r_reset.status_code == 200
    data = r_reset.json()
    assert data["status"] == "reset"
    assert data["was_reset"] is True
    assert data["active_frame"] is None


def test_api_resolve_endpoint_unresolvable_pronoun_clarification():
    """Verifies clarification payload returned over HTTP API when referent is missing."""
    sid = str(uuid.uuid4())
    r = client.post(
        "/api/context/resolve",
        json={"session_id": sid, "query": "Now show their attendance."},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "clarification"
    assert data["clarification_needed"] is True
    assert "their" in data["clarification_message"]


def test_api_frame_endpoint_found_and_not_found():
    """Verifies GET /api/context/frame/{session_id} returns 200 or 404."""
    sid = str(uuid.uuid4())

    # 404 on uninitialized session
    r_empty = client.get(f"/api/context/frame/{sid}")
    assert r_empty.status_code == 404

    # Initialize turn
    client.post(
        "/api/context/resolve",
        json={"session_id": sid, "query": "Show students in the AI department."},
    )

    # 200 on active session
    r_found = client.get(f"/api/context/frame/{sid}")
    assert r_found.status_code == 200
    data = r_found.json()
    assert data["status"] == "success"
    assert data["active_frame"]["session_id"] == sid
    assert data["active_frame"]["turn_count"] == 1


def test_api_reset_endpoint_success():
    """Verifies POST /api/context/reset/{session_id} endpoint."""
    sid = str(uuid.uuid4())
    client.post(
        "/api/context/resolve",
        json={"session_id": sid, "query": "Show students in the AI department."},
    )

    r_reset = client.post(f"/api/context/reset/{sid}")
    assert r_reset.status_code == 200
    assert r_reset.json()["status"] == "success"

    # Frame should now be 404
    assert client.get(f"/api/context/frame/{sid}").status_code == 404


def test_api_validation_invalid_uuid():
    """Verifies 422 Unprocessable Entity on malformed session UUID."""
    r = client.post(
        "/api/context/resolve",
        json={"session_id": "not-a-real-uuid", "query": "Show all students."},
    )
    assert r.status_code == 422

    r_frame = client.get("/api/context/frame/bad-uuid")
    assert r_frame.status_code == 422

    r_reset = client.post("/api/context/reset/bad-uuid")
    assert r_reset.status_code == 422


def test_api_validation_empty_query():
    """Verifies 422 Unprocessable Entity on empty or whitespace-only query."""
    sid = str(uuid.uuid4())
    r_empty = client.post(
        "/api/context/resolve",
        json={"session_id": sid, "query": ""},
    )
    assert r_empty.status_code == 422

    r_spaces = client.post(
        "/api/context/resolve",
        json={"session_id": sid, "query": "     "},
    )
    assert r_spaces.status_code == 422


# ---------------------------------------------------------------------------
# 8. Phase 5 Technical Correction Pass Tests
# ---------------------------------------------------------------------------

def test_context_engine_history_bounded_to_50_turns():
    """Verifies turn_history is bounded to MAX_TURNS_PER_SESSION (50) while turn_count increments monotonically."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    # Execute 55 consecutive turns
    for _ in range(55):
        res = ce.resolve_turn(sid, "Show students in the AI department.")
        assert res.status == "success"

    frame = ce.get_frame(sid)
    assert frame is not None
    # Invariant: Lifetime turn_count is preserved
    assert frame.turn_count == 55
    # Invariant: Retained turn_history is strictly bounded to 50
    assert len(frame.turn_history) == 50
    # Invariant: Oldest retained turn is 6, newest is 55
    assert frame.turn_history[0].turn_id == 6
    assert frame.turn_history[-1].turn_id == 55
    # Invariant: Active context slots are intact
    assert frame.active_entities.get("primary_table") == "students"
    assert frame.active_entities.get("department_code") == "AI"
    assert len(frame.active_filters) == 1


def test_context_engine_independent_query_now_marker_different_entity():
    """Verifies complete independent queries with discourse marker 'Now' do not inherit previous entity or filters."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    # Turn 1: AI department students
    r1 = ce.resolve_turn(sid, "Show students in the AI department.")
    assert r1.status == "success"
    assert r1.active_frame.active_entities.get("primary_table") == "students"
    assert r1.active_frame.active_entities.get("department_code") == "AI"

    # Turn 2: Independent instructors query starting with 'Now'
    r2 = ce.resolve_turn(sid, "Now show instructors who joined after 2018.")
    assert r2.status == "success"
    assert r2.was_follow_up is False
    assert r2.resolved_query == "Show instructors who joined after 2018."
    assert r2.active_frame.active_entities.get("primary_table") == "instructors"
    # Crucial check: AI department filter must NOT be inherited
    assert "department_code" not in r2.active_frame.active_entities
    assert len([f for f in r2.active_frame.active_filters if f.column == "departments.code"]) == 0


def test_context_engine_independent_query_and_marker_different_entity():
    """Verifies complete independent queries starting with 'And' start a fresh operational context."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    # Turn 1
    ce.resolve_turn(sid, "Show students in the AI department.")
    # Turn 2
    r2 = ce.resolve_turn(sid, "And show courses in the CS department.")
    assert r2.status == "success"
    assert r2.was_follow_up is False
    assert r2.resolved_query == "Show courses in the CS department."
    assert r2.active_frame.active_entities.get("primary_table") == "courses"
    assert r2.active_frame.active_entities.get("department_code") == "CS"
    # Only CS remains
    assert len(r2.active_frame.active_filters) == 1
    assert r2.active_frame.active_filters[0].value == "CS"


def test_context_engine_list_query_clears_sticky_metric():
    """Verifies that an independent list query does not inherit sticky metrics from prior turns."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    # Turn 1: Aggregation query setting active_metric
    r1 = ce.resolve_turn(sid, "Show average CGPA of AI students.")
    assert r1.status == "success"
    assert r1.active_frame.active_metric == "cgpa"

    # Turn 2: Pure list query for CS students
    r2 = ce.resolve_turn(sid, "Now list CS students.")
    assert r2.status == "success"
    assert r2.was_follow_up is False
    assert r2.resolved_query == "List CS students."
    assert r2.active_frame.active_entities.get("department_code") == "CS"
    # Crucial check: active_metric must be cleared to None
    assert r2.active_frame.active_metric is None


def test_context_engine_multiple_departments_triggers_clarification():
    """Verifies multiple explicitly mentioned departments trigger structured clarification."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    r = ce.resolve_turn(sid, "Show courses in AI and CS departments.")
    assert r.status == "clarification"
    assert r.clarification_needed is True
    assert "multiple departments" in r.clarification_message.lower()
    assert "'AI'" in r.clarification_message
    assert "'CS'" in r.clarification_message
    # Turn count should not advance for clarification responses
    assert r.turn_number == 0


def test_context_engine_multiple_entities_triggers_clarification():
    """Verifies multiple explicitly mentioned primary entities trigger structured clarification."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    r = ce.resolve_turn(sid, "Show students and instructors in the AI department.")
    assert r.status == "clarification"
    assert r.clarification_needed is True
    assert "multiple entities" in r.clarification_message.lower()
    assert "'instructors'" in r.clarification_message
    assert "'students'" in r.clarification_message
    assert r.turn_number == 0


def test_session_cleanup_clear_expired_sessions():
    """Verifies that clear_expired_sessions accurately identifies and purges expired sessions."""
    current_time = [1000.0]

    def mock_clock() -> float:
        return current_time[0]

    mgr = SessionManager(ttl_seconds=10, time_provider=mock_clock)
    ce = ContextMind(session_manager=mgr, time_provider=mock_clock)
    sid1 = str(uuid.uuid4())
    sid2 = str(uuid.uuid4())

    ce.resolve_turn(sid1, "Show students in the AI department.")
    ce.resolve_turn(sid2, "Show courses in the CS department.")
    assert mgr.session_count() == 2

    # Advance clock past TTL
    current_time[0] = 1015.0
    evicted = mgr.clear_expired_sessions()
    assert evicted == 2
    assert mgr.session_count() == 0


def test_context_engine_independent_query_then_marker_different_entity():
    """Verifies that an independent query beginning with 'Then' starts a fresh context and drops prior filters."""
    ce = ContextMind(session_manager=SessionManager(ttl_seconds=600))
    sid = str(uuid.uuid4())

    # Turn 1: AI department students
    r1 = ce.resolve_turn(sid, "Show students in the AI department.")
    assert r1.status == "success"
    assert r1.active_frame.active_entities.get("primary_table") == "students"
    assert r1.active_frame.active_entities.get("department_code") == "AI"

    # Turn 2: Exact prompt scenario: "Then show courses in the CS department."
    r2 = ce.resolve_turn(sid, "Then show courses in the CS department.")
    assert r2.status == "success"
    # Invariant 1: Second query classified as independent
    assert r2.was_follow_up is False
    assert r2.resolved_query == "Show courses in the CS department."
    # Invariant 2: CS department filter applied
    assert r2.active_frame.active_entities.get("primary_table") == "courses"
    assert r2.active_frame.active_entities.get("department_code") == "CS"
    assert len(r2.active_frame.active_filters) == 1
    assert r2.active_frame.active_filters[0].column == "departments.code"
    assert r2.active_frame.active_filters[0].value == "CS"
    # Invariant 3: Previous AI department filter removed
    ai_filters = [f for f in r2.active_frame.active_filters if f.value == "AI"]
    assert len(ai_filters) == 0
    # Invariant 4: No unrelated student context survives
    assert "students" not in r2.active_frame.active_entities.values()


def test_session_cleanup_interval_configuration(monkeypatch):
    """Verifies default cleanup interval is 60s and environment configuration can override it."""
    import importlib
    import app.core.config

    # Default interval verification
    settings_default = app.core.config.get_settings()
    assert settings_default.SESSION_CLEANUP_INTERVAL_SECONDS == 60

    # Environment configuration override
    monkeypatch.setenv("SESSION_CLEANUP_INTERVAL_SECONDS", "120")
    importlib.reload(app.core.config)
    settings_overridden = app.core.config.get_settings()
    assert settings_overridden.SESSION_CLEANUP_INTERVAL_SECONDS == 120

    # Clean teardown: restore original default
    monkeypatch.delenv("SESSION_CLEANUP_INTERVAL_SECONDS", raising=False)
    importlib.reload(app.core.config)
    settings_restored = app.core.config.get_settings()
    assert settings_restored.SESSION_CLEANUP_INTERVAL_SECONDS == 60


def test_fastapi_lifespan_task_lifecycle_and_clean_shutdown():
    """Verifies lifespan startup creates exactly one task, repeated entry reuses it, and shutdown cleanly cancels and awaits."""
    import asyncio
    import app.main as main_module
    from app.main import app as fastapi_app, lifespan

    async def scenario():
        # Pre-condition: global reference is clean
        assert main_module._cleanup_task is None

        # 1. Startup creates exactly one active cleanup task
        async with lifespan(fastapi_app):
            task1 = main_module._cleanup_task
            assert task1 is not None
            assert not task1.done()
            assert not task1.cancelled()

            # 2. Repeated nested/concurrent entry reuses active task without duplicates
            async with lifespan(fastapi_app):
                task2 = main_module._cleanup_task
                assert task2 is task1

        # 3. Shutdown cancels and awaits cleanup task
        assert main_module._cleanup_task is None
        assert task1.done()
        assert task1.cancelled()

        # 4. No pending cleanup tasks remain in the event loop
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        assert len(pending) == 0

    asyncio.run(scenario())


def test_fastapi_lifespan_repeated_sequential_cycles_no_orphans():
    """Verifies repeated sequential application lifespan cycles do not leave duplicate or orphaned tasks."""
    import asyncio
    import app.main as main_module
    from app.main import app as fastapi_app, lifespan

    async def scenario():
        # Cycle 1
        async with lifespan(fastapi_app):
            task_cycle1 = main_module._cleanup_task
            assert task_cycle1 is not None
            assert not task_cycle1.done()

        # Post-Cycle 1 assertion
        assert main_module._cleanup_task is None
        assert task_cycle1.done()
        assert task_cycle1.cancelled()

        # Cycle 2
        async with lifespan(fastapi_app):
            task_cycle2 = main_module._cleanup_task
            assert task_cycle2 is not None
            assert task_cycle2 is not task_cycle1
            assert not task_cycle2.done()

        # Post-Cycle 2 assertion
        assert main_module._cleanup_task is None
        assert task_cycle2.done()
        assert task_cycle2.cancelled()

        # Zero orphaned tasks remain
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        assert len(pending) == 0

    asyncio.run(scenario())

