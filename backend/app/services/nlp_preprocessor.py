"""Core NLP Preprocessing Service for QueryMind AI 2.0.

Provides deterministic, offline-capable text normalization, tokenization,
lemmatization, Penn Treebank POS tagging, and character/word n-gram extraction.
"""

import re
from typing import Dict, List, Tuple


# Penn Treebank tag mappings and vocabulary dictionary for offline deterministic POS tagging
POS_TAG_MAP = {
    # Wh-words
    "what": "WP",
    "which": "WDT",
    "who": "WP",
    "whom": "WP",
    "whose": "WP$",
    "where": "WRB",
    "when": "WRB",
    "why": "WRB",
    "how": "WRB",
    # Auxiliary & Modals (Standard & Negative Contractions)
    "is": "VBZ",
    "isn't": "VBZ",
    "are": "VBP",
    "aren't": "VBP",
    "was": "VBD",
    "wasn't": "VBD",
    "were": "VBD",
    "weren't": "VBD",
    "be": "VB",
    "been": "VBN",
    "being": "VBG",
    "have": "VBP",
    "haven't": "VBP",
    "has": "VBZ",
    "hasn't": "VBZ",
    "had": "VBD",
    "hadn't": "VBD",
    "do": "VBP",
    "don't": "VBP",
    "does": "VBZ",
    "doesn't": "VBZ",
    "did": "VBD",
    "didn't": "VBD",
    "can": "MD",
    "can't": "MD",
    "cannot": "MD",
    "could": "MD",
    "couldn't": "MD",
    "will": "MD",
    "won't": "MD",
    "would": "MD",
    "wouldn't": "MD",
    "should": "MD",
    "shouldn't": "MD",
    "may": "MD",
    "might": "MD",
    # Determiners & Prepositions
    "the": "DT",
    "a": "DT",
    "an": "DT",
    "this": "DT",
    "that": "DT",
    "these": "DT",
    "those": "DT",
    "in": "IN",
    "on": "IN",
    "at": "IN",
    "by": "IN",
    "for": "IN",
    "with": "IN",
    "from": "IN",
    "of": "IN",
    "to": "TO",
    "into": "IN",
    "through": "IN",
    "between": "IN",
    "among": "IN",
    "above": "IN",
    "below": "IN",
    "under": "IN",
    "over": "IN",
    # Conjunctions
    "and": "CC",
    "or": "CC",
    "but": "CC",
    "nor": "CC",
    # Imperative Verbs
    "show": "VB",
    "list": "VB",
    "find": "VB",
    "get": "VB",
    "display": "VB",
    "give": "VB",
    "calculate": "VB",
    "compute": "VB",
    "compare": "VB",
    "rank": "VB",
    "sort": "VB",
    "count": "VB",
    # Adjectives & Superlatives
    "average": "JJ",
    "mean": "JJ",
    "total": "JJ",
    "all": "DT",
    "high": "JJ",
    "higher": "JJR",
    "highest": "JJS",
    "low": "JJ",
    "lower": "JJR",
    "lowest": "JJS",
    "top": "JJ",
    "bottom": "JJ",
    "best": "JJS",
    "worst": "JJS",
    "active": "JJ",
    "probation": "NN",
    "graduated": "JJ",
    # Academic Nouns
    "student": "NN",
    "students": "NNS",
    "instructor": "NN",
    "instructors": "NNS",
    "faculty": "NN",
    "professor": "NN",
    "professors": "NNS",
    "course": "NN",
    "courses": "NNS",
    "offering": "NN",
    "offerings": "NNS",
    "section": "NN",
    "sections": "NNS",
    "department": "NN",
    "departments": "NNS",
    "enrollment": "NN",
    "enrollments": "NNS",
    "assessment": "NN",
    "assessments": "NNS",
    "exam": "NN",
    "exams": "NNS",
    "midterm": "NN",
    "final": "NN",
    "quiz": "NN",
    "quizzes": "NNS",
    "project": "NN",
    "projects": "NNS",
    "mark": "NN",
    "marks": "NNS",
    "score": "NN",
    "scores": "NNS",
    "grade": "NN",
    "grades": "NNS",
    "gpa": "NN",
    "cgpa": "NN",
    "attendance": "NN",
    "term": "NN",
    "terms": "NNS",
    "semester": "NN",
    "semesters": "NNS",
    "year": "NN",
    "years": "NNS",
    # Department Acronyms
    "ai": "NNP",
    "cs": "NNP",
    "ee": "NNP",
    "me": "NNP",
    "math": "NNP",
}

