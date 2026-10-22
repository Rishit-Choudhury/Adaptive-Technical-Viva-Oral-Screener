from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.api_v1.api import api_router
from app.api.endpoints.health import health_check
from app.core.config import settings
from app.core.exceptions import (
    AudioProcessingError,
    DatasetImportError,
    DuplicateAnswerError,
    QuestionNotFoundError,
    SessionNotFoundError,
    SessionStateError,
    VivaException,
)
from app.core.logging import get_logger, setup_logging
from app.db.mongodb import close_mongo_connection, connect_to_mongo
from app.db.repositories.answer_repository import AnswerRepository
from app.db.repositories.mastery_repository import MasteryRepository
from app.db.repositories.question_repository import QuestionRepository
from app.db.repositories.session_repository import SessionRepository

logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifecycle context manager:
    - Sets up logging
    - Establishes database connections on startup
    - Verifies repository indexes
    - Gracefully closes connections on shutdown
    """
    # Startup
    setup_logging(settings.LOG_LEVEL)
    logger.info("Starting up %s (v%s)...", settings.PROJECT_NAME, settings.VERSION)
    logger.info("Active environment: %s | Debug: %s", settings.ENVIRONMENT, settings.DEBUG)
    await connect_to_mongo()

    # Initialize repository indexes
    try:
        await QuestionRepository().create_indexes()
        await SessionRepository().create_indexes()
        await AnswerRepository().create_indexes()
        await MasteryRepository().create_indexes()
    except Exception as exc:
        logger.warning("Index initialization encountered an issue: %s", exc)

    yield

    # Shutdown
    logger.info("Shutting down %s...", settings.PROJECT_NAME)
    await close_mongo_connection()
    logger.info("Application shutdown complete.")


def create_application() -> FastAPI:
    """
    Application factory initializing FastAPI with middleware, routers, and handlers.
    """
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=(
            "Backend API for Adaptive Technical Viva & Oral Screener: "
            "Evaluates conceptual understanding in OS, DBMS, and Computer Networks "
            "using Speech-to-Text, Sentence Transformers, LLM Conceptual Analysis, "
            "and an Adaptive Question Engine."
        ),
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Configure CORS Middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Specific Domain Exception Handlers
    @application.exception_handler(QuestionNotFoundError)
    async def question_not_found_handler(request: Request, exc: QuestionNotFoundError) -> JSONResponse:
        logger.warning("Question not found on %s: %s", request.url.path, exc.message)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": exc.message, "status_code": status.HTTP_404_NOT_FOUND},
        )

    @application.exception_handler(SessionNotFoundError)
    async def session_not_found_handler(request: Request, exc: SessionNotFoundError) -> JSONResponse:
        logger.warning("Session not found on %s: %s", request.url.path, exc.message)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": exc.message, "status_code": status.HTTP_404_NOT_FOUND},
        )

    @application.exception_handler(DuplicateAnswerError)
    async def duplicate_answer_handler(request: Request, exc: DuplicateAnswerError) -> JSONResponse:
        logger.warning("Duplicate answer on %s: %s", request.url.path, exc.message)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": exc.message, "status_code": status.HTTP_409_CONFLICT},
        )

    @application.exception_handler(SessionStateError)
    async def session_state_handler(request: Request, exc: SessionStateError) -> JSONResponse:
        logger.warning("Session state violation on %s: %s", request.url.path, exc.message)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": exc.message, "status_code": status.HTTP_400_BAD_REQUEST},
        )

    @application.exception_handler(AudioProcessingError)
    async def audio_processing_handler(request: Request, exc: AudioProcessingError) -> JSONResponse:
        logger.warning("Audio processing error on %s: %s", request.url.path, exc.message)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": exc.message, "status_code": status.HTTP_400_BAD_REQUEST},
        )

    @application.exception_handler(DatasetImportError)
    async def dataset_import_handler(request: Request, exc: DatasetImportError) -> JSONResponse:
        logger.warning("Dataset import error on %s: %s", request.url.path, exc.message)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": exc.message, "status_code": status.HTTP_400_BAD_REQUEST},
        )

    @application.exception_handler(VivaException)
    async def viva_exception_handler(request: Request, exc: VivaException) -> JSONResponse:
        logger.warning("Viva domain error on %s: %s", request.url.path, exc.message)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": exc.message, "details": exc.details, "status_code": status.HTTP_400_BAD_REQUEST},
        )

    # Standard Starlette & Validation Exception Handlers
    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        logger.warning("HTTP %s on %s: %s", exc.status_code, request.url.path, exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "status_code": exc.status_code},
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning("Validation error on %s: %s", request.url.path, exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Request validation failed",
                "errors": exc.errors(),
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            },
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled server exception on %s: %s", request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal server error occurred.",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )

    # Root endpoint
    @application.get(
        "/",
        tags=["Root"],
        summary="API Root",
        description="Root entry point providing service metadata and documentation links.",
    )
    async def root():
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "documentation": "/docs",
            "health_check": f"{settings.API_V1_STR}/health",
        }

    # Route /api/v1 endpoints
    application.include_router(api_router, prefix=settings.API_V1_STR)

    # Direct /health alias
    application.add_api_route(
        "/health",
        endpoint=health_check,
        methods=["GET"],
        tags=["Health"],
        include_in_schema=False,
    )

    return application


app = create_application()
