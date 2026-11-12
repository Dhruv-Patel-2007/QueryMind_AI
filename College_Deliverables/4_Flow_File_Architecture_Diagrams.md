# QueryMind AI 2.0 — Architecture & Process Flowcharts (Flow File)
*Deliverable Document 4 | Updated — Phase 4 Schema Linking & Join Graph Construction*

> **Status:** Phase 4 Approved Process Diagram Specification  
> **Phase Milestone:** Phase 4 (Schema Linking & Join Graph Construction)  
> **Note:** This document provides formal Mermaid diagrams documenting architectural flows, database lifecycles, security execution boundaries, NLP intent classification decision pipelines, and Schema Linking & Steiner Tree Join Graph resolution algorithms.


---

## 1. High-Level System Architecture Flow

```mermaid
flowchart TD
    UserQuery(["User Natural Language Query"]) --> ContextModule["ContextMind Engine<br>(Session Memory & Anaphora Resolution)"]
    ContextModule --> NLPModule["NLP Pipeline<br>(Tokenization, POS, N-Grams, Intent Classifier)"]
    
    NLPModule --> AmbiguityCheck{"Ambiguity Detected?<br>(Confidence < 0.55 OR Polysemy)"}
    AmbiguityCheck -- "Yes" --> ClarificationResponse(["Smart Clarification Modal"])
    
    AmbiguityCheck -- "No" --> SchemaLinker["Semantic Schema Linker<br>(Maps slots to Academic Schema Graph)"]
    SchemaLinker --> SQLGen["SQLGlot AST Generator<br>(Constructs SQLite Dialect Query)"]
    
    SQLGen --> SecurityCheck{"SQLGlot Security Audit<br>(Single SELECT, Read-Only, Table Whitelist)"}
    SecurityCheck -- "Fails Security Policy" --> SecurityReject(["REJECT IMMEDIATELY<br>(No Repair Allowed)"])
    
    SecurityCheck -- "Passes Security Policy" --> DBExec["Read-Only SQLite Engine<br>(PRAGMA query_only = ON, Timeout 3s)"]
    
    DBExec -- "Execution Error" --> QueryDoc{"QueryDoctor Diagnostic<br>(Eligible Error & Attempts < 1?)"}
    QueryDoc -- "Yes" --> RepairAST["Apply Controlled 1-Step Repair"] --> SecurityCheck
    QueryDoc -- "No" --> ExecAbort(["ABORT & REPORT ERROR"])
    
    DBExec -- "Success (DataFrame)" --> Insights["InsightMind & TrustLens Engine"]
    Insights --> Visualizer["Recharts Visualizer & Data Grid"]
    Visualizer --> FinalUI(["Render Dashboard to User"])
```

---

## 2. Database Initialization & Deterministic Seeding Lifecycle

```mermaid
flowchart TD
    StartSeeder(["Execute scripts/seed_db.py [--reset]"]) --> CheckResetFlag{"Is --reset flag specified?"}
    
    CheckResetFlag -- "Yes" --> DropTables["Drop All Existing Relational Tables<br>(Base.metadata.drop_all)"]
    DropTables --> CreateSchema["Recreate All 9 Relational Tables<br>(Base.metadata.create_all)"]
    
    CheckResetFlag -- "No" --> CheckExistingData{"Inspect existing records<br>(SELECT COUNT(*) FROM departments)"}
    CheckExistingData -- "Count > 0" --> SkipSeeding(["Idempotent Bypass: Database already populated.<br>Display existing summary counts."])
    CheckExistingData -- "Count == 0" --> CreateSchema
    
    CreateSchema --> BindWriteEngine["Acquire WriteSessionLocal<br>(PRAGMA foreign_keys = ON)"]
    
    BindWriteEngine --> SeedStage1["1. Seed Departments (5 rows)"]
    SeedStage1 --> SeedStage2["2. Seed Instructors (20 rows) & Courses (15 rows)"]
    SeedStage2 --> SeedStage3["3. Seed Terms (6 rows: 2022-2025)"]
    SeedStage3 --> SeedStage4["4. Seed Students (120 rows, Seed=42, Synthetic Roll Codes)"]
    SeedStage4 --> SeedStage5["5. Seed Course Offerings (45 scheduled sections)"]
    SeedStage5 --> SeedStage6["6. Seed Assessments (135 evaluation components)"]
    SeedStage6 --> SeedStage7["7. Seed Enrollments (360 registrations) & Marks (1,080 scores)"]
    
    SeedStage7 --> CommitCheck{"Any Exceptions during transaction?"}
    CommitCheck -- "No" --> CommitTx["session.commit()<br>1,786 Total Records Verified"]
    CommitTx --> CloseSession["session.close()"] --> FinishSeeding(["Database Seeding Complete & Ready"])
    
    CommitCheck -- "Yes" --> RollbackTx["session.rollback()<br>All partial modifications undone"]
    RollbackTx --> ReportError(["Exit with error code 1"])
```

