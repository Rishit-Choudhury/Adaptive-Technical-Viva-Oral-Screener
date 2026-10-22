from typing import List, Optional
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.evaluation import ScoringBreakdown

logger = get_logger("app.services.scoring")


class ScoringService:
    """
    Independent Python scoring engine implementing weighted multi-factor evaluation.
    Never relies on external LLM overall scores.
    """

    def __init__(
        self,
        weight_concept_coverage: Optional[float] = None,
        weight_technical_correctness: Optional[float] = None,
        weight_semantic_similarity: Optional[float] = None,
        weight_reasoning_quality: Optional[float] = None,
    ) -> None:
        self.w_concept = weight_concept_coverage or settings.WEIGHT_CONCEPT_COVERAGE
        self.w_tech = weight_technical_correctness or settings.WEIGHT_TECHNICAL_CORRECTNESS
        self.w_sem = weight_semantic_similarity or settings.WEIGHT_SEMANTIC_SIMILARITY
        self.w_reason = weight_reasoning_quality or settings.WEIGHT_REASONING_QUALITY

        # Validate weights sum to 1.0 (with small float tolerance)
        total = self.w_concept + self.w_tech + self.w_sem + self.w_reason
        if abs(total - 1.0) > 0.001:
            logger.warning("Scoring weights do not sum to 1.0 (sum=%.3f). Normalizing weights.", total)
            self.w_concept /= total
            self.w_tech /= total
            self.w_sem /= total
            self.w_reason /= total

    def calculate_scores(
        self,
        covered_concepts: List[str],
        expected_concepts: List[str],
        technical_correctness: float,
        semantic_similarity_raw: float,
        reasoning_quality: float,
    ) -> ScoringBreakdown:
        """
        Calculate weighted composite score from normalized components.
        All input scores must be on a 0-100 scale, except semantic_similarity_raw which is 0.0-1.0.
        """
        # 1. Concept Coverage (0-100)
        if expected_concepts:
            concept_coverage = (len(covered_concepts) / len(expected_concepts)) * 100.0
        else:
            concept_coverage = 100.0 if covered_concepts else 50.0
        concept_coverage = max(0.0, min(100.0, concept_coverage))

        # 2. Technical Correctness (0-100)
        tech_score = max(0.0, min(100.0, technical_correctness))

        # 3. Semantic Similarity (normalized to 0-100)
        sem_score = max(0.0, min(100.0, semantic_similarity_raw * 100.0))

        # 4. Reasoning Quality (0-100)
        reason_score = max(0.0, min(100.0, reasoning_quality))

        # Weighted calculation
        final_score_100 = (
            (concept_coverage * self.w_concept)
            + (tech_score * self.w_tech)
            + (sem_score * self.w_sem)
            + (reason_score * self.w_reason)
        )
        final_score_100 = round(max(0.0, min(100.0, final_score_100)), 2)
        final_score_10 = round(final_score_100 / 10.0, 2)

        return ScoringBreakdown(
            concept_coverage=round(concept_coverage, 2),
            technical_correctness=round(tech_score, 2),
            semantic_similarity=round(sem_score, 2),
            reasoning_quality=round(reason_score, 2),
            final_score_100=final_score_100,
            final_score_10=final_score_10,
            weights_applied={
                "concept_coverage": self.w_concept,
                "technical_correctness": self.w_tech,
                "semantic_similarity": self.w_sem,
                "reasoning_quality": self.w_reason,
            },
        )


scoring_service = ScoringService()
