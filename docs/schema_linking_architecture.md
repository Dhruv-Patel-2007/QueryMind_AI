# QueryMind AI 2.0 — Schema Linking & Join Graph Architecture

## 1. Overview and Architectural Purpose

In the QueryMind AI 2.0 text-to-SQL architecture, **Phase 4: Schema Linking & Join Graph Construction** serves as the deterministic structural bridge connecting unstructured natural language queries to the underlying academic relational schema. 

```
                                  [ User Query ]
                                         │
                                         ▼
                     [ Phase 3: NLP Preprocessor & Classifier ]
                        (Tokens, Lemmas, N-Grams, POS Tags, Intent)
                                         │
                                         ▼
                     ┌─────────────────────────────────────────┐
                     │   Phase 4: Semantic Schema Linker       │
                     ├─────────────────────────────────────────┤
                     │ 1. Identifier Extraction (Regex)        │
                     │ 2. Multi-word Column Matching           │
                     │ 3. Domain Literal Value Linking         │
                     │ 4. Polysemy & Ambiguity Detection       │
                     │ 5. Table & Entity Synonym Resolution    │
                     │ 6. Single-Word Column Linking           │
                     │ 7. Unsupported Entity Blacklist         │
                     └─────────────────────────────────────────┘
                                         │
                                         ▼
                     ┌─────────────────────────────────────────┐
                     │   Phase 4: FK Join Graph (G = (V, E))   │
                     ├─────────────────────────────────────────┤
                     │ • BFS Shortest Path Resolver            │
                     │ • Multi-Table Steiner Tree Algorithm    │
                     │ • Alternative Path Ambiguity Detector   │
                     └─────────────────────────────────────────┘
                                         │
                                         ▼
               [ Structured Schema Link & Minimal Join Path Specification ]
                                         │
                                         ▼
                     [ Phase 6: AST-Based SQL Query Generator ]
```

### Key Responsibilities
1. **Dynamic Introspection**: Reflects directly on the live SQLite database through SQLAlchemy, extracting tables, columns, data types, primary keys, foreign keys, and unique constraints without hardcoding schema invariants.
2. **Deterministic Entity & Attribute Linking**: Maps academic terminology, domain synonyms, abbreviations, and composite phrases to fully-qualified database tables and columns.
3. **Domain Literal Extraction**: Identifies domain identifiers (e.g., student roll numbers `2024-CS-001`, course codes `CS101`, department codes `AI`), academic statuses, and categorical enum values.
4. **Polysemy & Ambiguity Detection**: Flags polysemous tokens (such as `grades`, `status`, `year`) that could refer to multiple attributes across tables without silently guessing.
5. **Unsupported Entity Detection**: Identifies out-of-catalog entities (e.g., `hostel`, `cafeteria`, `transport`) and marks queries as ambiguous with actionable explanations.
6. **Join Graph Topology & Minimal Join Resolution**: Represents database relationships as a bidirectional graph $G=(V, E)$, computes exact shortest paths, detects multiple candidate paths, and synthesizes minimal Steiner join trees across 3+ tables.

---

## 2. Dynamic Schema Introspection & Catalog

The `SchemaCatalog` class inspects the live SQLite database at startup using a read-only SQLAlchemy engine (`read_only_engine`).

### 2.1 Introspected Database Schema (9 Tables)

| Table Name | Entity Name | Primary Key | Foreign Keys | Key Unique Constraints / Indexes |
|---|---|---|---|---|
| `departments` | Department | `department_id` | *(None)* | `code` (Unique), `name` (Unique) |
| `students` | Student | `student_id` | `department_id` $\to$ `departments.department_id` | `roll_number` (Unique) |
| `instructors` | Instructor | `instructor_id` | `department_id` $\to$ `departments.department_id` | `email` (Unique) |
| `courses` | Course | `course_id` | `department_id` $\to$ `departments.department_id` | `course_code` (Unique) |
| `terms` | Term | `term_id` | *(None)* | `term_name` (Unique), `(academic_year, semester_type)` |
| `course_offerings`| Course Offering | `offering_id` | `course_id` $\to$ `courses.course_id`, `term_id` $\to$ `terms.term_id`, `instructor_id` $\to$ `instructors.instructor_id` | `(course_id, term_id, section)` |
| `enrollments` | Enrollment | `enrollment_id` | `student_id` $\to$ `students.student_id`, `offering_id` $\to$ `course_offerings.offering_id` | `(student_id, offering_id)` |
| `assessments` | Assessment | `assessment_id` | `offering_id` $\to$ `course_offerings.offering_id` | `(offering_id, title)` |
| `student_marks` | Student Mark | `mark_id` | `assessment_id` $\to$ `assessments.assessment_id`, `enrollment_id` $\to$ `enrollments.enrollment_id` | `(assessment_id, enrollment_id)` |

