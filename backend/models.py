"""Pydantic models = the exact shape of every request and response.

They are written to match frontend/app.py:
  - scores are numbers from 0 to 100 (the frontend shows "score / 100")
  - question fields: id, subject, topic, difficulty, question, model_answer,
    key_concepts, source
"""
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

QuestionId = Union[int, str]


# ---------------- questions ----------------
class QuestionOut(BaseModel):
    """Full question. Used inside sessions because the frontend requires every field."""
    model_config = ConfigDict(protected_namespaces=())   # allows the field name "model_answer"
    id: QuestionId
    subject: str
    topic: str
    difficulty: str
    question: str
    model_answer: str
    key_concepts: list[str]
    source: str = ""


class QuestionPreview(BaseModel):
    """Question WITHOUT the answer or concepts (used by the browsing endpoints)."""
    id: QuestionId
    subject: str
    topic: str
    difficulty: str
    question: str
    source: str = ""


class SubjectInfo(BaseModel):
    code: str
    name: str
    question_count: int
    topics: list[str]


# ---------------- sessions ----------------
class StartSessionRequest(BaseModel):
    subject: str = Field(..., min_length=1)
    num_questions: int = Field(5, ge=1, le=50)


class StartSessionResponse(BaseModel):
    session_id: str
    subject: str
    num_questions: int          # actual length (may be smaller than requested)
    question: QuestionOut
    reason: Optional[str] = None


class SessionIdRequest(BaseModel):
    """Body for /session/next and /session/end."""
    session_id: str = Field(..., min_length=1)


class AnswerRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    question_id: QuestionId
    answer: str = Field(..., max_length=5000)

    @field_validator("answer")
    @classmethod
    def answer_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Answer must not be empty")
        return v


class EvaluationResult(BaseModel):
    question_id: QuestionId
    score: Optional[float] = Field(None, ge=0, le=100)   # None = could not be scored
    max_score: int = 100
    strengths: list[str] = []
    covered_concepts: list[str] = []
    missing_concepts: list[str] = []
    suggestions: list[str] = []
    adaptation_note: Optional[str] = None
    source: str                                  # human-readable label shown in the UI
    mode: Literal["basic", "llm"]                # machine-readable evaluation mode
    attempt_number: int = 1


class NextQuestionResponse(BaseModel):
    question: Optional[QuestionOut] = None       # None = no more questions
    reason: Optional[str] = None
    session_complete: bool = False


# ---------------- report ----------------
class TopicPerformance(BaseModel):
    topic: str
    questions_attempted: int
    average_score: Optional[float]
    status: Literal["strong", "average", "weak", "unscored"]


class DifficultyPerformance(BaseModel):
    difficulty: str
    questions_attempted: int
    average_score: Optional[float]


class MissedConcept(BaseModel):
    concept: str
    times_missed: int


class QuestionSummary(BaseModel):
    number: int
    question_id: QuestionId
    topic: str
    difficulty: str
    question: str
    attempted: bool
    score: Optional[float]


class SessionReport(BaseModel):
    session_id: str
    subject: str
    status: str
    score_scale: str = "0-100"
    questions_served: int
    questions_attempted: int
    questions_skipped: int
    average_score: Optional[float]
    overall_rating: Optional[str]
    topic_performance: list[TopicPerformance]
    strong_topics: list[str]
    weak_topics: list[str]
    difficulty_performance: list[DifficultyPerformance]
    difficulty_note: Optional[str] = None
    covered_concepts: list[str]
    missing_concepts: list[str]
    most_missed_concepts: list[MissedConcept]
    revision_topics: list[str]
    difficulty_history: list[str]
    questions: list[QuestionSummary]
    evaluation_modes_used: list[str]
    ended_at: Optional[str] = None


# ---------------- voice / translation / health ----------------
class TranscriptionResponse(BaseModel):
    text: str
    model: str


class TranslateRequest(BaseModel):
    text: str = Field(..., max_length=5000)

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Text must not be empty")
        return v


class TranslateResponse(BaseModel):
    original_text: str
    translated_text: str
    model: str


class HealthResponse(BaseModel):
    status: str
    questions_loaded: dict[str, int]
    records_skipped: int
    warnings: list[str]
    evaluation_mode_configured: str
    llm_available: bool
    transcription_available: bool
