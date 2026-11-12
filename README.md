# QueryMind AI 2.0

**An NLP-Based Conversational Text-to-SQL System with Intelligent Data Visualization and Evidence-Based Insights**

QueryMind AI 2.0 is an intelligent, transparent full-stack conversational data analytics platform. It allows users to ask natural-language questions over a relational academic database, translates queries into safe, dialect-validated SQLite SQL using SQLGlot AST guardrails, executes queries in a hardened read-only runtime, visualizes results dynamically using Recharts, and produces grounded, evidence-based statistical insights.

---

## Key Features

- **Grounded Conversational Text-to-SQL**: Local deterministic translation pipeline powered by NLTK and Scikit-learn without requiring paid external LLMs.
- **Core Course NLP Techniques**:
  - Live tokenization, lemmatization, and rule-based POS tagging (30 supported Penn Treebank-style POS tags: 23 grammatical tags + 7 punctuation/symbol tags).
  - Character and word n-gram extraction (unigrams, bigrams, trigrams).
  - Supervised Intent Classification (Multinomial Logistic Regression with Softmax class probabilities across 7 canonical intents).
  - NLP Inspector diagnostic interface for academic review.
- **Deterministic Schema Linking & Join Graph Construction**:
  - Dynamic runtime introspection of 9 normalized academic tables via SQLAlchemy Inspector.
  - Comprehensive academic synonym dictionary linking tables, attributes, and categorical values.
  - Regex identification of student roll numbers (`\b\d{4}-[A-Za-z]{2,4}-\d{3,4}\b`) and course codes (`\b[A-Za-z]{2,4}\d{3}\b`).
  - Strict polysemy & ambiguity detection for multi-candidate attributes (`grades`, `year`, `status`, `name`) and unsupported terms (`hostel`, `cafeteria`).
  - Bidirectional foreign-key Join Graph ($G=(V, E)$) computing shortest-path BFS traversals, multiple candidate path detection, and minimal Steiner join trees.
- **ContextMind (Conversational Context Engine & Multi-Turn State Management)**:
  - Strongly-typed structured Context Frame: `<Entity References, Active Filters, Metric, Grouping, Sort Order, Limit, Intent, Turn History (bounded to 50), TTL>`.
  - Deterministic anaphora and pronoun resolution (*"that department"*, *"their attendance"*, *"sort them by credits"*, *"CS students instead"*).
  - Thread-safe volatile in-memory session manager with re-entrant locking (`RLock`) and zero cross-session data leakage.
  - Dual eviction model: lazy on-access expiration + FastAPI lifespan-managed periodic background cleanup (`SESSION_CLEANUP_INTERVAL_SECONDS = 60`).
  - Strict memory bounding: 50-turn retention cap per session (`MAX_TURNS_PER_SESSION = 50`) with monotonic lifetime `turn_count`.
  - Slot-based context merging with contradiction elimination (single active department filter invariant) and sticky metric clearing on list queries.
  - Multi-candidate clarification guards preventing arbitrary selection for queries with multiple departments or multiple primary entities.
  - Explicit reset triggers (*"clear context"*, *"reset"*, *"start over"*, *"new query"*) and service-level resets.
- **QueryDoctor (SQL Error Diagnosis & Repair)**:
  - Intelligent diagnosis of schema and syntax errors.
  - At most one controlled AST repair attempt with complete security re-validation.
  - Zero-tolerance immediate rejection for security violations (DML, DDL, multi-statement, injection).
- **InsightMind (Evidence-Based Insights)**:
  - Automated statistical evaluation: extrema, term-over-term trends, outliers, and category variances.
  - Every insight is mathematically grounded in returned query rows (no speculative hallucinations).
- **TrustLens (Auditability & Transparency)**:
  - Plain-English breakdown of tables joined, filter criteria, aggregations, and query limitations.
- **What-If Lab (Hypothetical Simulation)**:
  - In-memory Pandas perturbation sandbox for exploring scenario adjustments without modifying database records.
