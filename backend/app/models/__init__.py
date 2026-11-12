"""Academic ORM Domain Models Package for QueryMind AI 2.0.

Exports all 9 normalized relational entities:
- Department
- Student
- Instructor
- Course
- Term
- CourseOffering
- Enrollment
- Assessment
- StudentMark
"""

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

__all__ = [
    "Department",
    "Student",
    "Instructor",
    "Course",
    "Term",
    "CourseOffering",
    "Enrollment",
    "Assessment",
    "StudentMark",
]
