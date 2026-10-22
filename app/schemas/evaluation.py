from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ConceptAnalysisResult(BaseModel):
    """Structured analysis returned by the LLM evaluation agent."""
    technical_correctness: float = Field(
        ..., ge=0.0, le=100.0, description="Technical accuracy score from 0 to 100"
    )
    covered_concepts: List[str] = Field(
        default_factory=list, description="Expected concepts demonstrated in the student's answer"
    )
    missing_concepts: List[str] = Field(
        default_factory=list, description="Expected key concepts omitted by the student"
    )
    incorrect_statements: List[str] = Field(
        default_factory=list, description="Factually incorrect or misleading statements detected"
    )
    reasoning_quality: float = Field(
        ..., ge=0.0, le=100.0, description="Clarity and conceptual coherence score from 0 to 100"
    )
    feedback: str = Field(
        ..., description="Constructive qualitative feedback on the student's answer"
    )
    suggested_follow_up_focus: List[str] = Field(
        default_factory=list, description="Suggested concepts to probe in follow-up viva questions"
    )


class ScoringBreakdown(BaseModel):
    """Detailed score components calculated strictly by the backend scoring engine."""
    concept_coverage: float = Field(..., ge=0.0, le=100.0, description="Key concept coverage score (0-100)")
    technical_correctness: float = Field(..., ge=0.0, le=100.0, description="Technical correctness score (0-100)")
    semantic_similarity: float = Field(..., ge=0.0, le=100.0, description="Sentence Transformers cosine similarity score (0-100)")
    reasoning_quality: float = Field(..., ge=0.0, le=100.0, description="Reasoning and articulation quality score (0-100)")
    final_score_100: float = Field(..., ge=0.0, le=100.0, description="Weighted composite score out of 100")
    final_score_10: float = Field(..., ge=0.0, le=10.0, description="Weighted composite score out of 10")
    weights_applied: Dict[str, float] = Field(..., description="Weights applied in calculation")


class EvaluationResult(BaseModel):
    """Full evaluation record for a question response."""
    question_id: str
    student_answer: str
    scoring: ScoringBreakdown
    concept_analysis: ConceptAnalysisResult


class EvaluationPreviewRequest(BaseModel):
    """Input payload for previewing evaluation without updating a persistent session."""
    question_id: Optional[str] = None
    question: Optional[str] = None
    reference_answer: Optional[str] = None
    key_concepts: Optional[List[str]] = None
    student_answer: str = Field(..., min_length=1, description="Student's text response to evaluate")


class EvaluationPreviewResponse(BaseModel):
    """Response payload for evaluation preview."""
    question_id: Optional[str] = None
    scoring: ScoringBreakdown
    concept_analysis: ConceptAnalysisResult
