"""Schema Introspection, Academic Catalog, Join Graph, and Semantic Schema Linker.

QueryMind AI 2.0 - Phase 4: Schema Linking & Join Graph Construction.
Connects natural-language academic queries to the live SQLite relational schema.
"""

from collections import deque
from dataclasses import dataclass, field
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import inspect
from app.core.database import read_only_engine
from app.services.nlp_preprocessor import get_nlp_preprocessor, NLPPreprocessor


# ---------------------------------------------------------------------------
# Domain Metadata & Knowledge Dictionary (Extensible for Academic Schema)
# ---------------------------------------------------------------------------

ACADEMIC_TABLE_METADATA: Dict[str, Dict[str, Any]] = {
    "departments": {
        "entity_name": "Department",
        "description": "Academic divisions and departments (e.g., Computer Science, Artificial Intelligence).",
        "synonyms": [
            "department",
            "departments",
            "dept",
            "depts",
            "division",
            "divisions",
            "academic department",
            "academic departments",
            "branch",
            "branches",
        ],
    },
    "students": {
        "entity_name": "Student",
        "description": "Enrolled students, academic standing, roll numbers, semesters, and CGPA.",
        "synonyms": [
            "student",
            "students",
            "learner",
            "learners",
            "pupil",
            "pupils",
            "undergraduate",
            "undergraduates",
            "candidate",
            "candidates",
        ],
    },
    "instructors": {
        "entity_name": "Instructor",
        "description": "Faculty teaching staff, academic designations, and department affiliations.",
        "synonyms": [
            "instructor",
            "instructors",
            "faculty",
            "faculties",
            "teacher",
            "teachers",
            "professor",
            "professors",
            "prof",
            "profs",
            "lecturer",
            "lecturers",
        ],
    },
    "courses": {
        "entity_name": "Course",
        "description": "Curriculum course catalogue, course codes, names, credits, and academic levels.",
        "synonyms": [
            "course",
            "courses",
            "class",
            "classes",
            "subject",
            "subjects",
            "curriculum",
            "curricula",
            "module",
            "modules",
        ],
    },
    "terms": {
        "entity_name": "Term",
        "description": "Academic terms and calendar windows (Fall, Spring, Summer) by academic year.",
        "synonyms": [
            "term",
            "terms",
            "semester",
            "semesters",
            "academic term",
            "academic terms",
            "session",
            "sessions",
            "academic year",
            "academic years",
        ],
    },
    "course_offerings": {
        "entity_name": "CourseOffering",
        "description": "Scheduled instances of courses taught by specific instructors in specific terms and sections.",
        "synonyms": [
            "offering",
            "offerings",
            "course offering",
            "course offerings",
            "section",
            "sections",
            "class section",
            "class sections",
            "scheduled class",
            "scheduled classes",
        ],
    },
    "enrollments": {
        "entity_name": "Enrollment",
        "description": "Student course registrations, attendance percentages, final letter grades, and grade points.",
        "synonyms": [
            "enrollment",
            "enrollments",
            "registration",
            "registrations",
            "course enrollment",
            "course enrollments",
        ],
    },
    "assessments": {
        "entity_name": "Assessment",
        "description": "Course assessment components including Quizzes, Midterms, Finals, Assignments, and Projects.",
        "synonyms": [
            "assessment",
            "assessments",
            "exam",
            "exams",
            "examination",
            "examinations",
            "quiz",
            "quizzes",
            "assignment",
            "assignments",
            "midterm",
            "midterms",
            "final",
            "finals",
            "test",
            "tests",
            "project",
            "projects",
        ],
    },
    "student_marks": {
        "entity_name": "StudentMark",
        "description": "Numerical marks and scores achieved by students on specific assessments.",
        "synonyms": [
            "mark",
            "marks",
            "score",
            "scores",
            "result",
            "results",
            "marks obtained",
            "score obtained",
            "student mark",
            "student marks",
        ],
    },
}