- **Intelligent Data Visualization**:
  - Automated chart advisor recommending KPI cards, Bar charts, Line charts, Area charts, Scatter plots, Donut charts, or universal Data Tables.

---

## System Architecture

```
                       ┌───────────────────────────────────────────────┐
                       │          QueryMind AI User Interface          │
                       │     (React + TypeScript + Vite + Tailwind)     │
                       └───────────────────────┬───────────────────────┘
                                               │ HTTP / REST
                                               ▼
                       ┌───────────────────────────────────────────────┐
                       │            FastAPI Backend Engine             │
                       │           (Python 3.11 + Pydantic)            │
                       └───────┬───────────────────────────────┬───────┘
                               │                               │
                               ▼                               ▼
         ┌───────────────────────────────┐   ┌───────────────────────────────┐
         │     NLP & ML Query Engine     │   │     SQLGlot AST Validator     │
         │  • Intent Classification      │   │  • Syntax & Dialect Check     │
         │    (Scikit-Learn TF-IDF)      │   │  • Injection Prevention       │
         │  • Entity & Schema Linker     │   │  • Read-Only SELECT Safety    │
         │    (NLTK + WordNet)           │   └───────────────┬───────────────┘
         └───────────────┬───────────────┘                   │
                         │                                   │
                         └─────────────────┬─────────────────┘
                                           │ Safe SQL
                                           ▼
                       ┌───────────────────────────────────────────────┐
                       │              SQLAlchemy + SQLite              │
                       │    (Read-Only: mode=ro, PRAGMA query_only)    │
                       └───────────────────────┬───────────────────────┘
                                               │ Query Result Rows
                                               ▼
                       ┌───────────────────────────────────────────────┐
                       │         Pandas Transformation Engine          │
                       │  • Typing, Aggregation & Statistics           │
                       │  • Automated Chart Recommendation             │
                       └───────────────────────┬───────────────────────┘
                                               │ Structured Payload
                                               ▼
                       ┌───────────────────────────────────────────────┐
                       │      Recharts Interactive Data Visualizer     │
                       │   (Bar, Line, Area, Pie, Heatmap, Table)      │
                       └───────────────────────────────────────────────┘
```

---

## Academic Database Domain

The system models a comprehensive **Academic Institution** with 9 normalized entities:
1. `departments` (department_id, name, code, established_year, building)
2. `students` (student_id, department_id, roll_number, first_name, last_name, enrollment_year, current_semester, cgpa, academic_status)
3. `instructors` (instructor_id, department_id, first_name, last_name, designation, joining_year)
4. `courses` (course_id, department_id, course_code, course_name, credits, course_level)
5. `terms` (term_id, term_name, academic_year, semester_type, start_date, end_date)
6. `course_offerings` (offering_id, course_id, instructor_id, term_id, section, classroom)
7. `enrollments` (enrollment_id, student_id, offering_id, attendance_percentage, final_grade, grade_points, enrollment_status)
8. `assessments` (assessment_id, offering_id, title, assessment_type, max_marks, weightage_percent)
9. `student_marks` (mark_id, assessment_id, enrollment_id, marks_obtained)

---

## Directory Structure

```
QueryMind-AI/
├── .vscode/                               # Workspace formatting, Ruff, Prettier & Python settings
├── QueryMind_Environment_Setup/           # Verified environment setup & audit records
├── College_Deliverables/                  # 5 Formal academic deliverables (LID, HID, Code, Flow, Decision)
├── docs/                                  # Technical architecture & schema specifications
├── backend/                               # Python 3.11 Backend
│   ├── .venv/                             # Dedicated backend virtual environment
│   ├── requirements.txt                   # FastAPI, SQLAlchemy, Pandas, Scikit-learn, NLTK, SQLGlot
│   ├── app/
│   │   ├── api/                           # FastAPI route endpoints
│   │   ├── core/                          # Config & database engines (write + read-only)
│   │   ├── models/                        # SQLAlchemy 2.x relational ORM domain models
│   │   ├── schemas/                       # Pydantic validation schemas
│   │   └── services/                      # Analytical and NLP service modules
│   ├── data/                              # SQLite academic database (academic.db)
│   ├── scripts/                           # Database initialization & deterministic seeder
│   │   ├── init_db.py                     # Schema creation and reset utility
│   │   └── seed_db.py                     # Deterministic synthetic data generator (Seed=42)
│   └── tests/                             # Pytest automated test suites (health, db, models, seed)
├── frontend/                              # React 19 + TypeScript + Vite + Tailwind CSS + Recharts
│   ├── src/
│   │   ├── components/                    # UI cards, Visualizer, SQL Inspector, NLP Inspector, What-If Lab
│   │   ├── services/                      # Axios API clients
│   │   └── types/                         # TypeScript interfaces
│   └── package.json
├── .gitignore                             # Comprehensive Git exclusions
└── README.md                              # This file
```

