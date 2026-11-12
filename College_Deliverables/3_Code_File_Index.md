# QueryMind AI 2.0 — Source Code File Index
*Deliverable Document 3 | Updated — Phase 4 Schema Linking & Join Graph Construction*

> **Status:** Phase 4 Codebase Index  
> **Phase Milestone:** Phase 4 (Schema Linking & Join Graph Construction)  
> **Note:** This document catalogs all source code files across the repository, summarizing their responsibilities, exported symbols, module dependencies, and active implementation phases.

---

## 1. Backend Code Index (`backend/`)

| File Path | Module Responsibility | Key Classes / Functions | Status |
| :--- | :--- | :--- | :--- |
| `app/main.py` | FastAPI application initialization, CORS middleware, global lifespan, exception handlers, and router mounting. | `app`, `health_check()`, `root_info()` | **Phase 1, 3, 4 & 5 Active** |
| `app/core/config.py` | Application settings, environment loading via Pydantic Settings. | `Settings`, `get_settings()` | **Phase 1 Active** |
| `tests/test_health.py` | Automated pytest health-check test verifying FastAPI server response. | `test_health_endpoint()`, `test_root_endpoint()` | **Phase 1 Active** |
| `app/core/database.py` | SQLAlchemy database engines (write-enabled and read-only), connection listeners, sessionmakers. | `Base`, `write_engine`, `read_only_engine`, `get_db()`, `init_db()` | **Phase 2 Active** |
| `app/models/academic.py` | SQLAlchemy 2.x declarative ORM models for all 9 normalized academic entities. | `Department`, `Student`, `Instructor`, `Course`, `Term`, `CourseOffering`, `Enrollment`, `Assessment`, `StudentMark` | **Phase 2 Active** |
| `app/models/__init__.py` | Academic ORM models package export. | Exports all 9 ORM classes | **Phase 2 Active** |
| `scripts/init_db.py` | Safe database schema initialization and reset utility. | `initialize_database()`, `main()` | **Phase 2 Active** |
| `scripts/seed_db.py` | Deterministic synthetic academic data generator with fixed seed (Seed=42). | `seed_database()`, `seed_departments()`, `seed_students()` | **Phase 2 Active** |
| `scripts/evaluate_intent.py` | Rigorous group-aware model evaluation script with assertions (StratifiedGroupKFold, K=3). | `verify_group_invariants()`, `run_group_aware_evaluation()`, `main()` | **Phase 3 Active** |
| `scripts/verify_steiner_benchmark.py` | Independent exact brute-force Steiner reference solver and 502-combination reproducibility audit script. | `exact_minimum_steiner_tree_hops()`, `run_benchmark()` | **Phase 4 Active** |
| `tests/test_database.py` | Automated unit tests for database engines, read-only enforcement, and SQLite pragmas. | `test_read_only_strictly_blocks_insert()`, `test_foreign_keys_pragma()` | **Phase 2 Active** |
| `tests/test_models.py` | Automated unit tests for ORM constraints, primary keys, foreign keys, unique checks, and triggers. | 18 test functions | **Phase 2 Active** |
| `tests/test_seeding.py` | Automated unit tests for deterministic reproducibility, counts, and transaction rollback. | `test_seeding_determinism()`, `test_seeding_idempotency()` | **Phase 2 Active** |
| `app/services/nlp_preprocessor.py` | Deterministic text normalization, tokenization, morphological lemmatization, 30 supported Penn Treebank-style POS tags (23 grammatical tags + 7 punctuation/symbol tags), n-grams. | `NLPPreprocessor`, `get_nlp_preprocessor()` | **Phase 3 Active** |
| `app/services/intent_classifier.py` | Supervised Multinomial Logistic Regression model with Softmax class probabilities, margin calculation, and domain scope boundaries. | `IntentClassifier`, `get_intent_classifier()` | **Phase 3 Active** |
| `app/schemas/nlp.py` | Pydantic v2 schemas for NLP diagnostic inspection request and response payloads. | `NLPInspectRequest`, `NLPInspectResponse`, `NLPPreprocessData`, `IntentClassificationData` | **Phase 3 Active** |
| `app/api/endpoints/nlp.py` | FastAPI diagnostic inspection endpoints (`GET` and `POST` at `/api/nlp/inspect`). | `inspect_nlp_get()`, `inspect_nlp_post()` | **Phase 3 Active** |
| `tests/test_nlp_preprocessor.py` | Automated pytest suite for normalizer, regex tokenizer, rule-based POS tagger (30 supported Penn Treebank-style tags), contractions/possessives, lemmatizer, and n-grams. | 10 test functions | **Phase 3 Active** |
| `tests/test_intent_classifier.py` | Automated pytest suite for 7 intent categories, Softmax probability axioms, margins, out-of-domain rejection, and group-aware cross-validation invariants. | 22 test functions | **Phase 3 Active** |
| `tests/test_nlp_api.py` | Automated integration tests for `/api/nlp/inspect` HTTP GET and POST endpoints, validation errors, and latencies. | 6 test functions | **Phase 3 Active** |
| `app/services/schema_linker.py` | Dynamic schema introspection, synonym dictionary catalog, regex identifier extraction, ambiguity detection, and BFS/Steiner join graph resolver. | `SchemaCatalog`, `JoinGraph`, `SchemaLinker`, `get_schema_catalog()`, `get_join_graph()`, `get_schema_linker()` | **Phase 4 Active** |
| `app/schemas/schema_linker.py` | Pydantic v2 schemas for schema catalog, query linking, ambiguity candidates, and join path resolution. | `SchemaLinkRequest`, `SchemaLinkResponse`, `JoinPathRequest`, `JoinPathResponse`, `SchemaCatalogResponse` | **Phase 4 Active** |
| `app/api/endpoints/schema.py` | FastAPI route endpoints for schema catalog, query linking, and join paths (`/api/schema/catalog`, `/api/schema/link`, `/api/schema/join-path`). | `get_catalog_endpoint()`, `link_query_endpoint()`, `resolve_join_path_post()`, `resolve_join_path_get()` | **Phase 4 Active** |
| `tests/test_schema_linker.py` | Automated unit and integration tests for introspection, linking, polysemy, unsupported terms, BFS, Steiner tree, and API endpoints. | 19 test functions | **Phase 4 Active** |
| `app/services/context_engine.py` | ContextMind multi-turn conversational context engine integrating SchemaLinker and IntentClassifier, thread-safe session manager, dual-eviction sliding TTL + lifespan periodic cleanup, memory-bounded 50-turn history, and deterministic anaphora resolver. | `SessionManager`, `ContextMind`, `get_context_engine()` | **Phase 5 Active** |
| `app/schemas/context.py` | Pydantic v2 schemas for Context Frame, active filters, turn records, and `/api/context` requests and responses. | `ActiveFilterSchema`, `ActiveSortSchema`, `TurnRecordSchema`, `ContextFrameSchema`, `ContextResolveRequest`, `ContextResolveResponse`, `ContextFrameResponse`, `ContextResetResponse` | **Phase 5 Active** |
| `app/api/endpoints/context.py` | FastAPI route endpoints for multi-turn query resolution, frame inspection, and session reset (`/api/context/resolve`, `/api/context/frame/{id}`, `/api/context/reset/{id}`). | `resolve_context_endpoint()`, `get_context_frame_endpoint()`, `reset_context_endpoint()` | **Phase 5 Active** |
| `tests/test_context_engine.py` | Automated unit, integration, sliding TTL, concurrency, history bounding, lifespan background cleanup, and API tests for ContextMind engine. | 42 test functions | **Phase 5 Active** |
| `app/services/sql_generator.py` | Text-to-SQL rule generator and SQLGlot AST validation guardrails. | `SQLGenerator`, `ASTValidator` | Scheduled Phase 6 |
| `app/services/query_doctor.py` | QueryDoctor syntax/schema diagnostic engine and 1-step repair logic. | `QueryDoctor` | Scheduled Phase 6 |
| `app/services/trust_lens.py` | TrustLens transparency generator: joins explanation, filter audit, limitations. | `TrustLens` | Scheduled Phase 7 |
| `app/services/insight_mind.py` | Statistical evaluator detecting extrema, trends, outliers, and category comparisons. | `InsightMind` | Scheduled Phase 8 |