ACADEMIC_COLUMN_METADATA: Dict[Tuple[str, str], Dict[str, Any]] = {
    ("departments", "department_id"): {
        "description": "Unique integer identifier for the department (Primary Key).",
        "synonyms": ["department id", "dept id"],
    },
    ("departments", "name"): {
        "description": "Full formal name of the academic department.",
        "synonyms": ["department name", "dept name", "name of department", "branch name"],
    },
    ("departments", "code"): {
        "description": "Short uppercase department code (e.g., CS, AI, EE, ME, MATH).",
        "synonyms": ["department code", "dept code", "branch code", "department abbreviation"],
    },
    ("departments", "established_year"): {
        "description": "Calendar year the department was established.",
        "synonyms": ["established year", "founding year", "founded year", "department established"],
    },
    ("departments", "building"): {
        "description": "Campus building location housing the department.",
        "synonyms": ["building", "campus building", "department building", "hall", "block"],
    },
    ("students", "student_id"): {
        "description": "Unique integer identifier for the student (Primary Key).",
        "synonyms": ["student id", "student identifier"],
    },
    ("students", "department_id"): {
        "description": "Foreign key reference to departments.department_id.",
        "synonyms": ["student department id"],
    },
    ("students", "roll_number"): {
        "description": "Unique student registration roll number (e.g., 2024-CS-001).",
        "synonyms": ["roll number", "roll no", "roll", "registration number", "matric number"],
    },
    ("students", "first_name"): {
        "description": "Student given first name.",
        "synonyms": ["student first name", "student name", "first name"],
    },
    ("students", "last_name"): {
        "description": "Student family last name.",
        "synonyms": ["student last name", "student surname", "last name", "surname"],
    },
    ("students", "enrollment_year"): {
        "description": "Year of university admission / matriculation.",
        "synonyms": ["enrollment year", "admission year", "matriculation year", "batch", "batch year"],
    },
    ("students", "current_semester"): {
        "description": "Current active semester number (1 to 12).",
        "synonyms": ["current semester", "semester", "sem", "semester number", "term number"],
    },
    ("students", "cgpa"): {
        "description": "Cumulative Grade Point Average (0.00 to 4.00).",
        "synonyms": ["cgpa", "gpa", "grade point average", "cumulative gpa", "cumulative grade point average"],
    },
    ("students", "academic_status"): {
        "description": "Academic standing: Active, Probation, Graduated, or Suspended.",
        "synonyms": ["academic status", "standing", "student status", "academic standing", "probation status", "active status"],
    },
    ("instructors", "instructor_id"): {
        "description": "Unique integer identifier for the instructor (Primary Key).",
        "synonyms": ["instructor id", "faculty id", "teacher id"],
    },
    ("instructors", "department_id"): {
        "description": "Foreign key reference to departments.department_id.",
        "synonyms": ["instructor department id", "faculty department id"],
    },
    ("instructors", "first_name"): {
        "description": "Faculty given first name.",
        "synonyms": ["instructor first name", "faculty first name", "teacher first name"],
    },
    ("instructors", "last_name"): {
        "description": "Faculty family last name.",
        "synonyms": ["instructor last name", "faculty last name", "teacher last name", "faculty surname"],
    },
    ("instructors", "designation"): {
        "description": "Academic title: Professor, Associate Professor, Assistant Professor, etc.",
        "synonyms": ["designation", "faculty rank", "instructor title", "faculty designation", "title", "rank"],
    },
    ("instructors", "joining_year"): {
        "description": "Year the faculty member joined the institution.",
        "synonyms": ["joining year", "hire year", "hired year", "hire date", "appointment year"],
    },
    ("courses", "course_id"): {
        "description": "Unique integer identifier for the course (Primary Key).",
        "synonyms": ["course id", "subject id"],
    },
    ("courses", "department_id"): {
        "description": "Foreign key reference to departments.department_id.",
        "synonyms": ["course department id"],
    },
    ("courses", "course_code"): {
        "description": "Curriculum code (e.g., CS101, AI201, MATH101).",
        "synonyms": ["course code", "course number", "class code", "subject code"],
    },
    ("courses", "course_name"): {
        "description": "Official title of the course.",
        "synonyms": ["course name", "course title", "subject name", "class name", "curriculum title"],
    },
    ("courses", "credits"): {
        "description": "Academic credit units awarded upon completion (1 to 6).",
        "synonyms": ["credits", "credit hours", "units", "credit count", "total credits"],
    },
    ("courses", "course_level"): {
        "description": "Curriculum level: 100, 200, 300, 400, or 500.",
        "synonyms": ["course level", "level", "difficulty level", "academic level"],
    },
    ("terms", "term_id"): {
        "description": "Unique integer identifier for the academic term (Primary Key).",
        "synonyms": ["term id"],
    },
    ("terms", "term_name"): {
        "description": "Human-readable semester session name (e.g., Fall 2024, Spring 2024).",
        "synonyms": ["term name", "semester name", "academic term name", "session name"],
    },
    ("terms", "academic_year"): {
        "description": "Four-digit calendar academic year (e.g., 2024).",
        "synonyms": ["academic year", "calendar year", "school year"],
    },
    ("terms", "semester_type"): {
        "description": "Season of the academic term: Fall, Spring, or Summer.",
        "synonyms": ["semester type", "term type", "session type", "term season"],
    },
    ("terms", "start_date"): {
        "description": "Term beginning date.",
        "synonyms": ["start date", "term start", "semester start date"],
    },
    ("terms", "end_date"): {
        "description": "Term completion date.",
        "synonyms": ["end date", "term end", "semester end date"],
    },
    ("course_offerings", "offering_id"): {
        "description": "Unique integer identifier for the course offering (Primary Key).",
        "synonyms": ["offering id", "section id"],
    },
    ("course_offerings", "course_id"): {
        "description": "Foreign key reference to courses.course_id.",
        "synonyms": ["offering course id"],
    },
    ("course_offerings", "instructor_id"): {
        "description": "Foreign key reference to instructors.instructor_id.",
        "synonyms": ["offering instructor id"],
    },
    ("course_offerings", "term_id"): {
        "description": "Foreign key reference to terms.term_id.",
        "synonyms": ["offering term id"],
    },
    ("course_offerings", "section"): {
        "description": "Classroom cohort section identifier (e.g., A, B, C).",
        "synonyms": ["section", "class section", "offering section"],
    },
    ("course_offerings", "classroom"): {
        "description": "Physical lecture room or auditorium assigned for the section.",
        "synonyms": ["classroom", "room", "room number", "lecture hall", "auditorium"],
    },
    ("enrollments", "enrollment_id"): {
        "description": "Unique integer identifier for the course enrollment (Primary Key).",
        "synonyms": ["enrollment id", "registration id"],
    },
    ("enrollments", "student_id"): {
        "description": "Foreign key reference to students.student_id.",
        "synonyms": ["enrollment student id"],
    },
    ("enrollments", "offering_id"): {
        "description": "Foreign key reference to course_offerings.offering_id.",
        "synonyms": ["enrollment offering id"],
    },
    ("enrollments", "attendance_percentage"): {
        "description": "Percentage of lectures attended (0.0% to 100.0%).",
        "synonyms": [
            "attendance",
            "attendance percentage",
            "attendance rate",
            "presence",
            "presence percentage",
            "attendance percent",
        ],
    },
    ("enrollments", "final_grade"): {
        "description": "Letter grade awarded upon course completion (e.g., A, B+, C, F).",
        "synonyms": ["final grade", "letter grade", "course grade", "overall grade"],
    },
    ("enrollments", "grade_points"): {
        "description": "Numeric quality points earned for the course grade (0.0 to 4.0).",
        "synonyms": ["grade points", "grade point", "points"],
    },
    ("enrollments", "enrollment_status"): {
        "description": "Course registration status: Enrolled, Completed, or Dropped.",
        "synonyms": ["enrollment status", "registration status", "course status"],
    },
    ("assessments", "assessment_id"): {
        "description": "Unique integer identifier for the assessment (Primary Key).",
        "synonyms": ["assessment id", "exam id"],
    },
    ("assessments", "offering_id"): {
        "description": "Foreign key reference to course_offerings.offering_id.",
        "synonyms": ["assessment offering id"],
    },
    ("assessments", "title"): {
        "description": "Assessment descriptive title (e.g., Midterm Exam, Quiz 1).",
        "synonyms": ["assessment title", "assessment name", "exam title", "quiz title", "test title"],
    },
    ("assessments", "assessment_type"): {
        "description": "Type category: Quiz, Assignment, Midterm, Final, or Project.",
        "synonyms": ["assessment type", "exam type", "evaluation type"],
    },
    ("assessments", "max_marks"): {
        "description": "Maximum raw marks possible on this assessment component.",
        "synonyms": ["max marks", "maximum marks", "total marks", "out of marks", "max score"],
    },
    ("assessments", "weightage_percent"): {
        "description": "Contribution percentage of this component toward the final course grade (0.0% to 100.0%).",
        "synonyms": ["weightage", "weight", "weightage percent", "percentage weight", "weight percent"],
    },
    ("student_marks", "mark_id"): {
        "description": "Unique integer identifier for the student mark record (Primary Key).",
        "synonyms": ["mark id", "score id"],
    },
    ("student_marks", "assessment_id"): {
        "description": "Foreign key reference to assessments.assessment_id.",
        "synonyms": ["mark assessment id"],
    },
    ("student_marks", "enrollment_id"): {
        "description": "Foreign key reference to enrollments.enrollment_id.",
        "synonyms": ["mark enrollment id"],
    },
    ("student_marks", "marks_obtained"): {
        "description": "Actual raw score obtained by the student on the assessment.",
        "synonyms": [
            "marks obtained",
            "marks",
            "mark",
            "score",
            "scores",
            "score obtained",
            "points obtained",
            "marks scored",
        ],
    },
}

