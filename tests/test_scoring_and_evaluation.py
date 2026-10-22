import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.embedding_service import embedding_service
from app.services.scoring_service import ScoringService
from app.utils.text_processing import compute_heuristic_concept_coverage


def test_scoring_formula_exact_calculation():
    """Verify weighted multi-factor scoring calculation."""
    scorer = ScoringService(
        weight_concept_coverage=0.40,
        weight_technical_correctness=0.30,
        weight_semantic_similarity=0.20,
        weight_reasoning_quality=0.10,
    )
    # 3 of 4 concepts covered -> 75%
    # Technical correctness -> 80%
    # Semantic similarity raw 0.85 -> 85%
    # Reasoning quality -> 90%
    # Expected: (75 * 0.40) + (80 * 0.30) + (85 * 0.20) + (90 * 0.10)
    #           = 30.0 + 24.0 + 17.0 + 9.0 = 80.0
    scores = scorer.calculate_scores(
        covered_concepts=["A", "B", "C"],
        expected_concepts=["A", "B", "C", "D"],
        technical_correctness=80.0,
        semantic_similarity_raw=0.85,
        reasoning_quality=90.0,
    )

    assert scores.concept_coverage == 75.0
    assert scores.technical_correctness == 80.0
    assert scores.semantic_similarity == 85.0
    assert scores.reasoning_quality == 90.0
    assert scores.final_score_100 == 80.0
    assert scores.final_score_10 == 8.0


def test_missing_concept_detection():
    """Verify heuristic concept coverage identifies missing vs covered concepts."""
    expected = ["Mutual exclusion", "Hold and wait", "No preemption", "Circular wait"]
    answer = "A deadlock requires mutual exclusion and hold and wait to occur."

    covered, missing, coverage = compute_heuristic_concept_coverage(answer, expected)
    assert "Mutual exclusion" in covered
    assert "Hold and wait" in covered
    assert "No preemption" in missing
    assert "Circular wait" in missing
    assert coverage == 50.0


def test_semantic_similarity_basic():
    """Verify semantic similarity returns valid float between 0 and 1."""
    text1 = "A deadlock occurs when processes hold resources and wait for others."
    text2 = "Deadlock happens when processes wait indefinitely for allocated resources."

    sim = embedding_service.compute_similarity(text1, text2)
    assert 0.0 <= sim <= 1.0
    assert sim > 0.3  # Should have strong conceptual overlap

    # Empty answer should return 0.0
    empty_sim = embedding_service.compute_similarity("", text2)
    assert empty_sim == 0.0


@pytest.mark.asyncio
async def test_evaluation_preview_endpoint():
    """Verify POST /api/v1/evaluation/preview endpoint returns structured score without live session."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "question": "What are ACID properties in database transactions?",
            "reference_answer": "Atomicity, Consistency, Isolation, and Durability ensure reliable transaction execution.",
            "key_concepts": ["Atomicity", "Consistency", "Isolation", "Durability"],
            "student_answer": "ACID stands for Atomicity, Consistency, Isolation, and Durability."
        }
        response = await client.post("/api/v1/evaluation/preview", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert "scoring" in data
        assert "final_score_100" in data["scoring"]
        assert "concept_analysis" in data
        assert len(data["concept_analysis"]["covered_concepts"]) > 0
