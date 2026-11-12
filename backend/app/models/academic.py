"""SQLAlchemy 2.x Declarative Relational Models for Academic Institution Database.

Includes 9 normalized academic entities:
1. Department
2. Student
3. Instructor
4. Course
5. Term
6. CourseOffering
7. Enrollment
8. Assessment
9. StudentMark

Strictly implements the domain schema, constraints, indexes, and relationships
defined in the approved querymind_blueprint.md.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class Department(Base):
    """Academic Department entity managing academic divisions."""

    __tablename__ = "departments"
    __table_args__ = (
        CheckConstraint(
            "established_year >= 1800 AND established_year <= 2026",
            name="chk_dept_established_year",
        ),
    )

    department_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    code = Column(String(10), unique=True, nullable=False, index=True)
    established_year = Column(Integer, nullable=False)
    building = Column(String(50), nullable=False)

    # Relationships
    students = relationship("Student", back_populates="department", cascade="all, delete-orphan")
    instructors = relationship("Instructor", back_populates="department", cascade="all, delete-orphan")
    courses = relationship("Course", back_populates="department", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Department(code='{self.code}', name='{self.name}')>"


class Student(Base):
    """Student profile, enrollment standing, and cumulative academic performance."""

    __tablename__ = "students"
    __table_args__ = (
        CheckConstraint(
            "current_semester >= 1 AND current_semester <= 12",
            name="chk_student_current_semester",
        ),
        CheckConstraint(
            "cgpa >= 0.00 AND cgpa <= 4.00",
            name="chk_student_cgpa_range",
        ),
        CheckConstraint(
            "academic_status IN ('Active', 'Probation', 'Graduated', 'Suspended')",
            name="chk_student_academic_status",
        ),
    )

    student_id = Column(Integer, primary_key=True, autoincrement=True)
    department_id = Column(
        Integer,
        ForeignKey("departments.department_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    roll_number = Column(String(20), unique=True, nullable=False, index=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    enrollment_year = Column(Integer, nullable=False, index=True)
    current_semester = Column(Integer, nullable=False)
    cgpa = Column(Float, nullable=False, index=True)
    academic_status = Column(String(20), nullable=False, default="Active")

    # Relationships
    department = relationship("Department", back_populates="students")
    enrollments = relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Student(roll='{self.roll_number}', name='{self.first_name} {self.last_name}', cgpa={self.cgpa})>"


class Instructor(Base):
    """Faculty teaching staff associated with a department."""

    __tablename__ = "instructors"
    __table_args__ = (
        CheckConstraint(
            "designation IN ('Professor', 'Associate Professor', 'Assistant Professor', 'Senior Lecturer', 'Lecturer')",
            name="chk_instructor_designation",
        ),
        CheckConstraint(
            "joining_year >= 1950 AND joining_year <= 2026",
            name="chk_instructor_joining_year",
        ),
    )

    instructor_id = Column(Integer, primary_key=True, autoincrement=True)
    department_id = Column(
        Integer,
        ForeignKey("departments.department_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    designation = Column(String(50), nullable=False)
    joining_year = Column(Integer, nullable=False)

    # Relationships
    department = relationship("Department", back_populates="instructors")
    offerings = relationship("CourseOffering", back_populates="instructor", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Instructor(name='{self.first_name} {self.last_name}', designation='{self.designation}')>"


class Course(Base):
    """Curriculum course catalogue offered by departments."""

    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint(
            "credits >= 1 AND credits <= 6",
            name="chk_course_credits",
        ),
        CheckConstraint(
            "course_level IN (100, 200, 300, 400, 500)",
            name="chk_course_level",
        ),
    )

    course_id = Column(Integer, primary_key=True, autoincrement=True)
    department_id = Column(
        Integer,
        ForeignKey("departments.department_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_code = Column(String(20), unique=True, nullable=False, index=True)
    course_name = Column(String(100), nullable=False, index=True)
    credits = Column(Integer, nullable=False)
    course_level = Column(Integer, nullable=False)

    # Relationships
    department = relationship("Department", back_populates="courses")
    offerings = relationship("CourseOffering", back_populates="course", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Course(code='{self.course_code}', name='{self.course_name}')>"


class Term(Base):
    """Academic semester/session calendar window."""

    __tablename__ = "terms"
    __table_args__ = (
        CheckConstraint(
            "semester_type IN ('Fall', 'Spring', 'Summer')",
            name="chk_term_semester_type",
        ),
        CheckConstraint(
            "start_date < end_date",
            name="chk_term_date_sequence",
        ),
    )

    term_id = Column(Integer, primary_key=True, autoincrement=True)
    term_name = Column(String(50), unique=True, nullable=False, index=True)
    academic_year = Column(Integer, nullable=False, index=True)
    semester_type = Column(String(20), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    # Relationships
    offerings = relationship("CourseOffering", back_populates="term", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Term(name='{self.term_name}', year={self.academic_year})>"


class CourseOffering(Base):
    """Scheduled instance of a course taught by an instructor in a specific term."""

    __tablename__ = "course_offerings"
    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "term_id",
            "section",
            name="uq_course_term_section",
        ),
    )

    offering_id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(
        Integer,
        ForeignKey("courses.course_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    instructor_id = Column(
        Integer,
        ForeignKey("instructors.instructor_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    term_id = Column(
        Integer,
        ForeignKey("terms.term_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section = Column(String(10), nullable=False)
    classroom = Column(String(50), nullable=False)

    # Relationships
    course = relationship("Course", back_populates="offerings")
    instructor = relationship("Instructor", back_populates="offerings")
    term = relationship("Term", back_populates="offerings")
    enrollments = relationship("Enrollment", back_populates="offering", cascade="all, delete-orphan")
    assessments = relationship("Assessment", back_populates="offering", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<CourseOffering(id={self.offering_id}, section='{self.section}')>"


class Enrollment(Base):
    """Student registration in a course offering with attendance and grade outcomes."""

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "offering_id",
            name="uq_student_offering",
        ),
        CheckConstraint(
            "attendance_percentage >= 0.0 AND attendance_percentage <= 100.0",
            name="chk_enrollment_attendance",
        ),
        CheckConstraint(
            "grade_points IS NULL OR (grade_points >= 0.0 AND grade_points <= 4.0)",
            name="chk_enrollment_grade_points",
        ),
        CheckConstraint(
            "enrollment_status IN ('Enrolled', 'Completed', 'Dropped')",
            name="chk_enrollment_status",
        ),
    )

    enrollment_id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(
        Integer,
        ForeignKey("students.student_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    offering_id = Column(
        Integer,
        ForeignKey("course_offerings.offering_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attendance_percentage = Column(Float, nullable=False, index=True)
    final_grade = Column(String(5), nullable=True)
    grade_points = Column(Float, nullable=True)
    enrollment_status = Column(String(20), nullable=False, default="Completed")

    # Relationships
    student = relationship("Student", back_populates="enrollments")
    offering = relationship("CourseOffering", back_populates="enrollments")
    marks = relationship("StudentMark", back_populates="enrollment", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Enrollment(student_id={self.student_id}, offering_id={self.offering_id}, grade='{self.final_grade}')>"


class Assessment(Base):
    """Assessment component (Quiz, Midterm, Final, Project) for a course offering."""

    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint(
            "max_marks > 0.0",
            name="chk_assessment_max_marks",
        ),
        CheckConstraint(
            "weightage_percent >= 0.0 AND weightage_percent <= 100.0",
            name="chk_assessment_weightage",
        ),
        CheckConstraint(
            "assessment_type IN ('Quiz', 'Assignment', 'Midterm', 'Final', 'Project')",
            name="chk_assessment_type",
        ),
    )

    assessment_id = Column(Integer, primary_key=True, autoincrement=True)
    offering_id = Column(
        Integer,
        ForeignKey("course_offerings.offering_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(100), nullable=False)
    assessment_type = Column(String(30), nullable=False)
    max_marks = Column(Float, nullable=False)
    weightage_percent = Column(Float, nullable=False)

    # Relationships
    offering = relationship("CourseOffering", back_populates="assessments")
    student_marks = relationship("StudentMark", back_populates="assessment", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Assessment(title='{self.title}', type='{self.assessment_type}', max={self.max_marks})>"


class StudentMark(Base):
    """Numerical score obtained by an enrolled student for a specific assessment."""

    __tablename__ = "student_marks"
    __table_args__ = (
        UniqueConstraint(
            "assessment_id",
            "enrollment_id",
            name="uq_assessment_enrollment",
        ),
        CheckConstraint(
            "marks_obtained >= 0.0",
            name="chk_marks_obtained_positive",
        ),
    )

    mark_id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(
        Integer,
        ForeignKey("assessments.assessment_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enrollment_id = Column(
        Integer,
        ForeignKey("enrollments.enrollment_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    marks_obtained = Column(Float, nullable=False, index=True)

    # Relationships
    assessment = relationship("Assessment", back_populates="student_marks")
    enrollment = relationship("Enrollment", back_populates="marks")

    def __repr__(self) -> str:
        return f"<StudentMark(mark_id={self.mark_id}, marks={self.marks_obtained})>"


# ---------------------------------------------------------------------------
# Database-Level Integrity Triggers (SQLite)
# ---------------------------------------------------------------------------
from sqlalchemy import DDL, event

# 1. StudentMark Cross-Offering Integrity & Marks Boundary Triggers
trg_student_marks_insert = DDL("""
CREATE TRIGGER IF NOT EXISTS trg_student_marks_integrity_insert
BEFORE INSERT ON student_marks
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'Cross-offering integrity violation: Assessment and Enrollment must belong to the same course offering.')
    WHERE (SELECT offering_id FROM assessments WHERE assessment_id = NEW.assessment_id)
       != (SELECT offering_id FROM enrollments WHERE enrollment_id = NEW.enrollment_id);

    SELECT RAISE(ABORT, 'Marks boundary violation: marks_obtained cannot exceed assessment max_marks.')
    WHERE NEW.marks_obtained > (SELECT max_marks FROM assessments WHERE assessment_id = NEW.assessment_id);
