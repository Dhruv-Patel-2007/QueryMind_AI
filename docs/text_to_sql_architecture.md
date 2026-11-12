# QueryMind AI 2.0: Phase 6 Architecture Specification
## Deterministic Text-to-SQL Generator, SQLGlot Security Validator, & Hardened QueryDoctor

**Status:** ARCHITECTURE SPECIFICATION (PENDING APPROVAL)  
**Implementation Phase:** Phase 6.0  
**Implementation Authorization:** NOT GRANTED  
**Classification:** STRICTLY DOCUMENTATION ONLY  
**Supercedes:** Phase 6 Planning Drafts v1.0.0 through v2.9.0  
**Authoritative Relational Target:** SQLite 3 (`backend/data/academic.db`, SHA-256: `a5f726089b813ab44628f875c3a60ca152712840cb9f13c0a03152cd8e06f11d`)

---

## 1. Project Scope and Objectives

### 1.1 Architectural Vision
QueryMind AI 2.0 is an enterprise-grade conversational Text-to-SQL system designed for higher education institutions. The system enables non-technical academic stakeholders (administrators, registrars, department chairs, and students) to query relational academic data using natural language, receiving deterministic, verifiable SQL and tabular data.

### 1.2 Phase 6 Objectives
Phase 6 bridges conversational understanding and database execution. It consumes the contextual, linguistic, and schema-linked outputs from Phases 3–5 to synthesize, validate, execute, and self-heal SQL queries:
1. **Deterministic SQL Synthesis**: Translate the resolved intent, schema links, active slots, and conversational filters into structured Query Plan Intermediate Representations (`QueryPlanIR`), compiling them into SQLite-dialect SQL via an AST expression builder.
2. **Zero-Trust SQL Security Validation**: Intercept and validate all generated SQL queries using an in-memory SQLGlot AST pipeline before database submission. Enforce strict scope-aware column resolution, table alias hiding, unauthorized function blocking, bare wildcard prevention, placeholder binding verification, and Option A tautology/contradiction prohibition.
3. **Hardened 1-Step QueryDoctor**: Provide a strictly bounded, non-recursive self-healing engine capable of diagnosing and repairing eligible syntax or schema omissions (e.g., missing `GROUP BY` columns) in at most one attempt, while instantly hard-rejecting security violations.
4. **Isolated Read-Only Execution**: Execute validated queries exclusively across a hardened SQLite engine with C-level progress handlers (3.0s timeout), `mode=ro`, and `PRAGMA query_only = ON`.

---

## 2. Phase 6 Architecture Overview

The Phase 6 pipeline operates as a deterministic, unidirectional state machine with an isolated single-iteration healing loop.

```
 [ User Natural Language Query / Follow-up ]
                      │
                      ▼
 [ Phase 3: NLP Preprocessor & Intent Classifier ]
                      │
                      ▼
 [ Phase 4: Semantic Schema Linker & JoinGraph ]
                      │
                      ▼
 [ Phase 5: ContextMind Multi-Turn State Tracking ]
                      │
                      ▼
 ┌─────────────────────────────────────────────────────────┐
 │               PHASE 6: TEXT-TO-SQL PIPELINE             │
 │                                                         │
 │  1. QueryPlanner ─────────────────────────────────────┐ │
 │     • Ingests Context Frame & Resolved Query          │ │
 │     • Emits Validated QueryPlanIR                     │ │
 │                                                       ▼ │
 │  2. SQLGenerator                                        │ │
 │     • AST Assembly via SQLGlot                        │ │
 │     • Parameter Registry & Anchor Join Selection      │ │
 │     • Emits Raw Parameterized SQL & Bindings Map      │ │
 │                                                       │ │
 │  3. SQLSecurityValidator (ASTScope Traversal) ◄─────┐ │ │
 │     • Table/Column Allowlist Verification           │ │ │
 │     • Alias Hiding & Scope Resolution               │ │ │
 │     • Tautology / Contradiction Prohibition         │ │ │
 │     • Zero-Trust Placeholder Verification           │ │ │
 │     │                                               │ │ │
 │     ├─► [ Security Violation ] ──► Hard Rejection   │ │ │
 │     └─► [ Passed Security ]                         │ │ │
 │                │                                    │ │ │
 │                ▼                                    │ │ │
 │  4. QueryExecutor (Read-Only SQLite Engine)         │ │ │
 │     │                                               │ │ │
 │     ├─► [ Runtime Error ] ──► QueryDoctor ──────────┘ │ │
 │     │                         (Max 1 Repair Attempt)  │ │
 │     ▼                                                   │
 │  5. QueryResultPayload (Tabular Data & Grain Metadata)  │
 └─────────────────────────────────────────────────────────┘
```

---

## 3. System Components and Responsibilities

| Component | Module Name | Phase Subphase | Implementation Status | Core Responsibility |
| :--- | :--- | :--- | :--- | :--- |
| **QueryPlanner** | `app.services.query_plan_ir` | Phase 6.1 | `PLANNED / NOT IMPLEMENTED` | Validates slots and builds typed `QueryPlanIR`. Enforces cross-field consistency. |
| **ParameterRegistry**| `app.services.parameter_registry` | Phase 6.1 | `PLANNED / NOT IMPLEMENTED` | Single source of truth for parameterized literals (`:param_0`, `:param_1`). |
| **SQLGenerator** | `app.services.sql_generator` | Phase 6.2 | `PLANNED / NOT IMPLEMENTED` | Converts `QueryPlanIR` into parameter-bound SQLite AST using SQLGlot. |
| **SQLSecurityValidator**| `app.services.sql_validator` | Phase 6.3 | `PLANNED / NOT IMPLEMENTED` | Recursively validates AST nodes using `ASTScope`. Enforces security policies. |
| **QueryDoctor** | `app.services.query_doctor` | Phase 6.4 | `PLANNED / NOT IMPLEMENTED` | Performs 1-step repair for eligible non-security errors. Zero repair on security faults. |
| **QueryExecutor** | `app.services.query_executor` | Phase 6.5 | `PLANNED / NOT IMPLEMENTED` | Dispatches parameter-bound SQL to `read_only_engine` with row truncation guards. |
| **ContextMind** | `app.services.context_engine` | Phase 5.0 | `VERIFIED IN EXISTING SOURCE` | Maintains multi-turn context frames, slot inheritance, and follow-up resolutions. |
| **SchemaLinker** | `app.services.schema_linker` | Phase 4.0 | `VERIFIED IN EXISTING SOURCE` | Introspects catalog and resolves entities to tables and columns. |
| **JoinGraph** | `app.services.schema_linker` | Phase 4.0 | `VERIFIED IN EXISTING SOURCE` | 9-vertex, 11-edge relational graph calculating shortest foreign-key join paths. |

---

## 4. Query Planner and Intermediate Representation (QueryPlanIR)

