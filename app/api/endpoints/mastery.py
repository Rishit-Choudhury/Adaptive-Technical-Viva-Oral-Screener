from fastapi import APIRouter
from app.schemas.mastery import SessionMasteryResponse
from app.services.mastery_service import mastery_service
from app.services.session_service import session_service

router = APIRouter(tags=["Mastery"])


@router.get(
    "/sessions/{session_id}/mastery",
    response_model=SessionMasteryResponse,
    summary="Get Topic Mastery",
    description="Retrieve topic-by-topic understanding, mastery scores, and tracked concept strengths and gaps.",
)
async def get_session_mastery(session_id: str) -> SessionMasteryResponse:
    session = await session_service.get_session(session_id)
    return await mastery_service.get_session_mastery(session_id, session.subject)