---

## 2. Frontend Code Index (`frontend/`)

| File Path | Component Responsibility | Exported Symbols | Status |
| :--- | :--- | :--- | :--- |
| `src/main.tsx` | React 19 application entry point mounting root DOM node. | None (entry point) | **Phase 1 Active** |
| `src/App.tsx` | Main application shell and layout container. | `App` | **Phase 1 Active** |
| `src/index.css` | Tailwind CSS directives and dark-theme base styles. | CSS directives | **Phase 1 Active** |
| `vite.config.ts` | Vite configuration with React plugin and `/api` proxy mapping to `localhost:8000`. | `defineConfig` | **Phase 1 Active** |
| `tailwind.config.js` | Tailwind CSS theme extensions and content path definitions. | Theme configuration | **Phase 1 Active** |

---

## 3. Documentation & Technical Specifications (`docs/`)

| File Path | Document Topic | Status |
| :--- | :--- | :--- |
| `docs/architecture_overview.md` | Monorepo structure, technical stack, and design philosophy. | **Phase 1 Active** |
| `docs/database_schema.md` | Full relational data dictionary, ERD, constraints, and seeding specifications. | **Phase 2 Active** |
| `docs/nlp_architecture.md` | NLP preprocessor, rule-based POS tagger (30 supported Penn Treebank-style tags), TF-IDF + Logistic Regression model, Softmax probabilities, and API schemas. | **Phase 3 Active** |
| `docs/schema_linking_architecture.md` | Dynamic schema introspection, synonym catalog, identifier regexes, polysemy handling, and BFS/Steiner Join Graph algorithms. | **Phase 4 Active** |
| `docs/context_engine_architecture.md` | ContextMind multi-turn state management, sliding TTL lifecycle, anaphora resolution, contradiction elimination, and API contracts. | **Phase 5 Active** |

