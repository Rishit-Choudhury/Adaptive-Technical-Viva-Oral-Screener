"""
Central schema registry exporting domain models for API validation and serialization.
"""
from app.schemas.answer import AnswerSubmissionResponse, AudioAnswerResponse, TextAnswerRequest
from app.schemas.evaluation import (
    ConceptAnalysisResult,
    EvaluationPreviewRequest,
    EvaluationPreviewResponse,
    EvaluationResult,
    ScoringBreakdown,
)
from app.schemas.health import DatabaseHealth, HealthCheckResponse
from app.schemas.mastery import SessionMasteryResponse, TopicMastery
from app.schemas.question import (
    DifficultyEnum,
    QuestionBase,
    QuestionCreate,
    QuestionFilterParams,
    QuestionImportResult,
    QuestionInDB,
    QuestionSafe,
    SubjectEnum,
)
from app.schemas.report import FinalReport, TopicPerformance
from app.schemas.session import (
    AnswerRecord,
    SessionCreate,
    SessionHistoryResponse,
    SessionResponse,
    SessionStatus,
)

__all__ = [
    "HealthCheckResponse",
    "DatabaseHealth",
    "SubjectEnum",
    "DifficultyEnum",
    "QuestionBase",
    "QuestionSafe",
    "QuestionCreate",
    "QuestionInDB",
    "QuestionFilterParams",
    "QuestionImportResult",
    "ConceptAnalysisResult",
    "ScoringBreakdown",
    "EvaluationResult",
    "EvaluationPreviewRequest",
    "EvaluationPreviewResponse",
    "TextAnswerRequest",
    "AudioAnswerResponse",
    "AnswerSubmissionResponse",
    "TopicMastery",
    "SessionMasteryResponse",
    "TopicPerformance",
    "FinalReport",
    "SessionStatus",
    "SessionCreate",
    "SessionResponse",
    "SessionHistoryResponse",
    "AnswerRecord",
]
