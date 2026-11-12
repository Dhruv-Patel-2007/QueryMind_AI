# QueryMind AI 2.0 — Logical Input Design (LID)
*Deliverable Document 1 | Updated — Phase 5 ContextMind Conversational Context Engine*

> **Status:** Phase 5 Implemented & Verified Specification  
> **Phase Milestone:** Phase 5 (ContextMind Multi-Turn State Management)  
> **Note:** This document formalizes the input structures, constraints, validation rules, field domains, database boundary checks, NLP diagnostic payload schemas, Schema Linking & Join Graph specifications, and ContextMind conversational context engine contracts for QueryMind AI 2.0.


---

## 1. User Interface Inputs (Natural Language Query)

| Field Name | Data Type | Requirement | Character Limit | Allowed Characters | Validation Rule | Error Message |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `query` | `string` | Mandatory | 3 to 500 chars | UTF-8 printable text, alphanumeric, standard punctuation (`?`, `.`, `,`, `'`, `"`, `-`, `_`, `%`) | Min length 3, max length 500; must not contain null bytes or control characters | *"Query must be between 3 and 500 characters."* |
| `session_id` | `UUID v4` | Optional / Auto | 36 chars | Standard UUID format (`8-4-4-4-12` hex) | Valid UUID string matching regex `^[0-9a-fA-F-]{36}$` | *"Invalid session identifier format."* |

---

## 2. Academic Database Logical Input Design & Column Constraints

The system implements 9 normalized tables with strict input validation, domain check constraints, and foreign key boundaries:

### 2.1 Table: `departments`
- `department_id`: `INTEGER PRIMARY KEY AUTOINCREMENT`
- `name`: `VARCHAR(100) NOT NULL UNIQUE` (Min 2 chars, Max 100 chars)
- `code`: `VARCHAR(10) NOT NULL UNIQUE` (Uppercase acronym: `AI`, `CS`, `EE`, `ME`, `MATH`)
- `established_year`: `INTEGER NOT NULL` (`CHECK(established_year BETWEEN 1800 AND 2026)`)
- `building`: `VARCHAR(50) NOT NULL` (Campus structure name)

### 2.2 Table: `students`
- `student_id`: `INTEGER PRIMARY KEY AUTOINCREMENT`
- `department_id`: `INTEGER NOT NULL REFERENCES departments(department_id) ON DELETE CASCADE`
- `roll_number`: `VARCHAR(20) NOT NULL UNIQUE` (Pattern: `^[0-9]{4}-[A-Z]{2,5}-[0-9]{3}$`)
- `first_name`: `VARCHAR(50) NOT NULL` (Fictional alphabetic name)
- `last_name`: `VARCHAR(50) NOT NULL` (Fictional alphabetic family name)
- `enrollment_year`: `INTEGER NOT NULL` (`CHECK(enrollment_year BETWEEN 2000 AND 2026)`)
- `current_semester`: `INTEGER NOT NULL` (`CHECK(current_semester BETWEEN 1 AND 12)`)
- `cgpa`: `FLOAT NOT NULL` (`CHECK(cgpa >= 0.00 AND cgpa <= 4.00)`)
- `academic_status`: `VARCHAR(20) NOT NULL` (`CHECK(academic_status IN ('Active', 'Probation', 'Graduated', 'Suspended'))`)

### 2.3 Table: `instructors`
- `instructor_id`: `INTEGER PRIMARY KEY AUTOINCREMENT`
- `department_id`: `INTEGER NOT NULL REFERENCES departments(department_id) ON DELETE CASCADE`
- `first_name`: `VARCHAR(50) NOT NULL`
- `last_name`: `VARCHAR(50) NOT NULL`
- `designation`: `VARCHAR(50) NOT NULL` (`CHECK(designation IN ('Professor', 'Associate Professor', 'Assistant Professor', 'Senior Lecturer', 'Lecturer'))`)
- `joining_year`: `INTEGER NOT NULL` (`CHECK(joining_year BETWEEN 1950 AND 2026)`)

