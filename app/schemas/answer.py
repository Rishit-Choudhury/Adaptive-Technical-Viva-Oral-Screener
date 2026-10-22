from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.evaluation import EvaluationResult
from app.schemas.question import QuestionSafe


class TextAnswerRequest(BaseModel):
    """Payload for submitting a written viva answer."""
    question_id: Optional[str] = Field(default=None, description="Optional question ID being answered for duplicate verification")
    student_answer: str = Field(..., min_length=1, description="Student's answer text")


class AudioAnswerResponse(BaseModel):
    """Payload returned following speech-to-text audio transcription and evaluation."""
    transcript: str = Field(..., description="Transcribed text from the audio answer")
    evaluation: EvaluationResult = Field(..., description="Evaluation analysis and scoring")
    next_question: Optional[QuestionSafe] = Field(default=None, description="Next adaptive question if available")
    is_session_completed: bool = Field(default=False, description="Whether the session reached completion")


class AnswerSubmissionResponse(BaseModel):
    """Payload returned following text answer evaluation and topic mastery update."""
    question_id: str
    student_answer: str
    evaluation: EvaluationResult
    next_question: Optional[QuestionSafe] = None
    is_session_completed: bool = False