---

## 3. Hardened Read-Only Connection Lifecycle & Timeout Protection

```mermaid
sequenceDiagram
    autonumber
    actor API as FastAPI Endpoint
    participant Session as ReadOnlySessionLocal
    participant Engine as SQLite Driver (mode=ro)
    participant C_API as SQLite C-API Engine

    API->>Session: get_db() Dependency Requested
    Session->>Engine: connect() with URI file:...academic.db?mode=ro&uri=true
    Engine->>C_API: PRAGMA foreign_keys = ON;
    Engine->>C_API: PRAGMA query_only = ON;
    Engine->>C_API: PRAGMA busy_timeout = 3000;
    
    API->>Session: Execute User SELECT Query
    Session->>Engine: before_cursor_execute event fired
    Engine->>C_API: set_progress_handler(timeout_handler, 1000 opcodes)
    
    alt Query Completes in < 3.0 seconds
        C_API-->>Engine: Result Rows Returned
        Engine-->>Session: SQLAlchemy Result Proxy
        Session-->>API: Streamed Data Rows
    else Query Exceeds 3.0 seconds
        C_API->>Engine: timeout_handler returns 1 (ABORT)
        Engine-->>Session: sqlite3.OperationalError: query interrupted
        Session-->>API: HTTP 504 Query Execution Timeout
    end
    
    API->>Session: Session Closes (finally block)
    Session->>Engine: Connection returned to pool
```

---

## 4. QueryDoctor Error Repair & Security Isolation Loop

```mermaid
stateDiagram-v2
    [*] --> InitialAST
    InitialAST --> SecurityCheck
    
    state SecurityCheck {
        [*] --> CheckSingleStatement
        CheckSingleStatement --> CheckReadOnly
        CheckReadOnly --> CheckWhitelist
        CheckWhitelist --> SecurityApproved
        
        CheckSingleStatement --> SecurityViolation : Multi-statement
        CheckReadOnly --> SecurityViolation : DDL/DML detected
        CheckWhitelist --> SecurityViolation : Foreign table/col
    }

    SecurityViolation --> TerminalAbort : Zero Repair Allowed
    SecurityApproved --> ExecuteQuery

    state ExecuteQuery {
        [*] --> SQLiteDriver
        SQLiteDriver --> ExecutionSuccess
        SQLiteDriver --> ExecutionException
    }

    ExecutionSuccess --> [*]
    ExecutionException --> QueryDoctorDiagnosis

    state QueryDoctorDiagnosis {
        [*] --> ClassifyError
        ClassifyError --> IneligibleError : Out-of-scope/fatal
        ClassifyError --> EligibleError : Missing GROUP BY / alias
    }

    IneligibleError --> TerminalAbort
    EligibleError --> AttemptRepair : If Attempts == 0

    state AttemptRepair {
        [*] --> MutateAST
        MutateAST --> RepairedAST
    }

    RepairedAST --> SecurityCheck : MUST Re-pass Complete Security Audit
    TerminalAbort --> [*]
```

---

## 5. NLP Preprocessing Pipeline Flowchart

