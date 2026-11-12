# QueryMind AI 2.0 — Decision Logic & Rule Matrices (Decision File)
*Deliverable Document 5 | Updated — Phase 5 ContextMind Conversational Context Engine*

> **Status:** Phase 5 Implemented & Verified Specification  
> **Phase Milestone:** Phase 5 (ContextMind Multi-Turn State Management)  
> **Note:** This document formalizes operational decision tables mapping system inputs, error codes, database integrity constraints, join path traversals, deterministic seeding behaviors, supervised intent disambiguation rules, Schema Linking & Steiner Join Path disambiguation matrices, and ContextMind multi-turn conversational state decision logic to deterministic actions.


---

## 1. Academic Relational Join Graph Adjacency Matrix

Defines the valid deterministic join paths across all 9 normalized academic tables in the SQLite schema graph $G = (V, E)$:

| Source Entity ($T_1$) | Target Entity ($T_2$) | Foreign Key Relationship | Supported Join Operator | Join Condition Syntax |
| :--- | :--- | :--- | :--- | :--- |
| `departments` | `students` | 1-to-Many | `INNER JOIN` | `departments.department_id = students.department_id` |
| `departments` | `instructors` | 1-to-Many | `INNER JOIN` | `departments.department_id = instructors.department_id` |
| `departments` | `courses` | 1-to-Many | `INNER JOIN` | `departments.department_id = courses.department_id` |
| `courses` | `course_offerings` | 1-to-Many | `INNER JOIN` | `courses.course_id = course_offerings.course_id` |
| `instructors` | `course_offerings` | 1-to-Many | `INNER JOIN` | `instructors.instructor_id = course_offerings.instructor_id` |
| `terms` | `course_offerings` | 1-to-Many | `INNER JOIN` | `terms.term_id = course_offerings.term_id` |
| `students` | `enrollments` | 1-to-Many | `INNER JOIN` | `students.student_id = enrollments.student_id` |
| `course_offerings` | `enrollments` | 1-to-Many | `INNER JOIN` | `course_offerings.offering_id = enrollments.offering_id` |
| `course_offerings` | `assessments` | 1-to-Many | `INNER JOIN` | `course_offerings.offering_id = assessments.offering_id` |
| `enrollments` | `student_marks` | 1-to-Many | `INNER JOIN` / `LEFT JOIN` | `enrollments.enrollment_id = student_marks.enrollment_id` |
| `assessments` | `student_marks` | 1-to-Many | `INNER JOIN` / `LEFT JOIN` | `assessments.assessment_id = student_marks.assessment_id` |

*Note on Multi-Hop Join Traversal:* Queries linking non-adjacent tables (e.g. `departments` to `assessments`) use Dijkstra's shortest-path algorithm across this adjacency matrix:
$$\text{departments} \rightarrow \text{courses} \rightarrow \text{course\_offerings} \rightarrow \text{assessments}$$

---

## 2. Database Seeding & Initialization Decision Matrix

Defines system behavior for initialization, reset, and deterministic seeding operations:

| Invocation Mode | Database File State | Existing Table State | Specified Flags | Prescribed System Action | Transaction Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `init_db.py` | Absent | N/A | None | Creates file and executes `Base.metadata.create_all()` | 9 tables initialized blank |
| `init_db.py` | Present | Tables Exist | None | Safe inspection: verifies existing tables | 0 data modified; report status |
| `init_db.py` | Present | Tables Exist | `--reset` / `--drop` | Drops all tables via `drop_all()` then recreates | Clean empty schema; previous data destroyed |
| `seed_db.py` | Present | Clean / Empty Tables | None | Executes deterministic seeder (`seed=42`) | 1,786 records inserted and committed |
| `seed_db.py` | Present | Populated ($>0$ rows) | None | **Idempotent Bypass**: detect rows, skip re-insertion | 0 duplicate records; display counts |
| `seed_db.py` | Present | Populated | `--reset` | Recreates schema and executes fresh seed (`seed=42`) | Exactly 1,786 rows populated |
| Any Seeder Run | Any | Incomplete | Unhandled Exception | **Automatic Rollback**: catch exception, call `session.rollback()` | Zero partial state persisted |

