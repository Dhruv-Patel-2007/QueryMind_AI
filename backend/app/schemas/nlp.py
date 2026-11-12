"""Pydantic v2 Schemas for NLP Preprocessing and Intent Inspector API."""

from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class NLPInspectRequest(BaseModel):
    """Request payload for NLP pipeline inspection."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Natural language query string targeted at the Academic Institution schema",
        examples=["What is the average CGPA of students in the AI department?"],
    )


class NLPPreprocessData(BaseModel):
    """Output payload for tokenization, lemmatization, POS tagging, and n-grams."""

    raw_query: str = Field(..., description="Original raw user input string")
    normalized_query: str = Field(..., description="Whitespace-normalized, sanitised string")
    tokens: List[str] = Field(..., description="Ordered list of word and punctuation tokens")
    lemmas: List[str] = Field(..., description="Ordered list of base morphological lemmas")
    pos_tags: List[Tuple[str, str]] = Field(..., description="List of (token, Penn Treebank POS tag) pairs")
    word_ngrams: Dict[str, List[str]] = Field(..., description="Extracted word unigrams, bigrams, and trigrams")
    char_ngrams: List[str] = Field(..., description="Extracted character 3-grams")


class IntentClassificationData(BaseModel):
    """Output payload for supervised intent classification with Softmax class confidence."""

    predicted_intent: str = Field(..., description="Winning intent category (1 of 7 approved classes)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Softmax class probability of winning class (uncalibrated)")
    margin: float = Field(..., ge=0.0, le=1.0, description="Gap between top-1 and top-2 class probabilities")
    probabilities: Dict[str, float] = Field(..., description="Complete Softmax probability distribution across all 7 intents")
    is_ambiguous: bool = Field(..., description="Flag indicating if low-confidence or narrow margin triggered ambiguity")

    ambiguity_reason: Optional[str] = Field(None, description="Detailed reason if query is ambiguous ('LOW_CONFIDENCE', 'NARROW_MARGIN', 'OUT_OF_DOMAIN')")
    top_intents: List[Tuple[str, float]] = Field(..., description="Ranked list of (intent, probability) tuples sorted descending")


class NLPInspectResponse(BaseModel):
    """Unified response payload for the NLP Inspector diagnostic panel."""

    status: str = Field("success", description="Status indicator")
    query: str = Field(..., description="Analyzed input query")
    preprocessing: NLPPreprocessData = Field(..., description="Token, lemma, POS, and n-gram analysis")
    intent: IntentClassificationData = Field(..., description="Supervised intent classification diagnostics")
    execution_time_ms: float = Field(..., description="Total pipeline latency in milliseconds")