### 2.4 Table: `courses`
- `course_id`: `INTEGER PRIMARY KEY AUTOINCREMENT`
- `department_id`: `INTEGER NOT NULL REFERENCES departments(department_id) ON DELETE CASCADE`
- `course_code`: `VARCHAR(20) NOT NULL UNIQUE` (e.g., `CS101`, `AI301`, `MATH201`)
- `course_name`: `VARCHAR(100) NOT NULL`
- `credits`: `INTEGER NOT NULL` (`CHECK(credits BETWEEN 1 AND 6)`)
- `course_level`: `INTEGER NOT NULL` (`CHECK(course_level IN (100, 200, 300, 400, 500))`)

### 2.5 Table: `terms`
- `term_id`: `INTEGER PRIMARY KEY AUTOINCREMENT`
- `term_name`: `VARCHAR(50) NOT NULL UNIQUE` (e.g., `Fall 2024`)
- `academic_year`: `INTEGER NOT NULL`
- `semester_type`: `VARCHAR(20) NOT NULL` (`CHECK(semester_type IN ('Fall', 'Spring', 'Summer'))`)
- `start_date`: `DATE NOT NULL` (`CHECK(start_date < end_date)`)
- `end_date`: `DATE NOT NULL`

### 2.6 Table: `course_offerings`
- `offering_id`: `INTEGER PRIMARY KEY AUTOINCREMENT`
- `course_id`: `INTEGER NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE`
- `instructor_id`: `INTEGER NOT NULL REFERENCES instructors(instructor_id) ON DELETE CASCADE`
- `term_id`: `INTEGER NOT NULL REFERENCES terms(term_id) ON DELETE CASCADE`
- `section`: `VARCHAR(10) NOT NULL` (e.g., `'A'`, `'B'`)
- `classroom`: `VARCHAR(50) NOT NULL`
- **Constraint:** `UNIQUE(course_id, term_id, section)` prevents duplicate section scheduling.

### 2.7 Table: `enrollments`
- `enrollment_id`: `INTEGER PRIMARY KEY AUTOINCREMENT`
- `student_id`: `INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE`
- `offering_id`: `INTEGER NOT NULL REFERENCES course_offerings(offering_id) ON DELETE CASCADE`
- `attendance_percentage`: `FLOAT NOT NULL` (`CHECK(attendance_percentage BETWEEN 0.0 AND 100.0)`)
- `final_grade`: `VARCHAR(5) NULLABLE` (`CHECK(final_grade IN ('A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'F'))`)
- `grade_points`: `FLOAT NULLABLE` (`CHECK(grade_points BETWEEN 0.0 AND 4.0)`)
- `enrollment_status`: `VARCHAR(20) NOT NULL` (`CHECK(enrollment_status IN ('Enrolled', 'Completed', 'Dropped'))`)
- **Constraint:** `UNIQUE(student_id, offering_id)` ensures idempotent single enrollment per offering.

### 2.8 Table: `assessments`
- `assessment_id`: `INTEGER PRIMARY KEY AUTOINCREMENT`
- `offering_id`: `INTEGER NOT NULL REFERENCES course_offerings(offering_id) ON DELETE CASCADE`
- `title`: `VARCHAR(100) NOT NULL` (e.g., `Midterm Examination`)
- `assessment_type`: `VARCHAR(30) NOT NULL` (`CHECK(assessment_type IN ('Quiz', 'Assignment', 'Midterm', 'Final', 'Project'))`)
- `max_marks`: `FLOAT NOT NULL` (`CHECK(max_marks > 0.0)`)
- `weightage_percent`: `FLOAT NOT NULL` (`CHECK(weightage_percent BETWEEN 0.0 AND 100.0)`)

