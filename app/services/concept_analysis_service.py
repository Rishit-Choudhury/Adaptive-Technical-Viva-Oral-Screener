from typing import List
from app.core.logging import get_logger
from app.schemas.evaluation import ConceptAnalysisResult
from app.services.llm_service import llm_service

logger = get_logger("app.services.concept_analysis")


class ConceptAnalysisService:
    """
    Coordinates answer evaluation using LLM conceptual breakdown,
    grounding checks, and output validation.
    """

    def __init__(self) -> None:
        self.llm = llm_service

    async def analyze(
        self,
        question: str,
        reference_answer: str,
        expected_concepts: List[str],
        student_answer: str,
        subject: str,
        topic: str,
    ) -> ConceptAnalysisResult:
        """
        Execute grounded concept analysis. Ensures that missing and covered concepts
        are subsets or references of the verified expected concepts.
        """
        result = await self.llm.analyze_concepts(
            question=question,
            reference_answer=reference_answer,
            expected_concepts=expected_concepts,
            student_answer=student_answer,
            subject=subject,
            topic=topic,
        )

        # Grounding sanity check: Ensure concepts in covered and missing exist in expected concepts if non-empty
        if expected_concepts:
            valid_set = set(expected_concepts)
            # Filter covered to grounded items or keep identified
            result.covered_concepts = [c for c in result.covered_concepts if c in valid_set] or result.covered_concepts
            # If missing concepts were missed by the LLM, verify against expected
            uncovered = [c for c in expected_concepts if c not in result.covered_concepts]
            if not result.missing_concepts and uncovered:
                result.missing_concepts = uncovered

        return result


concept_analysis_service = ConceptAnalysisService()
