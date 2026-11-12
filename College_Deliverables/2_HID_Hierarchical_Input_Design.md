# QueryMind AI 2.0 — Hierarchical Input Design (HID)
*Deliverable Document 2 | Updated — Phase 5 ContextMind Conversational Context Engine*

> **Status:** Phase 5 Implemented & Verified Specification  
> **Phase Milestone:** Phase 5 (ContextMind Multi-Turn State Management)  
> **Note:** This document outlines the hierarchical interaction tree across the frontend application, user input dispatch layers, conversational context frame resolution, relational database data input hierarchies, NLP pipeline processing stages, and Schema Linking & Join Path hierarchies.


---

## 1. Top-Level Application Input Hierarchy

```mermaid
graph TD
    Root["App Root Container (App.tsx)"]
    
    Header["1. Header & System Status Bar"]
    Main["2. Main Interactive Workspace"]
    Footer["3. System Footer & Academic Disclosures"]

    Root --> Header
    Root --> Main
    Root --> Footer

    Header --> StatusBadge["• Engine Status Badge (Deterministic Local Mode)"]
    Header --> ResetBtn["• Explicit Context Reset Button ('Start Over')"]

    Main --> QuerySection["2.1 Conversational Query Section"]
    Main --> FeedbackSection["2.2 Result & Insight Display Section"]
    Main --> DiagnosticSection["2.3 Developer & Academic Audit Section"]

    QuerySection --> PromptBar["2.1.1 Natural Language Query Input (QueryInput.tsx)"]
    QuerySection --> SuggestionChips["2.1.2 Pre-built Academic Query Chips (Sample Prompts)"]
    QuerySection --> ClarifyModal["2.1.3 Smart Clarification Dialogue (Conditional Modal)"]

    FeedbackSection --> VizContainer["2.2.1 Dynamic Recharts Visualizer (DataVisualizer.tsx)"]
    FeedbackSection --> TableContainer["2.2.2 Universal Data Table (DataTable.tsx)"]
    FeedbackSection --> InsightsCard["2.2.3 InsightMind Evidence Cards (InsightPanel.tsx)"]
    FeedbackSection --> TrustLensCard["2.2.4 TrustLens Transparency Drawer (TrustLens.tsx)"]

    DiagnosticSection --> InspectorPanel["2.3.1 NLP Inspector Panel (NLPInspector.tsx)"]
    DiagnosticSection --> WhatIfPanel["2.3.2 What-If Lab Simulation Controls (WhatIfLab.tsx)"]
```

---

## 2. Academic Relational Database Input Hierarchy

The academic entity tree organizes data input, relational dependencies, and foreign key cascades across 4 hierarchical tiers:

```mermaid
graph TD
    subgraph Tier1 ["Tier 1: Foundational Roots"]
        Dept["departments<br>(department_id PK)"]
        Term["terms<br>(term_id PK)"]
    end

    subgraph Tier2 ["Tier 2: Primary Academic Entities"]
        Student["students<br>(student_id PK, department_id FK)"]
        Instructor["instructors<br>(instructor_id PK, department_id FK)"]
        Course["courses<br>(course_id PK, department_id FK)"]
    end

    subgraph Tier3 ["Tier 3: Academic Operations"]
        Offering["course_offerings<br>(offering_id PK, course_id FK, instructor_id FK, term_id FK)"]
    end

    subgraph Tier4 ["Tier 4: Performance & Evaluation Records"]
        Enrollment["enrollments<br>(enrollment_id PK, student_id FK, offering_id FK)"]
        Assessment["assessments<br>(assessment_id PK, offering_id FK)"]
        Mark["student_marks<br>(mark_id PK, assessment_id FK, enrollment_id FK)"]
    end

    Dept --> Student
    Dept --> Instructor
    Dept --> Course

    Course --> Offering
    Instructor --> Offering
    Term --> Offering

    Student --> Enrollment
    Offering --> Enrollment
    Offering --> Assessment

    Enrollment --> Mark
    Assessment --> Mark
```

### Relational Dependency Invariants:
1. **Root Precedence**: `departments` and `terms` must be seeded prior to any other entities.
2. **Entity Precedence**: `courses`, `instructors`, and `terms` must be established before a `course_offering` can be scheduled.
3. **Evaluation Precedence**: An `enrollment` and an `assessment` must both exist before a `student_mark` can be recorded.

---

## 3. Conversational Context Hierarchy (ContextMind)

```mermaid
graph TD
    ClientSession["Client Session Context<br>(RFC 4122 UUID: sessionStorage)"]
    
    ClientSession --> TTLBranch["Sliding TTL & Timestamps"]
    TTLBranch --> T1["created_at (UTC ISO 8601)"]
    TTLBranch --> T2["last_active (UTC ISO 8601)"]
    TTLBranch --> T3["expires_at (last_active + 600s)"]
    TTLBranch --> T4["ttl_seconds: 600"]

    ClientSession --> ActiveState["Current Operational Context Frame"]
    ActiveState --> ActiveEntities["1. Active Entities<br>• primary_table ('students', 'courses')<br>• department_code ('AI', 'CS')<br>• department_name ('Artificial Intelligence')"]
    ActiveState --> ActiveFilters["2. Active Filters<br>• List[ActiveFilterSchema]<br>• column, operator, value<br>• Single-department invariant"]
    ActiveState --> ActiveMetric["3. Active Metric & Modifier<br>• metric ('attendance', 'cgpa', 'marks')<br>• modifier ('average', 'total', 'max')"]
    ActiveState --> ActiveOrder["4. Active Sorting & Limit<br>• active_order_by (column, direction)<br>• active_limit (integer, e.g. 5)"]
    ActiveState --> ActiveIntent["5. Intent & Resolution Cache<br>• last_intent ('AGGREGATE', 'RANKING')<br>• last_resolved_query"]

    ClientSession --> TurnHistory["Turn 1..N History Stack<br>(Strictly bounded to 50 turns)"]
    TurnHistory --> TurnRecord["TurnRecordSchema<br>• turn_id (Monotonic total lifetime turns)<br>• max 50 retained history records<br>• timestamp (UTC ISO 8601)<br>• user_query (Raw)<br>• resolved_query (Standalone)<br>• was_follow_up (boolean)<br>• modifications (Slot mutation delta)"]
```