### 2.9 Table: `student_marks`
- `mark_id`: `INTEGER PRIMARY KEY AUTOINCREMENT`
- `assessment_id`: `INTEGER NOT NULL REFERENCES assessments(assessment_id) ON DELETE CASCADE`
- `enrollment_id`: `INTEGER NOT NULL REFERENCES enrollments(enrollment_id) ON DELETE CASCADE`
- `marks_obtained`: `FLOAT NOT NULL` (`CHECK(marks_obtained >= 0.0)`)
- **Constraint:** `UNIQUE(assessment_id, enrollment_id)` ensures at most one recorded mark per assessment per student.

---

## 3. Boundary & Edge Case Protections

1. **Foreign Key Enforceability**: SQLite runtime connection listeners execute `PRAGMA foreign_keys = ON;` on every connection. Inserting an entity with a non-existent foreign reference raises an immediate `sqlite3.IntegrityError`.
2. **Read-Only Runtime Enforcement**: The analytical runtime engine utilizes `sqlite:///file:.../academic.db?mode=ro&uri=true` and executes `PRAGMA query_only = ON;`. Any attempt to execute `INSERT`, `UPDATE`, `DELETE`, or `DROP` triggers `sqlite3.OperationalError: attempt to write a readonly database`.
3. **Query Execution Timeout**: A native SQLite C-API progress handler monitors execution opcodes every 1,000 instructions and aborts long-running queries exceeding 3,000 milliseconds.
4. **Boundary Range Check Rejection**: Numeric scores (CGPA, marks, attendance, weightage, semester) outside permissible mathematical bounds fail transaction validation and trigger immediate rollbacks.
5. **Cross-Offering Student Mark Integrity**: Enforced via native SQLite database triggers `trg_student_marks_integrity_insert` and `update`. An assessment and enrollment linked in `student_marks` must belong to the exact same `offering_id`; mismatched offering combinations are aborted with `sqlite3.IntegrityError: Cross-offering integrity violation`.
6. **Marks Upper Boundary Enforcement**: Enforced via database triggers `trg_student_marks_integrity_insert` and `update`. Marks obtained cannot exceed `assessment.max_marks`. Any insert or update exceeding `max_marks` is aborted with `sqlite3.IntegrityError: Marks boundary violation`.
7. **Cumulative Assessment Weightage Integrity**: Enforced via database triggers `trg_assessments_weightage_insert` and `update`. The cumulative sum of `weightage_percent` for all assessments in an offering cannot exceed 100 percent.

---

## 4. NLP Preprocessing & Intent Inspector Logical Input / Output Design

Implemented in `backend/app/schemas/nlp.py` and served via `GET /api/nlp/inspect` and `POST /api/nlp/inspect`.

### 4.1 Request Payload: `NLPInspectRequest`
| Field Name | Type | Constraint | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `query` | `string` | Min: 1 char, Max: 500 chars | Natural language query targeting the Academic schema | `"What is the average CGPA of students in the AI department?"` |

### 4.2 Response Payload: `NLPInspectResponse`
| Field Name | Type | Description |
| :--- | :--- | :--- |
| `status` | `string` | Execution status indicator (`"success"`) |
| `query` | `string` | Input query processed |
| `preprocessing` | `NLPPreprocessData` | Preprocessing breakdown (tokens, lemmas, POS tags, word/char n-grams) |
| `intent` | `IntentClassificationData` | Classification metrics (predicted intent, confidence, margin, probabilities, ambiguity flags) |
| `execution_time_ms` | `float` | Pipeline execution latency in milliseconds ($< 10\text{ ms}$) |

### 4.3 Preprocessing Sub-Structure: `NLPPreprocessData`
- `raw_query`: `str` — Original user input string.
- `normalized_query`: `str` — Control-character stripped, whitespace-normalized string.
- `tokens`: `List[str]` — Regex extracted word, contraction, and punctuation tokens.
- `lemmas`: `List[str]` — Morphologically reduced base dictionary headwords.
- `pos_tags`: `List[Tuple[str, str]]` — Ordered list of `(token, tag)` pairs across **30 supported Penn Treebank-style POS tags (23 grammatical tags + 7 punctuation/symbol tags)** emitted via deterministic rule-based approximation.
- `word_ngrams`: `Dict[str, List[str]]` — Dictionary containing `"unigrams"`, `"bigrams"`, and `"trigrams"`.
- `char_ngrams`: `List[str]` — Sliding character 3-grams for fuzzy schema linking.

