"""Supervised Intent Classification Engine for QueryMind AI 2.0.

Implements TF-IDF feature extraction paired with Multinomial Logistic Regression
to classify natural language queries into 7 distinct academic intent categories.
Produces nominal Softmax class probabilities, calculates confidence margins,
and flags low-confidence or narrow-margin ambiguities for smart clarification.
Note: Logistic Regression probabilities are uncalibrated Softmax outputs satisfying
the probability axioms (sum=1.0) without post-hoc Platt scaling or Isotonic calibration.
"""

import re
from typing import Dict, List, Optional, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

# 7 Approved Intent Categories from querymind_blueprint.md
INTENT_CATEGORIES = [
    "AGGREGATE",
    "RANKING",
    "FILTER",
    "COMPARISON",
    "TREND",
    "GENERAL_QUERY",
    "WHAT_IF",
]

# Confidence Thresholds from blueprint Section 4
CONFIDENCE_THRESHOLD = 0.55  # Minimum confidence required for autonomous SQL generation
MARGIN_THRESHOLD = 0.15      # Minimum gap required between top 1 and top 2 predictions

# Academic Domain Entity Keywords for Out-of-Domain Scope Boundary Enforcement (Blueprint Section 3.D)
# Note: Generic analytical operators (average, total, compare, top) are intentionally excluded
# so non-academic queries (e.g. "average banana price") are correctly flagged as OUT_OF_DOMAIN.
ACADEMIC_DOMAIN_KEYWORDS = {
    # Core academic schema entities and roles
    "student", "students", "instructor", "instructors", "faculty", "professor", "professors",
    "course", "courses", "department", "departments", "term", "terms", "semester", "semesters",
    "offering", "offerings", "section", "sections", "enrollment", "enrollments",
    "assessment", "assessments", "exam", "exams", "midterm", "final", "quiz", "quizzes",
    "mark", "marks", "score", "scores", "grade", "grades", "gpa", "cgpa", "attendance",
    "credit", "credits", "curriculum", "probation", "graduated", "active", "suspended",
    # Academic disciplines, department codes & curriculum terms
    "ai", "cs", "ee", "math", "artificial", "intelligence", "computer", "science",
    "electrical", "mechanical", "engineering", "mathematics", "statistics",
    "classroom", "lecture", "hall", "syllabus", "admission", "admitted", "prerequisite",
}


