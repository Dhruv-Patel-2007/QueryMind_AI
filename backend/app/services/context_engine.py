"""ContextMind Conversational Context Engine & Multi-Turn State Management.

QueryMind AI 2.0 - Phase 5: ContextMind Multi-Turn State Management.
Deterministic, rule-based, fully offline conversational context engine supporting:
- In-memory thread-safe session isolation with RLock
- Sliding TTL expiration with injectable clock
- Deterministic anaphora and follow-up query resolution
- Slot-based context merging and contradiction elimination
- Explicit context reset triggers and service-level resets
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
import threading
import time
from typing import Any, Callable, Dict, List, Literal, Optional, Set, Tuple
import uuid

from app.core.config import get_settings
from app.schemas.context import (
    ActiveFilterSchema,
    ActiveSortSchema,
    ContextFrameSchema,
    ContextResolveResponse,
    TurnRecordSchema,
)
from app.services.intent_classifier import get_intent_classifier
from app.services.schema_linker import get_schema_linker

settings = get_settings()

MAX_TURNS_PER_SESSION: int = 50

# Canonical academic department metadata lookup
DEPARTMENT_SYNONYMS: Dict[str, Tuple[str, str]] = {
    "ai": ("AI", "Artificial Intelligence"),
    "artificial intelligence": ("AI", "Artificial Intelligence"),
    "cs": ("CS", "Computer Science"),
    "computer science": ("CS", "Computer Science"),
    "ee": ("EE", "Electrical Engineering"),
    "electrical engineering": ("EE", "Electrical Engineering"),
    "me": ("ME", "Mechanical Engineering"),
    "mechanical engineering": ("ME", "Mechanical Engineering"),
    "math": ("MATH", "Mathematics"),
    "mathematics": ("MATH", "Mathematics"),
    "phy": ("PHY", "Physics"),
    "physics": ("PHY", "Physics"),
}

ENTITY_TABLE_MAP: Dict[str, str] = {
    "student": "students",
    "students": "students",
    "learner": "students",
    "learners": "students",
    "undergraduate": "students",
    "undergraduates": "students",
    "course": "courses",
    "courses": "courses",
    "subject": "courses",
    "subjects": "courses",
    "class": "courses",
    "classes": "courses",
    "instructor": "instructors",
    "instructors": "instructors",
    "faculty": "instructors",
    "faculties": "instructors",
    "teacher": "instructors",
    "teachers": "instructors",
    "professor": "instructors",
    "professors": "instructors",
    "prof": "instructors",
    "profs": "instructors",
    "department": "departments",
    "departments": "departments",
    "dept": "departments",
    "depts": "departments",
    "enrollment": "enrollments",
    "enrollments": "enrollments",
    "mark": "student_marks",
    "marks": "student_marks",
    "score": "student_marks",
    "scores": "student_marks",
    "assessment": "assessments",
    "assessments": "assessments",
}

RESET_PATTERN = re.compile(
    r"^\s*(clear\s+context|reset\s+context|reset|start\s+over|start\s+a\s+new\s+query|new\s+query)\s*[.?!]*$",
    re.IGNORECASE,
)

ANAPHORIC_PRONOUNS_PATTERN = re.compile(
    r"\b(their|them|those|these|that|this|the\s+same|same)\b",
    re.IGNORECASE,
)

FOLLOW_UP_MARKERS_PATTERN = re.compile(
    r"^(now|also|and|then|what\s+about|how\s+about)\b",
    re.IGNORECASE,
)


@dataclass
class ExtractedSlots:
    """Extracted query slots for context state updates."""
    primary_entity: Optional[str] = None
    all_entities: List[str] = field(default_factory=list)
    department_code: Optional[str] = None
    department_name: Optional[str] = None
    all_departments: List[Tuple[str, str]] = field(default_factory=list)
    metric: Optional[str] = None
    metric_modifier: Optional[str] = None
    sort_column: Optional[str] = None
    sort_direction: Literal["ASC", "DESC"] = "ASC"
    limit: Optional[int] = None
    filters: List[ActiveFilterSchema] = field(default_factory=list)
    has_pronoun: bool = False
    pronoun_token: Optional[str] = None
    is_replacement: bool = False
    replacement_token: Optional[str] = None
    is_list_query: bool = False


class SessionManager:
    """Thread-safe in-memory session manager with sliding TTL."""

    def __init__(
        self,
        ttl_seconds: Optional[int] = None,
        time_provider: Optional[Callable[[], float]] = None,
    ) -> None:
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else settings.CONTEXT_TTL_SECONDS
        self.time_provider = time_provider or time.time
        self._sessions: Dict[str, ContextFrameSchema] = {}
        self._lock = threading.RLock()

    def _now(self) -> float:
        return self.time_provider()

    def _to_iso(self, ts: float) -> str:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    def _parse_iso(self, iso_str: str) -> float:
        cleaned = iso_str.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned).timestamp()

    def get_session(self, session_id: str) -> Optional[ContextFrameSchema]:
        """Retrieves active session frame, automatically evicting if expired."""
        with self._lock:
            if session_id not in self._sessions:
                return None

            frame = self._sessions[session_id]
            expires_at_ts = self._parse_iso(frame.expires_at)
            if self._now() >= expires_at_ts:
                del self._sessions[session_id]
                return None

            return frame

    def create_or_get_session(self, session_id: str) -> ContextFrameSchema:
        """Retrieves existing active session, or creates a clean new frame."""
        with self._lock:
            existing = self.get_session(session_id)
            if existing is not None:
                return existing

            now_ts = self._now()
            created_iso = self._to_iso(now_ts)
            expires_iso = self._to_iso(now_ts + self.ttl_seconds)

            new_frame = ContextFrameSchema(
                session_id=session_id,
                created_at=created_iso,
                last_active=created_iso,
                expires_at=expires_iso,
                ttl_seconds=self.ttl_seconds,
                turn_count=0,
                active_entities={},
                active_filters=[],
                active_metric=None,
                active_group_by=[],
                active_order_by=None,
                active_limit=None,
                last_intent=None,
                last_query=None,
                last_resolved_query=None,
                turn_history=[],
            )
            self._sessions[session_id] = new_frame
            return new_frame

    def save_session(self, session_id: str, frame: ContextFrameSchema) -> None:
        """Saves session frame and refreshes sliding TTL."""
        with self._lock:
            now_ts = self._now()
            frame.last_active = self._to_iso(now_ts)
            frame.expires_at = self._to_iso(now_ts + self.ttl_seconds)
            self._sessions[session_id] = frame

    def reset_session(self, session_id: str) -> bool:
        """Explicitly resets and deletes a session context frame."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def clear_expired_sessions(self) -> int:
        """Prunes all expired sessions from memory."""
        with self._lock:
            now_ts = self._now()
            expired_keys = [
                sid
                for sid, frame in self._sessions.items()
                if now_ts >= self._parse_iso(frame.expires_at)
            ]
            for sid in expired_keys:
                del self._sessions[sid]
            return len(expired_keys)

    def clear_all_sessions(self) -> None:
        """Purges all sessions immediately (used for test teardown)."""
        with self._lock:
            self._sessions.clear()

    def session_count(self) -> int:
        """Returns total active non-expired sessions count."""
        with self._lock:
            self.clear_expired_sessions()
            return len(self._sessions)


