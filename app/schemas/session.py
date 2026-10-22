from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.evaluation import EvaluationResult
from app.schemas.question import DifficultyEnum, QuestionSafe, SubjectEnum
from app.schemas.report import FinalReport


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class SessionCreate(BaseModel):
    """Payload to initiate a new viva examination session."""
    subject: SubjectEnum = Field(..., description="Target technical subject ('OS', 'DBMS', 'CN')")
    initial_difficulty: Optional[DifficultyEnum] = Field(
        default=None, description="Starting difficulty level. Defaults to configured initial_difficulty."
    )
    max_questions: Optional[int] = Field(
        default=None, ge=1, le=50, description="Session question limit. Defaults to system configuration."
    )


class AnswerRecord(BaseModel):
    """Recorded student answer, evaluation, and timestamps within a session."""
    question_id: str
    question_text: str
    topic: str
    difficulty: str
    student_answer: str
    transcript: Optional[str] = None
    evaluation: EvaluationResult
    answered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionResponse(BaseModel):
    """Public session view."""
    session_id: str
    subject: SubjectEnum
    status: SessionStatus
    current_question: Optional[QuestionSafe] = None
    previously_asked_question_ids: List[str] = Field(default_factory=list)
    questions_answered_count: int = 0
    max_questions: int
    current_overall_score_100: Optional[float] = None
    current_overall_score_10: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class SessionHistoryResponse(BaseModel):
    """Complete chronological audit history for a viva session."""
    session_id: str
    subject: SubjectEnum
    status: SessionStatus
    answers: List[AnswerRecord] = Field(default_factory=list)
    report: Optional[FinalReport] = None