---

## 3. Database Cross-Table Integrity & Trigger Decision Matrix

| Operation | Target Entity | Evaluated Condition | Enforcing Database Mechanism | Trigger Action on Violation |
| :--- | :--- | :--- | :--- | :--- |
| `INSERT` / `UPDATE` | `student_marks` | `assessment.offering_id != enrollment.offering_id` | SQLite Trigger `trg_student_marks_integrity_*` | `RAISE(ABORT, 'Cross-offering integrity violation')` |
| `INSERT` / `UPDATE` | `student_marks` | `marks_obtained > assessment.max_marks` | SQLite Trigger `trg_student_marks_integrity_*` | `RAISE(ABORT, 'Marks boundary violation')` |
| `INSERT` / `UPDATE` | `student_marks` | `marks_obtained < 0.0` | Table CHECK `chk_marks_obtained_positive` | Rejection via `CHECK constraint failed` |
| `INSERT` / `UPDATE` | `student_marks` | Duplicate `(assessment_id, enrollment_id)` | Unique Constraint `uq_assessment_enrollment` | Rejection via `UNIQUE constraint failed` |
| `INSERT` / `UPDATE` | `assessments` | `SUM(weightage_percent) > 100.0` for offering | SQLite Trigger `trg_assessments_weightage_*` | `RAISE(ABORT, 'Assessment weightage violation')` |
| `UPDATE max_marks` | `assessments` | `NEW.max_marks < student_marks.marks_obtained` | SQLite Trigger `trg_assessments_max_marks_update` | `RAISE(ABORT, 'Marks boundary violation')` |
| `UPDATE offering_id` | `assessments` | Assessment has student marks linked to current offering | SQLite Trigger `trg_assessments_offering_update` | `RAISE(ABORT, 'Cross-offering integrity violation')` |
| `UPDATE offering_id` | `enrollments` | Enrollment has student marks linked to current offering | SQLite Trigger `trg_enrollments_offering_update` | `RAISE(ABORT, 'Cross-offering integrity violation')` |
| `INSERT` / `UPDATE` | `course_offerings`| Duplicate `(course_id, term_id, section)` | Unique Constraint `uq_course_term_section` | Rejection via `UNIQUE constraint failed` |
| `INSERT` / `UPDATE` | `enrollments` | Duplicate `(student_id, offering_id)` | Unique Constraint `uq_student_offering` | Rejection via `UNIQUE constraint failed` |
| Any Mutation | Any Table | Runtime Read-Only Engine (`mode=ro`) | Hardware `PRAGMA query_only = ON` | Abort via `attempt to write a readonly database` |

---

## 4. Automated Visualization Selection Decision Table

| Row Count ($N$) | Number of Numeric Columns ($C_{\text{num}}$) | Number of Categorical Columns ($C_{\text{cat}}$) | Has Date / Time Dimension? | Unique Categories ($K$) | Recommended Visualization | Fallback Option |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| $N = 1$ | $1$ | $0$ or $1$ | No | - | **KPI Stat Card** | Data Table |
| $1 < N \le 6$ | $1$ | $1$ | No | $K \le 6$ | **Donut / Pie Chart** | Bar Chart |
| $1 < N \le 25$ | $1$ | $1$ | No | $K \le 25$ | **Bar Chart** | Data Table |
| $N > 1$ | $1$ | $\ge 0$ | **Yes** | - | **Line Chart / Area Chart** | Data Table |
| $N > 1$ | $2$ | $\ge 0$ | No | - | **Scatter Plot** | Data Table |
| $N > 25$ OR Any | Any | $> 2$ | Any | $K > 25$ | **Data Table** | None |

---

## 5. Ambiguity Detection & Disambiguation Rules

