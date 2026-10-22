from typing import Optional
from fastapi import APIRouter, File, UploadFile, status

from app.schemas.answer import AnswerSubmissionResponse, AudioAnswerResponse, TextAnswerRequest
from app.schemas.question import QuestionSafe
from app.schemas.report import FinalReport
from app.schemas.session import SessionCreate, SessionHistoryResponse, SessionResponse
from app.services.session_service import session_service
from app.utils.validators import validate_audio_file

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Viva Session",
    description="Initiates a new viva examination session and selects the initial adaptive question.",
)
async def create_session(payload: SessionCreate) -> SessionResponse:
    return await session_service.create_session(payload)


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Get Session Status",
    description="Retrieve the current status, answered count, and metadata for a viva session.",
)
async def get_session(session_id: str) -> SessionResponse:
    return await session_service.get_session(session_id)


@router.get(
    "/{session_id}/current-question",
    response_model=QuestionSafe,
    summary="Get Current Question",
    description="Fetch the active question assigned to the student in this session.",
)
async def get_current_question(session_id: str) -> QuestionSafe:
    return await session_service.get_current_question(session_id)


@router.post(
    "/{session_id}/answers",
    response_model=AnswerSubmissionResponse,
    summary="Submit Text Answer",
    description="Submit a written viva answer. Runs semantic similarity, LLM concept analysis, and adaptive scoring.",
)
async def submit_text_answer(
    session_id: str,
    payload: TextAnswerRequest,
) -> AnswerSubmissionResponse:
    return await session_service.submit_text_answer(
        session_id=session_id,
        student_answer=payload.student_answer,
        question_id=payload.question_id,
    )


@router.post(
    "/{session_id}/audio-answers",
    response_model=AudioAnswerResponse,
    summary="Submit Audio Answer",
    description="Upload a recorded oral audio answer. Transcribes via Faster-Whisper, evaluates concepts, and updates state.",
)
async def submit_audio_answer(
    session_id: str,
    file: UploadFile = File(..., description="Audio recording of oral answer"),
) -> AudioAnswerResponse:
    content = await file.read()
    validate_audio_file(file, content)
    return await session_service.submit_audio_answer(
        session_id=session_id,
        audio_bytes=content,
        filename=file.filename or "answer.wav",
    )


@router.post(
    "/{session_id}/next-question",
    response_model=Optional[QuestionSafe],
    summary="Fetch Next Adaptive Question",
    description="Retrieves the next adaptive question based on missing concepts and topic mastery.",
)
async def next_question(session_id: str) -> Optional[QuestionSafe]:
    return await session_service.advance_to_next_question(session_id)


@router.post(
    "/{session_id}/complete",
    response_model=FinalReport,
    summary="Complete Viva Session",
    description="Explicitly marks the session as finished and generates the final performance report.",
)
async def complete_session(session_id: str) -> FinalReport:
    return await session_service.complete_session(session_id)


@router.get(
    "/{session_id}/history",
    response_model=SessionHistoryResponse,
    summary="Get Session History",
    description="Retrieve the complete chronological history of questions, answers, and evaluations.",
)
async def get_session_history(session_id: str) -> SessionHistoryResponse:
    return await session_service.get_session_history(session_id)