---

## Academic Deliverables

This repository maintains 5 formal academic engineering deliverables under [`College_Deliverables/`](./College_Deliverables/):
1. **LID (Logical Input Design)**: Validation rules, types, boundaries, sanitization regexes.
2. **HID (Hierarchical Input Design)**: UI layout tree and conversational context frame hierarchy.
3. **Code File (Source Code Index)**: File directory, module roles, class/function catalogues.
4. **Flow File (Flowcharts)**: Mermaid sequence diagrams, state machines, and repair loops.
5. **Decision File (Decision Tables & Rules)**: Truth tables for chart selection, ambiguity, and SQL repair.

---

## Setup & Run Instructions

### Prerequisites
- **Python**: Version 3.11 (Python 3.11.9 recommended)
- **Node.js**: Version 18.x or 20.x+ (npm included)
- **Git**

### Backend Setup & Execution

1. Navigate to the backend directory:
   ```powershell
   cd backend
   ```

2. Activate the Python 3.11 virtual environment:
   ```powershell
   # Windows PowerShell
   .\.venv\Scripts\Activate.ps1
   ```

3. Configure environment settings:
   ```powershell
   # Copy template if .env does not already exist
   Copy-Item .env.example .env
   ```

4. Initialize and Seed the Academic SQLite Database:
   ```powershell
   # Initialize tables
   python scripts/init_db.py

   # Seed 1,786 deterministic records (Seed=42)
   python scripts/seed_db.py
   ```

5. Run test suites:
   ```powershell
   # Run all 131 tests (database, models, seeding, health, NLP, intent classification, schema linker, context engine)
   pytest -v tests

   # Or run focused Phase 5 ContextMind tests
   pytest -v tests/test_context_engine.py
   ```

6. Run the FastAPI development server:
   ```powershell
   python -m uvicorn app.main:app --reload --port 8000
   ```
   The backend API will be available at: `http://localhost:8000`  
   Interactive API docs (Swagger): `http://localhost:8000/docs`  
   Health check endpoint: `http://localhost:8000/api/health`  
   NLP Diagnostic Inspector: `http://localhost:8000/api/nlp/inspect?query=What+is+the+average+CGPA+in+AI%3F`  
   Schema Catalog: `http://localhost:8000/api/schema/catalog`  
   Schema Linker Endpoint: `http://localhost:8000/api/schema/link`  
   Join Path Resolver: `http://localhost:8000/api/schema/join-path?tables=departments,students`  
   Context Resolver Endpoint: `http://localhost:8000/api/context/resolve`  
   Context Frame Inspection: `http://localhost:8000/api/context/frame/{session_id}`  
   Context Reset Endpoint: `http://localhost:8000/api/context/reset/{session_id}`


### Frontend Setup & Execution

1. Navigate to the frontend directory:
   ```powershell
   cd frontend
   ```

2. Configure environment settings:
   ```powershell
   Copy-Item .env.example .env
   ```

3. Run the development server (configured with `/api` reverse proxy to `:8000`):
   ```powershell
   npm run dev
   ```
   The frontend UI will be available at: `http://localhost:5173`

4. Type-check and build for production:
   ```powershell
   npm run build
   ```


