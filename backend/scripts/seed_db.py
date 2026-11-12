"""Deterministic Academic Database Seeder for QueryMind AI 2.0.

Populates the SQLite database with rich, realistic, and reproducible academic records
using a fixed random seed (42). Strictly fictional and anonymous data.
"""

import argparse
import random
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from sqlalchemy import inspect
from sqlalchemy.orm import Session, sessionmaker

# Add backend directory to sys.path for direct script execution
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import (
    Base,
    WriteSessionLocal,
    write_engine,
    get_db_path,
    init_db,
)
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

# Seed pseudo-random generators for absolute determinism and reproducibility
SEED = 42

# Fictional Name Banks (Strictly anonymous, fictional academic records)
FIRST_NAMES = [
    "Aarav", "Aditi", "Alexander", "Ananya", "Benjamin", "Charlotte", "Daniel",
    "Diya", "Elena", "Ethan", "Fatima", "Gabriel", "Grace", "Hannah", "Ibrahim",
    "Ishaan", "James", "Kavya", "Liam", "Lucas", "Maya", "Meera", "Nathan",
    "Noah", "Oliver", "Priya", "Rahul", "Riya", "Samuel", "Sarah", "Siddharth",
    "Sophia", "Tara", "Varun", "Victor", "William", "Zara", "Zayd", "Chloe", "Leo"
]

LAST_NAMES = [
    "Patel", "Sharma", "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
    "Miller", "Davis", "Khan", "Ali", "Chen", "Wang", "Kumar", "Singh", "Das",
    "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin", "Clark"
]


def seed_departments(session: Session) -> List[Department]:
    """Seeds 5 distinct Academic Departments."""
    dept_data = [
        {"name": "Artificial Intelligence", "code": "AI", "established_year": 2021, "building": "Turing Complex"},
        {"name": "Computer Science", "code": "CS", "established_year": 2005, "building": "Lovelace Hall"},
        {"name": "Electrical Engineering", "code": "EE", "established_year": 2000, "building": "Tesla Labs"},
        {"name": "Mechanical Engineering", "code": "ME", "established_year": 1998, "building": "Watt Engineering Centre"},
        {"name": "Mathematics & Statistics", "code": "MATH", "established_year": 1995, "building": "Euler Tower"},
    ]
    departments = [Department(**d) for d in dept_data]
    session.add_all(departments)
    session.flush()
    return departments


def seed_instructors(session: Session, departments: List[Department]) -> List[Instructor]:
    """Seeds 20 Faculty Instructors (4 per department) across standard academic ranks."""
    designations = ["Professor", "Associate Professor", "Assistant Professor", "Senior Lecturer"]
    instructors = []

    for dept in departments:
        for i in range(4):
            inst = Instructor(
                department_id=dept.department_id,
                first_name=FIRST_NAMES[(dept.department_id * 4 + i) % len(FIRST_NAMES)],
                last_name=LAST_NAMES[(dept.department_id * 3 + i) % len(LAST_NAMES)],
                designation=designations[i % len(designations)],
                joining_year=2010 + (i * 3) % 13,
            )
            instructors.append(inst)

    session.add_all(instructors)
    session.flush()
    return instructors