END;
""")

trg_student_marks_update = DDL("""
CREATE TRIGGER IF NOT EXISTS trg_student_marks_integrity_update
BEFORE UPDATE ON student_marks
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'Cross-offering integrity violation: Assessment and Enrollment must belong to the same course offering.')
    WHERE (SELECT offering_id FROM assessments WHERE assessment_id = NEW.assessment_id)
       != (SELECT offering_id FROM enrollments WHERE enrollment_id = NEW.enrollment_id);

    SELECT RAISE(ABORT, 'Marks boundary violation: marks_obtained cannot exceed assessment max_marks.')
    WHERE NEW.marks_obtained > (SELECT max_marks FROM assessments WHERE assessment_id = NEW.assessment_id);
END;
""")

# 2. Assessment Cumulative Weightage Trigger (Cumulative weightage <= 100.0 percent)
trg_assessments_weightage_insert = DDL("""
CREATE TRIGGER IF NOT EXISTS trg_assessments_weightage_insert
BEFORE INSERT ON assessments
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'Assessment weightage violation: Cumulative weightage for course offering cannot exceed 100 percent.')
    WHERE (SELECT COALESCE(SUM(weightage_percent), 0.0) FROM assessments WHERE offering_id = NEW.offering_id) + NEW.weightage_percent > 100.0;