# Domain-specific academic query corpus for training
TRAINING_DATA: List[Tuple[str, str]] = [
    # ------------------ AGGREGATE ------------------
    ("What is the average CGPA of students in the AI department?", "AGGREGATE"),
    ("Show mean attendance of students in Computer Science", "AGGREGATE"),
    ("Count total students enrolled in Fall 2024", "AGGREGATE"),
    ("What is the average score in Database Management Systems?", "AGGREGATE"),
    ("Total credits offered by Mathematics department", "AGGREGATE"),
    ("Find the maximum marks obtained in Midterm Exam", "AGGREGATE"),
    ("What is the lowest CGPA in Mechanical Engineering?", "AGGREGATE"),
    ("Calculate average marks for course CS101", "AGGREGATE"),
    ("How many instructors are there in Electrical Engineering?", "AGGREGATE"),
    ("Sum of all credits in Computer Science department", "AGGREGATE"),
    ("What is the overall average attendance percentage?", "AGGREGATE"),
    ("Give me the total number of courses offered", "AGGREGATE"),
    ("Count how many students are on academic probation", "AGGREGATE"),
    ("Average grade points of students in Artificial Intelligence", "AGGREGATE"),
    ("Compute the mean marks for final exams", "AGGREGATE"),
    ("What is the highest score in Natural Language Processing?", "AGGREGATE"),
    ("Find minimum attendance among all active students", "AGGREGATE"),
    ("How many course offerings are scheduled in Spring 2024?", "AGGREGATE"),
    ("What is the average mark in each course?", "AGGREGATE"),
    ("Total count of enrollments across all terms", "AGGREGATE"),
    ("Mean marks obtained in practical lab assignment", "AGGREGATE"),
    ("Maximum and minimum CGPA in the university", "AGGREGATE"),

    # ------------------ RANKING ------------------
    ("Top 5 students by CGPA in Computer Science", "RANKING"),
    ("Show top 3 instructors with most course offerings", "RANKING"),
    ("List lowest 10 students by attendance percentage", "RANKING"),
    ("Who are the best performing students in AI department?", "RANKING"),
    ("Rank departments by total student enrollment", "RANKING"),
    ("Top 5 highest marks in Final Comprehensive Exam", "RANKING"),
    ("Show bottom 5 courses by average attendance", "RANKING"),
    ("List top 10 students with highest marks in NLP", "RANKING"),
    ("Rank courses with highest credit hours", "RANKING"),
    ("Who are the top 3 students in semester 4?", "RANKING"),
    ("Show 5 worst scoring students in midterm", "RANKING"),
    ("Highest scoring students in Calculus", "RANKING"),
    ("Top 5 students with highest grade points", "RANKING"),
    ("List bottom 3 departments by established year", "RANKING"),
    ("Rank students from highest to lowest CGPA", "RANKING"),
    ("Find top 10 enrollments with best final grades", "RANKING"),
    ("Top 3 courses with highest average marks", "RANKING"),
    ("Which students have the highest attendance?", "RANKING"),
    ("Show bottom 5 enrollments by marks obtained", "RANKING"),
    ("Rank instructors by joining year", "RANKING"),

    # ------------------ FILTER ------------------
    ("List students with attendance below 75 percent", "FILTER"),
    ("Show all students whose CGPA is greater than 3.5", "FILTER"),
    ("Find instructors who joined after 2018", "FILTER"),
    ("List courses with credits equal to 4", "FILTER"),
    ("Show active students in semester 6", "FILTER"),
    ("Find students with CGPA between 3.0 and 3.5", "FILTER"),
    ("List students on probation in Electrical Engineering", "FILTER"),
    ("Show course offerings held in Auditorium-A", "FILTER"),
    ("Find assessments where max marks is greater than 50", "FILTER"),
    ("List students with attendance percentage above 90", "FILTER"),
    ("Show instructors with designation Professor", "FILTER"),
    ("Find courses that belong to 300 level", "FILTER"),
    ("List all students admitted in year 2023", "FILTER"),
    ("Show students who received grade F", "FILTER"),
    ("Find offerings in classroom Lab-AI", "FILTER"),
    ("Filter students having CGPA less than 2.50", "FILTER"),
    ("List enrollments with enrollment status Completed", "FILTER"),
    ("Show students where academic status is Probation", "FILTER"),
    ("Find all courses with level 100 or 200", "FILTER"),
    ("List course offerings with section A", "FILTER"),

    # ------------------ COMPARISON ------------------
    ("Compare average CGPA between AI and CS departments", "COMPARISON"),
    ("Compare attendance between Fall 2023 and Spring 2024", "COMPARISON"),
    ("How does student performance in CS compare to EE?", "COMPARISON"),
    ("Compare average marks between midterm and final exams", "COMPARISON"),
    ("Compare number of courses between ME and MATH departments", "COMPARISON"),
    ("Difference in attendance between semester 1 and semester 8", "COMPARISON"),
    ("Compare enrollment counts between AI and Electrical Engineering", "COMPARISON"),
    ("Which department has higher average CGPA AI or CS?", "COMPARISON"),
    ("Compare average marks between Section A and Section B", "COMPARISON"),
    ("Compare total credits between Mathematics and Computer Science", "COMPARISON"),
    ("How do grades in CS101 compare with AI101?", "COMPARISON"),
    ("Comparison of instructor counts between all departments", "COMPARISON"),
    ("Compare probation rates across departments", "COMPARISON"),
    ("Is average CGPA higher in AI compared to Mathematics?", "COMPARISON"),

    # ------------------ TREND ------------------
    ("Show enrollment trends by academic year", "TREND"),
    ("How has average CGPA changed over terms?", "TREND"),
    ("Show attendance trend from Fall 2022 to Spring 2025", "TREND"),
    ("Trend of student marks over time", "TREND"),
    ("How did performance change across semesters?", "TREND"),
    ("Show term over term growth in student enrollment", "TREND"),
    ("Track average grade points over academic years", "TREND"),
    ("Historical trend of department enrollment numbers", "TREND"),
    ("Trend of course offerings over recent years", "TREND"),
    ("How have student counts changed year over year?", "TREND"),
    ("Show semester-wise progression of student CGPAs", "TREND"),
    ("Annual enrollment trends across all departments", "TREND"),
    ("Attendance trend over terms for Computer Science", "TREND"),
    ("Performance trajectory across academic sessions", "TREND"),
    ("Show enrollment growth across terms from 2022 to 2024", "TREND"),
    ("What is the trend of average student CGPA over the years?", "TREND"),
    ("Show growth in student numbers over the years", "TREND"),
    ("Trend of student grades over time", "TREND"),

    # ------------------ GENERAL_QUERY ------------------
    ("Show all courses in the Mathematics department", "GENERAL_QUERY"),
    ("List all departments in the university", "GENERAL_QUERY"),
    ("Show details of instructor Alan Turing", "GENERAL_QUERY"),
    ("What are the courses offered by Computer Science?", "GENERAL_QUERY"),
    ("List all academic terms", "GENERAL_QUERY"),
    ("Show course catalogue for Artificial Intelligence", "GENERAL_QUERY"),
    ("Give me information about Turing Complex building", "GENERAL_QUERY"),
    ("List all faculty members in Mechanical Engineering", "GENERAL_QUERY"),
    ("Show all course offerings for Fall 2024", "GENERAL_QUERY"),
    ("Display all available courses", "GENERAL_QUERY"),
    ("List the buildings and established years of departments", "GENERAL_QUERY"),
    ("Show student profile for roll number 2024-AI-001", "GENERAL_QUERY"),
    ("What sections are available for course AI101?", "GENERAL_QUERY"),
    ("List instructors and their designations", "GENERAL_QUERY"),
    ("Show the curriculum for Electrical Engineering", "GENERAL_QUERY"),
    ("Show all details for course CS101", "GENERAL_QUERY"),
    ("Give information about the Electrical Engineering department", "GENERAL_QUERY"),
    ("Show information about courses offered", "GENERAL_QUERY"),
    ("List general information about students", "GENERAL_QUERY"),

    # ------------------ WHAT_IF ------------------
    ("What if assessment marks increase by 5 percent?", "WHAT_IF"),
    ("What if student attendance improves by 10%?", "WHAT_IF"),
    ("Simulate the impact if passing threshold is lowered to 50", "WHAT_IF"),
    ("What if all quiz marks are boosted by 3 points?", "WHAT_IF"),
    ("What happens if midterm weightage changes to 40 percent?", "WHAT_IF"),
    ("What if student CGPA decreases by 0.2?", "WHAT_IF"),
    ("Simulate scenario where attendance drops by 15%", "WHAT_IF"),
    ("What if all assignments are scaled up by 10%?", "WHAT_IF"),
    ("What if we increase final exam weightage to 60 percent?", "WHAT_IF"),
    ("Scenario analysis if marks obtained increase by 8 points?", "WHAT_IF"),
    ("What if CGPA across all students increases by 0.1?", "WHAT_IF"),
    ("Simulate if probation threshold was 2.8 instead of 2.5", "WHAT_IF"),
    ("Simulate the impact of dropping the lowest quiz score", "WHAT_IF"),
    ("What if we drop the lowest assessment score?", "WHAT_IF"),
    ("What if we simulate a 5 percent curve on final marks?", "WHAT_IF"),

]