def seed_courses(session: Session, departments: List[Department]) -> List[Course]:
    """Seeds 15 Academic Courses across all departments and course levels."""
    dept_map = {d.code: d.department_id for d in departments}
    courses_data = [
        # Artificial Intelligence
        {"department_id": dept_map["AI"], "course_code": "AI101", "course_name": "Introduction to Artificial Intelligence", "credits": 3, "course_level": 100},
        {"department_id": dept_map["AI"], "course_code": "AI201", "course_name": "Machine Learning Fundamentals", "credits": 4, "course_level": 200},
        {"department_id": dept_map["AI"], "course_code": "AI301", "course_name": "Natural Language Processing", "credits": 4, "course_level": 300},
        {"department_id": dept_map["AI"], "course_code": "AI401", "course_name": "Computer Vision & Deep Learning", "credits": 3, "course_level": 400},
        # Computer Science
        {"department_id": dept_map["CS"], "course_code": "CS101", "course_name": "Programming Fundamentals", "credits": 4, "course_level": 100},
        {"department_id": dept_map["CS"], "course_code": "CS201", "course_name": "Data Structures & Algorithms", "credits": 4, "course_level": 200},
        {"department_id": dept_map["CS"], "course_code": "CS301", "course_name": "Database Management Systems", "credits": 3, "course_level": 300},
        {"department_id": dept_map["CS"], "course_code": "CS401", "course_name": "Distributed Cloud Systems", "credits": 3, "course_level": 400},
        # Electrical Engineering
        {"department_id": dept_map["EE"], "course_code": "EE101", "course_name": "Linear Circuit Analysis", "credits": 3, "course_level": 100},
        {"department_id": dept_map["EE"], "course_code": "EE201", "course_name": "Digital Signal Processing", "credits": 4, "course_level": 200},
        {"department_id": dept_map["EE"], "course_code": "EE301", "course_name": "Microprocessors & Embedded Systems", "credits": 4, "course_level": 300},
        # Mechanical Engineering
        {"department_id": dept_map["ME"], "course_code": "ME101", "course_name": "Engineering Mechanics & Statics", "credits": 3, "course_level": 100},
        {"department_id": dept_map["ME"], "course_code": "ME201", "course_name": "Thermodynamics & Heat Transfer", "credits": 4, "course_level": 200},
        # Mathematics
        {"department_id": dept_map["MATH"], "course_code": "MATH101", "course_name": "Calculus & Analytical Geometry", "credits": 4, "course_level": 100},
        {"department_id": dept_map["MATH"], "course_code": "MATH201", "course_name": "Linear Algebra & Probability", "credits": 3, "course_level": 200},
    ]
    courses = [Course(**c) for c in courses_data]
    session.add_all(courses)
    session.flush()
    return courses


def seed_terms(session: Session) -> List[Term]:
    """Seeds 6 Academic Terms covering academic years 2022 through 2025."""
    terms_data = [
        {"term_name": "Fall 2022", "academic_year": 2022, "semester_type": "Fall", "start_date": date(2022, 9, 1), "end_date": date(2022, 12, 20)},
        {"term_name": "Spring 2023", "academic_year": 2023, "semester_type": "Spring", "start_date": date(2023, 1, 15), "end_date": date(2023, 5, 20)},
        {"term_name": "Fall 2023", "academic_year": 2023, "semester_type": "Fall", "start_date": date(2023, 9, 1), "end_date": date(2023, 12, 20)},
        {"term_name": "Spring 2024", "academic_year": 2024, "semester_type": "Spring", "start_date": date(2024, 1, 15), "end_date": date(2024, 5, 20)},
        {"term_name": "Fall 2024", "academic_year": 2024, "semester_type": "Fall", "start_date": date(2024, 9, 1), "end_date": date(2024, 12, 20)},
        {"term_name": "Spring 2025", "academic_year": 2025, "semester_type": "Spring", "start_date": date(2025, 1, 15), "end_date": date(2025, 5, 20)},
    ]
    terms = [Term(**t) for t in terms_data]
    session.add_all(terms)
    session.flush()
    return terms


def seed_students(session: Session, departments: List[Department]) -> List[Student]:
    """Seeds 120 Students (24 per department) with realistic, continuous CGPA distributions."""
    students = []
    roll_counter = {d.code: 1 for d in departments}

    for dept in departments:
        for idx in range(24):
            enrollment_year = 2021 + (idx % 4)
            current_semester = min(8, max(1, (2024 - enrollment_year) * 2 + (idx % 2 + 1)))

            # Sample CGPA deterministically from normal distribution (mean=3.32, sd=0.42)
            raw_cgpa = float(np.random.normal(3.32, 0.42))
            sampled_cgpa = round(float(np.clip(raw_cgpa, 2.05, 3.98)), 2)

            roll_str = f"{enrollment_year}-{dept.code}-{roll_counter[dept.code]:03d}"
            roll_counter[dept.code] += 1

            if sampled_cgpa < 2.50:
                status = "Probation"
            elif current_semester >= 8:
                status = "Graduated"
            else:
                status = "Active"

            fn_idx = (dept.department_id * 24 + idx) % len(FIRST_NAMES)
            ln_idx = (dept.department_id * 17 + idx * 2) % len(LAST_NAMES)

            student = Student(
                department_id=dept.department_id,
                roll_number=roll_str,
                first_name=FIRST_NAMES[fn_idx],
                last_name=LAST_NAMES[ln_idx],
                enrollment_year=enrollment_year,
                current_semester=current_semester,
                cgpa=sampled_cgpa,
                academic_status=status,
            )
            students.append(student)

    session.add_all(students)
    session.flush()
    return students


