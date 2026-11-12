"""NLP Pipeline Diagnostic Inspection Endpoints for QueryMind AI 2.0.

Provides GET and POST inspection endpoints to analyze natural language queries,
returning tokenization, lemmatization, POS tags, n-grams, intent classification,
Softmax confidence, margin separation, and ambiguity diagnostics.
"""

import time
from fastapi import APIRouter, Query, status
from app.schemas.nlp import (
    NLPInspectRequest,
    NLPInspectResponse,
    NLPPreprocessData,
    IntentClassificationData,
)
from app.services.nlp_preprocessor import get_nlp_preprocessor
from app.services.intent_classifier import get_intent_classifier

router = APIRouter()


@router.post(
    "/inspect",
    response_model=NLPInspectResponse,
    status_code=status.HTTP_200_OK,
    summary="Inspect NLP Preprocessing and Intent Classification (POST)",
    description=(
        "Processes an academic query through tokenization, lemmatization, "
        "Penn Treebank POS tagging, n-gram extraction, and supervised intent "
        "classification with Softmax class probabilities."
    ),
)

def inspect_nlp_post(payload: NLPInspectRequest) -> NLPInspectResponse:
    """Diagnostic endpoint to inspect the NLP pipeline via JSON payload."""
    start_time = time.perf_counter()

    preprocessor = get_nlp_preprocessor()
    classifier = get_intent_classifier()

    prep_result = preprocessor.preprocess(payload.query)
    intent_result = classifier.classify(payload.query)

    execution_time_ms = round((time.perf_counter() - start_time) * 1000.0, 3)

    return NLPInspectResponse(
        status="success",
        query=payload.query,
        preprocessing=NLPPreprocessData(**prep_result),
        intent=IntentClassificationData(**intent_result),
        execution_time_ms=execution_time_ms,
    )


@router.get(
    "/inspect",
    response_model=NLPInspectResponse,
    status_code=status.HTTP_200_OK,
    summary="Inspect NLP Preprocessing and Intent Classification (GET)",
    description=(
        "Processes an academic query through the NLP pipeline using a URL query parameter."
    ),
)
def inspect_nlp_get(
    query: str = Query(
        ...,
        min_length=1,
        max_length=500,
        description="Natural language query string targeted at the Academic Institution schema",
        examples=["What is the average CGPA of students in the AI department?"],
    )
) -> NLPInspectResponse:
    """Diagnostic endpoint to inspect the NLP pipeline via query parameter."""
    start_time = time.perf_counter()

    preprocessor = get_nlp_preprocessor()
    classifier = get_intent_classifier()

    prep_result = preprocessor.preprocess(query)
    intent_result = classifier.classify(query)

    execution_time_ms = round((time.perf_counter() - start_time) * 1000.0, 3)

    return NLPInspectResponse(
        status="success",
        query=query,
        preprocessing=NLPPreprocessData(**prep_result),
        intent=IntentClassificationData(**intent_result),
        execution_time_ms=execution_time_ms,
    )

