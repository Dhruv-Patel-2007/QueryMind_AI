"""Unit tests for Core NLP Preprocessor (Normalization, Tokenization, POS Tagging, Lemmatization, N-Grams)."""

import pytest
from app.services.nlp_preprocessor import NLPPreprocessor, get_nlp_preprocessor


@pytest.fixture
def preprocessor() -> NLPPreprocessor:
    """Provides a fresh NLPPreprocessor instance."""
    return get_nlp_preprocessor()


def test_normalization_whitespace_and_control_chars(preprocessor: NLPPreprocessor):
    """Verify normalizer cleans extra spaces, tabs, newlines, and control characters."""
    dirty_query = "  What   is  \t the   average\n\nCGPA   \x00of  students?  "
    normalized = preprocessor.normalize(dirty_query)
    assert normalized == "What is the average CGPA of students?"


def test_tokenization_words_and_punctuation(preprocessor: NLPPreprocessor):
    """Verify regex tokenizer extracts words, contractions, numbers with decimals, and punctuation."""
    query = "Show student's marks in CS101, Fall 2024! Cutoff: 3.85 and 75%."
    tokens = preprocessor.tokenize(query)
    assert "Show" in tokens
    assert "student's" in tokens
    assert "marks" in tokens
    assert "CS101" in tokens
    assert "," in tokens
    assert "Fall" in tokens
    assert "2024" in tokens
    assert "!" in tokens
    assert "3.85" in tokens
    assert "%" in tokens



def test_pos_tagging_penn_treebank(preprocessor: NLPPreprocessor):
    """Verify Penn Treebank POS tag assignments for academic queries."""
    tokens = ["What", "is", "the", "average", "CGPA", "of", "students", "in", "AI", "?"]
    tagged = preprocessor.pos_tag(tokens)

    tag_dict = dict(tagged)
    assert tag_dict["What"] == "WP"         # Wh-pronoun
    assert tag_dict["is"] == "VBZ"          # 3rd person singular present verb
    assert tag_dict["the"] == "DT"          # Determiner
    assert tag_dict["average"] == "JJ"      # Adjective
    assert tag_dict["students"] == "NNS"    # Plural noun
    assert tag_dict["in"] == "IN"           # Preposition
    assert tag_dict["?"] == "."             # Punctuation


def test_deterministic_lemmatization(preprocessor: NLPPreprocessor):
    """Verify morphological lemmatization converts inflected forms to base lemmas."""
    # Noun plurals
    assert preprocessor.lemmatize("students", "NNS") == "student"
    assert preprocessor.lemmatize("courses", "NNS") == "course"
    assert preprocessor.lemmatize("quizzes", "NNS") == "quiz"
    assert preprocessor.lemmatize("professors", "NNS") == "professor"
    assert preprocessor.lemmatize("departments", "NNS") == "department"

    # Possessive noun cleanup
    assert preprocessor.lemmatize("student's", "NN") == "student"
    assert preprocessor.lemmatize("instructor's", "NN") == "instructor"

    # Verb conjugations
    assert preprocessor.lemmatize("teaches", "VBZ") == "teach"
    assert preprocessor.lemmatize("taught", "VBD") == "teach"
    assert preprocessor.lemmatize("enrolled", "VBD") == "enroll"
    assert preprocessor.lemmatize("scoring", "VBG") == "score"
    assert preprocessor.lemmatize("was", "VBD") == "be"
    assert preprocessor.lemmatize("were", "VBD") == "be"
    assert preprocessor.lemmatize("been", "VBN") == "be"
    assert preprocessor.lemmatize("did", "VBD") == "do"
    assert preprocessor.lemmatize("done", "VBN") == "do"
    assert preprocessor.lemmatize("matrices", "NNS") == "matrix"


    # Comparative / Superlative adjectives
    assert preprocessor.lemmatize("highest", "JJS") == "high"
    assert preprocessor.lemmatize("higher", "JJR") == "high"
    assert preprocessor.lemmatize("lowest", "JJS") == "low"
    assert preprocessor.lemmatize("best", "JJS") == "good"


def test_word_ngrams_extraction(preprocessor: NLPPreprocessor):
    """Verify extraction of unigrams, bigrams, and trigrams."""
    tokens = ["average", "marks", "in", "calculus"]
    ngrams = preprocessor.extract_word_ngrams(tokens)

    assert ngrams["unigrams"] == ["average", "marks", "in", "calculus"]
    assert ngrams["bigrams"] == ["average marks", "marks in", "in calculus"]
    assert ngrams["trigrams"] == ["average marks in", "marks in calculus"]


def test_char_ngrams_extraction(preprocessor: NLPPreprocessor):
    """Verify character trigram extraction."""
    text = "CGPA"
    char_ngrams = preprocessor.extract_char_ngrams(text, n=3)
    assert char_ngrams == ["cgp", "gpa"]


