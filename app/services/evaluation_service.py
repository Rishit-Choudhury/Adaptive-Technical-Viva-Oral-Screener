from typing import List, Optional
from app.core.logging import get_logger
from app.schemas.evaluation import (
    ConceptAnalysisResult,
    EvaluationPreviewRequest,
    EvaluationPreviewResponse,
    EvaluationResult,
    ScoringBreakdown,
)
from app.services.concept_analysis_service import concept_analysis_service
from app.services.embedding_service import embedding_service
from app.services.scoring_service import scoring_service

logger = get_logger("app.services.evaluation")


class EvaluationService:
    """
    End-to-end evaluation pipeline coordinating embedding similarity,
    LLM concept analysis, and independent Python scoring.
    """

    def __init__(self) -> None:
        self.embedding = embedding_service
        self.concept_analyzer = concept_analysis_service
        self.scorer = scoring_service

    async def evaluate_answer(
        self,
        question_id: str,
        question: str,
        reference_answer: str,
        expected_concepts: List[str],
        student_answer: str,
        subject: str,
        topic: str,
    ) -> EvaluationResult:
        """
        Evaluate student response and produce scoring breakdown and conceptual feedback.
        """
        logger.info("Evaluating answer for question %s (%s - %s)...", question_id, subject, topic)

        # 1. Semantic Similarity via Sentence Transformers
        semantic_sim = self.embedding.compute_similarity(student_answer, reference_answer)

        # 2. Concept Analysis via LLM agent
        analysis: ConceptAnalysisResult = await self.concept_analyzer.analyze(
            question=question,
            reference_answer=reference_answer,
            expected_concepts=expected_concepts,
            student_answer=student_answer,
            subject=subject,
            topic=topic,
        )

        # 3. Composite Scoring via Scoring Engine
        scoring: ScoringBreakdown = self.scorer.calculate_scores(
            covered_concepts=analysis.covered_concepts,
            expected_concepts=expected_concepts,
            technical_correctness=analysis.technical_correctness,
            semantic_similarity_raw=semantic_sim,
            reasoning_quality=analysis.reasoning_quality,
        )

        return EvaluationResult(
            question_id=question_id,
            student_answer=student_answer,
            scoring=scoring,
            concept_analysis=analysis,
        )

    async def preview_evaluation(self, req: EvaluationPreviewRequest) -> EvaluationPreviewResponse:
        """
        Preview evaluation without updating session state or persistence.
        """
        ref_ans = req.reference_answer or "A valid technical answer addressing the core concepts."
        concepts = req.key_concepts or []
        q_text = req.question or "Oral viva question."

        res = await self.evaluate_answer(
            question_id=req.question_id or "PREVIEW",
            question=q_text,
            reference_answer=ref_ans,
            expected_concepts=concepts,
            student_answer=req.student_answer,
            subject="General",
            topic="Preview",
        )

        return EvaluationPreviewResponse(
            question_id=req.question_id,
            scoring=res.scoring,
            concept_analysis=res.concept_analysis,
        )


evaluation_service = EvaluationService()