### 2.2 Domain Synonym & Metadata Enrichment

The introspection engine supplements raw SQL metadata with rich academic domain knowledge:
- **Table Synonyms**: Maps aliases like `learners` $\to$ `students`, `faculty` $\to$ `instructors`, `curriculum` $\to$ `courses`, `semesters` $\to$ `terms`, `scores` $\to$ `student_marks`.
- **Column Synonyms**: Maps phrases like `cgpa` / `grade point average` $\to$ `students.cgpa`, `attendance` $\to$ `enrollments.attendance_percentage`, `max marks` $\to$ `assessments.max_marks`, `credits` $\to$ `courses.credits`.
- **Domain Literals**: Maps department abbreviations (`CS`, `AI`, `EE`, `ME`, `MATH`), academic statuses (`Active`, `Probation`, `Graduated`, `Suspended`), enrollment outcomes (`Enrolled`, `Completed`, `Dropped`), and assessment categories (`Quiz`, `Assignment`, `Midterm`, `Final`, `Project`).

---

## 3. Semantic Schema Linking Pipeline

The `SchemaLinker.link_query()` method executes a multi-stage deterministic pipeline:

```
[ Input Query: "Find attendance and CGPA of learners in AI department" ]
                               │
   ┌───────────────────────────┴───────────────────────────┐
   │ 1. Regex Identifier Extraction                        │
   │    • Roll Numbers: \b\d{4}-[A-Za-z]{2,4}-\d{3,4}\b     │
   │    • Course Codes: \b[A-Za-z]{2,4}\d{3}\b             │
   └───────────────────────────┬───────────────────────────┘
                               ▼
   ┌───────────────────────────────────────────────────────┐
   │ 2. Multi-Word Column Linking (Bigrams & Trigrams)      │
   │    • "attendance percentage" -> enrollments.attendance│
   └───────────────────────────┬───────────────────────────┘
                               ▼
   ┌───────────────────────────────────────────────────────┐
   │ 3. Domain Literal Value Linking                       │
   │    • "AI" -> departments.code = 'AI'                  │
   └───────────────────────────┬───────────────────────────┘
                               ▼
   ┌───────────────────────────────────────────────────────┐
   │ 4. Polysemy & Ambiguity Detection                     │
   │    • Bare tokens in AMBIGUOUS_COLUMNS_MAP             │
   │      (grade, year, status, name)                      │
   └───────────────────────────┬───────────────────────────┘
                               ▼
   ┌───────────────────────────────────────────────────────┐
   │ 5. Table & Entity Synonym Resolution                  │
   │    • "learners" -> students                           │
   │    • "department" -> departments                      │
   └───────────────────────────┬───────────────────────────┘
                               ▼
   ┌───────────────────────────────────────────────────────┐
   │ 6. Single-Word Column Linking                         │
   │    • "cgpa" -> students.cgpa                          │
   └───────────────────────────┬───────────────────────────┘
                               ▼
   ┌───────────────────────────────────────────────────────┐
   │ 7. Unsupported Entity Blacklist Detection             │
   │    • Checks blacklist: hostel, cafeteria, bus, etc.   │
   └───────────────────────────┬───────────────────────────┘
                               ▼
   ┌───────────────────────────────────────────────────────┐
   │ 8. Join Graph Path Resolution                         │
   │    • Tables: {departments, students, enrollments}     │
   │    • Resolved Path: departments <-> students <-> enr   │
   └───────────────────────────────────────────────────────┘
```