# Domain specific literal value maps for entity resolution
KNOWN_DOMAIN_VALUES: Dict[str, Dict[str, Tuple[str, str]]] = {
    # department codes
    "ai": ("departments", "code"),
    "cs": ("departments", "code"),
    "ee": ("departments", "code"),
    "me": ("departments", "code"),
    "math": ("departments", "code"),
    # department names
    "artificial intelligence": ("departments", "name"),
    "computer science": ("departments", "name"),
    "electrical engineering": ("departments", "name"),
    "mechanical engineering": ("departments", "name"),
    "mathematics": ("departments", "name"),
    # academic courses
    "database management systems": ("courses", "course_name"),
    "programming fundamentals": ("courses", "course_name"),
    "data structures & algorithms": ("courses", "course_name"),
    "data structures and algorithms": ("courses", "course_name"),
    "distributed cloud systems": ("courses", "course_name"),
    "introduction to artificial intelligence": ("courses", "course_name"),
    "machine learning fundamentals": ("courses", "course_name"),
    "natural language processing": ("courses", "course_name"),
    "computer vision & deep learning": ("courses", "course_name"),
    "computer vision and deep learning": ("courses", "course_name"),
    "linear circuit analysis": ("courses", "course_name"),
    "digital signal processing": ("courses", "course_name"),
    "microprocessors & embedded systems": ("courses", "course_name"),
    "microprocessors and embedded systems": ("courses", "course_name"),
    "engineering mechanics & statics": ("courses", "course_name"),
    "engineering mechanics and statics": ("courses", "course_name"),
    "thermodynamics & heat transfer": ("courses", "course_name"),
    "thermodynamics and heat transfer": ("courses", "course_name"),
    "calculus & analytical geometry": ("courses", "course_name"),
    "calculus and analytical geometry": ("courses", "course_name"),
    "linear algebra & probability": ("courses", "course_name"),
    "linear algebra and probability": ("courses", "course_name"),
    # academic status
    "active": ("students", "academic_status"),
    "probation": ("students", "academic_status"),
    "graduated": ("students", "academic_status"),
    "suspended": ("students", "academic_status"),
    # enrollment status
    "enrolled": ("enrollments", "enrollment_status"),
    "completed": ("enrollments", "enrollment_status"),
    "dropped": ("enrollments", "enrollment_status"),
    # assessment types
    "quiz": ("assessments", "assessment_type"),
    "assignment": ("assessments", "assessment_type"),
    "midterm": ("assessments", "assessment_type"),
    "final": ("assessments", "assessment_type"),
    "project": ("assessments", "assessment_type"),
    # term semester types
    "fall": ("terms", "semester_type"),
    "spring": ("terms", "semester_type"),
    "summer": ("terms", "semester_type"),
}

