from fastapi import APIRouter

from app.api.endpoints import evaluation, health, mastery, questions, reports, sessions

api_router = APIRouter()

# Register endpoint routers
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(questions.router)
api_router.include_router(sessions.router)
api_router.include_router(evaluation.router)
api_router.include_router(mastery.router)
api_router.include_router(reports.router)