### Confidence Scoring & Match Types
- **`EXACT` (1.00)**: Direct token match against official table or column name.
- **`SYNONYM_MATCH` (0.90 – 0.98)**: Canonical academic dictionary synonym match (multi-word phrases score 0.98, single words 0.90).
- **`CONTEXT_RESOLVED` (0.95)**: Ambiguous token resolved using explicit table context in the same query.

---

## 4. Ambiguity and Out-of-Catalog Entity Detection

### 4.1 Ambiguous Attributes (Polysemy)
Certain tokens cannot be unambiguously assigned to a single column without context:
- **`grades` / `grade`**: Plausible candidates include `student_marks.marks_obtained` (numeric score), `enrollments.final_grade` (letter grade A-F), or `enrollments.grade_points` (0.00 - 4.00).
- **`status`**: Plausible candidates include `students.academic_status` (Active, Probation) or `enrollments.enrollment_status` (Enrolled, Completed, Dropped).
- **`year`**: Plausible candidates include `students.enrollment_year`, `instructors.joining_year`, `terms.academic_year`, or `departments.established_year`.
- **`name`**: Plausible candidates include `departments.name`, `courses.course_name`, or `students.first_name`.

When these tokens appear in isolation without clarifying phrases (e.g., `grades` instead of `letter grade` or `final grade`), `SchemaLinker` sets:
```json
{
  "is_ambiguous": true,
  "ambiguity_reason": "MULTIPLE_COLUMN_CANDIDATES",
  "ambiguous_candidates": [
    {
      "token": "grades",
      "candidates": [
        {"table": "student_marks", "column": "marks_obtained", "description": "Numerical score obtained on an assessment"},
        {"table": "enrollments", "column": "final_grade", "description": "Letter grade (A, B, C) awarded for a completed course"},
        {"table": "enrollments", "column": "grade_points", "description": "Numeric grade points (0.0 to 4.0) earned for course"}
      ],
      "message": "Token 'grades' could refer to multiple schema attributes across tables."
    }
  ]
}
```

### 4.2 Unsupported Entities (Out-of-Domain Boundaries)
Queries mentioning non-academic or unmodeled entities (e.g., `cafeteria`, `hostel`, `transport`, `tuition`, `wifi`) are explicitly flagged with `ambiguity_reason = "UNSUPPORTED_ENTITIES"`, preventing hallucinated schema elements.

---

## 5. Join Graph ($G=(V, E)$) & Minimal Path Resolution

### 5.1 Graph Topology

The academic schema comprises 9 vertices ($|V|=9$) and 11 bidirectional foreign key edges ($|E|=11$):

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

### 5.2 Directed Edge Semantics
- **Forward Edge (`MANY_TO_ONE`)**: Referencing child table to referenced parent table (e.g., `students.department_id = departments.department_id`).
- **Reverse Edge (`ONE_TO_MANY`)**: Referenced parent table to referencing child table (e.g., `departments.department_id = students.department_id`).

### 5.3 Shortest Path Resolution (BFS)
For any pair of tables $(u, v)$, the graph searches for the path with minimal hop count.
- **Direct 1-Hop**: `departments` $\leftrightarrow$ `students` (1 hop)
- **2-Hop**: `students` $\to$ `departments` $\to$ `courses` (2 hops)
- **3-Hop**: `departments` $\to$ `students` $\to$ `enrollments` $\to$ `student_marks` (3 hops)

### 5.4 Multiple Shortest Path Detection
Between `departments` and `course_offerings`, there are two distinct 2-hop shortest paths:
1. **Path A (via curriculum)**: `departments` $\to$ `courses` $\to$ `course_offerings`
2. **Path B (via faculty)**: `departments` $\to$ `instructors` $\to$ `course_offerings`

When multiple shortest paths exist, `JoinGraph` detects the ambiguity, returns Path A as primary, records Path B in `alternative_paths`, and flags `alternative_paths_count > 0` with `MULTIPLE_JOIN_PATHS`.

### 5.5 Multi-Table Steiner Tree Approximation Algorithm

The Steiner Tree Problem in Graphs (finding a tree of minimal total edge weight/hops spanning a designated subset of terminal vertices $T \subseteq V$) is known to be **NP-hard** in general graph theory. 