### 4.4 Intent Sub-Structure: `IntentClassificationData`
- `predicted_intent`: `str` — One of 7 approved classes (`AGGREGATE`, `RANKING`, `FILTER`, `COMPARISON`, `TREND`, `GENERAL_QUERY`, `WHAT_IF`).
- `confidence`: `float` ($0.0 \le c \le 1.0$) — Softmax class probability of the top-1 predicted class (uncalibrated nominal score).
- `margin`: `float` ($0.0 \le m \le 1.0$) — Probability gap between top-1 and top-2 ranked classes.
- `probabilities`: `Dict[str, float]` — Full Softmax probability distribution across all 7 categories ($\sum P \approx 1.0$).
- `is_ambiguous`: `bool` — `True` if confidence $< 0.55$, margin $< 0.15$, empty query, or out-of-domain.

- `ambiguity_reason`: `Optional[str]` — `"LOW_CONFIDENCE"`, `"NARROW_MARGIN"`, `"OUT_OF_DOMAIN"`, or `"EMPTY_QUERY"`.
- `top_intents`: `List[Tuple[str, float]]` — All 7 intents sorted descending by probability.

---

## 5. Schema Linking & Join Graph Logical Input / Output Design

Implemented in `backend/app/schemas/schema_linker.py` and served via `/api/schema/catalog`, `/api/schema/link`, and `/api/schema/join-path`.

### 5.1 Request Payload: `SchemaLinkRequest`
| Field Name | Type | Constraint | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `query` | `string` | Min: 1 char, Max: 500 chars | Natural language query to be resolved against schema entities | `"Find attendance and CGPA of learners in AI department"` |

### 5.2 Response Payload: `SchemaLinkResponse`
| Field Name | Type | Description |
| :--- | :--- | :--- |
| `status` | `string` | Execution status indicator (`"success"`) |
| `query` | `string` | Echo of processed query |
| `linked_tables` | `List[str]` | Resolved database table names (e.g. `["departments", "enrollments", "students"]`) |
| `linked_columns` | `Dict[str, List[LinkedColumnMatch]]` | Dictionary mapping table names to matched column objects |
| `linked_values` | `List[LinkedValueMatch]` | Extracted literal filters, regex identifiers, or categorical values |
| `unsupported_entities`| `List[str]` | Flagged out-of-domain terms (e.g. `["hostel", "cafeteria"]`) |
| `is_ambiguous` | `bool` | True if multiple candidate columns, unsupported terms, or multiple join paths exist |
| `ambiguity_reason` | `Optional[str]` | Reason (`"MULTIPLE_COLUMN_CANDIDATES"`, `"UNSUPPORTED_ENTITIES"`, `"MULTIPLE_JOIN_PATHS"`) |
| `ambiguous_candidates`| `List[AmbiguousCandidateSchema]` | Alternative plausible interpretations requiring user disambiguation |
| `join_path` | `JoinPathResponse` | Complete resolved Steiner join tree across all linked tables |
| `execution_time_ms` | `float` | Pipeline execution latency in milliseconds ($< 5\text{ ms}$) |

### 5.3 Request Payload: `JoinPathRequest`
| Field Name | Type | Constraint | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `tables` | `List[str]` | Min: 1 item | List of target database tables to connect | `["departments", "students", "courses"]` |
| `preferred_anchor` | `Optional[str]` | Valid table name | Optional starting anchor table | `"departments"` |

---

## 6. ContextMind Conversational Context Engine Logical Input Design

Formal specifications for Phase 5 multi-turn state management, session frames, and `/api/context` contracts:

### 6.1 Request Payload: `ContextResolveRequest`
| Field Name | Type | Requirement | Constraints | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `session_id` | `string` | Mandatory | RFC 4122 UUID (`^[0-9a-fA-F-]{36}$`) | Unique conversational session identifier | `"3fa85f64-5717-4562-b3fc-2c963f66afa6"` |
| `query` | `string` | Mandatory | Min 1 char, Max 500 chars | Raw user input query or follow-up question | `"Now show their attendance."` |