# Ambiguous term candidates mapping
AMBIGUOUS_COLUMNS_MAP: Dict[str, List[Tuple[str, str, str]]] = {
    "grade": [
        ("student_marks", "marks_obtained", "Numerical score obtained on an assessment"),
        ("enrollments", "final_grade", "Letter grade (A, B, C) awarded for a completed course"),
        ("enrollments", "grade_points", "Numeric grade points (0.0 to 4.0) earned for course"),
    ],
    "grades": [
        ("student_marks", "marks_obtained", "Numerical score obtained on an assessment"),
        ("enrollments", "final_grade", "Letter grade (A, B, C) awarded for a completed course"),
        ("enrollments", "grade_points", "Numeric grade points (0.0 to 4.0) earned for course"),
    ],
    "year": [
        ("students", "enrollment_year", "Year student was admitted / enrolled"),
        ("instructors", "joining_year", "Year faculty member joined department"),
        ("terms", "academic_year", "Calendar academic year of term session"),
        ("departments", "established_year", "Founding year of department"),
    ],
    "name": [
        ("departments", "name", "Full name of academic department"),
        ("courses", "course_name", "Curriculum course title"),
        ("students", "first_name", "Student given first name"),
        ("instructors", "first_name", "Instructor given first name"),
        ("terms", "term_name", "Academic term label"),
    ],
    "status": [
        ("students", "academic_status", "Student standing (Active, Probation, etc.)"),
        ("enrollments", "enrollment_status", "Course registration outcome (Enrolled, Completed, Dropped)"),
    ],
    "code": [
        ("departments", "code", "Short department abbreviation (CS, AI, etc.)"),
        ("courses", "course_code", "Course curriculum identifier (CS101, AI201, etc.)"),
    ],
    "title": [
        ("courses", "course_name", "Curriculum course title"),
        ("assessments", "title", "Assessment assignment title"),
        ("instructors", "designation", "Faculty academic title/rank"),
    ],
}


# ---------------------------------------------------------------------------
# Data Models for Catalog & Join Graph
# ---------------------------------------------------------------------------

@dataclass
class ColumnMetadata:
    """Represents introspected and catalog metadata for a single database column."""
    name: str
    table_name: str
    data_type: str
    nullable: bool
    is_primary_key: bool
    is_foreign_key: bool
    foreign_key_target: Optional[str] = None
    description: str = ""
    synonyms: List[str] = field(default_factory=list)


@dataclass
class TableMetadata:
    """Represents introspected and catalog metadata for a single database table."""
    name: str
    entity_name: str
    description: str
    primary_keys: List[str]
    foreign_keys: List[Dict[str, Any]]
    unique_constraints: List[Dict[str, Any]]
    columns: Dict[str, ColumnMetadata]
    synonyms: List[str] = field(default_factory=list)


@dataclass
class JoinEdge:
    """Represents a directional foreign-key join relationship between two tables."""
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    direction: str  # "MANY_TO_ONE" or "ONE_TO_MANY"
    condition: str


@dataclass
class JoinPathStep:
    """Represents a single step in a multi-table join sequence."""
    from_table: str
    to_table: str
    join_type: str
    condition: str
    direction: str


@dataclass
class MultiTableJoinResult:
    """Structured result of multi-table join path resolution."""
    is_connected: bool
    anchor_table: Optional[str] = None
    joined_tables: List[str] = field(default_factory=list)
    total_hops: int = 0
    join_steps: List[JoinPathStep] = field(default_factory=list)
    alternative_paths: List[List[JoinPathStep]] = field(default_factory=list)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Schema Catalog
# ---------------------------------------------------------------------------

class SchemaCatalog:
    """Dynamic relational schema catalog holding introspected tables, columns, and academic synonyms."""

    def __init__(self, engine=read_only_engine) -> None:
        self.engine = engine
        self.tables: Dict[str, TableMetadata] = {}
        self._synonym_to_table: Dict[str, str] = {}
        self._synonym_to_column: Dict[str, List[Tuple[str, str]]] = {}
        self._introspect_and_build()

    def _introspect_and_build(self) -> None:
        """Inspects live SQLite database via SQLAlchemy Inspector and hydrates metadata."""
        inspector = inspect(self.engine)
        table_names = inspector.get_table_names()

        for t_name in table_names:
            pk_dict = inspector.get_pk_constraint(t_name)
            pks = pk_dict.get("constrained_columns", [])
            fks = inspector.get_foreign_keys(t_name)
            uqs = inspector.get_unique_constraints(t_name)
            try:
                for idx in inspector.get_indexes(t_name):
                    if idx.get("unique"):
                        c_names = idx.get("column_names", [])
                        if c_names and not any(u.get("column_names") == c_names for u in uqs):
                            uqs.append({"name": idx.get("name"), "column_names": c_names})
            except Exception:
                pass
            raw_cols = inspector.get_columns(t_name)

            fk_map: Dict[str, str] = {}
            for fk in fks:
                referred_table = fk["referred_table"]
                for c_col, r_col in zip(fk["constrained_columns"], fk["referred_columns"]):
                    fk_map[c_col] = f"{referred_table}.{r_col}"

            # Table domain metadata
            t_info = ACADEMIC_TABLE_METADATA.get(t_name, {
                "entity_name": t_name.capitalize(),
                "description": f"Relational entity table for {t_name}.",
                "synonyms": [t_name],
            })

            columns_dict: Dict[str, ColumnMetadata] = {}
            for col in raw_cols:
                c_name = col["name"]
                c_type = str(col["type"])
                c_nullable = bool(col.get("nullable", True))
                is_pk = c_name in pks
                is_fk = c_name in fk_map
                fk_target = fk_map.get(c_name)

                c_info = ACADEMIC_COLUMN_METADATA.get((t_name, c_name), {
                    "description": f"Attribute {c_name} in table {t_name}.",
                    "synonyms": [c_name],
                })

                col_meta = ColumnMetadata(
                    name=c_name,
                    table_name=t_name,
                    data_type=c_type,
                    nullable=c_nullable,
                    is_primary_key=is_pk,
                    is_foreign_key=is_fk,
                    foreign_key_target=fk_target,
                    description=c_info["description"],
                    synonyms=c_info["synonyms"],
                )
                columns_dict[c_name] = col_meta

                # Index column synonyms
                for syn in col_meta.synonyms:
                    norm_syn = syn.lower().strip()
                    self._synonym_to_column.setdefault(norm_syn, []).append((t_name, c_name))

            table_meta = TableMetadata(
                name=t_name,
                entity_name=t_info["entity_name"],
                description=t_info["description"],
                primary_keys=pks,
                foreign_keys=fks,
                unique_constraints=uqs,
                columns=columns_dict,
                synonyms=t_info["synonyms"],
            )
            self.tables[t_name] = table_meta

            # Index table synonyms
            for syn in table_meta.synonyms:
                norm_syn = syn.lower().strip()
                self._synonym_to_table[norm_syn] = t_name

    def get_table(self, table_name: str) -> Optional[TableMetadata]:
        """Returns metadata for a specific table."""
        return self.tables.get(table_name)

    def get_column(self, table_name: str, column_name: str) -> Optional[ColumnMetadata]:
        """Returns metadata for a specific column."""
        table = self.get_table(table_name)
        if table:
            return table.columns.get(column_name)
        return None

    def find_table_by_name_or_synonym(self, token: str) -> Optional[str]:
        """Resolves a raw string or alias to a canonical table name."""
        lower = token.lower().strip()
        if lower in self.tables:
            return lower
        return self._synonym_to_table.get(lower)

    def find_columns_by_name_or_synonym(self, token: str) -> List[Tuple[str, str]]:
        """Resolves a token to a list of matching (table_name, column_name) pairs."""
        lower = token.lower().strip()
        # Direct table.column syntax
        if "." in lower:
            parts = lower.split(".", 1)
            t_cand = self.find_table_by_name_or_synonym(parts[0])
            if t_cand:
                col = self.get_column(t_cand, parts[1])
                if col:
                    return [(t_cand, col.name)]

        matches = self._synonym_to_column.get(lower, [])
        if matches:
            return matches

        # Fallback exact column name match across tables
        res: List[Tuple[str, str]] = []
        for t_name, table in self.tables.items():
            if lower in table.columns:
                res.append((t_name, lower))
        return res