To prevent unvalidated strings from propagating into SQL generation, the planner produces a strongly typed intermediate representation:

```python
class QueryPlanIR(BaseModel):
    """Immutable, statically validated logical query representation."""
    model_config = ConfigDict(frozen=True)

    intent: str
    anchor_relation: str
    relation_instances: List[RelationInstance]
    projections: List[ProjectionIR]
    joins: List[JoinIR]
    predicates: List[PredicateIR]
    group_by: List[str]
    having: List[HavingIR]
    order_by: List[OrderByIR]
    limit: Optional[int]
    offset: Optional[int]
    parameter_registry: ParameterRegistry
```

### 4.1 Cross-Field Validation Invariants
The `QueryPlanIR` validator enforces:
1. **Unique Instance IDs & Aliases**: Every relation instance in the query must possess a unique identifier and alias.
2. **Anchor Invariant**: `anchor_relation` must exist in `relation_instances`.
3. **Column Resolution**: Every referenced column must exist in the authoritative database catalog for that relation instance.
4. **Join Endpoint Legality**: Every join must link two declared relation instances across an authorized foreign-key relationship.
5. **Aggregate/Grouping Validity**: If aggregate projections are present alongside non-aggregate columns, all non-aggregate columns must be explicitly present in `group_by`.
6. **Limit Constraint Validity**: If `limit` is specified, it must satisfy `limit >= 1`. Explicit `LIMIT 0`, negative numbers, or non-integer limits are strictly rejected during `QueryPlanIR` validation (`status="error"`, message: `"Invalid LIMIT: must be a positive integer >= 1"`). Zero database queries execute.

---

## 5. SQL Generator

The `SQLGenerator` compiles a `QueryPlanIR` into an AST expression using SQLGlot 30.30.0.

### 5.1 Compilation Rules
1. **Deterministic Clause Ordering**: Output queries strictly follow `SELECT ... FROM ... [JOIN ...] [WHERE ...] [GROUP BY ...] [HAVING ...] [ORDER BY ...] [LIMIT ...]`.
2. **Qualified References**: All column references in multi-table queries must be qualified with their declared table alias (e.g., `s.roll_number`, `c.course_code`).
3. **Parameter Placeholder Emission**: All literal values in filters must be extracted into named parameters (`:param_0`, `:param_1`). No raw strings or numbers are concatenated into the SQL text.
4. **Deterministic Ordering**: Every ranking or top-N query (`LIMIT N`) must append a verified unique tie-breaker to ensure query determinism.

---

## 6. SQLGlot-Based Security Validator

The `SQLSecurityValidator` intercepts SQL strings prior to database execution. It parses the SQL into an AST via `sqlglot.parse_one(sql, read="sqlite")` and executes a recursive tree traversal using scoped lexical environments (`ASTScope`).

### 6.1 ASTScope Hierarchy & Alias Hiding
When a table is aliased (e.g., `FROM students AS s`), SQL semantics dictate that the original table name `students` is hidden from the query block's column qualification scope.
- `SELECT s.roll_number FROM students AS s` $\rightarrow$ **VALID**.
- `SELECT students.roll_number FROM students AS s` $\rightarrow$ **REJECTED** (`Unknown table qualifier 'students'`).

### 6.2 Scope Traversal Algorithm
```python
class ASTScope:
    def __init__(self, parent: Optional["ASTScope"] = None):
        self.parent = parent
        self.visible_qualifiers: dict[str, str] = {}  # alias -> canonical_table
        self.cte_scope: dict[str, set[str]] = {}      # cte_name -> set(output_columns)
        if parent:
            self.cte_scope.update(parent.cte_scope)

    def resolve_column(self, col_name: str, qualifier: Optional[str]) -> bool:
        c_low = col_name.lower()
        if qualifier:
            q_low = qualifier.lower()
            if q_low in self.visible_qualifiers:
                target = self.visible_qualifiers[q_low]
                if target in self.cte_scope:
                    return c_low in self.cte_scope[target]
                return c_low in SCHEMA_ALLOWLIST[target]
            # Outer scope chain for correlated subqueries
            curr = self.parent
            while curr:
                if q_low in curr.visible_qualifiers:
                    target = curr.visible_qualifiers[q_low]
                    return c_low in SCHEMA_ALLOWLIST.get(target, set())
                curr = curr.parent
            return False
        # Unqualified column resolution
        matches = [t for a, t in self.visible_qualifiers.items() if c_low in SCHEMA_ALLOWLIST.get(t, set())]
        return len(matches) == 1
```

---

## 7. QueryDoctor and Its Repair Limitations

QueryDoctor (`app.services.query_doctor`) provides a strictly bounded, non-recursive self-healing diagnostic engine for non-security structural and syntactic faults.

```
       [ Fault Detected (AST Validation or SQLite Operational Error) ]
                                   │
                                   ▼
                       [ QueryDoctor Diagnosis ]
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
        [ Security Violation ]         [ Repairable Non-Security Fault ]
                    │                             │
                    ▼                             ▼
         Immediate Hard Reject          Check Attempts < 1?
         (Zero Repair Attempts)         ┌──────┴──────┐
                                        ▼             ▼
                                      [ Yes ]       [ No ]
                                        │             │
                                        ▼             ▼
                                  Apply AST Fix  Abort & Report
                                        │
                                        ▼
                              Re-validate Security
```