```mermaid
flowchart TD
    UserQuery(["Raw Natural Language Query"]) --> Normalizer["1. Normalizer<br>(Remove control chars, strip & collapse whitespace)"]
    Normalizer --> Tokenizer["2. Regex Tokenizer<br>(Matches words, contractions, numbers, punctuation)"]
    
    Tokenizer --> Tagging["3. Rule-Based POS Tagger<br>(30 supported Penn Treebank-style POS tags: 23 grammatical + 7 punctuation/symbol)"]
    Tagging --> Lemmatizer["4. Morphological Lemmatizer<br>(Contextual reduction to base dictionary headwords)"]
    
    Tokenizer --> WordNgrams["5. Word N-Gram Extractor<br>(Extracts Unigrams, Bigrams, and Trigrams)"]
    Normalizer --> CharNgrams["6. Character N-Gram Extractor<br>(Extracts Sliding 3-grams for typo-tolerant matching)"]
    
    Lemmatizer --> PreprocessOutput[("Structured NLP Preprocessing Payload")]
    Tagging --> PreprocessOutput
    WordNgrams --> PreprocessOutput
    CharNgrams --> PreprocessOutput
```

---

## 6. Supervised Intent Classification Decision Tree

```mermaid
flowchart TD
    PreprocessOutput[("NLP Preprocessed Query")] --> Vectorizer["TF-IDF Vectorizer<br>(1-2 Word N-Grams, Sublinear TF)"]
    Vectorizer --> LogReg["Multinomial Logistic Regression (C=5.0)"]
    LogReg --> Softmax["Softmax Class Probabilities (Uncalibrated)<br>(Sum of 7 Intent Probabilities = 1.0)"]
    
    Softmax --> MarginCalc["Calculate Margin<br>Delta = Top1_Prob - Top2_Prob"]
    
    MarginCalc --> CheckEmpty{"Is query empty<br>or whitespace?"}
    CheckEmpty -- "Yes" --> FlagEmpty["is_ambiguous = True<br>reason = 'EMPTY_QUERY'<br>Default: GENERAL_QUERY"]
    
    CheckEmpty -- "No" --> CheckDomain{"Contains Academic<br>Domain Keywords?"}
    CheckDomain -- "No" --> FlagOOD["is_ambiguous = True<br>reason = 'OUT_OF_DOMAIN'<br>Dampen Confidence <= 0.35"]
    
    CheckDomain -- "Yes" --> CheckConfidence{"Top Confidence >= 0.55?"}
    CheckConfidence -- "No" --> FlagLowConf["is_ambiguous = True<br>reason = 'LOW_CONFIDENCE'"]
    
    CheckConfidence -- "Yes" --> CheckMargin{"Margin Delta >= 0.15?"}
    CheckMargin -- "No" --> FlagNarrowMargin["is_ambiguous = True<br>reason = 'NARROW_MARGIN'"]
    
    CheckMargin -- "Yes" --> ClearIntent["Clear Intent Classified<br>(Autonomous SQL Generation Approved)"]
    
    FlagEmpty --> DiagnosticAPI[("Return Diagnostic Inspection Response")]
    FlagOOD --> DiagnosticAPI
    FlagLowConf --> DiagnosticAPI
    FlagNarrowMargin --> DiagnosticAPI
    ClearIntent --> DiagnosticAPI
```

---

## 7. Semantic Schema Linking Pipeline Flowchart

