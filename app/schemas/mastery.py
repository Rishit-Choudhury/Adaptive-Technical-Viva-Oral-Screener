from typing import List
from pydantic import BaseModel, Field

from app.schemas.question import SubjectEnum


class TopicMastery(BaseModel):
    """Detailed mastery metrics for an individual subject topic."""
    subject: SubjectEnum = Field(..., description="Subject code ('OS', 'DBMS', 'CN')")
    topic: str = Field(..., description="Topic name")
    questions_attempted: int = Field(default=0, ge=0)
    average_score: float = Field(default=0.0, ge=0.0, le=100.0)
    recent_scores: List[float] = Field(default_factory=list)
    estimated_mastery: float = Field(default=0.0, ge=0.0, le=100.0, description="Estimated concept mastery percentage")
    strong_concepts: List[str] = Field(default_factory=list)
    weak_concepts: List[str] = Field(default_factory=list)
    difficulties_handled: List[str] = Field(default_factory=list)


class SessionMasteryResponse(BaseModel):
    """Cumulative topic mastery record for a student viva session."""
    session_id: str
    subject: SubjectEnum
    topics: List[TopicMastery]
