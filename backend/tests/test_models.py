"""Unit tests for Academic SQLAlchemy Relational ORM Models and Constraints."""

from datetime import date
import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, Session

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


@pytest.fixture
def db_session() -> Session:
    """Fixture providing an isolated in-memory SQLite database session with Foreign Keys enabled."""
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_create_department_and_primary_key(db_session: Session):
    """Verify Department creation and autoincrement primary key."""
    dept = Department(
        name="Artificial Intelligence",
        code="AI",
        established_year=2021,
        building="Turing Complex",
    )
    db_session.add(dept)
    db_session.commit()

    assert dept.department_id is not None
    assert dept.code == "AI"
    assert dept.name == "Artificial Intelligence"


def test_duplicate_department_code_fails(db_session: Session):
    """Verify unique constraint on department code."""
    dept1 = Department(name="Computer Science", code="CS", established_year=2005, building="Hall A")
    db_session.add(dept1)
    db_session.commit()

    dept2 = Department(name="Cyber Security", code="CS", established_year=2020, building="Hall B")
    db_session.add(dept2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_foreign_key_enforcement_student(db_session: Session):
    """Verify that adding a student with non-existent department_id raises IntegrityError."""
    student = Student(
        department_id=9999,  # Non-existent department
        roll_number="2024-AI-001",
        first_name="Jane",
        last_name="Doe",
        enrollment_year=2024,
        current_semester=1,
        cgpa=3.5,
        academic_status="Active",
    )
    db_session.add(student)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_duplicate_student_roll_number_fails(db_session: Session):
    """Verify unique constraint on student roll_number."""
    dept = Department(name="Data Science", code="DS", established_year=2020, building="Ada Lab")
    db_session.add(dept)
    db_session.commit()

    s1 = Student(
        department_id=dept.department_id,
        roll_number="2024-DS-001",
        first_name="Alice",
        last_name="Smith",
        enrollment_year=2024,
        current_semester=2,
        cgpa=3.8,
        academic_status="Active",
    )
    db_session.add(s1)
    db_session.commit()

    s2 = Student(
        department_id=dept.department_id,
        roll_number="2024-DS-001",  # Duplicate roll number
        first_name="Bob",
        last_name="Jones",
        enrollment_year=2024,
        current_semester=1,
        cgpa=3.2,
        academic_status="Active",
    )
    db_session.add(s2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_student_cgpa_check_constraint(db_session: Session):
    """Verify CHECK constraint on student CGPA (must be between 0.00 and 4.00)."""
    dept = Department(name="Mathematics", code="MATH", established_year=1995, building="Euler Tower")
    db_session.add(dept)
    db_session.commit()

    invalid_student = Student(
        department_id=dept.department_id,
        roll_number="2024-MATH-099",
        first_name="Charlie",
        last_name="Brown",
        enrollment_year=2024,
        current_semester=1,
        cgpa=4.5,  # Invalid: > 4.00
        academic_status="Active",
    )
    db_session.add(invalid_student)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_student_academic_status_check_constraint(db_session: Session):
    """Verify CHECK constraint on student academic status."""
    dept = Department(name="Physics", code="PHYS", established_year=1990, building="Newton Hall")
    db_session.add(dept)
    db_session.commit()

    invalid_student = Student(
        department_id=dept.department_id,
        roll_number="2024-PHYS-001",
        first_name="David",
        last_name="Miller",
        enrollment_year=2024,
        current_semester=1,
        cgpa=3.0,
        academic_status="Expelled",  # Invalid status
    )
    db_session.add(invalid_student)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_course_offering_unique_constraint(db_session: Session):
    """Verify that a course cannot have duplicate sections in the same term."""
    dept = Department(name="Computer Science", code="CS", established_year=2000, building="Turing Hall")
    db_session.add(dept)
    db_session.commit()

    inst = Instructor(
        department_id=dept.department_id,
        first_name="Alan",
        last_name="Turing",
        designation="Professor",
        joining_year=2012,
    )
    course = Course(
        department_id=dept.department_id,
        course_code="CS101",
        course_name="Programming 101",
        credits=3,
        course_level=100,
    )
    term = Term(
        term_name="Fall 2024",
        academic_year=2024,
        semester_type="Fall",
        start_date=date(2024, 9, 1),
        end_date=date(2024, 12, 20),
    )
    db_session.add_all([inst, course, term])
    db_session.commit()

    off1 = CourseOffering(
        course_id=course.course_id,
        instructor_id=inst.instructor_id,
        term_id=term.term_id,
        section="A",
        classroom="Room 101",
    )
    db_session.add(off1)
    db_session.commit()

    off2 = CourseOffering(
        course_id=course.course_id,
        instructor_id=inst.instructor_id,
        term_id=term.term_id,
        section="A",  # Duplicate section in same term
        classroom="Room 102",
    )
    db_session.add(off2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_enrollment_unique_constraint(db_session: Session):
    """Verify that a student cannot enroll twice in the exact same course offering."""
    dept = Department(name="Electrical Engineering", code="EE", established_year=2002, building="Tesla Lab")
    db_session.add(dept)
    db_session.commit()

    inst = Instructor(department_id=dept.department_id, first_name="Nikola", last_name="Tesla", designation="Professor", joining_year=2015)
    course = Course(department_id=dept.department_id, course_code="EE101", course_name="Circuits", credits=4, course_level=100)
    term = Term(term_name="Spring 2024", academic_year=2024, semester_type="Spring", start_date=date(2024, 1, 15), end_date=date(2024, 5, 20))
    student = Student(department_id=dept.department_id, roll_number="2024-EE-001", first_name="Grace", last_name="Hopper", enrollment_year=2024, current_semester=1, cgpa=3.9, academic_status="Active")
    db_session.add_all([inst, course, term, student])
    db_session.commit()

    off = CourseOffering(course_id=course.course_id, instructor_id=inst.instructor_id, term_id=term.term_id, section="A", classroom="Lab 1")
    db_session.add(off)
    db_session.commit()

    enr1 = Enrollment(student_id=student.student_id, offering_id=off.offering_id, attendance_percentage=92.0, final_grade="A", grade_points=4.0, enrollment_status="Completed")
    db_session.add(enr1)
    db_session.commit()

    enr2 = Enrollment(student_id=student.student_id, offering_id=off.offering_id, attendance_percentage=85.0, final_grade="B", grade_points=3.0, enrollment_status="Completed")
    db_session.add(enr2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_assessment_mark_relationship_and_constraints(db_session: Session):
    """Verify Assessment and StudentMark creation, relationships, and unique constraint."""
    dept = Department(name="AI", code="AI", established_year=2020, building="Turing Complex")
    db_session.add(dept)
    db_session.commit()

    inst = Instructor(department_id=dept.department_id, first_name="Geoffrey", last_name="Hinton", designation="Professor", joining_year=2011)
    course = Course(department_id=dept.department_id, course_code="AI101", course_name="Intro to AI", credits=3, course_level=100)
    term = Term(term_name="Fall 2024", academic_year=2024, semester_type="Fall", start_date=date(2024, 9, 1), end_date=date(2024, 12, 20))
    student = Student(department_id=dept.department_id, roll_number="2024-AI-010", first_name="Yann", last_name="LeCun", enrollment_year=2024, current_semester=1, cgpa=3.95, academic_status="Active")
    db_session.add_all([inst, course, term, student])
    db_session.commit()

    off = CourseOffering(course_id=course.course_id, instructor_id=inst.instructor_id, term_id=term.term_id, section="A", classroom="Hall A")
    db_session.add(off)
    db_session.commit()

    enr = Enrollment(student_id=student.student_id, offering_id=off.offering_id, attendance_percentage=95.0, final_grade="A", grade_points=4.0, enrollment_status="Completed")
    assess = Assessment(offering_id=off.offering_id, title="Midterm", assessment_type="Midterm", max_marks=100.0, weightage_percent=30.0)
    db_session.add_all([enr, assess])
    db_session.commit()

    mark = StudentMark(assessment_id=assess.assessment_id, enrollment_id=enr.enrollment_id, marks_obtained=92.5)
    db_session.add(mark)
    db_session.commit()

    assert mark.mark_id is not None
    assert mark.marks_obtained == 92.5
    assert mark.assessment.title == "Midterm"
    assert mark.enrollment.student.first_name == "Yann"

    # Duplicate mark for the same student and assessment must fail
    dup_mark = StudentMark(assessment_id=assess.assessment_id, enrollment_id=enr.enrollment_id, marks_obtained=88.0)
    db_session.add(dup_mark)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_cascade_delete_department(db_session: Session):
    """Verify that deleting a Department cascades to delete associated students and courses."""
    dept = Department(name="Robotics", code="ROBO", established_year=2022, building="Bot Lab")
    db_session.add(dept)
    db_session.commit()

    student = Student(department_id=dept.department_id, roll_number="2024-ROBO-001", first_name="Rob", last_name="Ott", enrollment_year=2024, current_semester=1, cgpa=3.4, academic_status="Active")
    course = Course(department_id=dept.department_id, course_code="ROBO101", course_name="Kinematics", credits=3, course_level=100)
    db_session.add_all([student, course])
    db_session.commit()

    dept_id = dept.department_id
    db_session.delete(dept)
    db_session.commit()

    assert db_session.query(Student).filter_by(department_id=dept_id).count() == 0
    assert db_session.query(Course).filter_by(department_id=dept_id).count() == 0


def test_cross_offering_student_mark_rejected(db_session: Session):
    """Verify database trigger rejects marks when assessment and enrollment belong to different offerings."""
    dept = Department(name="Information Technology", code="IT", established_year=2010, building="Tech Centre")
    db_session.add(dept)
    db_session.commit()

    inst = Instructor(department_id=dept.department_id, first_name="Barbara", last_name="Liskov", designation="Professor", joining_year=2012)
    c1 = Course(department_id=dept.department_id, course_code="IT101", course_name="Web Tech", credits=3, course_level=100)
    c2 = Course(department_id=dept.department_id, course_code="IT201", course_name="Cloud Tech", credits=3, course_level=200)
    term = Term(term_name="Fall 2024", academic_year=2024, semester_type="Fall", start_date=date(2024, 9, 1), end_date=date(2024, 12, 20))
    student = Student(department_id=dept.department_id, roll_number="2024-IT-001", first_name="Ken", last_name="Thompson", enrollment_year=2024, current_semester=1, cgpa=3.7, academic_status="Active")
    db_session.add_all([inst, c1, c2, term, student])
    db_session.commit()

    # Offering 1 for c1, Offering 2 for c2
    off1 = CourseOffering(course_id=c1.course_id, instructor_id=inst.instructor_id, term_id=term.term_id, section="A", classroom="Lab 1")
    off2 = CourseOffering(course_id=c2.course_id, instructor_id=inst.instructor_id, term_id=term.term_id, section="A", classroom="Lab 2")
    db_session.add_all([off1, off2])
    db_session.commit()

    # Assessment belongs to Offering 1
    assess_off1 = Assessment(offering_id=off1.offering_id, title="Quiz 1", assessment_type="Quiz", max_marks=20.0, weightage_percent=10.0)
    # Enrollment belongs to Offering 2
    enr_off2 = Enrollment(student_id=student.student_id, offering_id=off2.offering_id, attendance_percentage=88.0, final_grade="B", grade_points=3.0, enrollment_status="Completed")
    db_session.add_all([assess_off1, enr_off2])
    db_session.commit()

    # Attempting to assign mark for Offering 1's assessment to Offering 2's enrollment MUST fail
    cross_mark = StudentMark(assessment_id=assess_off1.assessment_id, enrollment_id=enr_off2.enrollment_id, marks_obtained=18.0)
    db_session.add(cross_mark)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.commit()
    db_session.rollback()

    assert "Cross-offering integrity violation" in str(exc_info.value)


def test_marks_obtained_cannot_exceed_max_marks(db_session: Session):
    """Verify database trigger rejects marks obtained greater than assessment max_marks."""
    dept = Department(name="Cybernetics", code="CYB", established_year=2015, building="Wiener Lab")
    db_session.add(dept)
    db_session.commit()

    inst = Instructor(department_id=dept.department_id, first_name="Norbert", last_name="Wiener", designation="Professor", joining_year=2016)
    course = Course(department_id=dept.department_id, course_code="CYB101", course_name="Feedback Systems", credits=3, course_level=100)
    term = Term(term_name="Spring 2024", academic_year=2024, semester_type="Spring", start_date=date(2024, 1, 15), end_date=date(2024, 5, 20))
    student = Student(department_id=dept.department_id, roll_number="2024-CYB-001", first_name="Claude", last_name="Shannon", enrollment_year=2024, current_semester=1, cgpa=3.9, academic_status="Active")
    db_session.add_all([inst, course, term, student])
    db_session.commit()

    off = CourseOffering(course_id=course.course_id, instructor_id=inst.instructor_id, term_id=term.term_id, section="A", classroom="Hall C")
    db_session.add(off)
    db_session.commit()

    assess = Assessment(offering_id=off.offering_id, title="Midterm", assessment_type="Midterm", max_marks=50.0, weightage_percent=30.0)
    enr = Enrollment(student_id=student.student_id, offering_id=off.offering_id, attendance_percentage=90.0, final_grade="A", grade_points=4.0, enrollment_status="Completed")
    db_session.add_all([assess, enr])
    db_session.commit()

    # Valid mark <= 50.0 succeeds
    valid_mark = StudentMark(assessment_id=assess.assessment_id, enrollment_id=enr.enrollment_id, marks_obtained=48.5)
    db_session.add(valid_mark)
    db_session.commit()
    assert valid_mark.mark_id is not None

    # Invalid mark 55.0 > 50.0 max_marks MUST fail
    invalid_mark = StudentMark(assessment_id=assess.assessment_id, enrollment_id=enr.enrollment_id, marks_obtained=55.0)
    db_session.add(invalid_mark)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.commit()
    db_session.rollback()

    assert "Marks boundary violation" in str(exc_info.value)


def test_marks_obtained_negative_rejected(db_session: Session):
    """Verify CHECK constraint rejects negative marks obtained."""
    dept = Department(name="Bioinformatics", code="BIO", established_year=2018, building="Franklin Lab")
    db_session.add(dept)
    db_session.commit()

    inst = Instructor(department_id=dept.department_id, first_name="Rosalind", last_name="Franklin", designation="Professor", joining_year=2019)
    course = Course(department_id=dept.department_id, course_code="BIO101", course_name="Genomics", credits=3, course_level=100)
    term = Term(term_name="Fall 2024", academic_year=2024, semester_type="Fall", start_date=date(2024, 9, 1), end_date=date(2024, 12, 20))
    student = Student(department_id=dept.department_id, roll_number="2024-BIO-001", first_name="Francis", last_name="Crick", enrollment_year=2024, current_semester=1, cgpa=3.6, academic_status="Active")
    db_session.add_all([inst, course, term, student])
    db_session.commit()

    off = CourseOffering(course_id=course.course_id, instructor_id=inst.instructor_id, term_id=term.term_id, section="A", classroom="Bio 1")
    db_session.add(off)
    db_session.commit()

    assess = Assessment(offering_id=off.offering_id, title="Quiz", assessment_type="Quiz", max_marks=20.0, weightage_percent=10.0)
    enr = Enrollment(student_id=student.student_id, offering_id=off.offering_id, attendance_percentage=85.0, final_grade="B", grade_points=3.0, enrollment_status="Completed")
    db_session.add_all([assess, enr])
    db_session.commit()

    negative_mark = StudentMark(assessment_id=assess.assessment_id, enrollment_id=enr.enrollment_id, marks_obtained=-5.0)
    db_session.add(negative_mark)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_assessment_cumulative_weightage_exceeds_100_rejected(db_session: Session):
    """Verify database trigger rejects cumulative assessment weightage exceeding 100 percent."""
    dept = Department(name="Statistics", code="STAT", established_year=2008, building="Gauss Hall")
    db_session.add(dept)
    db_session.commit()

    inst = Instructor(department_id=dept.department_id, first_name="Carl", last_name="Gauss", designation="Professor", joining_year=2009)
    course = Course(department_id=dept.department_id, course_code="STAT101", course_name="Probability", credits=3, course_level=100)
    term = Term(term_name="Spring 2024", academic_year=2024, semester_type="Spring", start_date=date(2024, 1, 15), end_date=date(2024, 5, 20))
    db_session.add_all([inst, course, term])
    db_session.commit()

    off = CourseOffering(course_id=course.course_id, instructor_id=inst.instructor_id, term_id=term.term_id, section="A", classroom="Hall G")
    db_session.add(off)
    db_session.commit()

    # 1. First two assessments total 90% (50% + 40%) -> valid
    a1 = Assessment(offering_id=off.offering_id, title="Final Exam", assessment_type="Final", max_marks=100.0, weightage_percent=50.0)
    a2 = Assessment(offering_id=off.offering_id, title="Midterm", assessment_type="Midterm", max_marks=100.0, weightage_percent=40.0)
    db_session.add_all([a1, a2])
    db_session.commit()

    # 2. Third assessment of 20% would bring total to 110% (>100%) -> MUST fail
    a3_invalid = Assessment(offering_id=off.offering_id, title="Quiz Overweight", assessment_type="Quiz", max_marks=20.0, weightage_percent=20.0)
    db_session.add(a3_invalid)
    with pytest.raises(IntegrityError) as exc_info:
        db_session.commit()
    db_session.rollback()
    assert "Assessment weightage violation" in str(exc_info.value)

    # 3. Third assessment of 10% brings total to exactly 100% -> MUST succeed
    a3_valid = Assessment(offering_id=off.offering_id, title="Quiz Exact", assessment_type="Quiz", max_marks=20.0, weightage_percent=10.0)
    db_session.add(a3_valid)
    db_session.commit()
    assert a3_valid.assessment_id is not None


def test_assessment_weightage_update_trigger_behavior(db_session: Session):
    """Verify trg_assessments_weightage_update correctly excludes the updated row and enforces 100 percent cap."""
    dept = Department(name="Economics", code="ECON", established_year=2000, building="Smith Hall")
    db_session.add(dept)
    db_session.commit()

    inst = Instructor(department_id=dept.department_id, first_name="Adam", last_name="Smith", designation="Professor", joining_year=2005)
    course = Course(department_id=dept.department_id, course_code="ECON101", course_name="Microeconomics", credits=3, course_level=100)
    term = Term(term_name="Fall 2024", academic_year=2024, semester_type="Fall", start_date=date(2024, 9, 1), end_date=date(2024, 12, 20))
    db_session.add_all([inst, course, term])
    db_session.commit()

    off = CourseOffering(course_id=course.course_id, instructor_id=inst.instructor_id, term_id=term.term_id, section="A", classroom="Room 101")
    db_session.add(off)
    db_session.commit()

    # Create 3 assessments totaling exactly 100% (30% + 50% + 20%)
    a1 = Assessment(offering_id=off.offering_id, title="Midterm", assessment_type="Midterm", max_marks=100.0, weightage_percent=30.0)
    a2 = Assessment(offering_id=off.offering_id, title="Final", assessment_type="Final", max_marks=100.0, weightage_percent=50.0)
    a3 = Assessment(offering_id=off.offering_id, title="Project", assessment_type="Assignment", max_marks=100.0, weightage_percent=20.0)
    db_session.add_all([a1, a2, a3])
    db_session.commit()

    # 1. Update when already at 100%: increasing a1 weightage from 30% to 35% (total 105%) MUST fail
    a1.weightage_percent = 35.0
    with pytest.raises(IntegrityError) as exc_info:
        db_session.commit()
    db_session.rollback()
    assert "Assessment weightage violation" in str(exc_info.value)

    # 2. Valid update: decreasing a1 weightage from 30% to 25% (total 95%) MUST succeed
    a1 = db_session.query(Assessment).filter_by(title="Midterm").first()
    a1.weightage_percent = 25.0
    db_session.commit()
    assert a1.weightage_percent == 25.0

    # 3. Valid update restoring to 30% (total 25 -> 30, sum reaches exactly 100%) MUST succeed
    a1.weightage_percent = 30.0
    db_session.commit()
    assert a1.weightage_percent == 30.0


def test_assessment_weightage_move_offering(db_session: Session):
    """Verify moving an assessment to another offering enforces cumulative weightage cap on destination offering."""
    dept = Department(name="Philosophy", code="PHIL", established_year=1998, building="Kant Hall")
    db_session.add(dept)
    db_session.commit()

    inst = Instructor(department_id=dept.department_id, first_name="Immanuel", last_name="Kant", designation="Professor", joining_year=2000)
    course = Course(department_id=dept.department_id, course_code="PHIL101", course_name="Ethics", credits=3, course_level=100)
    term = Term(term_name="Fall 2024", academic_year=2024, semester_type="Fall", start_date=date(2024, 9, 1), end_date=date(2024, 12, 20))
    db_session.add_all([inst, course, term])
    db_session.commit()

    off1 = CourseOffering(course_id=course.course_id, instructor_id=inst.instructor_id, term_id=term.term_id, section="A", classroom="Room 1")
    off2 = CourseOffering(course_id=course.course_id, instructor_id=inst.instructor_id, term_id=term.term_id, section="B", classroom="Room 2")
    db_session.add_all([off1, off2])
    db_session.commit()

    # Destination Offering 2 already has 85% allocated
    db_session.add(Assessment(offering_id=off2.offering_id, title="Final B", assessment_type="Final", max_marks=100.0, weightage_percent=85.0))
    # Source Offering 1 has a 25% assessment
    a_move = Assessment(offering_id=off1.offering_id, title="Midterm A", assessment_type="Midterm", max_marks=100.0, weightage_percent=25.0)
    db_session.add(a_move)
    db_session.commit()

    # Moving a_move (25%) to off2 (which already has 85%) would total 110% (>100%) -> MUST fail
    a_move.offering_id = off2.offering_id
    with pytest.raises(IntegrityError) as exc_info:
        db_session.commit()
    db_session.rollback()
    assert "Assessment weightage violation" in str(exc_info.value)

    # If we reduce its weightage to 15% (85% + 15% = 100%), moving MUST succeed
    a_move = db_session.query(Assessment).filter_by(title="Midterm A").first()
    a_move.weightage_percent = 15.0
    a_move.offering_id = off2.offering_id
    db_session.commit()
    assert a_move.offering_id == off2.offering_id


def test_assessment_max_marks_update_boundary(db_session: Session):
    """Verify trigger prevents reducing max_marks below existing student marks."""
    dept = Department(name="Chemistry", code="CHEM", established_year=2001, building="Curie Labs")
    db_session.add(dept)
    db_session.commit()

    inst = Instructor(department_id=dept.department_id, first_name="Marie", last_name="Curie", designation="Professor", joining_year=2002)
    course = Course(department_id=dept.department_id, course_code="CHEM101", course_name="General Chemistry", credits=4, course_level=100)
    term = Term(term_name="Spring 2024", academic_year=2024, semester_type="Spring", start_date=date(2024, 1, 15), end_date=date(2024, 5, 20))
    student = Student(department_id=dept.department_id, roll_number="2024-CHEM-001", first_name="Dmitri", last_name="Mendeleev", enrollment_year=2024, current_semester=1, cgpa=3.85, academic_status="Active")
    db_session.add_all([inst, course, term, student])
    db_session.commit()

    off = CourseOffering(course_id=course.course_id, instructor_id=inst.instructor_id, term_id=term.term_id, section="A", classroom="Lab 10")
    db_session.add(off)
    db_session.commit()

    assess = Assessment(offering_id=off.offering_id, title="Final Exam", assessment_type="Final", max_marks=100.0, weightage_percent=50.0)
    enr = Enrollment(student_id=student.student_id, offering_id=off.offering_id, attendance_percentage=94.0, final_grade="A", grade_points=4.0, enrollment_status="Completed")
    db_session.add_all([assess, enr])
    db_session.commit()

    mark = StudentMark(assessment_id=assess.assessment_id, enrollment_id=enr.enrollment_id, marks_obtained=85.0)
    db_session.add(mark)
    db_session.commit()

    # Reducing max_marks to 80.0 when student has 85.0 MUST fail
    assess.max_marks = 80.0
    with pytest.raises(IntegrityError) as exc_info:
        db_session.commit()
    db_session.rollback()
    assert "Marks boundary violation" in str(exc_info.value)

    # Reducing max_marks to 90.0 (which is >= 85.0) MUST succeed
    assess = db_session.query(Assessment).filter_by(title="Final Exam").first()
    assess.max_marks = 90.0
    db_session.commit()
    assert assess.max_marks == 90.0


def test_parent_offering_update_integrity_rejection(db_session: Session):
    """Verify trigger prevents updating offering_id on assessment or enrollment when student marks exist."""
    dept = Department(name="Astronomy", code="ASTR", established_year=2012, building="Hubble Tower")
    db_session.add(dept)
    db_session.commit()

    inst = Instructor(department_id=dept.department_id, first_name="Edwin", last_name="Hubble", designation="Professor", joining_year=2014)
    c1 = Course(department_id=dept.department_id, course_code="ASTR101", course_name="Solar Systems", credits=3, course_level=100)
    c2 = Course(department_id=dept.department_id, course_code="ASTR201", course_name="Astrophysics", credits=4, course_level=200)
    term = Term(term_name="Fall 2024", academic_year=2024, semester_type="Fall", start_date=date(2024, 9, 1), end_date=date(2024, 12, 20))
    student = Student(department_id=dept.department_id, roll_number="2024-ASTR-001", first_name="Carl", last_name="Sagan", enrollment_year=2024, current_semester=1, cgpa=3.95, academic_status="Active")
    db_session.add_all([inst, c1, c2, term, student])
    db_session.commit()

    off1 = CourseOffering(course_id=c1.course_id, instructor_id=inst.instructor_id, term_id=term.term_id, section="A", classroom="Dome 1")
    off2 = CourseOffering(course_id=c2.course_id, instructor_id=inst.instructor_id, term_id=term.term_id, section="A", classroom="Dome 2")
    db_session.add_all([off1, off2])
    db_session.commit()

    assess1 = Assessment(offering_id=off1.offering_id, title="Midterm Obs", assessment_type="Midterm", max_marks=50.0, weightage_percent=30.0)
    enr1 = Enrollment(student_id=student.student_id, offering_id=off1.offering_id, attendance_percentage=98.0, final_grade="A", grade_points=4.0, enrollment_status="Completed")
    db_session.add_all([assess1, enr1])
    db_session.commit()

    mark = StudentMark(assessment_id=assess1.assessment_id, enrollment_id=enr1.enrollment_id, marks_obtained=47.0)
    db_session.add(mark)
    db_session.commit()

    # 1. Attempting to change assess1's offering_id to off2 when marks exist MUST fail
    assess1.offering_id = off2.offering_id
    with pytest.raises(IntegrityError) as exc_info:
        db_session.commit()
    db_session.rollback()
    assert "Cross-offering integrity violation" in str(exc_info.value)

    # 2. Attempting to change enr1's offering_id to off2 when marks exist MUST fail
    enr1 = db_session.query(Enrollment).filter_by(student_id=student.student_id).first()
    enr1.offering_id = off2.offering_id
    with pytest.raises(IntegrityError) as exc_info:
        db_session.commit()
    db_session.rollback()
    assert "Cross-offering integrity violation" in str(exc_info.value)

    # 3. An assessment in off1 with NO marks can be moved to off2 (as long as weightage cap is respected)
    assess_empty = Assessment(offering_id=off1.offering_id, title="Empty Quiz", assessment_type="Quiz", max_marks=20.0, weightage_percent=10.0)
    db_session.add(assess_empty)
    db_session.commit()

    assess_empty.offering_id = off2.offering_id
    db_session.commit()
    assert assess_empty.offering_id == off2.offering_id