def seed_course_offerings(
    session: Session,
    courses: List[Course],
    instructors: List[Instructor],
    terms: List[Term],
) -> List[CourseOffering]:
    """Seeds 36 Course Offerings across courses, terms, and sections."""
    offerings = []
    classrooms = ["Auditorium-A", "Hall-101", "Hall-102", "Lab-1", "Lab-2", "Lab-AI", "Room-204", "Room-305"]
    recent_terms = terms[-3:]  # Fall 2023, Spring 2024, Fall 2024

    for c_idx, course in enumerate(courses):
        dept_instructors = [inst for inst in instructors if inst.department_id == course.department_id]
        if not dept_instructors:
            dept_instructors = instructors

        # Schedule course in 2 to 3 terms
        for t_idx, term in enumerate(recent_terms):
            inst = dept_instructors[(c_idx + t_idx) % len(dept_instructors)]
            section = "A" if (c_idx + t_idx) % 2 == 0 else "B"
            classroom = classrooms[(c_idx * 2 + t_idx) % len(classrooms)]

            offering = CourseOffering(
                course_id=course.course_id,
                instructor_id=inst.instructor_id,
                term_id=term.term_id,
                section=section,
                classroom=classroom,
            )
            offerings.append(offering)

    session.add_all(offerings)
    session.flush()
    return offerings


def seed_assessments(session: Session, offerings: List[CourseOffering]) -> List[Assessment]:
    """Seeds 108 Assessments (Midterm 30%, Final 50%, Project/Lab 20% per offering)."""
    assessments = []
    for off in offerings:
        assessments.append(
            Assessment(
                offering_id=off.offering_id,
                title="Midterm Examination",
                assessment_type="Midterm",
                max_marks=100.0,
                weightage_percent=30.0,
            )
        )
        assessments.append(
            Assessment(
                offering_id=off.offering_id,
                title="Final Comprehensive Examination",
                assessment_type="Final",
                max_marks=100.0,
                weightage_percent=50.0,
            )
        )
        assessments.append(
            Assessment(
                offering_id=off.offering_id,
                title="Course Project / Practical Lab",
                assessment_type="Assignment",
                max_marks=100.0,
                weightage_percent=20.0,
            )
        )

    session.add_all(assessments)
    session.flush()
    return assessments


def seed_enrollments_and_marks(
    session: Session,
    students: List[Student],
    offerings: List[CourseOffering],
    assessments: List[Assessment],
) -> Tuple[List[Enrollment], List[StudentMark]]:
    """Seeds Enrollments (~360+) and Student Marks (~1080) with realistic score correlations."""
    enrollments: List[Enrollment] = []
    marks: List[StudentMark] = []

    grade_scale = [
        (90.0, "A", 4.0),
        (85.0, "A-", 3.7),
        (80.0, "B+", 3.3),
        (75.0, "B", 3.0),
        (70.0, "B-", 2.7),
        (65.0, "C+", 2.3),
        (60.0, "C", 2.0),
        (0.0, "F", 0.0),
    ]

    # Map assessments by offering_id for fast lookup
    assessment_map: Dict[int, List[Assessment]] = {}
    for a in assessments:
        assessment_map.setdefault(a.offering_id, []).append(a)

    for s_idx, student in enumerate(students):
        # Select offerings matching student's department or introductory 100/200-level offerings
        eligible = [
            off for off in offerings
            if off.course.department_id == student.department_id or off.course.course_level <= 200
        ]
        num_enroll = 3 if len(eligible) >= 3 else len(eligible)
        # Deterministic selection based on student index
        selected_offerings = [eligible[(s_idx + k * 5) % len(eligible)] for k in range(num_enroll)]

        # Eliminate duplicate offerings in selection
        seen_off_ids = set()
        unique_offerings = []
        for off in selected_offerings:
            if off.offering_id not in seen_off_ids:
                seen_off_ids.add(off.offering_id)
                unique_offerings.append(off)

        for off in unique_offerings:
            # Deterministic attendance sampling around 82.0%
            raw_att = float(np.random.normal(82.5, 9.5))
            attendance = round(float(np.clip(raw_att, 55.0, 99.5)), 1)

            # Performance correlated with CGPA and attendance
            base_score = (student.cgpa / 4.0) * 82.0 + (attendance / 100.0) * 18.0 + float(np.random.uniform(-4.0, 4.0))
            composite_score = float(np.clip(base_score, 48.0, 98.0))

            final_grade = "F"
            grade_points = 0.0
            for min_score, letter, pts in grade_scale:
                if composite_score >= min_score:
                    final_grade = letter
                    grade_points = pts
                    break

            enrollment = Enrollment(
                student_id=student.student_id,
                offering_id=off.offering_id,
                attendance_percentage=attendance,
                final_grade=final_grade,
                grade_points=grade_points,
                enrollment_status="Completed",
            )
            enrollments.append(enrollment)

    session.add_all(enrollments)
    session.flush()

    # Generate marks for each assessment
    for enr in enrollments:
        off_assessments = assessment_map.get(enr.offering_id, [])
        for a in off_assessments:
            perf_factor = (enr.grade_points / 4.0) if enr.grade_points else 0.5
            raw_mark = float(np.random.normal(perf_factor * 86.0 + 8.0, 5.5))
            score = round(float(np.clip(raw_mark, 42.0, 99.0)), 1)

            mark = StudentMark(
                assessment_id=a.assessment_id,
                enrollment_id=enr.enrollment_id,
                marks_obtained=score,
            )
            marks.append(mark)

    session.add_all(marks)
    session.flush()

    return enrollments, marks


