from datetime import datetime, timezone
from typing import List
from pydantic import BaseModel, Field

from app.schemas.question import SubjectEnum


class TopicPerformance(BaseModel):
    """Aggregated topic performance breakdown in the final report."""
    topic: str
    questions_attempted: int
    average_score: float
    mastery_percentage: float
    mastery_rating: str  # e.g., "Proficient", "Developing", "Needs Review"


class FinalReport(BaseModel):
    """Comprehensive performance report generated at the completion of a viva session."""
    session_id: str
    subject: SubjectEnum
    status: str
    overall_score_100: float = Field(..., ge=0.0, le=100.0)
    overall_score_10: float = Field(..., ge=0.0, le=10.0)
    questions_attempted: int = Field(..., ge=0)
    average_answer_score: float = Field(..., ge=0.0, le=100.0)
    topic_wise_performance: List[TopicPerformance] = Field(default_factory=list)
    strong_concepts: List[str] = Field(default_factory=list)
    weak_concepts: List[str] = Field(default_factory=list)
    frequently_missed_concepts: List[str] = Field(default_factory=list)
    difficulty_levels_handled: List[str] = Field(default_factory=list)
    revision_recommendations: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