| Condition | Detected Pattern | System Action | UI Presentation |
| :--- | :--- | :--- | :--- |
| Intent Confidence Low | $\max_c P(y = c \mid \mathbf{x}) < 0.55$ | Halt SQL Generation $\rightarrow$ Trigger Clarification | Present top 3 potential query interpretations as buttons |
| Narrow Intent Margin | $P_{\text{top1}} - P_{\text{top2}} < 0.15$ | Halt SQL Generation $\rightarrow$ Disambiguate Intent | *"Did you mean to aggregate or rank these students?"* |
| Missing Target Metric | Query asks for *"Top students"* without metric | Halt SQL Generation $\rightarrow$ Request Metric Choice | Options: `["By CGPA", "By Course Marks", "By Attendance"]` |
| Polysemous Entity | Course title matches both standard and honors sections | Request Section Clarification | Options: `["Section A (Regular)", "Section B (Honors)"]` |

---

## 6. QueryDoctor Error Diagnosis & Action Matrix

| Error Trigger | Error Code / Root Cause | Error Classification | Maximum Attempts | Prescribed Action |
| :--- | :--- | :--- | :--- | :--- |
| Multi-statement syntax | Semicolon (`;`) separating queries | **Security Failure** | **0** | **Immediate Rejection** |
| DML/DDL command | `DROP`, `DELETE`, `UPDATE`, `ALTER` | **Security Failure** | **0** | **Immediate Rejection** |
| Foreign Table Name | Table not in academic schema allowlist | **Security Failure** | **0** | **Immediate Rejection** |
| SQLite system call | `PRAGMA`, `ATTACH`, `sqlite_master` | **Security Failure** | **0** | **Immediate Rejection** |
| Missing `GROUP BY` column | Unaggregated column in `SELECT` with `AVG()` | **Repairable Schema Error** | **1** | Append missing column to AST `GROUP BY` clause |
| Output alias in `WHERE` | Column alias referenced in SQLite filter | **Repairable Syntax Error** | **1** | Substitute raw column expression into `WHERE` AST |

---

## 7. Supervised Intent Classification & Scope Boundary Matrix

Formal decision table for the 7 approved intent categories and out-of-domain scope enforcement in `IntentClassifier`:

| Intent Category | Primary Linguistic Triggers | Target SQL Operation | Disambiguation Rule ($\Delta < 0.15$ or $\tau < 0.55$) |
| :--- | :--- | :--- | :--- |
| `AGGREGATE` | *average, mean, total, count, sum, min, max, how many* | `SELECT AGG(col) FROM ... GROUP BY ...` | Disambiguate vs `RANKING` if ordered limits are implied |
| `RANKING` | *top, lowest, bottom, highest, best, worst, rank, sort* | `ORDER BY col DESC/ASC LIMIT N` | Disambiguate vs `AGGREGATE` if aggregate keywords present |
| `FILTER` | *above, below, greater than, less than, enrolled, between* | `WHERE col > val` / `WHERE status = 'Active'` | Disambiguate vs `COMPARISON` if multiple entities specified |
| `COMPARISON` | *compare, vs, difference, higher between, compared to* | Multi-group aggregation / paired difference subqueries | Disambiguate vs `TREND` if time dimension is present |
| `TREND` | *trend, over time, year over year, progression, growth* | `GROUP BY academic_year, term_name ORDER BY date` | Disambiguate vs `AGGREGATE` if simple single-term average requested |
| `GENERAL_QUERY` | *show all, list, details, profile, information, curriculum* | Simple relational projection without aggregation | Default fallback when confidence is uniform |
| `WHAT_IF` | *what if, simulate, suppose, scenario, if we increase/drop* | Simulated recalculation with parameter adjustment | Disambiguate vs `FILTER` if hypothetical condition is complex |
| **OUT_OF_DOMAIN** | Zero academic domain keywords (e.g. weather, dogs, flight) | **Execution Rejected** | `is_ambiguous = True`, `reason = 'OUT_OF_DOMAIN'`, $c \le 0.35$ |
| **EMPTY_QUERY** | Null, blank, or whitespace-only input string | **Execution Rejected** | `is_ambiguous = True`, `reason = 'EMPTY_QUERY'` |

---

## 8. Schema Linking Polysemy & Ambiguity Decision Matrix