END;
""")

trg_assessments_weightage_update = DDL("""
CREATE TRIGGER IF NOT EXISTS trg_assessments_weightage_update
BEFORE UPDATE ON assessments
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'Assessment weightage violation: Cumulative weightage for course offering cannot exceed 100 percent.')
    WHERE (SELECT COALESCE(SUM(weightage_percent), 0.0) FROM assessments WHERE offering_id = NEW.offering_id AND assessment_id != OLD.assessment_id) + NEW.weightage_percent > 100.0;
END;
""")

# 3. Assessment Maximum Marks Reduction Guard Trigger
trg_assessments_max_marks_update = DDL("""
CREATE TRIGGER IF NOT EXISTS trg_assessments_max_marks_update
BEFORE UPDATE OF max_marks ON assessments
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'Marks boundary violation: New max_marks cannot be less than existing student marks recorded for this assessment.')
    WHERE EXISTS (
        SELECT 1 FROM student_marks
        WHERE assessment_id = OLD.assessment_id
          AND marks_obtained > NEW.max_marks
    );
END;
""")

# 4. Assessment Parent Offering Relocation Guard Trigger
trg_assessments_offering_update = DDL("""
CREATE TRIGGER IF NOT EXISTS trg_assessments_offering_update
BEFORE UPDATE OF offering_id ON assessments
FOR EACH ROW
WHEN NEW.offering_id != OLD.offering_id
BEGIN
    SELECT RAISE(ABORT, 'Cross-offering integrity violation: Cannot change offering_id of an assessment with existing student marks.')
    WHERE EXISTS (
        SELECT 1 FROM student_marks sm
        JOIN enrollments e ON sm.enrollment_id = e.enrollment_id
        WHERE sm.assessment_id = OLD.assessment_id
          AND e.offering_id != NEW.offering_id
    );
END;
""")

# 5. Enrollment Parent Offering Relocation Guard Trigger
trg_enrollments_offering_update = DDL("""
CREATE TRIGGER IF NOT EXISTS trg_enrollments_offering_update
BEFORE UPDATE OF offering_id ON enrollments
FOR EACH ROW
WHEN NEW.offering_id != OLD.offering_id
BEGIN
    SELECT RAISE(ABORT, 'Cross-offering integrity violation: Cannot change offering_id of an enrollment with existing student marks.')
    WHERE EXISTS (
        SELECT 1 FROM student_marks sm
        JOIN assessments a ON sm.assessment_id = a.assessment_id
        WHERE sm.enrollment_id = OLD.enrollment_id
          AND a.offering_id != NEW.offering_id
    );
END;
""")

event.listen(StudentMark.__table__, "after_create", trg_student_marks_insert)
event.listen(StudentMark.__table__, "after_create", trg_student_marks_update)
event.listen(Assessment.__table__, "after_create", trg_assessments_weightage_insert)
event.listen(Assessment.__table__, "after_create", trg_assessments_weightage_update)
event.listen(Assessment.__table__, "after_create", trg_assessments_max_marks_update)
event.listen(Assessment.__table__, "after_create", trg_assessments_offering_update)
event.listen(Enrollment.__table__, "after_create", trg_enrollments_offering_update)



