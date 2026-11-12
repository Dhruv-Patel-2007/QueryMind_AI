"""Unit and integration tests for NLP Pipeline Diagnostic Inspection API Endpoints."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_nlp_inspect_get_success():
    """Verify GET /api/nlp/inspect returns full preprocessing and intent diagnostics."""
    response = client.get("/api/nlp/inspect?query=What+is+the+average+CGPA+of+students+in+the+AI+department%3F")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert "average" in data["query"]

    # Preprocessing fields
    prep = data["preprocessing"]
    assert "What" in prep["tokens"]
    assert "student" in prep["lemmas"]  # Plural lemmatized to singular
    assert any(tag[0] == "What" and tag[1] == "WP" for tag in prep["pos_tags"])
    assert "unigrams" in prep["word_ngrams"]
    assert "bigrams" in prep["word_ngrams"]
    assert "trigrams" in prep["word_ngrams"]
    assert len(prep["char_ngrams"]) > 0

    # Intent fields
    intent = data["intent"]
    assert intent["predicted_intent"] == "AGGREGATE"
    assert intent["confidence"] >= 0.55
    assert not intent["is_ambiguous"]
    assert len(intent["probabilities"]) == 7
    assert len(intent["top_intents"]) == 7

    # Latency metric
    assert data["execution_time_ms"] >= 0.0


def test_nlp_inspect_post_success():
    """Verify POST /api/nlp/inspect processes JSON query payload."""
    payload = {"query": "Top 5 students in Computer Science by CGPA"}
    response = client.post("/api/nlp/inspect", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["query"] == payload["query"]

    intent = data["intent"]
    assert intent["predicted_intent"] == "RANKING"
    assert intent["confidence"] >= 0.55
    assert not intent["is_ambiguous"]
    assert intent["margin"] > 0.15


def test_nlp_inspect_out_of_domain_query():
    """Verify out-of-domain query is flagged as ambiguous with OUT_OF_DOMAIN reason."""
    payload = {"query": "What is the capital city of France?"}
    response = client.post("/api/nlp/inspect", json=payload)
    assert response.status_code == 200

    data = response.json()
    intent = data["intent"]
    assert intent["is_ambiguous"] is True
    assert intent["ambiguity_reason"] == "OUT_OF_DOMAIN"
    assert intent["confidence"] <= 0.35


def test_nlp_inspect_validation_empty_query():
    """Verify POST /api/nlp/inspect rejects empty query string with 422."""
    response = client.post("/api/nlp/inspect", json={"query": ""})
    assert response.status_code == 422


def test_nlp_inspect_validation_query_too_long():
    """Verify POST /api/nlp/inspect rejects query exceeding 500 characters with 422."""
    long_query = "What is the average mark " + ("and score " * 100)
    assert len(long_query) > 500
    response = client.post("/api/nlp/inspect", json={"query": long_query})
    assert response.status_code == 422


def test_nlp_inspect_get_missing_parameter():
    """Verify GET /api/nlp/inspect without query parameter returns 422."""
    response = client.get("/api/nlp/inspect")
    assert response.status_code == 422