### 7.1 Strictly Prohibited Actions (Zero-Repair Violations)
QueryDoctor **never** attempts to repair:
1. SQL injection signatures or multi-statement queries.
2. DDL/DML statements (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`).
3. Disallowed system table references (`sqlite_master`, `pragma_table_info`).
4. Unauthorized functions (`LOAD_EXTENSION`, `EXEC`, `EVAL`).
5. Option A tautologies or contradictions (`1=1`, `s.cgpa = s.cgpa`, `s.cgpa != s.cgpa`).
6. Parameter binding count mismatches or missing parameter keys.

*Policy Invariant:* Any security or safety violation triggers an immediate hard rejection with zero repair attempts.

### 7.2 Repair Semantics and Eligibility Rules
QueryDoctor operates under strict deterministic constraints:
- **Maximum 1 Repair Attempt**: If the repaired query fails security re-validation or execution, the pipeline immediately aborts and returns an error. No cascading or recursive repair loops are permitted.
- **Security Re-Validation Loop**: All repaired ASTs must be resubmitted to `SQLSecurityValidator` before execution.
- **No Speculative or Semantics-Altering Repairs**: If semantic equivalence to the user's intent cannot be mathematically or structurally proven, QueryDoctor must not guess or speculate; it must abort and request clarification.

#### Specific Eligibility and Repair Rules:
1. **Missing `GROUP BY` Column (Static Diagnostic Resolution)**:
   - *SQLite Behavioral Semantics:* By default, SQLite permits non-standard aggregate queries where non-aggregate columns are omitted from `GROUP BY`, silently selecting an arbitrary row's value rather than raising an operational error.
   - *Diagnostic Requirement:* QueryDoctor does **not** rely on SQLite raising an error. Instead, missing `GROUP BY` columns are intercepted during `QueryPlanner` and `SQLSecurityValidator` static AST analysis when an aggregate expression coexists with unaggregated projections.
   - *Repair Action:* QueryDoctor appends the missing projected attributes to the `GROUP BY` clause **only** when proven semantically equivalent to the user's request (e.g. projecting department name and code alongside `COUNT()` or `AVG()`).
2. **Ambiguous Output Alias in WHERE Clauses**:
   - QueryDoctor does **not** automatically rewrite expressions in `WHERE` clauses.
   - *Repair Action:* An alias reference in a `WHERE` clause is rewritten to its underlying column expression **only** if the underlying expression is completely unambiguous, maps directly to a verified relation column in the scope, and preserves strict semantic equivalence. If the reference is ambiguous or could alter filter logic, the repair is aborted.
3. **Missing Foreign-Key Hops (Upstream Planning Domain)**:
   - Missing foreign-key hops between disconnected entities are treated as **planning and schema-linking issues**, not generic runtime repairs.
   - *Resolution:* Entity join paths must be deterministically computed upstream by `QueryPlanner` using the 9-vertex, 11-edge `JoinGraph`. If the planner or validator identifies an incomplete join path, QueryDoctor does not invent ad-hoc joins; the request is handled via JoinGraph shortest-path completion during planning or flagged as unanswerable.

---

## 8. Read-Only Query Executor

All SQL queries execute exclusively through the hardened `read_only_engine` initialized in [`app.core.database`](file:///c:/Users/OMEN/OneDrive/Desktop/STUDY/Projects/Nlp/QueryMind-AI/backend/app/core/database.py).

### 8.1 SQLite Hardening Controls
- **URI Mode**: `sqlite:///{DB_PATH}?mode=ro&uri=true`
- **Query Only PRAGMA**: `PRAGMA query_only = ON;`
- **Foreign Keys**: `PRAGMA foreign_keys = ON;`
- **C-Level Progress Handler**: Set to 30,000 opcodes with a wall-clock timeout of 3.0 seconds to terminate denial-of-service queries.

### 8.2 Global Result Row Limits and Truncation Guard
To ensure predictable latency, avoid runaway database scans, and prevent client browser memory exhaustion, QueryMind AI strictly enforces a global ceiling of 100 rows across all query execution paths.

#### 8.2.1 Effective Limit Formulation
The logical query limit submitted to SQL compilation is defined deterministically:

$$\text{effective\_limit} = \min(\text{user\_limit}, 100) \quad \text{when } \text{user\_limit is present and } \text{user\_limit} \ge 1$$
$$\text{effective\_limit} = 100 \quad \text{when } \text{user\_limit is absent (unconstrained query)}$$

- **Enforcement of Global 100-Row Ceiling:** No user request can bypass the global 100-row cap. For example, a user request for *"Top 500 students by CGPA"* evaluates to $\text{effective\_limit} = \min(500, 100) = 100$.
- **User Limits Below 100:** If the user requests fewer than 100 rows (e.g., *"Top 5 students"*), $\text{effective\_limit} = \min(5, 100) = 5$.
- **Default Cap on Unconstrained Queries:** When a query has no user-specified limit (e.g., *"Show active students in semester 6"*), $\text{effective\_limit} = 100$.

#### 8.2.2 Boundary Semantics: LIMIT 0, Negative, and Malformed Limits
- **LIMIT 0:** Strictly rejected during `QueryPlanIR` validation (`limit >= 1`). The system returns `status="error"` with error message `"Invalid LIMIT: must be a positive integer >= 1"`. No database query is executed, and no empty result set payload is returned.
- **Negative Limits (e.g., LIMIT -1, LIMIT -5):** SQLite interprets negative limits as unconstrained ("return all rows"). Permitting negative limits would allow an adversary or malformed query to disable row bounds and bypass the 100-row cap. Therefore, negative limits are strictly prohibited and hard-rejected during `QueryPlanIR` Pydantic validation and `SQLSecurityValidator` AST traversal (`status="error"`, `"Invalid LIMIT: must be a positive integer >= 1"`).
- **Non-Integer or Malformed Limits:** Non-integer, float, or string values (e.g. `LIMIT 'abc'`) are rejected during schema validation with `status="error"`.

#### 8.2.3 L+1 Probing and Execution Mechanics
The SQLGenerator compiles the query into SQLite-dialect SQL with:
$$\text{SQL LIMIT} = \text{effective\_limit} + 1$$
The `QueryExecutor` executes the query against SQLite via `read_only_engine` and fetches up to $\text{effective\_limit} + 1$ rows:
1. **Truncation Detected ($\text{Fetched Rows} = \text{effective\_limit} + 1$):**
   - The result set contains more matching records than `effective_limit`.
   - `is_truncated` is set to `True`.
   - The executor slices the result and returns exactly the first `effective_limit` rows in `rows` (guaranteeing $\le 100$ rows returned).
   - `row_count` is set to `effective_limit` (`len(rows)`).
2. **Complete Return ($\text{Fetched Rows} \le \text{effective\_limit}$):**
   - All matching records fit within `effective_limit`.
   - `is_truncated` is set to `False`.
   - All fetched rows are returned in `rows`.
   - `row_count` is set to `len(rows)`.

#### 8.2.4 Returned Rows vs. Total Matching Rows Semantic Guarantee
- **Payload `row_count` Integrity:** The `row_count` field in `TextToSQLResponse` strictly reports the count of rows actually returned in the payload (`len(rows)`), which is guaranteed to never exceed 100.
- **No False Total Count Claims:** When execution terminates at $\text{effective\_limit} + 1$ with `is_truncated = True`, the system, API response, and documentation **never** claim that the total number of matching rows in the database is known. Determining the total matching row count requires an unconstrained full-table scan or an explicit aggregate `SELECT COUNT(*)`, which was intentionally not executed. If a user requires the true total count, they must formulate an explicit counting query (e.g., *"How many students are enrolled in Computer Science?"*).
- **Client Transparency:** `is_truncated: bool` is prominently exposed in `TextToSQLResponse` to enable client interfaces to render a clear informational banner: *"Showing first {row_count} results. Additional matching records exist in the database."*

---

## 9. Integration Contracts: Phase 3, Phase 4, and Phase 5

The Phase 6 Text-to-SQL pipeline integrates directly with the verified contracts established in Phases 3, 4, and 5.

### 9.1 Phase 5 ContextMind Integration Contracts

The Text-to-SQL generator integrates with [`ContextMind.resolve_turn`](file:///c:/Users/OMEN/OneDrive/Desktop/STUDY/Projects/Nlp/QueryMind-AI/backend/app/services/context_engine.py) to inherit conversational state and resolved follow-ups.

#### Authoritative Source Signature & Invocation Convention:
- **Exact Python Method Signature:**
  ```python
  def resolve_turn(self, session_id: str, query: str) -> ContextResolveResponse
  ```
- **Class & Module Location:** Defined on class `ContextMind` in [`app.services.context_engine`](file:///c:/Users/OMEN/OneDrive/Desktop/STUDY/Projects/Nlp/QueryMind-AI/backend/app/services/context_engine.py). Accessible via the singleton accessor `get_context_engine()`.
- **Actual Argument Order:** 
  1. `session_id: str` (first parameter)
  2. `query: str` (second parameter)
- **Mandatory `session_id` Requirement:** `session_id` is strictly **mandatory** (non-optional). The method validates `session_id` against RFC 4122 via `uuid.UUID(session_id)`. Passing `None`, omitting the argument, or supplying an invalid UUID string raises a runtime `ValueError`.
- **Correct Invocation Convention for Phase 6:** Phase 6 callers (e.g. endpoint handlers or query planners) invoke `resolve_turn` directly on the singleton instance using keyword or positional arguments matching the exact parameter order:
  ```python
  from app.services.context_engine import get_context_engine, ContextMind
  
  context_engine: ContextMind = get_context_engine()
  context_response: ContextResolveResponse = context_engine.resolve_turn(
      session_id=session_id,
      query=query,
  )
  ```
  *(Note: Any prior documentation notation suggesting `ContextMind.resolve_turn(query: str, session_id: Optional[str] = None)` was an erroneous legacy draft. In the verified source code, `session_id` is required, precedes `query`, and no argument reordering or wrapper exists).*

#### Complete Response Contract: `ContextResolveResponse` (All 10 Fields)
Defined in [`app.schemas.context`](file:///c:/Users/OMEN/OneDrive/Desktop/STUDY/Projects/Nlp/QueryMind-AI/backend/app/schemas/context.py):
1. `status: Literal["success", "clarification", "reset"]` — Execution status of the turn resolution.
2. `session_id: str` — Validated RFC 4122 session UUID.
3. `original_query: str` — Raw, unmodified natural language query from the user.
4. `resolved_query: str` — Fully resolved, standalone, unambiguous natural language query.
5. `was_follow_up: bool` — `True` if the query was resolved as an elliptical follow-up to prior context.
6. `was_reset: bool` — `True` if the query triggered an explicit conversational reset.
7. `active_frame: Optional[ContextFrameSchema]` — Active conversational state frame after resolution.
8. `clarification_needed: bool` — `True` if anaphora or ambiguity requires user clarification.
9. `clarification_message: Optional[str]` — User-facing prompt requesting referent clarification.
10. `turn_number: int` — Monotonically increasing sequence index for this interaction turn.

#### Complete Frame Contract: `ContextFrameSchema` (All 16 Fields)
Defined in [`app.schemas.context`](file:///c:/Users/OMEN/OneDrive/Desktop/STUDY/Projects/Nlp/QueryMind-AI/backend/app/schemas/context.py):
1. `session_id: str` — Unique UUID session identifier.
2. `created_at: str` — ISO 8601 UTC creation timestamp.
3. `last_active: str` — ISO 8601 UTC last activity timestamp.
4. `expires_at: str` — ISO 8601 UTC expiration timestamp.
5. `ttl_seconds: int` — Configured sliding TTL window (default 600s).
6. `turn_count: int` — Total number of conversational turns completed in this session.
7. `active_entities: Dict[str, Any]` — Referenced entity slots (e.g., `{"primary_table": "students", "department_code": "CS"}`).
8. `active_filters: List[ActiveFilterSchema]` — Currently active query filters (`column`, `operator`, `value`).
9. `active_metric: Optional[str]` — Active analytical/aggregation metric (e.g., `cgpa`, `attendance_percentage`).
10. `active_group_by: List[str]` — Active grouping attributes (e.g., `["departments.name"]`).
11. `active_order_by: Optional[ActiveSortSchema]` — Active sorting configuration (`column`, `direction`).
12. `active_limit: Optional[int]` — Active result row limit.
13. `last_intent: Optional[str]` — Most recently classified query intent category.
14. `last_query: Optional[str]` — Most recent raw user query.
15. `last_resolved_query: Optional[str]` — Most recent fully resolved query.
16. `turn_history: List[TurnRecordSchema]` — Sequential audit trail of conversational turns.

#### Supporting Helper Schemas:
- `ActiveFilterSchema`: `column: str`, `operator: str` (e.g., `=`, `>`, `<`, `LIKE`, `IN`), `value: Any`.
- `ActiveSortSchema`: `column: str`, `direction: Literal["ASC", "DESC"]`.
- `TurnRecordSchema`: `turn_id: int`, `timestamp: str`, `user_query: str`, `resolved_query: str`, `intent: Optional[str]`, `was_follow_up: bool`, `modifications: Dict[str, Any]`.

---

### 9.2 Phase 4 SchemaLinker Integration Contracts

The generator invokes [`SchemaLinker.link_query`](file:///c:/Users/OMEN/OneDrive/Desktop/STUDY/Projects/Nlp/QueryMind-AI/backend/app/services/schema_linker.py) to resolve natural language tokens to catalog elements:

#### Method Signatures:
- **Service Implementation:**
  ```python
  def link_query(self, query: str) -> Dict[str, Any]
  ```
- **Phase 6 Context-Aware Interface:**
  ```python
  SchemaLinker.link_query(query: str, session_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]
  ```

#### Complete Response Dictionary Fields:
1. `linked_tables: Set[str]` — Set of resolved physical table names (e.g., `{"students", "departments"}`).
2. `linked_columns: Dict[str, List[Dict[str, Any]]]` — Map of table to matched column details (`column_name`, `matched_token`, `confidence`, `match_type`).
3. `linked_values: List[Dict[str, Any]]` — List of extracted literal values (`matched_token`, `table_name`, `column_name`, `value`, `confidence`).
4. `join_path: Dict[str, Any]` — Calculated relational path (`is_connected`, `total_cost`, `tables_in_path`, `path_steps`, `alternative_paths`, `error`).
5. `is_ambiguous: bool` — `True` if any token matches multiple candidate attributes without disambiguation.
6. `ambiguity_reasons: List[str]` — Detailed reasons for detected ambiguity.
7. `ambiguous_candidates: List[Dict[str, Any]]` — Candidate options presented for clarification.
8. `unsupported_entities: List[str]` — Extracted tokens not present in the academic catalog.
9. `execution_time_ms: float` — Wall-clock runtime for the schema linking step.

---

### 9.3 Phase 3 IntentClassifier Integration Contracts

The generator utilizes [`IntentClassifier.predict`](file:///c:/Users/OMEN/OneDrive/Desktop/STUDY/Projects/Nlp/QueryMind-AI/backend/app/services/intent_classifier.py) to determine the user's analytical goal:

#### Method Signature:
```python
IntentClassifier.predict(query: str) -> Dict[str, Any]
```

#### Complete Response Dictionary Fields:
1. `predicted_intent: str` — Top predicted intent category (one of `LIST_STUDENTS`, `COUNT_STUDENTS`, `STUDENT_ATTENDANCE`, `STUDENT_GRADES`, `COURSE_DETAILS`, `FACULTY_INFO`, `GENERAL_QUERY`).
2. `confidence: float` — Calibrated Softmax probability score $P(y = c \mid x) \in [0.0, 1.0]$.
3. `probabilities: Dict[str, float]` — Full probability distribution across all 7 supported intents.
4. `is_ambiguous: bool` — `True` if margin between top 2 intents is below the ambiguity threshold ($\Delta < 0.15$).
5. `ambiguity_reason: Optional[str]` — Diagnostic explanation if marked ambiguous (e.g., `LOW_CONFIDENCE_MARGIN`).
6. `top_intents: List[Tuple[str, float]]` — Sorted descending list of `(intent, probability)` tuples.

---

## 10. Phase 4 SchemaLinker and JoinGraph Integration

### 10.1 JoinGraph Topology
The academic catalog forms an undirected graph $G = (V, E)$ comprising **9 table vertices** ($|V|=9$), **11 physical foreign keys**, **22 directed adjacency edges**, and **11 unique undirected edges**:

```
                       [ departments ]
                       ▲      ▲      ▲
         department_id │      │      │ department_id
                       │      │      ▼
               ┌───────┘      │    [ courses ]
               │              │      ▲
               ▼              │      │ course_id
          [ students ]        │      ▼
               ▲              │    [ course_offerings ] ◄──┐
               │              │      ▲       ▲             │
    student_id │  department_id      │       │             │ instructor_id
               │              │      │       │             ▼
               ▼              ▼      │  offering_id   [ instructors ]
          [ enrollments ] ────┼──────┘       │
               ▲              │              │
               │              └──────────────┼─────────────┐
               │                             │             │
 enrollment_id │                             │ offering_id │
               ▼                             ▼             │
          [ student_marks ] ◄────────── [ assessments ]   │
                               assessment_id               │
                                                           │
   [ terms ] ◄─────────────────────────────────────────────┘
               term_id
```

### 10.2 All 11 Verified Undirected Graph Edges
1. `assessments` $\leftrightarrow$ `course_offerings` on `assessments.offering_id = course_offerings.offering_id`
2. `assessments` $\leftrightarrow$ `student_marks` on `student_marks.assessment_id = assessments.assessment_id`
3. `course_offerings` $\leftrightarrow$ `courses` on `course_offerings.course_id = courses.course_id`
4. `course_offerings` $\leftrightarrow$ `enrollments` on `enrollments.offering_id = course_offerings.offering_id`
5. `course_offerings` $\leftrightarrow$ `instructors` on `course_offerings.instructor_id = instructors.instructor_id`
6. `course_offerings` $\leftrightarrow$ `terms` on `course_offerings.term_id = terms.term_id`
7. `courses` $\leftrightarrow$ `departments` on `courses.department_id = departments.department_id`
8. `departments` $\leftrightarrow$ `instructors` on `instructors.department_id = departments.department_id`
9. `departments` $\leftrightarrow$ `students` on `students.department_id = departments.department_id`
10. `enrollments` $\leftrightarrow$ `student_marks` on `student_marks.enrollment_id = enrollments.enrollment_id`
11. `enrollments` $\leftrightarrow$ `students` on `enrollments.student_id = students.student_id`

*(Note: The historical Phase 4 documentation count of "10 FK constraints" was a typographical error. All 11 physical foreign keys are present in SQLite and represented in `JoinGraph`).*

---

## 11. Parameter Binding and SQL Generation Rules

1. **Zero Raw Literals**: All user-supplied filter literals must use named parameters (`:param_0`, `:param_1`).
2. **Parameter Type Casting**: Parameter values must match the database column types (`INTEGER`, `FLOAT`, `VARCHAR`, `DATE`).
3. **No Dynamic SQL String Inlining**: Query structures must be generated via AST node trees.

---

## 12. JOIN Selection and Anchor Entity Preservation Rule

### 12.1 Anchor Entity Preservation Rule
When a natural language request contains a universal quantifier modifying the anchor parent entity (*"all courses offered..."*, *"all departments..."*, *"all instructors..."*) followed by optional child entities (*"with their students"*, *"with their enrollments"*):
- Joins to required 1:1 parent dimensions (`courses`, `terms`, `instructors`) use **`INNER JOIN`**.
- Joins to optional 1:N dependent child entities (`enrollments`, `students`) must use **`LEFT JOIN`**.
- **Guarantee**: Preserves parent entities having zero child records, avoiding silent omission of legitimate anchor records.
- **Grain**: Returns rows at the child grain (e.g. Enrollment Grain), with child columns evaluating to `NULL` for anchor records with zero children.

---

## 13. SQL Security Policies and Rejection Conditions

### 13.1 Option A: Tautology and Contradiction Policy
QueryMind AI strictly prohibits identical-operand comparisons across all binary equality and inequality expressions:
- Numeric tautologies/contradictions: `1 = 1`, `1 != 1`, `1 <> 1`, `0 = 0` $\rightarrow$ **REJECTED**.
- Boolean tautologies/contradictions: `TRUE = TRUE`, `FALSE = FALSE` $\rightarrow$ **REJECTED**.
- Self-column comparisons: `s.cgpa = s.cgpa`, `s.cgpa != s.cgpa` $\rightarrow$ **REJECTED**.
- Parameter self-comparisons: `:param_0 = :param_0` $\rightarrow$ **REJECTED**.
- *SQL Logic Note:* Although `s.cgpa = s.cgpa` evaluates to `UNKNOWN` in three-valued logic when `s.cgpa IS NULL`, it is strictly rejected because it mimics SQL injection bypass patterns.

### 13.2 Prohibited SQL Nodes
- `exp.Insert`, `exp.Update`, `exp.Delete`, `exp.Drop`, `exp.Alter`
- `exp.Command` (`PRAGMA`, `ATTACH`, `DETACH`)
- System tables: `sqlite_master`, `sqlite_temp_master`, `sqlite_sequence`, `sqlite_stat1`
- Positional placeholders (`?`) $\rightarrow$ Must use named parameters (`:param_N`).
- Bare wildcards (`SELECT *`) $\rightarrow$ Prohibited; projections must be explicit.

---

## 14. Error Handling and Clarification Workflow

When a query cannot be safely resolved, validated, or executed, the pipeline emits one of four canonical API statuses (`success`, `clarification_needed`, `unsupported`, `error`):

1. **Successful Execution (`status="success"`)**:
   - The query was deterministically planned, compiled, validated by ASTScope security checks, and executed against `read_only_engine`.
   - Returns populated `generated_sql`, `parameters`, `columns`, `rows`, `row_count`, `is_truncated`, and `grain`.

2. **Conversational / Schema Ambiguity (`status="clarification_needed"`)**:
   - Triggered when a query token matches multiple columns equally across tables (e.g. `"status"`, `"name"`, `"date"`), or when an elliptical anaphora cannot be uniquely resolved to prior context.
   - The engine halts execution before SQL generation and returns `clarification_message` containing candidate options and disambiguation choices.

3. **Out-of-Domain or Unanswerable Requests (`status="unsupported"`)**:
   - **Out-of-Domain:** Requests referencing campus infrastructure outside the academic database (e.g., hostels, cafeteria, sports, library, bus routes) are intercepted by `SchemaLinker` token blacklists.
   - **Unanswerable Relational Entities:** Requests querying attributes disconnected from the relational schema (e.g., *"Course offerings in Science Hall"* where classroom strings lack building foreign keys).
   - Returns an educational explanation detailing why the query cannot be answered, accompanied by relevant catalog suggestions.

4. **Security, Syntax, or Execution Faults (`status="error"`)**:
   - Triggered by AST security violations (Option A tautologies, forbidden DDL/DML, system catalog access, unauthorized functions), unrepairable SQLite syntax errors, or execution timeouts (> 3.0s).
   - Security violations trigger immediate hard rejection with zero repair attempts. Non-security syntax faults are routed to QueryDoctor for at most 1 bounded repair attempt before returning an error.

---

## 15. All 15 Corrected Representative SQL Examples

All 15 queries below have been verified against the 55-column catalog and executed against `academic.db` via `read_only_engine`:

### Example 1: Active students in semester 6
- **NL:** *"Show active students in semester 6"*
- **SQL:**
  ```sql
  SELECT s.roll_number, s.first_name, s.last_name, s.cgpa, s.current_semester, s.academic_status
  FROM students s
  WHERE s.academic_status = :param_0 AND s.current_semester = :param_1
  ORDER BY s.roll_number ASC;
  ```
- **Params:** `{"param_0": "Active", "param_1": 6}`
- **Grain & Result:** Student Grain | **30 rows**

### Example 2: Students enrolled in Computer Science
- **NL:** *"How many students are enrolled in Computer Science?"*
- **SQL:**
  ```sql
  SELECT COUNT(s.student_id) AS student_count
  FROM students s
  JOIN departments d ON s.department_id = d.department_id
  WHERE d.code = :param_0;
  ```
- **Params:** `{"param_0": "CS"}`
- **Grain & Result:** Scalar Aggregate Grain | **1 row** (`24`)

### Example 3: Spring 2024 Course Offerings with Instructors and Students
- **NL:** *"List all courses offered in Spring 2024 with their instructors and enrolled students"*
- **SQL (Anchor Entity Preservation Rule):**
  ```sql
  SELECT c.course_code, c.course_name, i.first_name || ' ' || i.last_name AS instructor_name,
         s.roll_number, s.first_name || ' ' || s.last_name AS student_name, e.enrollment_status
  FROM course_offerings co
  JOIN terms t ON co.term_id = t.term_id
  JOIN courses c ON co.course_id = c.course_id
  JOIN instructors i ON co.instructor_id = i.instructor_id
  LEFT JOIN enrollments e ON co.offering_id = e.offering_id
  LEFT JOIN students s ON e.student_id = s.student_id
  WHERE t.semester_type = :param_0 AND t.academic_year = :param_1
  ORDER BY c.course_code ASC, s.roll_number ASC;
  ```
- **Params:** `{"param_0": "Spring", "param_1": 2024}`
- **Grain & Result:** Enrollment Grain (with offering preservation) | **120 rows**

### Example 4: Average CGPA by Department
- **NL:** *"Average CGPA of students by department"*
- **SQL:**
  ```sql
  SELECT d.code AS department_code, d.name AS department_name, ROUND(AVG(s.cgpa), 2) AS average_cgpa
  FROM students s
  JOIN departments d ON s.department_id = d.department_id
  GROUP BY d.department_id, d.code, d.name
  ORDER BY average_cgpa DESC, d.code ASC;
  ```
- **Params:** `{}`
- **Grain & Result:** Department Grain | **5 rows**

### Example 5: Instructors in Electrical Engineering
- **NL:** *"List all instructors in the Electrical Engineering department"*
- **SQL:**
  ```sql
  SELECT i.first_name, i.last_name, i.designation, i.joining_year
  FROM instructors i
  JOIN departments d ON i.department_id = d.department_id
  WHERE d.code = :param_0
  ORDER BY i.instructor_id ASC;
  ```
- **Params:** `{"param_0": "EE"}`
- **Grain & Result:** Instructor Grain | **4 rows**

### Example 6: Students with CGPA > 3.5 on Probation
- **NL:** *"Find students with CGPA greater than 3.5 on probation"*
- **SQL:**
  ```sql
  SELECT s.roll_number, s.first_name, s.last_name, s.cgpa, s.academic_status
  FROM students s
  WHERE s.cgpa > :param_0 AND s.academic_status = :param_1
  ORDER BY s.cgpa DESC, s.roll_number ASC;
  ```
- **Params:** `{"param_0": 3.5, "param_1": "Probation"}`
- **Grain & Result:** Student Grain | **0 rows** (Verified)

### Example 7: Count of Courses by Department
- **NL:** *"Count of courses by department"*
- **SQL:**
  ```sql
  SELECT d.code AS department_code, d.name AS department_name, COUNT(c.course_id) AS course_count
  FROM departments d
  LEFT JOIN courses c ON d.department_id = c.department_id
  GROUP BY d.department_id, d.code, d.name
  ORDER BY course_count DESC, d.code ASC;
  ```
- **Params:** `{}`
- **Grain & Result:** Department Grain | **5 rows**

### Example 8: Top 5 Students by CGPA (Unconstrained)
- **NL:** *"Top 5 students by CGPA"*
- **SQL (Without Unsupported Active Filter):**
  ```sql
  SELECT s.roll_number, s.first_name, s.last_name, s.cgpa
  FROM students s
  ORDER BY s.cgpa DESC, s.roll_number ASC
  LIMIT 5;
  ```
- **Params:** `{}`
- **Grain & Result:** Ranked Student Grain | **5 rows** (All CGPA 3.98)

### Example 9: Top 3 Courses by Average Attendance
- **NL:** *"Top 3 courses with the highest average attendance"*
- **SQL (Deterministic Tie-Breaker):**
  ```sql
  SELECT c.course_code, c.course_name, ROUND(AVG(e.attendance_percentage), 2) AS avg_attendance
  FROM courses c
  JOIN course_offerings co ON c.course_id = co.course_id
  JOIN enrollments e ON co.offering_id = e.offering_id
  GROUP BY c.course_id, c.course_code, c.course_name
  ORDER BY avg_attendance DESC, c.course_code ASC
  LIMIT 3;
  ```
- **Params:** `{}`
- **Grain & Result:** Ranked Course Grain | **3 rows** (CS301: 84.2%, AI301: 83.85%, ME201: 83.67%)

### Example 10: Students Who Failed Any Course (Grade F)
- **NL:** *"Students who failed any course (final grade F)"*
- **SQL:**
  ```sql
  SELECT DISTINCT s.roll_number, s.first_name, s.last_name, c.course_code, e.final_grade
  FROM students s
  JOIN enrollments e ON s.student_id = e.student_id
  JOIN course_offerings co ON e.offering_id = co.offering_id
  JOIN courses c ON co.course_id = c.course_id
  WHERE e.final_grade = :param_0
  ORDER BY s.roll_number ASC, c.course_code ASC;
  ```
- **Params:** `{"param_0": "F"}`
- **Grain & Result:** Failed Enrollment Grain | **1 row**

### Example 11: Total Credits Offered by Department (Catalogue Credits)
- **NL:** *"Total credits offered by each department"*
- **SQL (Curriculum Catalogue Scope):**
  ```sql
  SELECT d.code AS department_code, d.name AS department_name, SUM(c.credits) AS total_credits
  FROM departments d
  JOIN courses c ON d.department_id = c.department_id
  GROUP BY d.department_id, d.code, d.name
  ORDER BY total_credits DESC, d.code ASC;
  ```
- **Params:** `{}`
- **Grain & Result:** Department Grain | **5 rows**

### Example 12: Assessments for CS301 in Fall 2023
- **NL:** *"Assessments for Database Management Systems in Fall 2023"*
- **SQL:**
  ```sql
  SELECT a.title, a.assessment_type, a.max_marks, a.weightage_percent
  FROM assessments a
  JOIN course_offerings co ON a.offering_id = co.offering_id
  JOIN courses c ON co.course_id = c.course_id
  JOIN terms t ON co.term_id = t.term_id
  WHERE c.course_code = :param_0 AND t.term_name = :param_1
  ORDER BY a.assessment_id ASC;
  ```
- **Params:** `{"param_0": "CS301", "param_1": "Fall 2023"}`
- **Grain & Result:** Assessment Grain | **0 rows** (CS301 was not offered in Fall 2023)

### Example 13: Active Semester 6 Students with CGPA > 3.0
- **NL:** *"Active students in semester 6 with CGPA above 3.0"*
- **SQL:**
  ```sql
  SELECT s.roll_number, s.first_name, s.last_name, s.cgpa, s.current_semester, s.academic_status
  FROM students s
  WHERE s.academic_status = :param_0 AND s.current_semester = :param_1 AND s.cgpa > :param_2
  ORDER BY s.roll_number ASC;
  ```
- **Params:** `{"param_0": "Active", "param_1": 6, "param_2": 3.0}`
- **Grain & Result:** Student Grain | **25 rows**

### Example 14: AI Students with Courses and Grades
- **NL:** *"Find all students in the Artificial Intelligence department with their courses and grades"*
- **SQL:**
  ```sql
  SELECT s.roll_number, s.first_name || ' ' || s.last_name AS student_name,
         c.course_code, c.course_name, e.final_grade, e.attendance_percentage
  FROM students s
  JOIN departments d ON s.department_id = d.department_id
  JOIN enrollments e ON s.student_id = e.student_id
  JOIN course_offerings co ON e.offering_id = co.offering_id
  JOIN courses c ON co.course_id = c.course_id
  WHERE d.code = :param_0
  ORDER BY s.roll_number ASC, c.course_code ASC;
  ```
- **Params:** `{"param_0": "AI"}`
- **Grain & Result:** Enrollment Grain | **72 rows** (24 students $\times$ 3 courses)

### Example 15: Course Offerings in Classroom Hall-101
- **NL:** *"Course offerings scheduled in classroom Hall-101 with section and term"*
- **SQL (Valid Replacement for Unsupported Science Hall Query):**
  ```sql
  SELECT c.course_code, c.course_name, co.section, co.classroom, t.term_name
  FROM course_offerings co
  JOIN courses c ON co.course_id = c.course_id
  JOIN terms t ON co.term_id = t.term_id
  WHERE co.classroom = :param_0
  ORDER BY c.course_code ASC, co.section ASC, t.term_name ASC;
  ```
- **Params:** `{"param_0": "Hall-101"}`
- **Grain & Result:** Offering Grain | **4 rows**  
*(Note: The query "Course offerings in building Science Hall" is classified as unsupported because "Science Hall" does not exist in the database and classrooms have no foreign-key link to department buildings).*

---

## 16. Query Execution and Result-Grain Policies

| Entity Target | Output Grain | Deterministic Sort Tie-Breaker | Truncation Guard Policy |
| :--- | :--- | :--- | :--- |
| **Students** | 1 row per student | `s.roll_number ASC` | L+1 probe with UI banner |
| **Courses** | 1 row per course | `c.course_code ASC` | L+1 probe with UI banner |
| **Instructors** | 1 row per faculty member | `i.instructor_id ASC` | L+1 probe with UI banner |
| **Departments** | 1 row per department | `d.code ASC` | Full return ($\le 5$ rows) |
| **Course Offerings** | 1 row per offering session | `co.offering_id ASC` | L+1 probe with UI banner |
| **Enrollments** | 1 row per student registration | `s.roll_number ASC, c.course_code ASC` | L+1 probe with UI banner |
| **Assessments** | 1 row per assessment test | `a.assessment_id ASC` | L+1 probe with UI banner |

### 16.1 Global Result Row Limits and Truncation Guard Semantics

#### 16.1.1 Effective Limit Formulation
All query executions strictly adhere to the global 100-row maximum cap:
$$\text{effective\_limit} = \min(\text{user\_limit}, 100) \quad \text{when } \text{user\_limit is present and } \text{user\_limit} \ge 1$$
$$\text{effective\_limit} = 100 \quad \text{when } \text{user\_limit is absent (unconstrained query)}$$

1. **User Requests Exceeding 100 Rows:** Requests for more than 100 rows (e.g. `LIMIT 500`) are clamped to `min(500, 100) = 100`. The 100-row global ceiling cannot be bypassed.
2. **User Requests Below 100 Rows:** Requests for fewer than 100 rows (e.g. `LIMIT 5`) evaluate to `effective_limit = 5`.
3. **Unconstrained Queries:** Queries without user-specified limits evaluate to `effective_limit = 100`.

#### 16.1.2 Boundary Condition and Security Enforcement
- **LIMIT 0:** Strictly rejected during `QueryPlanIR` validation (`limit >= 1`). Emits an error response (`status="error"`) with message `"Invalid LIMIT: must be a positive integer >= 1"`. Zero database queries are executed, and no empty result set is returned.
- **Negative Limits (e.g. LIMIT -1, LIMIT -5):** In SQLite, negative limits disable limit enforcement, returning all rows. Permitting negative limits would allow circumvention of the global 100-row cap. Negative limits are strictly prohibited and hard-rejected during Pydantic validation and AST traversal (`status="error"`, `"Invalid LIMIT: must be a positive integer >= 1"`).
- **Non-Integer or Malformed Limits:** Rejected during Pydantic schema validation with `status="error"`.

#### 16.1.3 L+1 Probing and Truncation Protocol
- The generated SQL compiles with: $\text{SQL LIMIT} = \text{effective\_limit} + 1$.
- **When Fetched Rows $= \text{effective\_limit} + 1$:**
  - `is_truncated` is set to `True`.
  - Result rows are sliced to return exactly the first `effective_limit` rows in `rows` ($\le 100$).
  - `row_count` is set to `effective_limit` (`len(rows)`).
- **When Fetched Rows $\le \text{effective\_limit}$:**
  - `is_truncated` is set to `False`.
  - All fetched rows are returned in `rows`.
  - `row_count` is set to `len(rows)`.

#### 16.1.4 Returned vs. Total Rows Semantic Guarantee
- **Payload `row_count` Reports Returned Rows Only:** `row_count` strictly reflects `len(rows)` in the response payload (never exceeding 100).
- **No False Total Count Claims:** When execution terminates at $\text{effective\_limit} + 1$ with `is_truncated = True`, the system and API **never** claim that the total matching count is known. Calculating total matching records requires an explicit `COUNT(*)` aggregate query.
- **Client Communication:** `is_truncated: bool` notifies clients to display a prominent UI banner alerting the user that additional matching records exist.

---

## 17. API Contracts and Response Structures

### 17.1 Text-to-SQL API Endpoint
`POST /api/v1/query/generate`

#### Request Payload
```python
class TextToSQLRequest(BaseModel):
    session_id: str = Field(..., description="Valid UUID session identifier")
    query: str = Field(..., min_length=1, max_length=500, description="Natural language query")
```

#### Response Payload
```python
class TextToSQLResponse(BaseModel):
    status: Literal["success", "clarification_needed", "unsupported", "error"]
    session_id: str
    original_query: str
    generated_sql: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    columns: List[str] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    is_truncated: bool = False
    grain: Optional[str] = None
    execution_time_ms: float = 0.0
    was_repaired_by_doctor: bool = False
    repair_summary: Optional[str] = None
    clarification_message: Optional[str] = None
    error_message: Optional[str] = None
```

---

## 18. Testing Strategy and Acceptance Criteria

The Phase 6 test suite will be implemented in `backend/tests/` to validate:
1. **IR Synthesis Tests**: Verify that `QueryPlanner` converts all 7 intents into valid `QueryPlanIR` instances.
2. **Security Traversal Tests**: Verify all 32 prototype security scenarios (alias hiding, tautologies, CTE scopes, function allowlists).
3. **Execution Correctness Tests**: Execute all 15 representative queries against `academic.db` and match exact row counts.
4. **QueryDoctor Loop Tests**: Verify that repairable errors are healed in 1 step, while security errors abort immediately.
5. **Regression Invariant**: All 131 pre-existing tests in `backend/tests/` must remain passing.

---

## 19. Known Limitations and Unsupported Queries

1. **Zero Self-Referencing Foreign Keys**: The database schema does not define hierarchical self-references (e.g. prerequisite trees or student mentors). Arbitrary non-FK self-joins are rejected.
2. **Disconnected Classroom Entities**: Classrooms are string labels in `course_offerings` and cannot be joined to campus building locations. Queries asking for "all offerings in building X" are unsupported.
3. **Single-Iteration Repair Cap**: QueryDoctor terminates after one repair attempt. Cascading multi-step errors are intentionally aborted to prevent execution loops.

---

## 20. Phase 6 Subphase Implementation Sequence

```
+-------------------------------------------------------------------------------------------------------------+
|                                    PHASE 6 IMPLEMENTATION ROADMAP                                           |
+-----------+-----------------------------------+-------------------------------------------------------------+
| Subphase  | Target Modules                    | Deliverables & Core Milestones                              |
+-----------+-----------------------------------+-------------------------------------------------------------+
| Phase 6.1 | app/services/parameter_registry.py| ParameterRegistry, RelationInstance, ProjectionIR,          |
|           | app/services/query_plan_ir.py     | QueryPlanIR cross-field Pydantic validation.                |
+-----------+-----------------------------------+-------------------------------------------------------------+
| Phase 6.2 | app/services/sql_generator.py     | AST expression builder, deterministic tie-breakers,         |
|           |                                   | Anchor Entity Preservation Rule join compiler.              |
+-----------+-----------------------------------+-------------------------------------------------------------+
| Phase 6.3 | app/services/sql_validator.py     | ASTScope tree traversal, table alias hiding, Option A       |
|           |                                   | tautology/contradiction blocking, placeholder validation.   |
+-----------+-----------------------------------+-------------------------------------------------------------+
| Phase 6.4 | app/services/query_doctor.py      | Strictly bounded 1-step self-healing diagnostic engine;     |
|           |                                   | non-security error classification; zero repair on security. |
+-----------+-----------------------------------+-------------------------------------------------------------+
| Phase 6.5 | app/services/query_executor.py    | Read-only SQLite execution with C-level progress handlers;  |
|           | app/api/endpoints/query.py        | L+1 truncation probing & 100-row global default cap;        |
|           | backend/tests/test_text_to_sql.py | unified Text-to-SQL API endpoints and test suite.           |
+-----------+-----------------------------------+-------------------------------------------------------------+
```

---

## 21. Document Authorization & Verification Record

- **Authoritative Document Location:** `docs/text_to_sql_architecture.md`
- **Verification Basis:** SQLite `PRAGMA table_info`, `PRAGMA foreign_key_list`, SQLAlchemy models, Phase 4 `JoinGraph`, Phase 5 `ContextMind`, and v2.9.0 audit decisions.
- **Git State:** 0 tracked modifications or deletions; pre-existing untracked files preserved because repository has no prior commits; the authorized architecture documentation file is untracked; 0 staging and 0 commits executed.
- **Implementation Status:** STRICTLY PLANNING ONLY. Phase 6 implementation authorization is **NOT GRANTED**.

