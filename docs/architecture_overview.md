# QueryMind AI 2.0 — Architecture Overview

QueryMind AI 2.0 is a full-stack, local deterministic conversational Text-to-SQL system designed for academic institutions.

## Core Pillars
1. **Academic Institution Domain**: Normalized relational database containing Departments, Students, Instructors, Courses, Terms, Offerings, Enrollments, Assessments, and Student Marks.
2. **Local Deterministic NLP**: NLTK tokenization, POS tagging, n-gram extraction, and Scikit-learn Multinomial Logistic Regression with Softmax probabilities.
3. **ContextMind**: Anaphora resolution and multi-turn state preservation across isolated sessions.
4. **SQLGlot AST Guardrails & QueryDoctor**: Enforced read-only SELECT queries with controlled 1-step repair for non-security syntax/schema errors.
5. **InsightMind & TrustLens**: Automated evidence-based statistical insights (extrema, trends, outliers) with complete schema provenance disclosure.
6. **Dynamic Visualizer**: Recharts data-driven chart selection (KPI card, Bar, Line, Area, Scatter, Donut, Data Table).

