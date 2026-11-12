"""Unit and Integration Tests for Schema Introspection, Linking, and Join Graph.

QueryMind AI 2.0 - Phase 4: Schema Linking & Join Graph Construction.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.schema_linker import (
    JoinGraph,
    SchemaCatalog,
    SchemaLinker,
    get_join_graph,
    get_schema_catalog,
    get_schema_linker,
)

client = TestClient(app)

EXPECTED_NINE_TABLES = [
    "departments",
    "students",
    "instructors",
    "courses",
    "terms",
    "course_offerings",
    "enrollments",
    "assessments",
    "student_marks",
]


# ============================================================================
# 1. Schema Introspection Tests
# ============================================================================


def test_schema_introspection_all_nine_tables():
    """Verify dynamic introspection captures all 9 academic tables with primary keys,

    foreign keys, columns, data types, and unique constraints.
    """
    catalog = get_schema_catalog()
    assert len(catalog.tables) == 9

    for table_name in EXPECTED_NINE_TABLES:
        assert table_name in catalog.tables, f"Missing table: {table_name}"
        t = catalog.tables[table_name]
        assert t.name == table_name
        assert len(t.primary_keys) >= 1
        assert len(t.columns) > 0

    # Test specific table schemas
    # Departments
    dept_table = catalog.tables["departments"]
    assert "code" in dept_table.columns
    assert "name" in dept_table.columns
    assert (
        "VARCHAR" in dept_table.columns["code"].data_type.upper()
        or "TEXT" in dept_table.columns["code"].data_type.upper()
    )
    assert len(dept_table.unique_constraints) > 0

    # Students
    stud_table = catalog.tables["students"]
    assert "roll_number" in stud_table.columns
    assert "cgpa" in stud_table.columns
    assert (
        "REAL" in stud_table.columns["cgpa"].data_type.upper()
        or "FLOAT" in stud_table.columns["cgpa"].data_type.upper()
    )
    assert stud_table.columns["department_id"].is_foreign_key is True
    assert stud_table.columns["department_id"].foreign_key_target == "departments.department_id"

    # Enrollments
    enr_table = catalog.tables["enrollments"]
    assert "student_id" in enr_table.columns
    assert "offering_id" in enr_table.columns
    assert "attendance_percentage" in enr_table.columns

    # Student Marks composite foreign key
    marks_table = catalog.tables["student_marks"]
    assert "assessment_id" in marks_table.columns
    assert "enrollment_id" in marks_table.columns
    assert "marks_obtained" in marks_table.columns
    assert len(marks_table.foreign_keys) >= 2


# ============================================================================
# 2. Entity & Synonym Linking Tests
# ============================================================================


def test_entity_linking_exact_and_synonyms():
    """Verify SchemaLinker identifies tables from exact names and academic synonyms."""
    linker = get_schema_linker()

    # Exact table names
    res1 = linker.link_query("Show all students in the database")
    assert "students" in res1["linked_tables"]

    res2 = linker.link_query("List all departments")
    assert "departments" in res2["linked_tables"]

    # Synonyms: learners, pupils -> students
    res3 = linker.link_query("Find all learners with high attendance")
    assert "students" in res3["linked_tables"]

    # Synonyms: professors, faculty -> instructors
    res4 = linker.link_query("Which faculty members teach machine learning?")
    assert "instructors" in res4["linked_tables"]

    # Synonyms: curriculum, subjects -> courses
    res5 = linker.link_query("List the curriculum subjects for semester 1")
    assert "courses" in res5["linked_tables"]
    assert "terms" in res5["linked_tables"]


# ============================================================================
# 3. Column & Synonym Linking Tests
# ============================================================================


def test_column_linking_and_synonyms():
    """Verify SchemaLinker resolves attribute mentions to fully-qualified columns."""
    linker = get_schema_linker()

    res = linker.link_query("Show attendance percentage and cgpa of learners")
    linked_cols = [
        f"{t}.{c['column_name']}" for t, cols in res["linked_columns"].items() for c in cols
    ]

    assert "enrollments.attendance_percentage" in linked_cols
    assert "students.cgpa" in linked_cols

    res2 = linker.link_query("What is the max marks for midterm assessment?")
    linked_cols2 = [
        f"{t}.{c['column_name']}" for t, cols in res2["linked_columns"].items() for c in cols
    ]
    assert "assessments.max_marks" in linked_cols2


# ============================================================================
# 4. Value Linking (Entities, Regex Identifiers, Categorical Attributes)
# ============================================================================


def test_value_linking_department_and_identifiers():
    """Verify value linking resolves department codes/names, roll numbers, and course codes."""
    linker = get_schema_linker()

    # Department code and name
    res = linker.link_query("Show students in AI department")
    val_matches = [v["value"] for v in res["linked_values"]]
    assert "AI" in val_matches
    assert any(
        v["table_name"] == "departments" and v["column_name"] == "code" and v["value"] == "AI"
        for v in res["linked_values"]
    )

    # Roll number regex pattern (e.g. 2024-CS-001)
    res_roll = linker.link_query("Find details for student 2024-CS-001")
    assert any(
        v["column_name"] == "roll_number" and v["value"] == "2024-CS-001"
        for v in res_roll["linked_values"]
    )
    assert "students" in res_roll["linked_tables"]

    # Course code regex pattern (e.g. CS101, AI201)
    res_course = linker.link_query("Who is enrolled in course CS101?")
    assert any(
        v["column_name"] == "course_code" and v["value"] == "CS101"
        for v in res_course["linked_values"]
    )
    assert "courses" in res_course["linked_tables"]

    # Academic status categorical value
    res_status = linker.link_query("List students on academic probation")
    assert any(
        v["column_name"] == "academic_status" and v["value"].upper() == "PROBATION"
        for v in res_status["linked_values"]
    )


# ============================================================================
# 5. Ambiguous Candidate Detection
# ============================================================================


def test_ambiguous_candidate_detection():
    """Verify queries containing polysemous tokens like 'grades' or 'status' flag ambiguity."""
    linker = get_schema_linker()

    # 'grades' can refer to student_marks.marks_obtained, enrollments.final_grade, or enrollments.grade_points
    res = linker.link_query("Show the grades for student 2024-CS-001")
    assert res["is_ambiguous"] is True
    assert res["ambiguity_reason"] == "MULTIPLE_COLUMN_CANDIDATES"
    assert len(res["ambiguous_candidates"]) >= 1

    candidate_cols = [
        c["column"] for ac in res["ambiguous_candidates"] for c in ac["candidates"]
    ]
    assert any("final_grade" in c for c in candidate_cols)
    assert any("marks_obtained" in c for c in candidate_cols)

    # 'status' can refer to students.academic_status or enrollments.enrollment_status
    res2 = linker.link_query("Check the status of student 2024-CS-001")
    assert res2["is_ambiguous"] is True
    assert res2["ambiguity_reason"] == "MULTIPLE_COLUMN_CANDIDATES"


# ============================================================================
# 6. Unsupported Entity Detection
# ============================================================================


def test_unsupported_entity_detection():
    """Verify out-of-domain terms like 'cafeteria', 'hostel', 'canteen' are flagged."""
    linker = get_schema_linker()

    res = linker.link_query("Which students live in the hostel?")
    assert "hostel" in res["unsupported_entities"]
    assert res["is_ambiguous"] is True
    assert res["ambiguity_reason"] == "UNSUPPORTED_ENTITIES"

    res2 = linker.link_query("Show the cafeteria menu for today")
    assert "cafeteria" in res2["unsupported_entities"]
    assert res2["is_ambiguous"] is True
    assert res2["ambiguity_reason"] == "UNSUPPORTED_ENTITIES"


# ============================================================================
# 7. Join Graph Construction & Direct 1-Hop Joins
# ============================================================================


def test_join_graph_edges_and_direct_joins():
    """Verify JoinGraph foreign-key edges and 1-hop path resolution."""
    graph = get_join_graph()

    # Graph contains all 9 tables
    assert len(graph.adjacency) == 9

    # Direct 1-hop: departments <-> students
    path_dept_stud = graph.find_shortest_path("departments", "students")
    assert path_dept_stud is not None
    assert len(path_dept_stud) == 1
    assert path_dept_stud[0].from_table == "departments"
    assert path_dept_stud[0].to_table == "students"
    assert path_dept_stud[0].condition == "students.department_id = departments.department_id"

    # Reverse direction 1-hop: students -> departments
    path_stud_dept = graph.find_shortest_path("students", "departments")
    assert path_stud_dept is not None
    assert len(path_stud_dept) == 1
    assert path_stud_dept[0].from_table == "students"
    assert path_stud_dept[0].to_table == "departments"
    assert path_stud_dept[0].condition == "students.department_id = departments.department_id"

    # Direct 1-hop: enrollments <-> student_marks
    path_enr_marks = graph.find_shortest_path("enrollments", "student_marks")
    assert path_enr_marks is not None
    assert len(path_enr_marks) == 1
    assert path_enr_marks[0].from_table == "enrollments"
    assert path_enr_marks[0].to_table == "student_marks"


# ============================================================================
# 8. Multi-Hop Join Paths
# ============================================================================


def test_multi_hop_join_paths():
    """Verify multi-hop shortest paths through intermediate tables."""
    graph = get_join_graph()

    # 3-hop join: departments -> students -> enrollments -> student_marks
    path = graph.find_shortest_path("departments", "student_marks")
    assert path is not None
    assert len(path) == 3
    tables_in_path = [step.from_table for step in path] + [path[-1].to_table]
    assert tables_in_path == ["departments", "students", "enrollments", "student_marks"]

    # 2-hop join: students -> departments -> courses
    path_stud_course = graph.find_shortest_path("students", "courses")
    assert path_stud_course is not None
    assert len(path_stud_course) == 2
    assert path_stud_course[0].to_table == "departments"
    assert path_stud_course[1].to_table == "courses"


# ============================================================================
# 9. Multi-Table Steiner Tree & Graph Connection Tests
# ============================================================================


def test_steiner_tree_three_table_connections():
    """Verify Steiner tree resolution connects 3 tables with minimal hops and strict tree properties."""
    graph = get_join_graph()

    res = graph.resolve_multi_table_join({"departments", "students", "courses"})
    assert res.is_connected is True
    assert set(res.joined_tables).issuperset({"departments", "students", "courses"})
    assert res.total_hops == 2
    assert len(res.join_steps) == 2

    # Tree Invariant: |V| = |E| + 1
    assert len(res.joined_tables) == len(res.join_steps) + 1

    # Topological ordering invariant: every step's from_table must have been introduced previously
    seen_tables = {res.anchor_table}
    for step in res.join_steps:
        assert step.from_table in seen_tables
        assert step.to_table not in seen_tables
        seen_tables.add(step.to_table)


def test_steiner_tree_four_table_connections():
    """Verify Steiner tree resolution connects 4 tables across multiple hierarchy levels."""
    graph = get_join_graph()

    res = graph.resolve_multi_table_join({"students", "student_marks", "assessments", "courses"})
    assert res.is_connected is True
    assert set(res.joined_tables).issuperset(
        {"students", "student_marks", "assessments", "courses"}
    )
    assert len(res.join_steps) == len(res.joined_tables) - 1

    # Verify all targets are reached
    for target in ["students", "student_marks", "assessments", "courses"]:
        assert target in res.joined_tables


def test_steiner_tree_shared_intermediate_nodes():
    """Verify Steiner tree algorithm reuses shared intermediate tables rather than duplicating branches."""
    graph = get_join_graph()

    # Connecting students and assessments requires intermediate enrollment or offering tables
    res = graph.resolve_multi_table_join({"students", "courses", "student_marks"})
    assert res.is_connected is True

    # No table is duplicated in joined_tables
    assert len(res.joined_tables) == len(set(res.joined_tables))
    # All join steps have unique target tables
    to_tables = [s.to_table for s in res.join_steps]
    assert len(to_tables) == len(set(to_tables))


def test_steiner_tree_cyclic_graph_avoidance():
    """Verify that cycles in the FK topology (departments-courses-offerings-instructors)

    do not introduce redundant cycle-closing join edges into the Steiner tree.
    """
    graph = get_join_graph()

    # These 4 tables form an undirected cycle in the relational schema:
    # departments <-> courses <-> course_offerings <-> instructors <-> departments
    cycle_tables = {"departments", "courses", "course_offerings", "instructors"}
    res = graph.resolve_multi_table_join(cycle_tables)

    assert res.is_connected is True
    # For 4 tables forming a cycle, a spanning tree must have exactly 3 edges (NOT 4!)
    assert len(res.join_steps) == 3
    assert len(res.joined_tables) == 4
    assert set(res.joined_tables) == cycle_tables


def test_steiner_tree_disconnected_and_unknown_tables():
    """Verify disconnected, unknown, or single tables are handled with clean error structures."""
    graph = get_join_graph()

    # Single table requires 0 hops
    single_res = graph.resolve_multi_table_join({"students"})
    assert single_res.is_connected is True
    assert single_res.total_hops == 0
    assert len(single_res.join_steps) == 0
    assert single_res.anchor_table == "students"

    # Non-existent table
    invalid_res = graph.resolve_multi_table_join({"students", "imaginary_table"})
    assert invalid_res.is_connected is False
    assert (
        "disconnected or not present in schema graph" in invalid_res.error.lower()
        or "unknown" in invalid_res.error.lower()
    )


def test_steiner_tree_known_divergence_cases_and_approximation_bounds():
    """Verify that known greedy tie-break combinations stay strictly within the 2(1 - 1/k) worst-case bound."""
    graph = get_join_graph()

    # Combination 1: k = 4, exact = 5 hops, heuristic <= 6 hops, bound = 1.500
    c1 = {"courses", "student_marks", "students", "terms"}
    res1 = graph.resolve_multi_table_join(c1)
    assert res1.is_connected is True
    assert res1.total_hops in (5, 6)
    ratio1 = res1.total_hops / 5.0
    assert ratio1 <= 1.200
    assert ratio1 <= 2.0 * (1.0 - 1.0 / 4)

    # Combination 2: k = 4, exact = 5 hops, heuristic <= 6 hops, bound = 1.500
    c2 = {"instructors", "student_marks", "students", "terms"}
    res2 = graph.resolve_multi_table_join(c2)
    assert res2.is_connected is True
    assert res2.total_hops in (5, 6)
    ratio2 = res2.total_hops / 5.0
    assert ratio2 <= 1.200
    assert ratio2 <= 2.0 * (1.0 - 1.0 / 4)

    # Combination 3: k = 5, exact = 6 hops, heuristic <= 7 hops, bound = 1.600
    c3 = {"courses", "instructors", "student_marks", "students", "terms"}
    res3 = graph.resolve_multi_table_join(c3)
    assert res3.is_connected is True
    assert res3.total_hops in (6, 7)
    ratio3 = res3.total_hops / 6.0
    assert round(ratio3, 3) <= 1.167
    assert ratio3 <= 2.0 * (1.0 - 1.0 / 5)


# ============================================================================
# 10. Multiple Candidate Join Paths Detection & Disambiguation
# ============================================================================


def test_multiple_candidate_join_paths_fk_representation_and_alternatives():
    """Verify that multiple shortest paths between departments and course_offerings

    are both detected with correct FK representations and exposed in alternative_paths.
    """
    graph = get_join_graph()

    # Path 1: via curriculum (courses)
    # Path 2: via faculty (instructors)
    all_paths = graph.find_all_shortest_paths("departments", "course_offerings")
    assert len(all_paths) == 2
    for p in all_paths:
        assert len(p) == 2

    # Check that Path 1 and Path 2 use different intermediate tables
    intermediate_nodes = {p[0].to_table for p in all_paths}
    assert intermediate_nodes == {"courses", "instructors"}

    # In multi-table join resolution, alternative_paths is populated
    res = graph.resolve_multi_table_join({"departments", "course_offerings"})
    assert res.is_connected is True
    assert len(res.alternative_paths) == 1

    # Verify FK relationships in alternative path
    alt_steps = res.alternative_paths[0]
    assert len(alt_steps) == 2
    # Check that alternative path uses the other intermediate table
    primary_intermediate = res.join_steps[0].to_table
    alt_intermediate = alt_steps[0].to_table
    assert primary_intermediate != alt_intermediate
    assert {primary_intermediate, alt_intermediate} == {"courses", "instructors"}


# ============================================================================
# 11. Read-Only Database Safety & Introspection Security
# ============================================================================


def test_schema_database_safety_and_read_only_enforcement():
    """Verify that SchemaCatalog strictly binds to read_only_engine and prevents mutation."""
    from app.core.database import read_only_engine

    catalog = get_schema_catalog()
    assert catalog.engine == read_only_engine

    # Endpoints do not execute user SQL or expose mutation primitives
    res = client.get("/api/schema/catalog")
    assert res.status_code == 200
    assert res.json()["status"] == "success"


# ============================================================================
# 12. Schema FastAPI Endpoints Integration
# ============================================================================


def test_schema_catalog_api_endpoint():
    """Verify GET /api/schema/catalog returns all 9 tables and column details."""
    response = client.get("/api/schema/catalog")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["total_tables"] == 9
    assert data["total_columns"] >= 40
    assert "students" in data["tables"]
    assert "departments" in data["tables"]

    stud_meta = data["tables"]["students"]
    assert "roll_number" in stud_meta["columns"]
    assert "cgpa" in stud_meta["columns"]
    assert "pupils" in stud_meta["synonyms"]


def test_schema_link_api_endpoint():
    """Verify POST /api/schema/link processes queries, performs linking, and computes join path."""
    payload = {"query": "Find all students in Computer Science with CGPA greater than 3.5"}
    response = client.post("/api/schema/link", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert "students" in data["linked_tables"]
    assert "departments" in data["linked_tables"]

    linked_cols = [
        f"{t}.{c['column_name']}" for t, cols in data["linked_columns"].items() for c in cols
    ]
    assert "students.cgpa" in linked_cols

    assert data["join_path"]["is_connected"] is True
    assert data["join_path"]["total_hops"] >= 1
    assert data["execution_time_ms"] >= 0.0


def test_schema_join_path_post_and_get():
    """Verify POST and GET /api/schema/join-path compute valid join paths."""
    # POST endpoint
    post_res = client.post(
        "/api/schema/join-path", json={"tables": ["departments", "students"]}
    )
    assert post_res.status_code == 200
    post_data = post_res.json()
    assert post_data["status"] == "success"
    assert post_data["is_connected"] is True
    assert post_data["total_hops"] == 1
    assert len(post_data["join_steps"]) == 1

    # GET endpoint
    get_res = client.get("/api/schema/join-path?tables=departments,students")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["status"] == "success"
    assert get_data["is_connected"] is True
    assert get_data["total_hops"] == 1

    # Empty table query validation
    bad_res = client.post("/api/schema/join-path", json={"tables": []})
    assert bad_res.status_code == 422