def test_preprocess_complete_pipeline(preprocessor: NLPPreprocessor):
    """Verify full preprocessing pipeline execution and output dictionary structure."""
    query = "What is the average CGPA of students in AI?"
    result = preprocessor.preprocess(query)

    assert result["raw_query"] == query
    assert result["normalized_query"] == query
    assert len(result["tokens"]) > 0
    assert len(result["lemmas"]) == len(result["tokens"])
    assert len(result["pos_tags"]) == len(result["tokens"])
    assert "unigrams" in result["word_ngrams"]
    assert "bigrams" in result["word_ngrams"]
    assert "trigrams" in result["word_ngrams"]
    assert len(result["char_ngrams"]) > 0


def test_contraction_and_possessive_pos_tagging(preprocessor: NLPPreprocessor):
    """Verify that verbal contractions and possessive nouns are tagged accurately per Penn Treebank."""
    # Verbal contractions must be tagged as auxiliary / modal verbs (not NNP)
    contractions = [
        ("don't", "VBP"),
        ("Don't", "VBP"),
        ("doesn't", "VBZ"),
        ("Doesn't", "VBZ"),
        ("didn't", "VBD"),
        ("Didn't", "VBD"),
        ("isn't", "VBZ"),
        ("Isn't", "VBZ"),
        ("aren't", "VBP"),
        ("Aren't", "VBP"),
        ("can't", "MD"),
        ("Can't", "MD"),
        ("won't", "MD"),
        ("Won't", "MD"),
    ]
    for word, expected_tag in contractions:
        res = preprocessor.pos_tag([word])
        assert res[0][1] == expected_tag, f"Expected {word} to be tagged {expected_tag}, got {res[0][1]}"

    # Possessive nouns: single-token units tagged by base noun category (not plural NNS)
    possessives = [
        ("student's", "NN"),
        ("Student's", "NN"),
        ("instructor's", "NN"),
        ("department's", "NN"),
        ("Alice's", "NNP"),
        ("Bob's", "NNP"),
    ]
    for word, expected_tag in possessives:
        res = preprocessor.pos_tag([word])
        assert res[0][1] == expected_tag, f"Expected {word} to be tagged {expected_tag}, got {res[0][1]}"

    # Contrast with true plural noun
    assert preprocessor.pos_tag(["students"])[0][1] == "NNS"

    # Contextual sentence verification
    query = "Don't show student's marks if they can't attend"
    tokens = preprocessor.tokenize(query)
    tagged = dict(preprocessor.pos_tag(tokens))
    assert tagged["Don't"] == "VBP"
    assert tagged["student's"] == "NN"
    assert tagged["can't"] == "MD"


def test_supported_penn_treebank_style_pos_inventory(preprocessor: NLPPreprocessor):
    """Verify exact emission of 30 supported Penn Treebank-style POS tags (23 grammatical + 7 punctuation)."""
    # 23 grammatical categories
    grammatical_samples = [
        ("what", "WP"),
        ("where", "WRB"),
        ("which", "WDT"),
        ("whose", "WP$"),
        ("calculate", "VB"),
        ("don't", "VBP"),
        ("doesn't", "VBZ"),
        ("didn't", "VBD"),
        ("been", "VBN"),
        ("being", "VBG"),
        ("can't", "MD"),
        ("student", "NN"),
        ("students", "NNS"),
        ("AI", "NNP"),
        ("average", "JJ"),
        ("higher", "JJR"),
        ("highest", "JJS"),
        ("in", "IN"),
        ("to", "TO"),
        ("the", "DT"),
        ("and", "CC"),
        ("quickly", "RB"),
        ("3.85", "CD"),
    ]

    # 7 punctuation / symbol categories
    punctuation_samples = [
        (".", "."),
        (",", ","),
        (":", ":"),
        ("(", "("),
        (")", ")"),
        ("$", "$"),
        ("%", "%"),
    ]

    all_samples = grammatical_samples + punctuation_samples
    assert len(grammatical_samples) == 23
    assert len(punctuation_samples) == 7
    assert len(all_samples) == 30

    tokens = [item[0] for item in all_samples]
    expected_tags = [item[1] for item in all_samples]

    tagged = preprocessor.pos_tag(tokens)
    emitted_tags = [tag for _, tag in tagged]

    assert emitted_tags == expected_tags, f"Tag mismatch: {emitted_tags} != {expected_tags}"
    assert len(set(emitted_tags)) == 30, f"Expected 30 unique tags, got {len(set(emitted_tags))}"


def test_empty_query_preprocessing(preprocessor: NLPPreprocessor):
    """Verify graceful handling of empty or whitespace-only queries."""
    result = preprocessor.preprocess("   ")
    assert result["normalized_query"] == ""
    assert result["tokens"] == []
    assert result["lemmas"] == []
    assert result["pos_tags"] == []
    assert result["word_ngrams"]["unigrams"] == []
    assert result["char_ngrams"] == []