# ---------------------------------------------------------------------------
# Join Graph
# ---------------------------------------------------------------------------

class JoinGraph:
    """Undirected graph G = (V, E) connecting database tables via foreign key constraints.

    Provides shortest-path Dijkstra/BFS resolution and multi-table Steiner join trees.
    """

    def __init__(self, catalog: SchemaCatalog) -> None:
        self.catalog = catalog
        self.adj: Dict[str, List[JoinEdge]] = {}
        self._build_graph()

    def _build_graph(self) -> None:
        """Constructs bidirectional join adjacency list from catalog foreign keys."""
        for t_name in self.catalog.tables.keys():
            self.adj.setdefault(t_name, [])

        for src_table, table in self.catalog.tables.items():
            for fk in table.foreign_keys:
                tgt_table = fk["referred_table"]
                for src_col, tgt_col in zip(fk["constrained_columns"], fk["referred_columns"]):
                    condition = f"{src_table}.{src_col} = {tgt_table}.{tgt_col}"

                    # Forward: Referencing (child) -> Referenced (parent) (MANY_TO_ONE)
                    fwd_edge = JoinEdge(
                        from_table=src_table,
                        from_column=src_col,
                        to_table=tgt_table,
                        to_column=tgt_col,
                        direction="MANY_TO_ONE",
                        condition=condition,
                    )
                    self.adj[src_table].append(fwd_edge)

                    # Reverse: Referenced (parent) -> Referencing (child) (ONE_TO_MANY)
                    rev_edge = JoinEdge(
                        from_table=tgt_table,
                        from_column=tgt_col,
                        to_table=src_table,
                        to_column=src_col,
                        direction="ONE_TO_MANY",
                        condition=condition,
                    )
                    self.adj[tgt_table].append(rev_edge)

    @property
    def adjacency(self) -> Dict[str, List[JoinEdge]]:
        """Access the bidirectional adjacency map of the join graph."""
        return self.adj

    def find_shortest_path(self, start: str, goal: str) -> Optional[List[JoinEdge]]:
        """Finds the primary shortest path between two tables, or None if disconnected."""
        paths = self.find_all_shortest_paths(start, goal)
        return paths[0] if paths else None

    def find_all_shortest_paths(self, start: str, goal: str) -> List[List[JoinEdge]]:
        """Finds all shortest paths (minimal hop count) between two tables using BFS."""
        if start not in self.adj or goal not in self.adj:
            return []
        if start == goal:
            return [[]]

        queue = deque([[(start, None)]])
        visited_at_depth: Dict[str, int] = {start: 0}
        shortest_paths: List[List[Any]] = []
        min_len: Optional[int] = None

        while queue:
            path = queue.popleft()
            current_node, _ = path[-1]
            depth = len(path) - 1

            if min_len is not None and depth > min_len:
                break

            if current_node == goal:
                if min_len is None:
                    min_len = depth
                shortest_paths.append(path)
                continue

            for edge in self.adj.get(current_node, []):
                nxt = edge.to_table
                if nxt not in visited_at_depth or visited_at_depth[nxt] == depth + 1:
                    visited_at_depth[nxt] = depth + 1
                    new_path = list(path)
                    new_path.append((nxt, edge))
                    queue.append(new_path)

        # Convert node steps to list of JoinEdges
        res: List[List[JoinEdge]] = []
        for p in shortest_paths:
            edges = [step[1] for step in p[1:] if step[1] is not None]
            res.append(edges)
        return res

    def resolve_multi_table_join(
        self,
        required_tables: Set[str],
        preferred_anchor: Optional[str] = None,
    ) -> MultiTableJoinResult:
        """Computes the minimal join tree connecting all requested tables without arbitrary joins."""
        all_tables = set(self.adj.keys())

        # Validate that all requested tables exist in the schema graph
        for t in required_tables:
            if t not in all_tables:
                return MultiTableJoinResult(
                    is_connected=False,
                    error=f"Table '{t}' is disconnected or not present in schema graph.",
                )

        if not required_tables:
            return MultiTableJoinResult(is_connected=True)

        if len(required_tables) == 1:
            single = list(required_tables)[0]
            return MultiTableJoinResult(
                is_connected=True,
                anchor_table=single,
                joined_tables=[single],
                total_hops=0,
                join_steps=[],
            )

        # 2-table shortcut: check for multiple paths
        if len(required_tables) == 2:
            t1, t2 = list(required_tables)
            paths = self.find_all_shortest_paths(t1, t2)
            if not paths:
                return MultiTableJoinResult(
                    is_connected=False,
                    error=f"No valid join path exists between '{t1}' and '{t2}'.",
                )

            primary_path = paths[0]
            alt_path_steps: List[List[JoinPathStep]] = []
            if len(paths) > 1:
                for alt_edges in paths[1:]:
                    steps = [
                        JoinPathStep(
                            from_table=e.from_table,
                            to_table=e.to_table,
                            join_type="INNER JOIN",
                            condition=e.condition,
                            direction=e.direction,
                        )
                        for e in alt_edges
                    ]
                    alt_path_steps.append(steps)

            join_steps = [
                JoinPathStep(
                    from_table=e.from_table,
                    to_table=e.to_table,
                    join_type="INNER JOIN",
                    condition=e.condition,
                    direction=e.direction,
                )
                for e in primary_path
            ]
            joined_tables = [t1] + [e.to_table for e in primary_path]

            return MultiTableJoinResult(
                is_connected=True,
                anchor_table=t1,
                joined_tables=joined_tables,
                total_hops=len(join_steps),
                join_steps=join_steps,
                alternative_paths=alt_path_steps,
            )

        # Multi-table (>= 3): Steiner Tree Approximation via Takahashi-Matsuyama heuristic over candidate roots
        candidate_roots = list(all_tables)
        if preferred_anchor and preferred_anchor in all_tables:
            candidate_roots = [preferred_anchor] + [r for r in candidate_roots if r != preferred_anchor]

        def _order_tree(
            start_node: str, edges: List[Tuple[str, str, JoinEdge]]
        ) -> Tuple[List[str], List[JoinPathStep]]:
            visited = {start_node}
            q = deque([start_node])
            steps: List[JoinPathStep] = []
            tables_order = [start_node]

            while q:
                curr = q.popleft()
                for u, v, edge in edges:
                    if u == curr and v not in visited:
                        visited.add(v)
                        tables_order.append(v)
                        steps.append(
                            JoinPathStep(
                                from_table=u,
                                to_table=v,
                                join_type="INNER JOIN",
                                condition=edge.condition,
                                direction=edge.direction,
                            )
                        )
                        q.append(v)
                    elif v == curr and u not in visited:
                        visited.add(u)
                        tables_order.append(u)
                        rev_dir = "ONE_TO_MANY" if edge.direction == "MANY_TO_ONE" else "MANY_TO_ONE"
                        steps.append(
                            JoinPathStep(
                                from_table=v,
                                to_table=u,
                                join_type="INNER JOIN",
                                condition=edge.condition,
                                direction=rev_dir,
                            )
                        )
                        q.append(u)

            return tables_order, steps

        best_tree = None
        min_edge_count = float("inf")
        alternative_trees: List[Tuple[str, Set[str], List[Tuple[str, str, JoinEdge]]]] = []
        visited_tree_edge_sets: Set[frozenset] = set()

        for root in candidate_roots:
            tree_nodes: Set[str] = {root}
            tree_edges: List[Tuple[str, str, JoinEdge]] = []
            visited_pairs: Set[Tuple[str, str]] = set()

            remaining_targets = set(required_tables) - tree_nodes
            possible = True

            while remaining_targets:
                # Multi-source BFS from existing tree_nodes to find the closest remaining target
                q = deque([[(n, None)] for n in tree_nodes])
                vis = set(tree_nodes)
                found_path = None

                while q:
                    p = q.popleft()
                    curr, _ = p[-1]
                    if curr in remaining_targets:
                        found_path = p
                        break
                    for edge in self.adj.get(curr, []):
                        nxt = edge.to_table
                        if nxt not in vis:
                            vis.add(nxt)
                            new_p = list(p)
                            new_p.append((nxt, edge))
                            q.append(new_p)

                if not found_path:
                    possible = False
                    break

                for i in range(len(found_path) - 1):
                    u = found_path[i][0]
                    v = found_path[i + 1][0]
                    edge_obj = found_path[i + 1][1]
                    pair_key = tuple(sorted([u, v]))
                    if pair_key not in visited_pairs:
                        visited_pairs.add(pair_key)
                        tree_edges.append((u, v, edge_obj))
                        tree_nodes.add(u)
                        tree_nodes.add(v)

                remaining_targets = set(required_tables) - tree_nodes

            if possible and required_tables.issubset(tree_nodes):
                edge_frozenset = frozenset(tuple(sorted([u, v])) for u, v, _ in tree_edges)
                if len(tree_edges) < min_edge_count:
                    min_edge_count = len(tree_edges)
                    best_tree = (root, tree_nodes, tree_edges)
                    alternative_trees = []
                    visited_tree_edge_sets = {edge_frozenset}
                elif len(tree_edges) == min_edge_count and best_tree is not None:
                    if edge_frozenset not in visited_tree_edge_sets:
                        visited_tree_edge_sets.add(edge_frozenset)
                        alternative_trees.append((root, tree_nodes, tree_edges))

        if not best_tree:
            return MultiTableJoinResult(
                is_connected=False,
                error="Unable to discover a connected join path spanning all requested tables.",
            )

        root, _, tree_edges = best_tree
        joined_tables, ordered_steps = _order_tree(root, tree_edges)

        alt_path_steps: List[List[JoinPathStep]] = []
        for alt_root, _, alt_edges in alternative_trees:
            _, alt_steps = _order_tree(alt_root, alt_edges)
            alt_path_steps.append(alt_steps)

        return MultiTableJoinResult(
            is_connected=True,
            anchor_table=root,
            joined_tables=joined_tables,
            total_hops=len(ordered_steps),
            join_steps=ordered_steps,
            alternative_paths=alt_path_steps,
        )