# Irregular morphological lemmatization mapping
LEMMA_EXCEPTIONS = {
    "students": "student",
    "courses": "course",
    "instructors": "instructor",
    "professors": "professor",
    "departments": "department",
    "offerings": "offering",
    "sections": "section",
    "enrollments": "enrollment",
    "assessments": "assessment",
    "exams": "exam",
    "quizzes": "quiz",
    "projects": "project",
    "marks": "mark",
    "scores": "score",
    "grades": "grade",
    "semesters": "semester",
    "terms": "term",
    "years": "year",
    "highest": "high",
    "higher": "high",
    "lowest": "low",
    "lower": "low",
    "best": "good",
    "better": "good",
    "worst": "bad",
    "worse": "bad",
    "has": "have",
    "had": "have",
    "is": "be",
    "was": "be",
    "were": "be",
    "are": "be",
    "did": "do",
    "does": "do",
    "done": "do",
    "been": "be",
    "scored": "score",
    "scoring": "score",
    "taught": "teach",
    "teaches": "teach",
    "teaching": "teach",
    "enrolled": "enroll",
    "enrolling": "enroll",
    "matrices": "matrix",
}


class NLPPreprocessor:
    """Core NLP Preprocessor providing tokenization, normalization, lemmatization,

    30 supported Penn Treebank-style POS tags (23 grammatical tags + 7 punctuation/symbol tags),
    and n-gram extraction.
    Operates as a deterministic rule-based approximation (lexicon lookup + morphological suffix heuristics)
    100% offline without external statistical taggers (HMM/CRF/Perceptron) or NLTK corpus downloads.
    """

    def __init__(self) -> None:
        # Regex token pattern matching numbers with decimals, words with contractions, and symbols
        self._token_pattern = re.compile(r"\b\d+\.\d+\b|\b\w+(?:'\w+)?\b|[^\w\s]")

    def normalize(self, query: str) -> str:
        """Cleans and normalizes query text by stripping control characters and trimming."""
        if not query:
            return ""
        # Remove null bytes, non-printable characters
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", query)
        # Collapse multiple spaces
        return " ".join(cleaned.strip().split())

    def tokenize(self, text: str) -> List[str]:
        """Tokenizes input string into a list of word, numeric, and punctuation tokens."""
        if not text:
            return []
        return self._token_pattern.findall(text)

    def lemmatize(self, word: str, pos: str = "NN") -> str:
        """Deterministically lemmatizes an English word to its dictionary root form."""
        lower = word.lower()

        # Clean possessive endings (e.g. student's -> student)
        if lower.endswith("'s"):
            lower = lower[:-2]
        elif lower.endswith("'") and len(lower) > 2:
            lower = lower[:-1]

        # Check explicit exception table
        if lower in LEMMA_EXCEPTIONS:
            return LEMMA_EXCEPTIONS[lower]


        # Rule-based morphological suffix stripping
        if pos.startswith("N"):  # Noun
            if lower.endswith("ies") and len(lower) > 4:
                return lower[:-3] + "y"
            if lower.endswith("sses") or lower.endswith("shes") or lower.endswith("ches") or lower.endswith("xes"):
                return lower[:-2]
            if lower.endswith("s") and not lower.endswith("ss") and len(lower) > 2:
                return lower[:-1]
        elif pos.startswith("V"):  # Verb
            if lower.endswith("ing") and len(lower) > 4:
                return lower[:-3]
            if lower.endswith("ed") and len(lower) > 3:
                return lower[:-2] if not lower.endswith("eed") else lower[:-1]
        elif pos.startswith("J"):  # Adjective
            if lower.endswith("est") and len(lower) > 4:
                return lower[:-3]
            if lower.endswith("er") and len(lower) > 3:
                return lower[:-2]

        return lower

    def pos_tag(self, tokens: List[str]) -> List[Tuple[str, str]]:
        """Applies deterministic rule-based POS tagging using 30 supported Penn Treebank-style POS tags (23 grammatical tags + 7 punctuation/symbol tags)."""
        tagged: List[Tuple[str, str]] = []

        for token in tokens:
            lower = token.lower()

            # Punctuation tags
            if token in (".", "!", "?"):
                tagged.append((token, "."))
            elif token in (",", ";"):
                tagged.append((token, ","))
            elif token in ("(", "[", "{"):
                tagged.append((token, "("))
            elif token in (")", "]", "}"):
                tagged.append((token, ")"))
            elif token in (":", "--", "-"):
                tagged.append((token, ":"))
            elif token in ("%", "$"):
                tagged.append((token, token))
            elif re.match(r"^\d+(?:\.\d+)?$", token):
                tagged.append((token, "CD"))  # Cardinal number
            elif lower in POS_TAG_MAP:
                tagged.append((token, POS_TAG_MAP[lower]))
            elif lower.endswith("'s") or lower.endswith("’s"):
                # Possessive token (e.g. student's, Alice's). In standard Penn Treebank,
                # clitics ('s) are tokenized separately. Since QueryMind's tokenizer
                # preserves contractions and possessives as single units, we tag the composite token
                # by its base noun class (NN for academic entities, NNP for capitalized names).
                base = lower[:-2]
                if base in POS_TAG_MAP:
                    base_tag = POS_TAG_MAP[base]
                    tagged.append((token, "NN" if base_tag in ("NN", "NNS") else base_tag))
                elif token[0].isupper():
                    tagged.append((token, "NNP"))
                else:
                    tagged.append((token, "NN"))
            elif token.isupper() and len(token) <= 5:
                tagged.append((token, "NNP"))  # Proper Noun / Acronym
            elif token[0].isupper() and token[1:].islower():
                tagged.append((token, "NNP"))  # Proper Noun (e.g. Names)
            elif lower.endswith("ly"):
                tagged.append((token, "RB"))  # Adverb
            elif lower.endswith("tion") or lower.endswith("ment") or lower.endswith("ness"):
                tagged.append((token, "NN"))  # Noun
            elif lower.endswith("s") and len(lower) > 2:
                tagged.append((token, "NNS"))  # Plural noun
            else:
                tagged.append((token, "NN"))  # Default noun

        return tagged

    def extract_word_ngrams(self, tokens: List[str]) -> Dict[str, List[str]]:
        """Extracts word-level unigrams, bigrams, and trigrams."""
        # Filter alphanumeric tokens for clean n-grams
        words = [t.lower() for t in tokens if re.search(r"\w", t)]

        unigrams = list(words)
        bigrams = [" ".join(words[i : i + 2]) for i in range(len(words) - 1)]
        trigrams = [" ".join(words[i : i + 3]) for i in range(len(words) - 2)]

        return {
            "unigrams": unigrams,
            "bigrams": bigrams,
            "trigrams": trigrams,
        }

    def extract_char_ngrams(self, text: str, n: int = 3) -> List[str]:
        """Extracts sliding character n-grams from normalized text."""
        cleaned = re.sub(r"\s+", " ", text.lower().strip())
        if len(cleaned) < n:
            return [cleaned] if cleaned else []
        return [cleaned[i : i + n] for i in range(len(cleaned) - n + 1)]

    def preprocess(self, query: str) -> Dict:
        """Executes the complete preprocessing pipeline and produces the diagnostic payload."""
        normalized = self.normalize(query)
        tokens = self.tokenize(normalized)
        pos_tags = self.pos_tag(tokens)

        # Lemmatize each token using its assigned POS tag
        lemmas = [self.lemmatize(token, pos) for token, pos in pos_tags]

        word_ngrams = self.extract_word_ngrams(tokens)
        char_ngrams = self.extract_char_ngrams(normalized, n=3)

        return {
            "raw_query": query,
            "normalized_query": normalized,
            "tokens": tokens,
            "lemmas": lemmas,
            "pos_tags": pos_tags,
            "word_ngrams": word_ngrams,
            "char_ngrams": char_ngrams,
        }


# Global singleton instance
_cached_preprocessor: NLPPreprocessor | None = None


def get_nlp_preprocessor() -> NLPPreprocessor:
    """Returns the cached singleton NLPPreprocessor instance."""
    global _cached_preprocessor
    if _cached_preprocessor is None:
        _cached_preprocessor = NLPPreprocessor()
    return _cached_preprocessor


nlp_preprocessor = get_nlp_preprocessor()