Rather than relying on exponential-time exact solvers (e.g. Dreyfus-Wagner or branch-and-cut), `JoinGraph.resolve_multi_table_join` implements a mathematically grounded, polynomial-time approximation heuristic based on the **Takahashi-Matsuyama (1980) Multi-Source BFS Algorithm** evaluated across all candidate root anchors:

```
[ Target Terminals T = {t_1, t_2, ..., t_k} ]
                      │
                      ▼
       [ For each candidate root r in V ]
                      │
                      ▼
   ┌───────────────────────────────────────────────┐
   │ 1. Initialize Tree: V_tree = {r}, E_tree = [] │
   │ 2. While (T \ V_tree) is not empty:           │
   │    • Run Multi-Source BFS from V_tree to find │
   │      nearest unreached terminal t_i in T      │
   │    • Add shortest path edges to E_tree        │
   │    • Add path nodes to V_tree                 │
   │ 3. Verify acyclic tree property:              │
   │    |E_tree| == |V_tree| - 1                   │
   └──────────────────────┬────────────────────────┘
                          │
                          ▼
        [ Select Tree with Minimum |E_tree| ]
    (Preserve alternative distinct minimal trees in alternative_paths)
                          │
                          ▼
       [ Topological BFS Ordering from Anchor ]
```

#### Mathematical Properties & Algorithmic Bounds
1. **Algorithmic Classification**: Greedy Shortest-Path Tree Approximation Heuristic (Takahashi-Matsuyama Heuristic over All-Roots).
2. **Theoretical Approximation Bound**: Proven $2\left(1 - \frac{1}{k}\right)$-approximation ratio on general graphs, where $k = |T|$ is the number of terminal tables.
3. **Time Complexity**: $O(|V| \cdot k \cdot (|V| + |E|))$. For our academic schema graph ($|V|=9$ tables, $|E|=11$ FK constraints), $9 \times k \times 20 \le 1,620$ operations, executing in under $1\text{ ms}$.
4. **Space Complexity**: $O(|V| + |E|)$ auxiliary space for queue and visited sets.
5. **Acyclic Tree Invariant**: By growing the tree strictly via multi-source BFS from existing tree vertices to unreached terminals, no cycle-closing edges are ever introduced. The resulting subgraph is mathematically guaranteed to be a connected tree satisfying $|E_{\text{tree}}| = |V_{\text{tree}}| - 1$.
6. **Shared Intermediate Node Reuse**: Multi-source BFS connects to the *nearest* already-joined node, maximizing intermediate table sharing (e.g., `course_offerings`, `enrollments`) without creating redundant parallel branches.
7. **Alternative Tree Preservation & Limitations**:
   - For 2-table queries: `alternative_paths` preserves all minimal BFS shortest paths of equal hop count (e.g. curriculum path vs. faculty path between `departments` and `course_offerings`).
   - For $\ge 3$ tables: `alternative_paths` records alternative minimal trees discovered across different candidate roots with distinct edge sets. It does **not** perform exhaustive combinatorial enumeration of all spanning Steiner topologies, avoiding combinatorial explosion.
8. **Empirical Benchmarks vs. Theoretical Guarantees**:
   - **Theoretical Guarantee**: The worst-case approximation ratio is mathematically bounded by $2\left(1 - \frac{1}{k}\right)$, where $k = |T|$ is the number of terminal tables.
   - **Exhaustive Empirical Verification**: An exhaustive evaluation across all $502$ non-trivial terminal subsets ($\sum_{k=2}^9 \binom{9}{k} = 502$) on the 9-node academic graph compared the heuristic against an exact brute-force minimum Steiner reference solver:
     - **Exact Globally Minimal Match**: $499$ of $502$ combinations (**$99.40\%$**) achieve the exact minimum edge count.
     - **Heuristic Divergence**: Exactly $3$ of $502$ combinations (**$0.60\%$**) deviate by $+1$ edge due to greedy BFS tie-breaking:
       1. `{'courses', 'student_marks', 'students', 'terms'}`: heuristic = $6$ hops, exact = $5$ hops (approximation ratio = $1.20 \le 1.50$).
       2. `{'instructors', 'student_marks', 'students', 'terms'}`: heuristic = $6$ hops, exact = $5$ hops (approximation ratio = $1.20 \le 1.50$).
       3. `{'courses', 'instructors', 'student_marks', 'students', 'terms'}`: heuristic = $7$ hops, exact = $6$ hops (approximation ratio = $1.167 \le 1.60$).
     - In all 3 divergence cases, the empirical ratio ($\le 1.20$) remains well within the theoretical worst-case upper bound of $2(1 - 1/k)$. Universal theoretical optimality is not claimed; the algorithm is formally characterized as an approximation heuristic.