# ---------------------------------------------------------------------------
# Semantic Schema Linker
# ---------------------------------------------------------------------------

class SchemaLinker:
    """Semantic Schema Linker connecting natural language queries to database tables and columns."""

    def __init__(
        self,
        catalog: Optional[SchemaCatalog] = None,
        join_graph: Optional[JoinGraph] = None,
        preprocessor: Optional[NLPPreprocessor] = None,
    ) -> None:
        self.catalog = catalog or SchemaCatalog()
        self.join_graph = join_graph or JoinGraph(self.catalog)
        self.preprocessor = preprocessor or get_nlp_preprocessor()

    def link_query(self, query: str) -> Dict[str, Any]:
        """Executes full schema linking on input natural language query."""
        start_time = time.time()
        prep = self.preprocessor.preprocess(query)
        tokens = prep["tokens"]
        lemmas = prep["lemmas"]
        unigrams = prep["word_ngrams"]["unigrams"]
        bigrams = prep["word_ngrams"]["bigrams"]
        trigrams = prep["word_ngrams"]["trigrams"]

        linked_tables: Set[str] = set()
        linked_columns: Dict[str, List[Dict[str, Any]]] = {}
        linked_values: List[Dict[str, Any]] = []
        unsupported_entities: List[str] = []
        ambiguous_candidates: List[Dict[str, Any]] = []
        is_ambiguous = False
        ambiguity_reasons: List[str] = []

        all_phrases = trigrams + bigrams + unigrams

        # 0. Academic Identifier Recognition (Roll Numbers & Course Codes)
        extracted_roll_tokens: Set[str] = set()
        roll_matches = re.findall(r"\b\d{4}-[A-Za-z]{2,4}-\d{3,4}\b", query)
        for r_val in roll_matches:
            linked_tables.add("students")
            extracted_roll_tokens.add(r_val.lower())
            linked_values.append({
                "matched_token": r_val,
                "table_name": "students",
                "column_name": "roll_number",
                "value": r_val.upper(),
                "confidence": 1.0,
            })

        extracted_course_tokens: Set[str] = set()
        course_code_matches = re.findall(r"\b[A-Za-z]{2,4}\d{3}\b", query)
        for c_val in course_code_matches:
            linked_tables.add("courses")
            extracted_course_tokens.add(c_val.lower())
            linked_values.append({
                "matched_token": c_val,
                "table_name": "courses",
                "column_name": "course_code",
                "value": c_val.upper(),
                "confidence": 1.0,
            })

        # 1. Multi-word Column / Attribute Linking (Trigrams & Bigrams)
        matched_column_phrases: Set[str] = set()
        matched_column_words: Set[str] = set()

        for phrase in trigrams + bigrams:
            if phrase in matched_column_phrases:
                continue
            col_matches = self.catalog.find_columns_by_name_or_synonym(phrase)
            if col_matches:
                t_cand, c_cand = col_matches[0]
                linked_tables.add(t_cand)
                linked_columns.setdefault(t_cand, []).append({
                    "column_name": c_cand,
                    "matched_token": phrase,
                    "confidence": 0.98,
                    "match_type": "SYNONYM_MATCH",
                })
                matched_column_phrases.add(phrase)
                for w in phrase.split():
                    matched_column_words.add(w)

        # 2. Known Domain Literal Values Check
        norm_query_lower = f" {prep['normalized_query'].lower()} "
        for phrase, (t_name, c_name) in KNOWN_DOMAIN_VALUES.items():
            pattern = rf"\b{re.escape(phrase)}\b"
            # Check if this occurrence was simply part of an extracted roll number
            if re.search(rf"\d+-{re.escape(phrase)}-\d+", norm_query_lower):
                standalone = re.sub(rf"\d+-{re.escape(phrase)}-\d+", "", norm_query_lower)
                if not re.search(pattern, standalone):
                    continue

            if re.search(pattern, norm_query_lower):
                linked_tables.add(t_name)
                linked_values.append({
                    "matched_token": phrase,
                    "table_name": t_name,
                    "column_name": c_name,
                    "value": phrase.upper() if len(phrase) <= 5 and phrase in ("ai", "cs", "ee", "me", "math") else phrase.title(),
                    "confidence": 1.0,
                })

        # 3. Ambiguity Detection on Bare Unigrams (e.g. 'grade', 'year', 'status')
        for word in unigrams:
            if word in AMBIGUOUS_COLUMNS_MAP:
                # If this word was part of an explicitly matched multi-word column phrase, do not flag
                if word in matched_column_words:
                    continue

                candidates = AMBIGUOUS_COLUMNS_MAP[word]
                is_ambiguous = True
                ambiguity_reasons.append("MULTIPLE_COLUMN_CANDIDATES")
                ambiguous_candidates.append({
                    "token": word,
                    "candidates": [
                        {"table": c[0], "column": c[1], "description": c[2]}
                        for c in candidates
                    ],
                    "message": f"Token '{word}' could refer to multiple schema attributes across tables.",
                })

        # 4. Table / Entity Linking
        for phrase in all_phrases:
            t_match = self.catalog.find_table_by_name_or_synonym(phrase)
            if t_match:
                linked_tables.add(t_match)

        # 5. Single-Word Column / Attribute Linking (Unigrams not matched yet)
        for phrase in unigrams:
            if phrase in matched_column_phrases or phrase in matched_column_words or phrase in AMBIGUOUS_COLUMNS_MAP:
                continue
            col_matches = self.catalog.find_columns_by_name_or_synonym(phrase)
            if col_matches:
                # If multiple matches across tables, filter by linked_tables if possible
                if len(col_matches) > 1 and linked_tables:
                    filtered = [m for m in col_matches if m[0] in linked_tables]
                    if filtered:
                        col_matches = filtered

                if len(col_matches) == 1:
                    t_cand, c_cand = col_matches[0]
                    linked_tables.add(t_cand)
                    linked_columns.setdefault(t_cand, []).append({
                        "column_name": c_cand,
                        "matched_token": phrase,
                        "confidence": 0.90,
                        "match_type": "SYNONYM_MATCH",
                    })
                    matched_column_phrases.add(phrase)
                elif len(col_matches) > 1:
                    is_ambiguous = True
                    ambiguity_reasons.append("MULTIPLE_COLUMN_CANDIDATES")
                    ambiguous_candidates.append({
                        "token": phrase,
                        "candidates": [{"table": m[0], "column": m[1]} for m in col_matches],
                        "message": f"Attribute '{phrase}' matches multiple columns across tables.",
                    })
                    ambiguous_candidates.append({
                        "token": phrase,
                        "candidates": [{"table": m[0], "column": m[1]} for m in col_matches],
                        "message": f"Attribute '{phrase}' matches multiple columns across tables.",
                    })

        # 5. Unsupported Entity / Out-of-Catalog Token Detection
        academic_known_stems = {
            "student", "course", "instructor", "faculty", "professor", "department",
            "term", "semester", "offering", "enrollment", "assessment", "mark",
            "grade", "cgpa", "gpa", "attendance", "quiz", "midterm", "final", "score",
            "section", "classroom", "credit", "year", "building", "code", "ai", "cs", "ee", "me", "math"
        }
        unsupported_blacklist = {
            "hostel", "hostels", "cafeteria", "canteen", "library", "bus", "transport",
            "fee", "fees", "tuition", "sports", "gym", "scholarship", "parking",
            "wifi", "salary", "alumni", "mess", "dorm", "dormitory"
        }
        for token, lemma in zip(tokens, lemmas):
            token_lower = token.lower()
            lemma_lower = lemma.lower()
            if token_lower in unsupported_blacklist or lemma_lower in unsupported_blacklist:
                if token_lower not in unsupported_entities:
                    unsupported_entities.append(token_lower)
                    is_ambiguous = True
                    ambiguity_reasons.append("UNSUPPORTED_ENTITIES")

        # 6. Resolve Join Path across all linked tables
        join_path_res = self.join_graph.resolve_multi_table_join(linked_tables)
        if not join_path_res.is_connected and linked_tables:
            is_ambiguous = True
            ambiguity_reasons.append("DISCONNECTED_TABLES")

        if len(join_path_res.alternative_paths) > 0:
            is_ambiguous = True
            ambiguity_reasons.append("MULTIPLE_JOIN_PATHS")

        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "query": query,
            "linked_tables": sorted(list(linked_tables)),
            "linked_columns": linked_columns,
            "linked_values": linked_values,
            "unsupported_entities": unsupported_entities,
            "is_ambiguous": is_ambiguous,
            "ambiguity_reason": ambiguity_reasons[0] if ambiguity_reasons else None,
            "ambiguous_candidates": ambiguous_candidates,
            "join_path": {
                "is_connected": join_path_res.is_connected,
                "anchor_table": join_path_res.anchor_table,
                "joined_tables": join_path_res.joined_tables,
                "total_hops": join_path_res.total_hops,
                "join_steps": [
                    {
                        "from_table": step.from_table,
                        "to_table": step.to_table,
                        "join_type": step.join_type,
                        "condition": step.condition,
                        "direction": step.direction,
                    }
                    for step in join_path_res.join_steps
                ],
                "alternative_paths_count": len(join_path_res.alternative_paths),
                "alternative_paths": [
                    [
                        {
                            "from_table": step.from_table,
                            "to_table": step.to_table,
                            "join_type": step.join_type,
                            "condition": step.condition,
                            "direction": step.direction,
                        }
                        for step in alt_path
                    ]
                    for alt_path in join_path_res.alternative_paths
                ],
                "error": join_path_res.error,
            },
            "execution_time_ms": elapsed_ms,
        }


# ---------------------------------------------------------------------------
# Global Singletons
# ---------------------------------------------------------------------------

_cached_catalog: Optional[SchemaCatalog] = None
_cached_join_graph: Optional[JoinGraph] = None
_cached_schema_linker: Optional[SchemaLinker] = None


def get_schema_catalog() -> SchemaCatalog:
    """Returns the cached singleton SchemaCatalog instance."""
    global _cached_catalog
    if _cached_catalog is None:
        _cached_catalog = SchemaCatalog()
    return _cached_catalog


def get_join_graph() -> JoinGraph:
    """Returns the cached singleton JoinGraph instance."""
    global _cached_join_graph
    if _cached_join_graph is None:
        _cached_join_graph = JoinGraph(get_schema_catalog())
    return _cached_join_graph


def get_schema_linker() -> SchemaLinker:
    """Returns the cached singleton SchemaLinker instance."""
    global _cached_schema_linker
    if _cached_schema_linker is None:
        catalog = get_schema_catalog()
        join_graph = get_join_graph()
        preprocessor = get_nlp_preprocessor()
        _cached_schema_linker = SchemaLinker(catalog, join_graph, preprocessor)
    return _cached_schema_linker


schema_linker = get_schema_linker()
