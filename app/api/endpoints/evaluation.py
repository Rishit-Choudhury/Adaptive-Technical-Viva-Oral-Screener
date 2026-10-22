from fastapi import APIRouter
from app.schemas.evaluation import EvaluationPreviewRequest, EvaluationPreviewResponse
from app.services.evaluation_service import evaluation_service

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])


@router.post(
    "/preview",
    response_model=EvaluationPreviewResponse,
    summary="Preview Evaluation",
    description="Test answer evaluation and concept analysis on arbitrary text without mutating any persistent session.",
)
async def preview_evaluation(payload: EvaluationPreviewRequest) -> EvaluationPreviewResponse:
    return await evaluation_service.preview_evaluation(payload)
