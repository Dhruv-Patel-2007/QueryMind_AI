"""Unit tests for Deterministic Database Seeding, Reproducibility, and Transactions."""

from pathlib import Path
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.academic import (
    Department,
    Student,
    Instructor,
    Course,
    Term,
    CourseOffering,
    Enrollment,
    Assessment,
    StudentMark,
)
from scripts.seed_db import seed_database


def create_temp_db_engine(db_path: Path):
    """Creates a temporary SQLite engine with Foreign Keys enabled."""
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()

    return engine


def test_seed_database_record_counts(tmp_path: Path):
    """Verify that seeding creates the expected record counts for all 9 entities."""
    test_db = tmp_path / "seed_counts.db"
    test_engine = create_temp_db_engine(test_db)

    counts = seed_database(engine=test_engine, reset=True)

    assert counts["departments"] == 5
    assert counts["instructors"] == 20
    assert counts["courses"] == 15
    assert counts["terms"] == 6
    assert counts["students"] == 120
    assert counts["course_offerings"] == 45
    assert counts["assessments"] == 135
    assert counts["enrollments"] == 360
    assert counts["student_marks"] == 1080


def test_seeding_foreign_key_integrity(tmp_path: Path):
    """Verify all seeded records maintain valid foreign key references with zero orphaned rows."""
    test_db = tmp_path / "seed_fk.db"
    test_engine = create_temp_db_engine(test_db)

    seed_database(engine=test_engine, reset=True)

    session_factory = sessionmaker(bind=test_engine)
    session = session_factory()
    try:
        # Check students link to valid departments
        dept_ids = {d.department_id for d in session.query(Department).all()}
        for s in session.query(Student).all():
            assert s.department_id in dept_ids, f"Student {s.roll_number} has invalid department_id"

        # Check offerings link to valid courses, instructors, and terms
        course_ids = {c.course_id for c in session.query(Course).all()}
        instructor_ids = {i.instructor_id for i in session.query(Instructor).all()}
        term_ids = {t.term_id for t in session.query(Term).all()}
        for off in session.query(CourseOffering).all():
            assert off.course_id in course_ids
            assert off.instructor_id in instructor_ids
            assert off.term_id in term_ids

        # Check marks link to valid assessments and enrollments
        assessment_ids = {a.assessment_id for a in session.query(Assessment).all()}
        enrollment_ids = {e.enrollment_id for e in session.query(Enrollment).all()}
        for m in session.query(StudentMark).all():
            assert m.assessment_id in assessment_ids
            assert m.enrollment_id in enrollment_ids
    finally:
        session.close()


def test_seeding_determinism_and_reproducibility(tmp_path: Path):
    """Verify that seeding two distinct databases produces identical records (seed=42)."""
    db1_path = tmp_path / "db1.db"
    db2_path = tmp_path / "db2.db"

    engine1 = create_temp_db_engine(db1_path)
    engine2 = create_temp_db_engine(db2_path)

    seed_database(engine=engine1, reset=True)
    seed_database(engine=engine2, reset=True)

    session1 = sessionmaker(bind=engine1)()
    session2 = sessionmaker(bind=engine2)()

    try:
        # Compare students: roll numbers, names, and CGPAs must be 100% identical
        students1 = session1.query(Student).order_by(Student.student_id).all()
        students2 = session2.query(Student).order_by(Student.student_id).all()

        assert len(students1) == len(students2)
        for s1, s2 in zip(students1, students2):
            assert s1.roll_number == s2.roll_number
            assert s1.first_name == s2.first_name
            assert s1.last_name == s2.last_name
            assert s1.cgpa == s2.cgpa
            assert s1.academic_status == s2.academic_status

        # Compare student marks
        marks1 = session1.query(StudentMark).order_by(StudentMark.mark_id).all()
        marks2 = session2.query(StudentMark).order_by(StudentMark.mark_id).all()

        assert len(marks1) == len(marks2)
        for m1, m2 in zip(marks1, marks2):
            assert m1.marks_obtained == m2.marks_obtained
            assert m1.assessment_id == m2.assessment_id
            assert m1.enrollment_id == m2.enrollment_id

    finally:
        session1.close()
        session2.close()


def test_seeding_idempotency(tmp_path: Path):
    """Verify that running seed_database without reset on an existing database is idempotent."""
    test_db = tmp_path / "seed_idempotent.db"
    test_engine = create_temp_db_engine(test_db)

    # First run
    counts1 = seed_database(engine=test_engine, reset=True)
    # Second run without reset
    counts2 = seed_database(engine=test_engine, reset=False)

    assert counts1 == counts2

    session = sessionmaker(bind=test_engine)()
    try:
        # Verify no duplicate students or departments were added
        assert session.query(Student).count() == 120
        assert session.query(Department).count() == 5
    finally:
        session.close()


def test_seeding_transaction_rollback_on_failure(tmp_path: Path):
    """Verify that database transaction safely rolls back on an unhandled exception."""
    test_db = tmp_path / "seed_rollback.db"
    test_engine = create_temp_db_engine(test_db)

    Base.metadata.create_all(bind=test_engine)
    session_factory = sessionmaker(bind=test_engine)
    session = session_factory()

    try:
        # Insert a valid department
        dept = Department(name="Initial Dept", code="INIT", established_year=2020, building="Alpha")
        session.add(dept)
        session.flush()

        # Attempt to insert an invalid record that violates NOT NULL
        broken_student = Student(
            department_id=dept.department_id,
            roll_number=None,  # NOT NULL violation
            first_name="Broken",
            last_name="Record",
            enrollment_year=2024,
            current_semester=1,
            cgpa=3.0,
            academic_status="Active",
        )
        session.add(broken_student)
        with pytest.raises(Exception):
            session.commit()
        session.rollback()

        # After rollback, verify database is clean of partial transaction
        clean_count = session.query(Department).filter_by(code="INIT").count()
        assert clean_count == 0

    finally:
        session.close()