class IntentClassifier:
    """Supervised Intent Classifier utilizing TF-IDF (1-2 word n-grams) and

    Multinomial Logistic Regression with Softmax class probabilities.
    Note: Probabilities are nominal Softmax outputs, not post-hoc calibrated.
    """


    def __init__(self, random_state: int = 42) -> None:
        self.random_state = random_state
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            strip_accents="unicode",
            lowercase=True,
            token_pattern=r"\b\w+\b",
        )
        self.model = LogisticRegression(
            solver="lbfgs",
            max_iter=1000,
            random_state=self.random_state,
            C=5.0,
        )
        self._is_trained = False
        self._train()

    def _train(self) -> None:
        """Trains the TF-IDF Vectorizer and Multinomial Logistic Regression model."""
        texts = [item[0] for item in TRAINING_DATA]
        labels = [item[1] for item in TRAINING_DATA]

        X = self.vectorizer.fit_transform(texts)
        self.model.fit(X, labels)
        self._is_trained = True

    def predict(self, query: str) -> Dict:
        """Predicts the intent class of a query with Softmax confidence and ambiguity metrics.

        Returns:
            Dictionary with predicted_intent, confidence, probabilities, is_ambiguous,
            ambiguity_reason, and top_intents.
        """
        if not query or not query.strip():
            # Return neutral ambiguous classification on empty query
            uniform_prob = round(1.0 / len(INTENT_CATEGORIES), 4)
            return {
                "predicted_intent": "GENERAL_QUERY",
                "confidence": uniform_prob,
                "probabilities": {intent: uniform_prob for intent in INTENT_CATEGORIES},
                "is_ambiguous": True,
                "ambiguity_reason": "EMPTY_QUERY",
                "top_intents": [(intent, uniform_prob) for intent in INTENT_CATEGORIES],
            }

        X_query = self.vectorizer.transform([query])
        # Predict class probabilities via Softmax: P(y=c|x)
        probs = self.model.predict_proba(X_query)[0]
        classes = self.model.classes_

        # Build class-probability dictionary
        prob_dict = {str(cls_name): round(float(prob), 4) for cls_name, prob in zip(classes, probs)}

        # Sort intents by probability descending
        sorted_intents = [(str(cls_name), round(float(prob), 4)) for cls_name, prob in sorted(prob_dict.items(), key=lambda item: item[1], reverse=True)]
        top_intent, top_confidence = sorted_intents[0]
        second_intent, second_confidence = sorted_intents[1] if len(sorted_intents) > 1 else (None, 0.0)

        # Domain vocabulary overlap check (Blueprint Section 3.D Scope Boundary)
        query_words = set(re.findall(r"\b\w+\b", query.lower()))
        has_domain_overlap = bool(query_words & ACADEMIC_DOMAIN_KEYWORDS)

        # Ambiguity Evaluation Rules from Blueprint Section 4
        is_ambiguous = False
        ambiguity_reason: Optional[str] = None

        margin = top_confidence - second_confidence

        if not has_domain_overlap:
            is_ambiguous = True
            ambiguity_reason = "OUT_OF_DOMAIN"
            # Dampen confidence for queries that share zero academic domain keywords
            top_confidence = min(top_confidence, 0.35)
        elif top_confidence < CONFIDENCE_THRESHOLD:
            is_ambiguous = True
            ambiguity_reason = "LOW_CONFIDENCE"
        elif margin < MARGIN_THRESHOLD:
            is_ambiguous = True
            ambiguity_reason = "NARROW_MARGIN"

        return {
            "predicted_intent": str(top_intent),
            "confidence": round(float(top_confidence), 4),
            "margin": round(float(margin), 4),
            "probabilities": prob_dict,
            "is_ambiguous": is_ambiguous,
            "ambiguity_reason": ambiguity_reason,
            "top_intents": sorted_intents,
        }

    # Alias predict as classify for convenience
    classify = predict



# Global cached singleton instance for high-performance sub-millisecond predictions
_cached_classifier: Optional[IntentClassifier] = None


def get_intent_classifier() -> IntentClassifier:
    """Returns the cached singleton IntentClassifier instance."""
    global _cached_classifier
    if _cached_classifier is None:
        _cached_classifier = IntentClassifier(random_state=42)
    return _cached_classifier


intent_classifier = get_intent_classifier()