def seed_database(
    session: Session | None = None,
    engine=write_engine,
    reset: bool = False,
) -> Dict[str, int]:
    """Main execution function: populates the Academic SQLite database deterministically.

    Args:
        session: Optional SQLAlchemy Session. If None, WriteSessionLocal() is created.
        engine: Engine to use (defaults to write_engine).
        reset: If True, explicitly rebuilds tables before seeding.

    Returns:
        Dictionary containing entity counts for all 9 academic tables.
    """
    # Reset random seeds for absolute determinism
    random.seed(SEED)
    np.random.seed(SEED)

    close_session_at_end = False
    if session is None:
        init_db(engine=engine, drop_existing=reset)
        session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = session_factory()
        close_session_at_end = True

    try:
        # Check if already seeded (idempotency check)
        existing_depts = session.query(Department).count()
        if existing_depts > 0 and not reset:
            print("--> [seed_db] Database already contains records. Idempotent check passed (use --reset to re-seed).")
            counts = {
                "departments": session.query(Department).count(),
                "students": session.query(Student).count(),
                "instructors": session.query(Instructor).count(),
                "courses": session.query(Course).count(),
                "terms": session.query(Term).count(),
                "course_offerings": session.query(CourseOffering).count(),
                "enrollments": session.query(Enrollment).count(),
                "assessments": session.query(Assessment).count(),
                "student_marks": session.query(StudentMark).count(),
            }
            return counts

        print("--> [seed_db] Seeding Academic Database with Seed=42...")
        depts = seed_departments(session)
        instructors = seed_instructors(session, depts)
        courses = seed_courses(session, depts)
        terms = seed_terms(session)
        students = seed_students(session, depts)
        offerings = seed_course_offerings(session, courses, instructors, terms)
        assessments = seed_assessments(session, offerings)
        enrollments, marks = seed_enrollments_and_marks(session, students, offerings, assessments)

        session.commit()
        print("==> [seed_db] Seeding completed successfully and transaction committed.")

        counts = {
            "departments": len(depts),
            "instructors": len(instructors),
            "courses": len(courses),
            "terms": len(terms),
            "students": len(students),
            "course_offerings": len(offerings),
            "assessments": len(assessments),
            "enrollments": len(enrollments),
            "student_marks": len(marks),
        }

        print("--> [seed_db] Record Count Summary:")
        for entity, count in counts.items():
            print(f"    • {entity}: {count}")

        return counts

    except Exception as exc:
        session.rollback()
        print(f"ERROR: [seed_db] Seeding transaction failed, rolled back: {exc}", file=sys.stderr)
        raise
    finally:
        if close_session_at_end:
            session.close()


def main() -> None:
    """CLI entry point for seeding the database."""
    parser = argparse.ArgumentParser(
        description="Seed QueryMind AI 2.0 Academic Database with Deterministic Synthetic Data."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Explicitly drops existing tables and reseeds from scratch.",
    )
    args = parser.parse_args()

    try:
        counts = seed_database(reset=args.reset)
        print(f"==> [seed_db] Academic database ready at: {get_db_path()}")
    except Exception as exc:
        print(f"ERROR: [seed_db] Seeding failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
