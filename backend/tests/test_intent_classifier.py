"""Unit tests for Supervised Intent Classifier (7 Categories, Softmax Probabilities, Margins, and Ambiguity Detection)."""

import pytest
from app.services.intent_classifier import (
    IntentClassifier,
    get_intent_classifier,
    INTENT_CATEGORIES,
    CONFIDENCE_THRESHOLD,
    MARGIN_THRESHOLD,
    TRAINING_DATA,
)



@pytest.fixture
def classifier() -> IntentClassifier:
    """Provides a fresh/cached IntentClassifier instance."""
    return get_intent_classifier()


def test_all_seven_blueprint_intents_recognized(classifier: IntentClassifier):
    """Verify that classifier supports all 7 blueprint intent categories."""
    assert len(INTENT_CATEGORIES) == 7
    expected = {"AGGREGATE", "RANKING", "FILTER", "COMPARISON", "TREND", "GENERAL_QUERY", "WHAT_IF"}
    assert set(INTENT_CATEGORIES) == expected


@pytest.mark.parametrize(
    "query,expected_intent",
    [
        ("What is the average CGPA of students in the AI department?", "AGGREGATE"),
        ("Show mean attendance of students in Computer Science", "AGGREGATE"),
        ("Count total students enrolled in Fall 2024", "AGGREGATE"),
        ("Top 5 students in Computer Science by CGPA", "RANKING"),
        ("List lowest 10 students by attendance percentage", "RANKING"),
        ("List all students with attendance below 75 percent", "FILTER"),
        ("Find instructors who joined after 2018", "FILTER"),
        ("Compare average marks between Spring 2024 and Fall 2024", "COMPARISON"),
        ("Difference in pass rate between CS and EE departments", "COMPARISON"),
        ("Show enrollment growth across terms from 2022 to 2024", "TREND"),
        ("What is the trend of average student CGPA over the years?", "TREND"),
        ("Show all details for course CS101", "GENERAL_QUERY"),
        ("Give information about the Electrical Engineering department", "GENERAL_QUERY"),
        ("What if we increase midterm weightage by 10 percent?", "WHAT_IF"),
        ("Simulate the impact of dropping the lowest quiz score", "WHAT_IF"),
    ],
)
def test_intent_classification_predictions(classifier: IntentClassifier, query: str, expected_intent: str):
    """Verify high-accuracy intent classification across all 7 categories on benchmark queries."""
    result = classifier.classify(query)
    assert result["predicted_intent"] == expected_intent
    assert result["confidence"] >= CONFIDENCE_THRESHOLD
    assert not result["is_ambiguous"]


def test_softmax_probability_distribution_properties(classifier: IntentClassifier):
    """Verify mathematical properties of Softmax class probabilities."""
    query = "What is the average CGPA of students in Computer Science?"

    result = classifier.classify(query)

    probs = result["probabilities"]
    assert len(probs) == 7

    # 1. Non-negativity and upper bound
    for intent, p in probs.items():
        assert 0.0 <= p <= 1.0, f"Probability for {intent} must be in [0, 1]"

    # 2. Sum to 1.0 within rounding precision
    total_prob = sum(probs.values())
    assert abs(total_prob - 1.0) < 0.01, f"Probabilities sum to {total_prob}, expected ~1.0"


def test_margin_and_top_intents_ordering(classifier: IntentClassifier):
    """Verify that top_intents is strictly sorted descending and margin is correctly calculated."""
    query = "Top 5 students by CGPA in AI"
    result = classifier.classify(query)

    top_intents = result["top_intents"]
    assert len(top_intents) == 7

    # Check descending order
    for i in range(len(top_intents) - 1):
        assert top_intents[i][1] >= top_intents[i + 1][1]

    # Verify margin calculation: P(top1) - P(top2)
    expected_margin = round(top_intents[0][1] - top_intents[1][1], 4)
    assert abs(result["margin"] - expected_margin) < 1e-4


def test_out_of_domain_scope_boundary_detection(classifier: IntentClassifier):
    """Verify queries sharing zero academic schema vocabulary are flagged as OUT_OF_DOMAIN with damped confidence."""
    ood_queries = [
        "What is the weather in Paris today?",
        "Tell me a funny joke about dogs",
        "Book a flight ticket to London tomorrow morning",
        "What is the average price of bananas at Walmart?",
        "The total population of Tokyo is 14 million.",
        "Can you compare Apple and Microsoft stock prices?",
    ]

    for ood in ood_queries:
        result = classifier.classify(ood)
        assert result["is_ambiguous"] is True
        assert result["ambiguity_reason"] == "OUT_OF_DOMAIN", f"Expected OUT_OF_DOMAIN for '{ood}', got {result['ambiguity_reason']}"
        assert result["confidence"] <= 0.35, "Out-of-domain confidence must be damped to <= 0.35"



def test_empty_query_classification(classifier: IntentClassifier):
    """Verify empty or whitespace query produces ambiguous neutral output."""
    result = classifier.classify("   ")
    assert result["is_ambiguous"] is True
    assert result["ambiguity_reason"] == "EMPTY_QUERY"
    assert result["predicted_intent"] == "GENERAL_QUERY"


def test_classification_determinism_and_reproducibility(classifier: IntentClassifier):
    """Verify classifier is strictly deterministic across repeated invocations."""
    query = "Find students with CGPA greater than 3.8"
    run_1 = classifier.classify(query)
    run_2 = classifier.classify(query)

    assert run_1["predicted_intent"] == run_2["predicted_intent"]
    assert run_1["confidence"] == run_2["confidence"]
    assert run_1["margin"] == run_2["margin"]
    assert run_1["probabilities"] == run_2["probabilities"]


def test_group_aware_cross_validation_invariants():
    """Verify that semantic template grouping enforces strict group disjointness and class coverage across 3 folds."""
    from scripts.evaluate_intent import GROUP_MAP, verify_group_invariants, run_group_aware_evaluation

    texts = [t[0] for t in TRAINING_DATA]
    labels = [t[1] for t in TRAINING_DATA]

    # Group invariants
    verify_group_invariants(texts, labels, GROUP_MAP)

    # 3-Fold evaluation execution and assertion checks
    results = run_group_aware_evaluation(texts, labels, GROUP_MAP)
    assert round(results["accuracy"], 4) == 0.6016
    assert round(results["log_loss"], 4) == 1.3335
    assert round(results["mean_brier"], 4) == 0.0883