```mermaid
flowchart TD
    InQuery(["User Natural Language Query"]) --> NLP["NLP Preprocessor<br>(Tokens, Lemmas, Unigrams, Bigrams, Trigrams)"]
    
    NLP --> IDRegex["1. Identifier Recognition (Regex)<br>• Roll Number: \\b\\d{4}-[A-Za-z]{2,4}-\\d{3,4}\\b<br>• Course Code: \\b[A-Za-z]{2,4}\\d{3}\\b"]
    IDRegex --> ColMulti["2. Multi-Word Column Linking<br>(Matches 2-3 word phrases against column synonyms)"]
    ColMulti --> LiteralCheck["3. Domain Literals & Enums<br>(Department Codes, Academic/Enrollment Statuses)"]
    
    LiteralCheck --> PolysemyCheck{"4. Check Bare Tokens in<br>AMBIGUOUS_COLUMNS_MAP?<br>(grades, year, status, name)"}
    PolysemyCheck -- "Yes & Unresolved" --> FlagAmbiguous["is_ambiguous = True<br>reason = 'MULTIPLE_COLUMN_CANDIDATES'<br>Record Candidate Explanations"]
    PolysemyCheck -- "No or Disambiguated" --> TableLink["5. Table & Entity Synonym Resolution<br>(Maps aliases e.g. learners -> students)"]
    
    TableLink --> ColSingle["6. Single-Word Column Linking<br>(Matches unigrams e.g. cgpa, credits)"]
    ColSingle --> BlacklistCheck{"7. Unsupported Entity Check?<br>(hostel, cafeteria, transport)"}
    
    BlacklistCheck -- "Yes" --> FlagUnsupported["is_ambiguous = True<br>reason = 'UNSUPPORTED_ENTITIES'<br>List Unsupported Tokens"]
    BlacklistCheck -- "No" --> PathResolve["8. Join Graph Path Resolution<br>(Input: linked_tables Set)"]
    
    FlagAmbiguous --> PathResolve
    FlagUnsupported --> PathResolve
    PathResolve --> FinalOutput(["Emit SchemaLinkResponse"])
```

---

## 8. Foreign-Key Join Graph Adjacency & Steiner Tree Resolver Flowchart

