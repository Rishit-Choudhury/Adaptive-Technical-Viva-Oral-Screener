import pytest
from app.db.repositories.question_repository import QuestionRepository
from app.schemas.evaluation import ConceptAnalysisResult, EvaluationResult, ScoringBreakdown
from app.schemas.question import SubjectEnum
from app.services.adaptive_engine import AdaptiveEngine


@pytest.fixture
async def seeded_repo():
    """Create in-memory question repository with easy, medium, and hard questions."""
    repo = QuestionRepository()
    questions = [
        {
            "question_id": "Q_EASY_01",
            "subject": "OS",
            "topic": "Deadlocks",
            "difficulty": "easy",
            "question": "What is mutual exclusion?",
            "reference_answer": "Mutual exclusion means only one process can hold a resource at a time.",
            "key_concepts": ["Mutual exclusion", "Resource sharing"],
        },
        {
            "question_id": "Q_MED_01",
            "subject": "OS",
            "topic": "Deadlocks",
            "difficulty": "medium",
            "question": "Explain Banker's Algorithm.",
            "reference_answer": "Banker's Algorithm avoids deadlocks by simulating safe resource allocation.",
            "key_concepts": ["Safe sequence", "Banker algorithm", "Available resources"],
        },
        {
            "question_id": "Q_HARD_01",
            "subject": "OS",
            "topic": "Deadlocks",
            "difficulty": "hard",
            "question": "Compare Deadlock Prevention and Avoidance performance trade-offs.",
            "reference_answer": "Prevention restricts conditions while avoidance calculates safe states dynamically.",
            "key_concepts": ["Coffman conditions", "Runtime overhead", "Cycle detection"],
        },
        {
            "question_id": "Q_MED_02",
            "subject": "OS",
            "topic": "Virtual Memory",
            "difficulty": "medium",
            "question": "What is TLB thrashing?",
            "reference_answer": "TLB thrashing occurs when the working set exceeds TLB capacity.",
            "key_concepts": ["TLB miss", "Working set", "Page table walk"],
        },
    ]
    await repo.insert_many(questions)
    return repo


@pytest.mark.asyncio
async def test_adaptive_difficulty_increase_on_excellent_score(seeded_repo):
    """Verify that an excellent score (>=80) targets harder questions."""
    engine = AdaptiveEngine(repo=seeded_repo)
    last_q = {
        "question_id": "Q_EASY_01",
        "subject": "OS",
        "topic": "Deadlocks",
        "difficulty": "easy",
    }
    last_eval = EvaluationResult(
        question_id="Q_EASY_01",
        student_answer="Mutual exclusion ensures only one process accesses the resource.",
        scoring=ScoringBreakdown(
            concept_coverage=100.0,
            technical_correctness=95.0,
            semantic_similarity=90.0,
            reasoning_quality=90.0,
            final_score_100=94.0,
            final_score_10=9.4,
            weights_applied={},
        ),
        concept_analysis=ConceptAnalysisResult(
            technical_correctness=95.0,
            covered_concepts=["Mutual exclusion", "Resource sharing"],
            missing_concepts=[],
            incorrect_statements=[],
            reasoning_quality=90.0,
            feedback="Excellent explanation.",
            suggested_follow_up_focus=["Safe sequence"],
        ),
    )

    next_q, reason = await engine.select_next_question(
        subject=SubjectEnum.OS,
        last_question=last_q,
        last_evaluation=last_eval,
        previously_asked_ids=["Q_EASY_01"],
    )

    assert next_q is not None
    assert next_q.question_id != "Q_EASY_01"  # Never repeat previous question
    assert next_q.difficulty in ["medium", "hard"]  # Difficulty increased from easy


@pytest.mark.asyncio
async def test_adaptive_difficulty_decrease_on_weak_score(seeded_repo):
    """Verify that a weak score (<50) targets easier questions and missing concepts."""
    engine = AdaptiveEngine(repo=seeded_repo)
    last_q = {
        "question_id": "Q_HARD_01",
        "subject": "OS",
        "topic": "Deadlocks",
        "difficulty": "hard",
    }
    last_eval = EvaluationResult(
        question_id="Q_HARD_01",
        student_answer="I don't know the exact trade-offs.",
        scoring=ScoringBreakdown(
            concept_coverage=0.0,
            technical_correctness=20.0,
            semantic_similarity=10.0,
            reasoning_quality=15.0,
            final_score_100=10.5,
            final_score_10=1.05,
            weights_applied={},
        ),
        concept_analysis=ConceptAnalysisResult(
            technical_correctness=20.0,
            covered_concepts=[],
            missing_concepts=["Mutual exclusion"],
            incorrect_statements=[],
            reasoning_quality=15.0,
            feedback="Needs review.",
            suggested_follow_up_focus=["Mutual exclusion"],
        ),
    )

    next_q, reason = await engine.select_next_question(
        subject=SubjectEnum.OS,
        last_question=last_q,
        last_evaluation=last_eval,
        previously_asked_ids=["Q_HARD_01"],
    )

    assert next_q is not None
    assert next_q.question_id != "Q_HARD_01"
    # Target should be easier than hard
    assert next_q.difficulty in ["easy", "medium"]
