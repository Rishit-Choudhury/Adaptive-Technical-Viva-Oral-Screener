from fastapi import APIRouter
from app.schemas.report import FinalReport
from app.services.session_service import session_service

router = APIRouter(tags=["Reports"])


@router.get(
    "/sessions/{session_id}/report",
    response_model=FinalReport,
    summary="Get Final Viva Report",
    description="Retrieve the complete examination report including aggregate metrics, topic breakdowns, and revision recommendations.",
)
async def get_session_report(session_id: str) -> FinalReport:
    return await session_service.get_session_report(session_id)