Formal decision table resolving polysemous academic tokens across schema entities without silently guessing:

| Ambiguous Token | Plausible Candidate Columns | Candidate Descriptions | Disambiguation Condition | Prescribed System Action |
| :--- | :--- | :--- | :--- | :--- |
| `grade` / `grades` | `student_marks.marks_obtained`<br>`enrollments.final_grade`<br>`enrollments.grade_points` | Numerical assessment score<br>Letter grade (A, B, C)<br>Numeric GPA points (0.0 - 4.0) | Bare token used without multi-word qualifier (`final grade`, `letter grade`, `marks`) | Flag `is_ambiguous = True`<br>`reason = 'MULTIPLE_COLUMN_CANDIDATES'`<br>Present candidate explanations |
| `status` | `students.academic_status`<br>`enrollments.enrollment_status` | Student standing (Active, Probation)<br>Course outcome (Enrolled, Dropped) | Bare token used without qualifier (`academic status`, `enrollment status`) | Flag `is_ambiguous = True`<br>`reason = 'MULTIPLE_COLUMN_CANDIDATES'`<br>Present candidate options |
| `year` | `students.enrollment_year`<br>`instructors.joining_year`<br>`terms.academic_year`<br>`departments.established_year` | Student admission calendar year<br>Faculty appointment year<br>Term session academic year<br>Department founding year | Token used without entity context | Flag `is_ambiguous = True`<br>`reason = 'MULTIPLE_COLUMN_CANDIDATES'`<br>Disambiguate attribute |
| `name` | `departments.name`<br>`courses.course_name`<br>`students.first_name`<br>`instructors.first_name` | Department formal name<br>Curriculum course title<br>Student first name<br>Instructor first name | Token used without entity context | Flag `is_ambiguous = True`<br>`reason = 'MULTIPLE_COLUMN_CANDIDATES'` |
| `code` | `departments.code`<br>`courses.course_code` | Department acronym (AI, CS)<br>Course identifier (CS101) | Bare token without qualifier | Flag `is_ambiguous = True`<br>`reason = 'MULTIPLE_COLUMN_CANDIDATES'` |
| `title` | `courses.course_name`<br>`assessments.title`<br>`instructors.designation` | Course title<br>Assessment assignment title<br>Faculty academic rank | Bare token without entity context | Flag `is_ambiguous = True`<br>`reason = 'MULTIPLE_COLUMN_CANDIDATES'` |
| Out-of-Domain Entities (`hostel`, `cafeteria`, `wifi`, `tuition`) | None (Unmodeled non-academic entities) | Out-of-catalog facilities, fees, services | Query mentions non-academic concepts | Flag `is_ambiguous = True`<br>`reason = 'UNSUPPORTED_ENTITIES'`<br>Halt generation |

---

## 9. Join Path Disambiguation & Steiner Tree Decision Matrix

Formal decision table for resolving foreign-key connections across requested table sets $T$:

| Requested Tables $T$ | Connected Components | Shortest Path Topology | Alternative Shortest Paths Count | Prescribed Action & Join Path Output |
| :--- | :--- | :--- | :--- | :--- |
| `{"students"}` | 1 | 0 hops (Single table) | 0 | `total_hops = 0`, `anchor_table = "students"`, `join_steps = []` |
| `{"departments", "students"}` | 1 | 1 hop direct edge | 0 | `departments.department_id = students.department_id` |
| `{"students", "courses"}` | 1 | 2 hops via `departments` | 0 | `students` $\to$ `departments` $\to$ `courses` (2 hops) |
| `{"departments", "student_marks"}` | 1 | 3 hops via `students` & `enrollments` | 0 | `departments` $\to$ `students` $\to$ `enrollments` $\to$ `student_marks` (3 hops) |
| `{"departments", "course_offerings"}` | 1 | 2 hops (Two equal-length shortest paths) | **1 Alternative** | **Primary:** `departments` $\to$ `courses` $\to$ `course_offerings`<br>**Alternative:** `departments` $\to$ `instructors` $\to$ `course_offerings`<br>Flag `MULTIPLE_JOIN_PATHS`, `alternative_paths_count = 1` |
| `{"departments", "students", "courses"}` | 1 | 2 hops Steiner Tree | 0 | Minimal tree with root `departments`: joins `students` and `courses` directly (2 hops) |
| `{"students", "student_marks", "assessments"}` | 1 | 2 hops Steiner Tree | 0 | Connects via `enrollments` and `student_marks` cleanly |
| `{"students", "imaginary_table"}` | Disconnected / Unknown | Table not in schema graph | 0 | `is_connected = False`, error: `"Table 'imaginary_table' is disconnected or not present in schema graph."` |