class ContextMind:
    """Conversational Context Engine for QueryMind AI 2.0.
    
    Provides deterministic reference resolution, slot merging, contradiction handling,
    and thread-safe multi-turn conversational session management.
    """

    def __init__(
        self,
        session_manager: Optional[SessionManager] = None,
        ttl_seconds: Optional[int] = None,
        time_provider: Optional[Callable[[], float]] = None,
    ) -> None:
        self.session_manager = session_manager or SessionManager(
            ttl_seconds=ttl_seconds, time_provider=time_provider
        )
        self.schema_linker = get_schema_linker()
        self.intent_classifier = get_intent_classifier()
        self.max_turns_per_session: int = MAX_TURNS_PER_SESSION

    def is_reset_phrase(self, query: str) -> bool:
        """Detects explicit reset commands."""
        return bool(RESET_PATTERN.match(query.strip()))

    def detect_anaphoric_pronouns(self, query: str) -> List[str]:
        """Detects anaphoric pronouns and reference terms in query."""
        return ANAPHORIC_PRONOUNS_PATTERN.findall(query)

    def _extract_slots(self, query: str) -> ExtractedSlots:
        """Extracts candidate entities, filters, metrics, sorting, and limits from query."""
        slots = ExtractedSlots()
        query_lower = query.lower().strip()

        # Pronoun check
        pronouns = self.detect_anaphoric_pronouns(query)
        if pronouns:
            slots.has_pronoun = True
            slots.pronoun_token = pronouns[0].lower()

        # Replacement ("instead") check
        if re.search(r"\binstead\b", query, re.IGNORECASE):
            slots.is_replacement = True

        # Detect pure list query intent
        slots.is_list_query = bool(
            re.search(r"\b(list|show\s+all|get\s+all|display\s+all)\b", query_lower)
        )

        # Extract Department(s) via Schema Linker & Dictionary
        seen_dept_codes: Set[str] = set()
        schema_result = self.schema_linker.link_query(query)
        for val in schema_result.get("linked_values", []):
            if val.get("table_name") == "departments" and val.get("column_name") == "code":
                code = str(val.get("value")).upper()
                if code not in seen_dept_codes:
                    seen_dept_codes.add(code)
                    name = DEPARTMENT_SYNONYMS.get(code.lower(), (code, code))[1]
                    slots.all_departments.append((code, name))

        for alias, (code, name) in DEPARTMENT_SYNONYMS.items():
            if re.search(rf"\b{re.escape(alias)}\b", query_lower):
                if code not in seen_dept_codes:
                    seen_dept_codes.add(code)
                    slots.all_departments.append((code, name))

        if len(slots.all_departments) == 1:
            slots.department_code, slots.department_name = slots.all_departments[0]
            slots.filters.append(
                ActiveFilterSchema(
                    column="departments.code", operator="=", value=slots.department_code
                )
            )

        # Extract Entity Noun(s)
        seen_entity_tables: Set[str] = set()
        for word, table in ENTITY_TABLE_MAP.items():
            if re.search(rf"\b{re.escape(word)}\b", query_lower):
                seen_entity_tables.add(table)

        if len(seen_entity_tables) > 1:
            # If 'departments' was matched alongside specific department code(s) (e.g. "AI department"),
            # an anaphoric reference ("the same department"), or prepositional phrase ("in the ... department")
            if "departments" in seen_entity_tables and (
                len(slots.all_departments) > 0
                or re.search(r"\b(?:the\s+)?same\s+department[s]?\b", query_lower)
                or re.search(
                    r"\b(?:in|of|from)\s+(?:the\s+)?[a-zA-Z_]*\s*department[s]?\b", query_lower
                )
            ):
                seen_entity_tables.remove("departments")
            # If 'student_marks' was matched alongside 'students' (e.g. "student marks")
            if "student_marks" in seen_entity_tables and "students" in seen_entity_tables:
                seen_entity_tables.remove("student_marks")
            # If 'enrollments' was matched alongside 'students' or 'courses' (e.g. "student enrollments")
            if "enrollments" in seen_entity_tables and ("students" in seen_entity_tables or "courses" in seen_entity_tables):
                seen_entity_tables.remove("enrollments")

        slots.all_entities = sorted(list(seen_entity_tables))
        if len(slots.all_entities) == 1:
            slots.primary_entity = slots.all_entities[0]

        # Extract Metric
        if re.search(r"\battendance(?:\s+percentage|\s+rate)?\b", query_lower):
            slots.metric = "attendance"
        elif re.search(r"\b(?:cgpa|gpa|grade\s+point(?:\s+average)?)\b", query_lower):
            slots.metric = "cgpa"
        elif re.search(r"\b(?:marks?|scores?)\b", query_lower):
            slots.metric = "marks"
        elif re.search(r"\b(?:credits?|credit\s+hours?)\b", query_lower):
            slots.metric = "credits"
        elif re.search(r"\b(?:enrollment|enrolled|count)\b", query_lower):
            slots.metric = "enrollment_count"

        # If list query without explicit metric attributes, ensure metric is cleared
        if slots.is_list_query and not re.search(
            r"\b(attendance|cgpa|gpa|marks?|scores?|credits?)\b", query_lower
        ):
            slots.metric = None

        # Metric modifier
        if re.search(r"\b(?:average|mean|avg)\b", query_lower):
            slots.metric_modifier = "average"
        elif re.search(r"\b(?:total|sum)\b", query_lower):
            slots.metric_modifier = "total"
        elif re.search(r"\b(?:highest|max|maximum)\b", query_lower):
            slots.metric_modifier = "maximum"
        elif re.search(r"\b(?:lowest|min|minimum)\b", query_lower):
            slots.metric_modifier = "minimum"

        # Extract Sort
        sort_match = re.search(
            r"\b(?:sort|order)(?:\s+(?:them|those|these|the\s+same|same))?\s+by\s+([a-zA-Z_]+)(?:\s+(asc|ascending|desc|descending))?\b",
            query_lower,
        )
        if sort_match:
            slots.sort_column = sort_match.group(1).strip()
            direction = sort_match.group(2)
            slots.sort_direction = (
                "DESC" if direction and direction in ("desc", "descending") else "ASC"
            )
            # If sorting by attribute, don't confuse sort column with metric
            slots.metric = None
        elif re.search(r"\bhighest\s+([a-zA-Z_]+)\b", query_lower):
            match = re.search(r"\bhighest\s+([a-zA-Z_]+)\b", query_lower)
            slots.sort_column = match.group(1).strip()
            slots.sort_direction = "DESC"
        elif re.search(r"\blowest\s+([a-zA-Z_]+)\b", query_lower):
            match = re.search(r"\blowest\s+([a-zA-Z_]+)\b", query_lower)
            slots.sort_column = match.group(1).strip()
            slots.sort_direction = "ASC"

        # Extract Limit
        limit_match = re.search(r"\b(?:top|limit(?:\s+to)?|first)\s+(\d+)\b", query_lower)
        if limit_match:
            slots.limit = int(limit_match.group(1))

        return slots

    def _is_follow_up(
        self,
        query: str,
        frame: ContextFrameSchema,
        slots: ExtractedSlots,
    ) -> bool:
        """Determines if the current query is anaphoric / follow-up to prior context."""
        if frame.turn_count == 0 or not frame.active_entities:
            return False

        # Explicit reset is handled separately
        if self.is_reset_phrase(query):
            return False

        # Has anaphoric pronouns (their, them, those, these, that, this, the same, same)
        if slots.has_pronoun or self.detect_anaphoric_pronouns(query):
            return True

        # Has replacement "instead"
        if slots.is_replacement or re.search(r"\binstead\b", query, re.IGNORECASE):
            return True

        # Has reference to "same department"
        if re.search(r"\b(?:the\s+)?same\s+department[s]?\b", query, re.IGNORECASE):
            return True

        # Complete independent query specifying a different primary entity:
        # E.g. Turn 1 was "students", Turn 2 is "Now show instructors who joined after 2018."
        primary_table = frame.active_entities.get("primary_table")
        if slots.primary_entity and primary_table and slots.primary_entity != primary_table:
            return False

        # Complete independent list query specifying its own department without pronouns or replacement:
        # E.g. Turn 1 was "Show average CGPA of AI students.", Turn 2 is "Now list CS students."
        if (
            slots.is_list_query
            and slots.department_code
            and not slots.metric
            and not slots.is_replacement
        ):
            return False

        # Starts with sort/order or top/limit without mentioning a new subject
        if re.search(r"^\s*(?:sort|order|top|limit)\b", query, re.IGNORECASE):
            return True

        # If query is short fragment asking for metric (e.g. "attendance", "what is their cgpa", "cgpa")
        query_lower = query.lower().strip()
        if re.search(
            r"^(?:now\s+)?(?:show\s+)?(attendance|cgpa|marks|credits)[.?!]*$", query_lower
        ):
            return True

        # Has conversational question continuation ("what about", "how about")
        if re.search(r"^(what\s+about|how\s+about)\b", query.strip(), re.IGNORECASE):
            return True

        # If query starts with conversational discourse starter ("now", "also", "and", "then"):
        # If it does not specify a new entity or department, it modifies the active context
        if FOLLOW_UP_MARKERS_PATTERN.search(query.strip()):
            return True

        return False

    def _merge_slots(
        self,
        frame: ContextFrameSchema,
        slots: ExtractedSlots,
        is_follow_up: bool,
    ) -> Dict[str, Any]:
        """Merges extracted slots into active frame with strict contradiction resolution."""
        modifications: Dict[str, Any] = {}

        if not is_follow_up:
            # Independent query: reset active slots to fresh state
            frame.active_entities = {}
            frame.active_filters = []
            frame.active_metric = None
            frame.active_group_by = []
            frame.active_order_by = None
            frame.active_limit = None

            if slots.primary_entity:
                frame.active_entities["primary_table"] = slots.primary_entity
            if slots.department_code:
                frame.active_entities["department_code"] = slots.department_code
                frame.active_entities["department_name"] = slots.department_name
                frame.active_filters = [
                    ActiveFilterSchema(
                        column="departments.code", operator="=", value=slots.department_code
                    )
                ]
            if slots.metric:
                frame.active_metric = slots.metric
            if slots.sort_column:
                frame.active_order_by = ActiveSortSchema(
                    column=slots.sort_column, direction=slots.sort_direction
                )
            if slots.limit:
                frame.active_limit = slots.limit

            modifications["action"] = "new_topic_initialized"
            return modifications

        # --- Follow-Up Slot Merging ---
        # 1. Entity update / preservation
        if slots.primary_entity:
            if slots.primary_entity != frame.active_entities.get("primary_table"):
                modifications["entity_replaced"] = {
                    "old": frame.active_entities.get("primary_table"),
                    "new": slots.primary_entity,
                }
                frame.active_entities["primary_table"] = slots.primary_entity
        else:
            modifications["entity_preserved"] = frame.active_entities.get("primary_table")

        # 2. Department contradiction handling & override
        if slots.department_code:
            old_dept = frame.active_entities.get("department_code")
            if old_dept and old_dept != slots.department_code:
                modifications["department_override"] = {
                    "old": old_dept,
                    "new": slots.department_code,
                }
            frame.active_entities["department_code"] = slots.department_code
            frame.active_entities["department_name"] = slots.department_name

            # Evict existing department filter to prevent contradictory coexistence
            frame.active_filters = [
                f for f in frame.active_filters if f.column != "departments.code"
            ]
            frame.active_filters.append(
                ActiveFilterSchema(
                    column="departments.code", operator="=", value=slots.department_code
                )
            )
        elif "department_code" in frame.active_entities:
            modifications["department_preserved"] = frame.active_entities["department_code"]

        # 3. Metric update / preservation / clearing for pure list queries
        if slots.is_list_query and not slots.metric and not slots.is_replacement:
            if frame.active_metric is not None:
                modifications["metric_cleared"] = {
                    "old": frame.active_metric,
                    "new": None,
                    "reason": "list_query_reset",
                }
                frame.active_metric = None
        elif slots.metric:
            modifications["metric_updated"] = {
                "old": frame.active_metric,
                "new": slots.metric,
            }
            frame.active_metric = slots.metric
        elif frame.active_metric:
            modifications["metric_preserved"] = frame.active_metric

        # 4. Sort update / preservation
        if slots.sort_column:
            # Qualify sort column with entity table if known
            table = frame.active_entities.get("primary_table", "")
            qualified_col = f"{table}.{slots.sort_column}" if table else slots.sort_column
            frame.active_order_by = ActiveSortSchema(
                column=qualified_col, direction=slots.sort_direction
            )
            modifications["sort_updated"] = qualified_col
        elif frame.active_order_by:
            modifications["sort_preserved"] = frame.active_order_by.column

        # 5. Limit update / preservation
        if slots.limit:
            modifications["limit_updated"] = {"old": frame.active_limit, "new": slots.limit}
            frame.active_limit = slots.limit
        elif frame.active_limit:
            modifications["limit_preserved"] = frame.active_limit

        return modifications

    def _resolve_query_text(
        self,
        query: str,
        frame: ContextFrameSchema,
        slots: ExtractedSlots,
    ) -> str:
        """Generates an unambiguous standalone natural language query from context."""
        cleaned_query = query.strip()
        query_lower = cleaned_query.lower()

        # Case 1: Replacement with "instead" (e.g. "Now show CS students instead.")
        if slots.is_replacement or re.search(r"\binstead\b", query_lower):
            old_dept = frame.active_entities.get("department_code")
            new_dept = slots.department_code
            if old_dept and new_dept and old_dept != new_dept:
                if frame.last_resolved_query:
                    # Substitute the old department acronym with the new department acronym
                    resolved = re.sub(
                        rf"\b{re.escape(old_dept)}\b",
                        new_dept,
                        frame.last_resolved_query,
                        flags=re.IGNORECASE,
                    )
                    return resolved

            # Fallback synthesis for replacement
            entity = frame.active_entities.get("primary_table", "students")
            dept_code = slots.department_code or frame.active_entities.get("department_code", "")
            metric = frame.active_metric
            if metric:
                mod = slots.metric_modifier or "average"
                metric_name = metric.upper() if len(metric) <= 4 else metric
                return f"Show {mod} {metric_name} of {dept_code} {entity}."
            return f"Show {entity} in the {dept_code} department."

        # Case 2: Anaphoric pronoun + Sort (e.g. "Sort them by credits.")
        sort_match = re.search(
            r"^(?:now\s+)?(?:sort|order)\s+(?:them|those|these|the\s+same|same)?\s*by\s+([a-zA-Z_]+)(?:\s+(asc|ascending|desc|descending))?[.?!]*$",
            query_lower,
        )
        if sort_match or slots.sort_column:
            sort_attr = slots.sort_column or sort_match.group(1).lower()
            direction = slots.sort_direction
            base = (frame.last_resolved_query or "").rstrip(".?!")
            if not base:
                entity = frame.active_entities.get("primary_table", "items")
                dept_code = frame.active_entities.get("department_code")
                dept_str = f" in the {dept_code} department" if dept_code else ""
                base = f"Show {entity}{dept_str}"

            # Strip existing sorted by clause if present
            base = re.sub(r"\s+sorted\s+by\s+.*$", "", base, flags=re.IGNORECASE)
            dir_str = " descending" if direction == "DESC" else ""
            return f"{base} sorted by {sort_attr}{dir_str}."

        # Case 3: Reference to "those <entities> with/having <filter>" (e.g. "Show those courses with credits > 3")
        those_match = re.search(
            r"^(?:now\s+)?(?:show\s+)?(?:those|these)\s+([a-zA-Z_]+)\s+(with|where|having)\s+(.+)[.?!]*$",
            query_lower,
        )
        if those_match:
            entity = those_match.group(1)
            conj = those_match.group(2)
            cond = those_match.group(3).rstrip(".?!")
            dept_code = frame.active_entities.get("department_code")
            dept_str = f" in the {dept_code} department" if dept_code else ""
            return f"Show {entity}{dept_str} {conj} {cond}."

        # Case 4: Anaphoric pronoun + Metric (e.g. "Now show their attendance.", "Show their CGPA")
        pronoun_metric_match = re.search(
            r"^(?:now\s+)?(?:show|get|list|display|find|what\s+is)\s+(?:their|them)\s+(attendance|marks?|cgpa|gpa|credits?|scores?)(?:\s+(?:percentage|rate))?[.?!]*$",
            query_lower,
        )
        if pronoun_metric_match or (slots.pronoun_token in ("their", "them") and slots.metric):
            metric = slots.metric or pronoun_metric_match.group(1).lower()
            entity = frame.active_entities.get("primary_table", "students")
            dept_code = frame.active_entities.get("department_code")
            dept_str = f" in the {dept_code} department" if dept_code else ""
            return f"Show {metric} of {entity}{dept_str}."

        # Case 5: Reference to "the same department" (e.g. "Compare the same departments.")
        if re.search(r"\b(?:the\s+)?same\s+department[s]?\b", query_lower):
            dept_code = frame.active_entities.get("department_code")
            if dept_code:
                resolved = re.sub(
                    r"\b(?:the\s+)?same\s+department[s]?\b",
                    f"{dept_code} department",
                    cleaned_query,
                    flags=re.IGNORECASE,
                )
                resolved = re.sub(r"^(?:now\s+)?", "", resolved, flags=re.IGNORECASE).strip()
                if not resolved.endswith("."):
                    resolved += "."
                return resolved[0].upper() + resolved[1:]

        # Case 6: Limit / Ranking follow-up (e.g. "Top 5 by CGPA.", "Limit to 10")
        if slots.limit and not slots.primary_entity:
            entity = frame.active_entities.get("primary_table", "students")
            dept_code = frame.active_entities.get("department_code")
            dept_str = f" in the {dept_code} department" if dept_code else ""
            by_str = f" by {slots.sort_column.upper()}" if slots.sort_column else ""
            return f"Show top {slots.limit} {entity}{dept_str}{by_str}."

        # Case 7: General elliptical follow-up stripped of conversational discourse markers
        resolved = re.sub(r"^(?:now\s+|also\s+|and\s+|then\s+)", "", cleaned_query, flags=re.IGNORECASE).strip()
        if not resolved.endswith("."):
            resolved += "."
        return resolved[0].upper() + resolved[1:]

    def resolve_turn(self, session_id: str, query: str) -> ContextResolveResponse:
        """Resolves an incoming user query or follow-up against the conversational session.
        
        Enforces:
        - RFC 4122 UUID validation
        - Explicit context reset triggers
        - Anaphora resolution with clarification fallback
        - Context slot merging with contradiction elimination
        - Sliding TTL refresh upon valid interaction
        """
        # 1. UUID Validation
        try:
            val_uuid = uuid.UUID(session_id)
            canonical_session_id = str(val_uuid)
        except (ValueError, AttributeError, TypeError):
            raise ValueError(f"Invalid session UUID format: '{session_id}'. Must be a valid UUID string.")

        cleaned_query = query.strip()
        if not cleaned_query:
            raise ValueError("Query string cannot be empty or whitespace only.")

        # 2. Check Explicit Reset
        if self.is_reset_phrase(cleaned_query):
            self.session_manager.reset_session(canonical_session_id)
            return ContextResolveResponse(
                status="reset",
                session_id=canonical_session_id,
                original_query=cleaned_query,
                resolved_query=cleaned_query,
                was_follow_up=False,
                was_reset=True,
                active_frame=None,
                clarification_needed=False,
                clarification_message="Conversational context has been cleared.",
                turn_number=0,
            )

        # 3. Retrieve or Create Session Frame
        existing_frame = self.session_manager.get_session(canonical_session_id)
        is_fresh_session = existing_frame is None

        if is_fresh_session:
            frame = self.session_manager.create_or_get_session(canonical_session_id)
        else:
            # Work on existing frame
            frame = existing_frame

        # 4. Check for Unresolvable Pronoun in Empty/Fresh Context
        pronouns = self.detect_anaphoric_pronouns(cleaned_query)
        if pronouns and (is_fresh_session or frame.turn_count == 0 or not frame.active_entities):
            return ContextResolveResponse(
                status="clarification",
                session_id=canonical_session_id,
                original_query=cleaned_query,
                resolved_query=cleaned_query,
                was_follow_up=False,
                was_reset=False,
                active_frame=frame,
                clarification_needed=True,
                clarification_message=(
                    f"I could not resolve the reference '{pronouns[0]}' because there is no prior "
                    f"conversational context. Please specify which entity (e.g., students, courses, "
                    f"or instructors) you are referring to."
                ),
                turn_number=frame.turn_count,
            )

        # 5. Extract Query Slots & Detect Ambiguous Multiple Entities / Departments
        slots = self._extract_slots(cleaned_query)

        # Multiple departments guard: require explicit clarification rather than arbitrarily selecting first
        if len(slots.all_departments) > 1:
            dept_codes = [f"'{code}'" for code, _ in slots.all_departments]
            self.session_manager.save_session(canonical_session_id, frame)
            return ContextResolveResponse(
                status="clarification",
                session_id=canonical_session_id,
                original_query=cleaned_query,
                resolved_query=cleaned_query,
                was_follow_up=False,
                was_reset=False,
                active_frame=frame,
                clarification_needed=True,
                clarification_message=(
                    f"Your query specifies multiple departments ({', '.join(dept_codes)}). "
                    "QueryMind AI evaluates one department at a time. Please clarify which department you want to query."
                ),
                turn_number=frame.turn_count,
            )

        # Multiple primary entities guard: require explicit clarification rather than arbitrarily selecting first
        if len(slots.all_entities) > 1:
            entities_str = [f"'{ent}'" for ent in slots.all_entities]
            self.session_manager.save_session(canonical_session_id, frame)
            return ContextResolveResponse(
                status="clarification",
                session_id=canonical_session_id,
                original_query=cleaned_query,
                resolved_query=cleaned_query,
                was_follow_up=False,
                was_reset=False,
                active_frame=frame,
                clarification_needed=True,
                clarification_message=(
                    f"Your query references multiple entities ({', '.join(entities_str)}). "
                    "QueryMind AI operates on a single primary entity per turn. Please query one entity at a time."
                ),
                turn_number=frame.turn_count,
            )

        # 6. Determine Follow-Up Nature
        is_follow_up = self._is_follow_up(cleaned_query, frame, slots)

        # 7. Resolve Query Text
        if is_follow_up:
            resolved_query = self._resolve_query_text(cleaned_query, frame, slots)
        else:
            # Independent query: strip leading conversational discourse starters ("Now", "And", "Then", "Also")
            resolved = re.sub(
                r"^(?:now\s+|also\s+|and\s+|then\s+)", "", cleaned_query, flags=re.IGNORECASE
            ).strip()
            if resolved:
                resolved = resolved[0].upper() + resolved[1:]
            if resolved and not resolved.endswith((".", "?", "!")):
                resolved += "."
            resolved_query = resolved or cleaned_query

        # 8. Slot Merging & Contradiction Resolution
        modifications = self._merge_slots(frame, slots, is_follow_up)

        # 9. Classify Intent on Resolved Query
        intent_res = self.intent_classifier.predict(resolved_query)
        detected_intent = intent_res.get("predicted_intent", "GENERAL_QUERY")

        # 10. Update Session Frame
        frame.turn_count += 1
        frame.last_intent = detected_intent
        frame.last_query = cleaned_query
        frame.last_resolved_query = resolved_query

        turn_record = TurnRecordSchema(
            turn_id=frame.turn_count,
            timestamp=self.session_manager._to_iso(self.session_manager._now()),
            user_query=cleaned_query,
            resolved_query=resolved_query,
            intent=detected_intent,
            was_follow_up=is_follow_up,
            modifications=modifications,
        )
        frame.turn_history.append(turn_record)

        # Enforce history bound: retain only the most recent MAX_TURNS_PER_SESSION turns (turn_count represents total lifetime turns)
        if len(frame.turn_history) > self.max_turns_per_session:
            frame.turn_history = frame.turn_history[-self.max_turns_per_session:]

        # 11. Persist Session Frame & Refresh Sliding TTL
        self.session_manager.save_session(canonical_session_id, frame)

        return ContextResolveResponse(
            status="success",
            session_id=canonical_session_id,
            original_query=cleaned_query,
            resolved_query=resolved_query,
            was_follow_up=is_follow_up,
            was_reset=False,
            active_frame=frame,
            clarification_needed=False,
            clarification_message=None,
            turn_number=frame.turn_count,
        )

    def get_frame(self, session_id: str) -> Optional[ContextFrameSchema]:
        """Retrieves active context frame for session if present and unexpired."""
        try:
            val = uuid.UUID(session_id)
            canonical_session_id = str(val)
        except (ValueError, AttributeError, TypeError):
            raise ValueError(f"Invalid session UUID: '{session_id}'.")

        return self.session_manager.get_session(canonical_session_id)

    def reset_session(self, session_id: str) -> bool:
        """Service-level programmatic session reset."""
        try:
            val = uuid.UUID(session_id)
            canonical_session_id = str(val)
        except (ValueError, AttributeError, TypeError):
            raise ValueError(f"Invalid session UUID: '{session_id}'.")

        return self.session_manager.reset_session(canonical_session_id)


# Cached singleton instance
_cached_context_engine: Optional[ContextMind] = None


def get_context_engine() -> ContextMind:
    """Returns cached singleton ContextMind engine instance."""
    global _cached_context_engine
    if _cached_context_engine is None:
        _cached_context_engine = ContextMind()
    return _cached_context_engine
