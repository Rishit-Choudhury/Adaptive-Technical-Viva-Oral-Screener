import re
from typing import List, Set


def normalize_text(text: str) -> str:
    """
    Standardize text by stripping excess whitespace and normalizing casing.
    """
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_keywords(text: str) -> Set[str]:
    """
    Extract meaningful normalized word tokens for keyword matching.
    """
    if not text:
        return set()
    words = re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", text.lower())
    # Exclude common stop words
    stop_words = {
        "the", "and", "that", "this", "with", "for", "from", "are", "was", "were",
        "have", "has", "had", "which", "when", "where", "what", "how", "why",
        "can", "could", "will", "would", "should", "not", "but", "also"
    }
    return {w for w in words if w not in stop_words}


def compute_heuristic_concept_coverage(
    student_answer: str,
    key_concepts: List[str]
) -> tuple[List[str], List[str], float]:
    """
    Fast heuristic matching of key concepts in text.
    Used for standalone validation, testing, and fallback when LLM is unavailable.
    Returns (covered_concepts, missing_concepts, coverage_score_0_100).
    """
    if not key_concepts:
        return [], [], 100.0

    if not student_answer or not student_answer.strip():
        return [], list(key_concepts), 0.0

    normalized_answer = student_answer.lower()
    covered = []
    missing = []

    for concept in key_concepts:
        concept_normalized = concept.lower()
        # Direct phrase match
        if concept_normalized in normalized_answer:
            covered.append(concept)
            continue

        # Sub-word token overlap
        concept_tokens = [t for t in re.findall(r"\w+", concept_normalized) if len(t) > 2]
        if concept_tokens and all(tok in normalized_answer for tok in concept_tokens):
            covered.append(concept)
        else:
            missing.append(concept)

    score = round((len(covered) / len(key_concepts)) * 100.0, 2)
    return covered, missing, score