---

## 6. REST API Endpoints

The schema module exposes four REST endpoints mounted at `/api/schema`:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/schema/catalog` | Returns complete introspected schema for all 9 tables, PKs, FKs, UQs, and domain synonyms. |
| `POST` | `/api/schema/link` | Semantic schema linking, literal extraction, polysemy analysis, and join path resolution for a user query. |
| `POST` | `/api/schema/join-path` | Computes minimal connecting join path across a JSON list of tables. |
| `GET` | `/api/schema/join-path?tables=t1,t2` | Convenience GET endpoint for join path resolution. |

### Sample Response (`POST /api/schema/link`)
```json
{
  "status": "success",
  "query": "Find attendance and CGPA of learners in AI department",
  "linked_tables": ["departments", "enrollments", "students"],
  "linked_columns": {
    "enrollments": [
      {
        "column_name": "attendance_percentage",
        "matched_token": "attendance",
        "confidence": 0.9,
        "match_type": "SYNONYM_MATCH"
      }
    ],
    "students": [
      {
        "column_name": "cgpa",
        "matched_token": "cgpa",
        "confidence": 0.9,
        "match_type": "SYNONYM_MATCH"
      }
    ]
  },
  "linked_values": [
    {
      "matched_token": "ai",
      "table_name": "departments",
      "column_name": "code",
      "value": "AI",
      "confidence": 1.0
    }
  ],
  "unsupported_entities": [],
  "is_ambiguous": false,
  "ambiguity_reason": null,
  "ambiguous_candidates": [],
  "join_path": {
    "status": "success",
    "is_connected": true,
    "anchor_table": "departments",
    "joined_tables": ["departments", "students", "enrollments"],
    "total_hops": 2,
    "join_steps": [
      {
        "from_table": "departments",
        "to_table": "students",
        "join_type": "INNER JOIN",
        "condition": "students.department_id = departments.department_id",
        "direction": "ONE_TO_MANY"
      },
      {
        "from_table": "students",
        "to_table": "enrollments",
        "join_type": "INNER JOIN",
        "condition": "enrollments.student_id = students.student_id",
        "direction": "ONE_TO_MANY"
      }
    ],
    "alternative_paths_count": 0,
    "error": null
  },
  "execution_time_ms": 3.42
}
```

---

## 7. Verification and Testing

The automated test suite `backend/tests/test_schema_linker.py` comprises 18 dedicated test functions verifying:
1. Full 9-table dynamic introspection (columns, data types, primary keys, foreign keys, unique constraints).
2. Entity linking exact matches and academic domain synonyms.
3. Column linking and multi-word attribute synonyms.
4. Value linking for department codes, student roll numbers (`\b\d{4}-[A-Za-z]{2,4}-\d{3,4}\b`), course codes (`\b[A-Za-z]{2,4}\d{3}\b`), course names, and status enums.
5. Ambiguity detection for polysemous tokens (`grades`, `status`).
6. Unsupported entity detection (`cafeteria`, `hostel`, `dormitory`).
7. 1-hop direct joins and bidirectional edges.
8. Multi-hop shortest paths (2-hop and 3-hop traversal).
9. Three-table Steiner tree connections with minimal hops and topological ordering.
10. Four-table Steiner tree connections across multiple hierarchy levels.
11. Shared intermediate node reuse without redundant branching.
12. Cyclic graph avoidance on relational cycles (departments-courses-offerings-instructors).
13. Disconnected and unknown table error handling.
14. Multiple candidate join path ambiguity detection with complete foreign key representations.
15. Read-only database safety and introspection security.
16. Schema Catalog API endpoint (`GET /api/schema/catalog`).
17. Schema Linking API endpoint (`POST /api/schema/link`).
18. Join Path API endpoints (`POST` and `GET /api/schema/join-path`).

All 88 tests across the backend test suite pass with 100% success in under 7 seconds.