### 6.2 Response Payload: `ContextResolveResponse`
| Field Name | Type | Description |
| :--- | :--- | :--- |
| `status` | `string` | Execution status: `"success"`, `"clarification"`, or `"reset"` |
| `session_id` | `string` | Session UUID echoing request identifier |
| `original_query` | `string` | Raw user input query |
| `resolved_query` | `string` | Unambiguous standalone natural language query produced by ContextMind |
| `was_follow_up` | `bool` | True if turn resolved anaphoric referents or inherited context from prior turns |
| `was_reset` | `bool` | True if turn triggered explicit context reset (`"clear context"`, `"reset"`) |
| `active_frame` | `Optional[ContextFrameSchema]` | Full serialized context frame post-resolution (or `None` on reset) |
| `clarification_needed` | `bool` | True if disambiguation is required (unresolvable pronoun, multiple departments, or multiple primary entities) |
| `clarification_message` | `Optional[str]` | Human-readable clarification prompt if `clarification_needed=True` |
| `turn_number` | `int` | Monotonically increasing sequential turn counter for the session |

### 6.3 Context Frame State Structure: `ContextFrameSchema`
| Field Name | Type | Constraints | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `session_id` | `string` | RFC 4122 UUID | Active session identifier | `"3fa85f64-5717-4562-b3fc-2c963f66afa6"` |
| `created_at` | `string` | ISO 8601 UTC | Session initial creation timestamp | `"2026-11-07T10:30:00Z"` |
| `last_active` | `string` | ISO 8601 UTC | Timestamp of most recent turn interaction | `"2026-11-07T10:32:15Z"` |
| `expires_at` | `string` | ISO 8601 UTC | Sliding TTL expiration timestamp | `"2026-11-07T10:42:15Z"` |
| `ttl_seconds` | `int` | Default: 600 | Inactivity timeout window in seconds | `600` |
| `turn_count` | `int` | $\ge 0$ | Total lifetime completed conversational turns (monotonically incremented, unaffected by history trimming) | `2` |
| `active_entities` | `Dict[str, Any]` | Schema-bound | Active referenced entities (`primary_table`, `department_code`) | `{"primary_table": "students", "department_code": "AI"}` |
| `active_filters` | `List[ActiveFilterSchema]`| Valid columns | List of active SQL filters (`column`, `operator`, `value`) | `[{"column": "departments.code", "operator": "=", "value": "AI"}]` |
| `active_metric` | `Optional[str]` | Domain metrics | Active aggregation/analytical metric | `"attendance"`, `"cgpa"` |
| `active_group_by`| `List[str]` | Valid columns | Grouping relational attributes | `["departments.name"]` |
| `active_order_by`| `Optional[ActiveSortSchema]`| Valid column | Active sorting attribute and direction | `{"column": "courses.credits", "direction": "ASC"}` |
| `active_limit` | `Optional[int]` | Integer $> 0$ | Active row limit for ranking | `5` |
| `last_intent` | `Optional[str]` | Blueprint intents | Intent classification of most recent resolved query | `"AGGREGATE"` |
| `last_query` | `Optional[str]` | String | Previous raw user query | `"Now show their attendance."` |
| `last_resolved_query`| `Optional[str]` | String | Previous resolved query | `"Show attendance of students in the AI department."` |
| `turn_history` | `List[TurnRecordSchema]`| Max 50 turns | Sequential turn audit trail strictly bounded to most recent 50 turns (`MAX_TURNS_PER_SESSION = 50`) | `[...]` |

### 6.4 Response Payload: `ContextResetResponse`
| Field Name | Type | Description |
| :--- | :--- | :--- |
| `status` | `string` | Execution confirmation (`"success"`) |
| `session_id` | `string` | Reset session UUID |
| `message` | `string` | Informational confirmation of memory purge |