```mermaid
flowchart TD
    TargetTables(["Target Tables Set: T = {t1, t2, ..., tk}"]) --> CountCheck{"Table Count |T|"}
    
    CountCheck -- "|T| == 0" --> EmptyPath["Return Empty Connected Result (0 Hops)"]
    CountCheck -- "|T| == 1" --> SinglePath["Return Anchor Table (0 Hops, No Joins)"]
    
    CountCheck -- "|T| == 2" --> BFS2["Run BFS Shortest Path between (t1, t2)"]
    BFS2 --> MultiPathCheck{"Multiple Shortest<br>Paths of Same Length?"}
    MultiPathCheck -- "Yes" --> SetAltPaths["Primary: Path A<br>Alternative: Path B<br>alternative_paths_count > 0<br>is_ambiguous = True ('MULTIPLE_JOIN_PATHS')"]
    MultiPathCheck -- "No" --> DirectSteps["Construct Ordered Join Steps<br>(1 to 3 hops)"]
    
    CountCheck -- "|T| >= 3" --> SteinerInit["Takahashi-Matsuyama Steiner Tree Heuristic<br>(Over all candidate root anchors r in V)"]
    SteinerInit --> LoopRoots["For each root r, initialize V_tree = {r}, E_tree = []"]
    LoopRoots --> ForEachRoot["While unreached terminals in T:<br>Run Multi-Source BFS from V_tree to nearest terminal"]
    ForEachRoot --> MergeEdges["Add Shortest Path to V_tree & E_tree<br>(Guaranteed Acyclic: |E| == |V| - 1)"]
    MergeEdges --> CycleCheck{"All terminals in T<br>successfully reached?"}
    CycleCheck -- "Yes" --> ScoreTree["Record Total Hops = |E_tree|"]
    CycleCheck -- "No" --> DiscardRoot["Discard Disconnected Candidate"]
    
    ScoreTree --> FindMinTree["Select Candidate Root & Tree with Minimum Total Hops<br>(Preserve alternative distinct minimal trees)"]
    FindMinTree --> OrderSteps["Topologically Order Join Steps Outward from Anchor via BFS"]
    
---

## 9. ContextMind Conversational Context Resolution Flowchart

```mermaid
flowchart TD
    Req(["Incoming Query Request (session_id, query)"]) --> UUIDCheck{"Valid RFC 4122 UUID?"}
    UUIDCheck -- "No" --> Err422(["Raise HTTP 422 Unprocessable Entity"])
    
    UUIDCheck -- "Yes" --> ResetCheck{"Matches Reset Trigger?<br>('clear context', 'reset', 'start over')"}
    ResetCheck -- "Yes" --> PurgeSession["Purge Session Frame from Memory<br>(del _sessions[session_id])"]
    PurgeSession --> EmitReset(["Return ContextResolveResponse<br>(status='reset', was_reset=True)"])
    
    ResetCheck -- "No" --> GetSession["Retrieve Session Frame<br>(with self._lock, sliding TTL check)"]
    GetSession --> ExpiredCheck{"Session Exists &<br>now >= expires_at?"}
    ExpiredCheck -- "Yes (Expired)" --> EvictSession["Evict Expired Frame<br>(del _sessions[session_id])"] --> CreateFresh["Create Clean Session Frame"]
    ExpiredCheck -- "No (Valid)" --> CheckPriorTurn{"turn_count > 0 &<br>active_entities present?"}
    
    CheckPriorTurn -- "No (Fresh Context)" --> CheckPronounFresh{"Query contains<br>anaphoric pronouns?<br>('their', 'them')"}
    CheckPronounFresh -- "Yes" --> EmitClarifyEmpty(["Return Clarification Required<br>(status='clarification', zero prior context)"])
    CheckPronounFresh -- "No" --> ExtractSlots["Extract Slots (all_entities, all_departments, metric, sort, limit)"]
    
    CheckPriorTurn -- "Yes (Active Context)" --> ExtractSlots
    
    ExtractSlots --> MultiDeptCheck{"Multiple Departments?<br>len(all_departments) > 1"}
    MultiDeptCheck -- "Yes" --> EmitClarifyDept(["Return Clarification Required<br>(status='clarification', specify single department)"])
    
    MultiDeptCheck -- "No" --> MultiEntityCheck{"Multiple Primary Entities?<br>len(all_entities) > 1"}
    MultiEntityCheck -- "Yes" --> EmitClarifyEntity(["Return Clarification Required<br>(status='clarification', specify single entity)"])
    
    MultiEntityCheck -- "No" --> DetectFollowUp{"Is Follow-Up Query?<br>• Pronouns ('their', 'them', 'those')<br>• Replacement ('instead')<br>• Same department<br>• Not new entity topic shift<br>• Not independent list query"}
    
    DetectFollowUp -- "No (Topic Shift / New Query)" --> ResetActiveSlots["Re-initialize Active Context Slots<br>(resolved_query stripped of discourse markers,<br>was_follow_up=False, sticky metrics cleared)"]
    
    DetectFollowUp -- "Yes (Follow-Up)" --> AnaphoraSynthesize["Deterministic Anaphora Resolution & Natural Language Synthesis<br>• 'their attendance' -> 'Show attendance of students in AI'<br>• 'sort them by credits' -> 'Show courses in CS sorted by credits'<br>• 'CS students instead' -> 'Show average CGPA of CS students'"]
    
    AnaphoraSynthesize --> SlotMerge["Context Slot Merging & Contradiction Resolution<br>• Dept override: new dept replaces old dept (expunges old filter)<br>• Metric update: new metric updates active_metric<br>• List query: clears active_metric to None<br>• Orthogonal preservation: unrelated filters/entities preserved"]
    
    SlotMerge --> ClassifyIntent["Classify Intent of Resolved Query via IntentClassifier"]
    ResetActiveSlots --> ClassifyIntent
    
    ClassifyIntent --> IncrementTurns["Monotonically Increment turn_count += 1"]
    IncrementTurns --> AppendAudit["Append TurnRecord to turn_history Stack<br>Trim: retain only last 50 turns (MAX_TURNS_PER_SESSION = 50)"]
    AppendAudit --> RefreshTTL["Persist Frame & Refresh Sliding TTL<br>(last_active = now, expires_at = now + 600s)"]
    RefreshTTL --> FinalResponse(["Return ContextResolveResponse<br>(status='success', resolved_query, active_frame)"])
```