### Context Resolution & Slot Merging Hierarchy:
1. **Level 0 (Sanitization & Reset Gate)**: Validates UUID format, checks for explicit reset triggers (`clear context`, `reset`, `start over`). If triggered, immediate frame purge.
2. **Level 1 (Anaphora & Follow-Up Detection)**: Detects pronouns (`their`, `them`, `those`, `these`, `same`), replacement markers (`instead`), and elliptical discourse starters (`now`, `also`, `sort by`). Differentiates independent queries with discourse markers from follow-ups (queries introducing a new entity start a fresh context; pure list queries clear sticky metrics).
3. **Level 2 (Referent Binding & Clarification)**: If pronouns present without active context $\to$ triggers structured clarification. If multiple departments or multiple primary entities are present $\to$ triggers structured clarification (zero arbitrary selection). If context is unambiguous $\to$ binds referents to active entities/filters.
4. **Level 3 (Deterministic Natural Language Synthesis)**: Synthesizes fully qualified, unambiguous standalone query text.
5. **Level 4 (State Merging & Contradiction Resolution)**: Overrides conflicting slots (e.g., department $CS$ overrides $AI$), preserves orthogonal slots, clears sticky metrics on list queries, bounds turn history to 50 turns (`MAX_TURNS_PER_SESSION = 50`), refreshes sliding TTL, and registers for lifespan-managed background cleanup.

---

## 4. NLP Preprocessing & Intent Classification Hierarchy

The Phase 3 NLP processing hierarchy operates in three sequential levels:

```mermaid
graph TD
    Raw["Level 1: Lexical Normalization & Tokenization"]
    Raw --> Norm["Whitespace Sanitization & Control Character Removal"]
    Norm --> Tok["Word, Contraction, Symbol Token Extraction"]

    Tok --> Level2["Level 2: Syntactic & Morphological Analysis"]
    Level2 --> POS["Rule-Based POS Tagging<br>(30 supported Penn Treebank-style POS tags)"]
    Level2 --> Lem["Morphological Lemmatization (Contextual POS + Exceptions)"]
    Level2 --> Ngram["Word & Character N-Gram Extraction (1..3 grams)"]

    Level2 --> Level3["Level 3: Supervised Statistical Intent Classification"]
    Level3 --> Vect["TF-IDF Vectorization (1-2 Word N-Grams)"]
    Vect --> LogReg["Multinomial Logistic Regression"]
    LogReg --> Softmax["Softmax Probability Computation (Uncalibrated, 7 Classes)"]
    Softmax --> Decision["Ambiguity & Out-of-Domain Separation Rules"]
    Decision --> Output["Structured Diagnostic Intent Payload"]
```

---

## 5. Schema Linking & Minimal Join Graph Hierarchy (Level 4)

The Phase 4 Schema Linking layer bridges linguistic intent and physical database relationships:

```mermaid
graph TD
    NLP["Input: NLP Preprocessed Tokens, N-Grams & Query"]
    
    subgraph Stage1 ["Stage 1: Entity & Value Extraction"]
        RegexExtract["Regex Extractor<br>• Roll Number: \\b\\d{4}-[A-Za-z]{2,4}-\\d{3,4}\\b<br>• Course Code: \\b[A-Za-z]{2,4}\\d{3}\\b"]
        LiteralMatch["Domain Literal Matcher<br>• Department Codes (AI, CS, EE, ME, MATH)<br>• Enums (Probation, Active, Quiz, Midterm)"]
    end

    subgraph Stage2 ["Stage 2: Attribute & Table Semantic Linking"]
        MultiCol["Multi-word Column Matcher<br>(e.g. 'attendance percentage', 'max marks')"]
        AmbiguityCheck["Bare Ambiguity Checker<br>(grades, year, status, name)"]
        TableMatch["Table Synonym Matcher<br>(learners -> students, faculty -> instructors)"]
        SingleCol["Single-word Column Matcher<br>(cgpa, credits, roll_number)"]
        OutCheck["Unsupported Entity Blacklist<br>(hostel, cafeteria, transport)"]
    end

    subgraph Stage3 ["Stage 3: Join Graph Resolution G = (V, E)"]
        GraphAdj["Bidirectional Graph Adjacency<br>(9 Vertices, 11 FK Edges)"]
        BFSShortest["BFS Shortest Path Resolver<br>(Direct & Multi-hop Paths)"]
        AltDetect["Alternative Shortest Path Detector<br>(e.g. Dept -> Offerings via Course vs Instructor)"]
        SteinerTree["Minimal Steiner Tree Join Optimizer<br>(Cycle-Free Connected Tree for >= 3 Tables)"]
    end

    NLP --> Stage1
    Stage1 --> Stage2
    Stage2 --> Stage3
    Stage3 --> SchemaOut["Output: SchemaLinkResponse (Tables, Columns, Values, Join Steps)"]
```