### Notes on Multi-Table Steiner Tree Heuristic & Empirical Benchmarks
1. **Algorithmic Nature**: The multi-table join resolver implements the Takahashi-Matsuyama (1980) Multi-Source BFS heuristic evaluated across all candidate roots. It is formally classified as a **polynomial-time approximation heuristic**, not an exact solver.
2. **Theoretical Bound**: For any set of $k = |T|$ terminal tables, the algorithm satisfies the proven worst-case upper bound of $2\left(1 - \frac{1}{k}\right)$.
3. **Exhaustive Empirical Validation ($k \in [2, 9]$)**:
   - Evaluated across all $\sum_{k=2}^9 \binom{9}{k} = 502$ possible terminal combinations against a brute-force minimum Steiner tree reference solver on the 9-node academic graph.
   - **499 / 502 combinations (99.40%)** achieve the exact globally optimal minimum hop count.
   - **3 / 502 combinations (0.60%)** deviate by $+1$ hop due to greedy BFS tie-breaking:
     - `('courses', 'student_marks', 'students', 'terms')`: heuristic 6 vs exact 5 (ratio = 1.20 <= 1.50).
     - `('instructors', 'student_marks', 'students', 'terms')`: heuristic 6 vs exact 5 (ratio = 1.20 <= 1.50).
     - `('courses', 'instructors', 'student_marks', 'students', 'terms')`: heuristic 7 vs exact 6 (ratio = 1.167 <= 1.60).
   - In all divergence cases, the ratio is $\le 1.20$, well within the theoretical bound.
4. **Alternative Paths Limitation**:
   - For 2-table queries: `alternative_paths` records all minimal BFS paths of equal hop count.
   - For $\ge 3$ tables: `alternative_paths` captures distinct minimal trees discovered across different candidate roots with unique edge sets. It does not perform exhaustive combinatorial enumeration of all spanning Steiner topologies.

---

## 10. ContextMind Multi-Turn State Management & Anaphora Decision Matrix

Formal decision table governing conversational memory, anaphora resolution, slot replacement, and contradiction elimination:

| Prior Context ($\text{Turn}_{N-1}$) | Query Pattern ($\text{Turn}_N$) | Detected Pattern / Trigger | Prescribed ContextMind Action | Resolved Standalone Query | State Mutation & Contradiction Action |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Any Active Context | `"clear context"`, `"reset"`, `"start over"` | Explicit Reset Trigger | Purge session frame from volatile memory | Raw Query Echo | Immediate deletion: `del _sessions[sid]`, `active_frame = None`, `was_reset = True` |
| Empty / Reset / Expired Context | `"Now show their attendance."` | Anaphoric pronoun without referent | Trigger Structured Clarification Modal | Raw Query Echo | No state mutation; prompt: *"I could not resolve 'their' because there is no prior context."* |
| `students`, `departments.code='AI'` | `"Now show their attendance."` | Possessive pronoun (`"their"`) + Metric | Binds `"their"` to `students in AI`; sets metric to `attendance` | *"Show attendance of students in the AI department."* | `active_metric = 'attendance'`; `students` & `AI` filter preserved; TTL refreshed |
| `courses`, `departments.code='CS'` | `"Sort them by credits."` | Objective pronoun (`"them"`) + Sort directive | Binds `"them"` to `courses in CS`; sets sort column `courses.credits` | *"Show courses in the CS department sorted by credits."* | `active_order_by = {'column': 'courses.credits', 'direction': 'ASC'}`; TTL refreshed |
| `students`, `departments.code='AI'`, `metric='cgpa'` | `"Now show CS students instead."` | Explicit replacement keyword (`"instead"`) | Replaces `AI` with `CS`; preserves metric `CGPA` and entity `students` | *"Show average CGPA of CS students."* | **Contradiction Elimination**: `AI` filter purged; `departments.code='CS'` set; `cgpa` preserved |
| `courses`, `departments.code='CS'` | `"Show those courses with credits > 3."` | Demonstrative determiner (`"those"`) + Condition | Binds `"those courses"` to `courses in CS`; appends filter | *"Show courses in the CS department with credits greater than 3."* | Preserves `CS` filter; appends credit filter; TTL refreshed |
| `courses`, `departments.code='AI'` | `"Show instructors in the same department."` | Reciprocal reference (`"the same department"`) | Resolves referent to `AI department`; updates entity to `instructors` | *"Show instructors in the AI department."* | `primary_table = 'instructors'`; `departments.code='AI'` preserved |
| `students`, `departments.code='AI'` | `"Top 5 by CGPA."` | Elliptical ranking fragment (`"top 5"`) | Applies limit 5 and sort by `CGPA DESC` to active entity | *"Show top 5 students in the AI department by CGPA."* | `active_limit = 5`; `active_order_by = {'column': 'cgpa', 'direction': 'DESC'}` |
| Any Active Context | `"Show courses in AI and CS departments."` | Multiple Explicit Departments (`AI`, `CS`) | Trigger Structured Clarification Modal (zero arbitrary selection) | Raw Query Echo | No state mutation; prompt: *"Your query specifies multiple departments ('AI', 'CS'). Please clarify which department you want to query."* |
| Any Active Context | `"Show students and instructors in AI."` | Multiple Explicit Primary Entities (`students`, `instructors`) | Trigger Structured Clarification Modal (single entity per turn) | Raw Query Echo | No state mutation; prompt: *"Your query references multiple entities ('instructors', 'students'). Please query one entity at a time."* |
| `students`, `departments.code='AI'` | `"Now show instructors who joined after 2018."` | Connector (`"Now"`) with new primary entity (`instructors`) | Independent Query Topic Shift (`was_follow_up=False`) | *"Show instructors who joined after 2018."* | Re-initializes operational context with `instructors`; previous `AI` department filter expunged |
| `students`, `departments.code='AI'`, `metric='cgpa'` | `"Now list CS students."` | Connector (`"Now"`) with pure list query and new department | Independent List Query (`was_follow_up=False`) | *"List CS students."* | Re-initializes operational context for `CS` students; **sticky metric `cgpa` cleared to `None`** |
| Active Session ($\text{Turns} > 50$) | Any valid turn interaction | Session history bound exceeded | Retain most recent 50 turns (`MAX_TURNS_PER_SESSION = 50`) | Resolved Output | `turn_count` monotonically incremented; `turn_history = turn_history[-50:]`; active slots unaffected |
| Active Session ($t$) | Periodic background interval ($60\text{s}$) | Lifespan background cleanup task | Purge all sessions where $t \ge t_{\text{expires}}$ | N/A | Proactive in-memory garbage collection; prevents memory accumulation |
| Active Session ($t$) | No query for $t \ge 600\text{ seconds}$ | Inactivity timeout threshold | Session marked expired; pruned on next access or by background worker | N/A | Frame evicted; next turn treated as fresh session |
| Active Session ($t$) | Valid query interaction at $t < 600\text{ seconds}$ | Inactivity window valid | Execute turn; sliding TTL refreshed | Resolved Output | $t_{\text{expires}} \leftarrow t_{\text{current}} + 600\text{s}$; frame updated |
| Active Session | Multi-threaded simultaneous queries | Concurrent requests on same/distinct sessions | Synchronize via `threading.RLock()` | Independent thread outputs | Zero race conditions; thread-safe dictionary isolation guaranteed |



