from typing import List, Optional
from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.core.exceptions import DatasetImportError, QuestionNotFoundError
from app.dependencies import verify_admin_api_key
from app.schemas.question import (
    DifficultyEnum,
    QuestionFilterParams,
    QuestionImportResult,
    QuestionSafe,
    SubjectEnum,
)
from app.services.question_service import question_service

router = APIRouter(prefix="/questions", tags=["Questions"])


@router.get(
    "",
    response_model=List[QuestionSafe],
    summary="Filter Questions",
    description="Retrieve student-safe question representations filtered by subject, topic, or difficulty.",
)
async def list_questions(
    subject: Optional[SubjectEnum] = Query(None, description="Subject filter ('OS', 'DBMS', 'CN')"),
    topic: Optional[str] = Query(None, description="Topic filter (e.g. 'Deadlocks')"),
    difficulty: Optional[DifficultyEnum] = Query(None, description="Difficulty filter ('easy', 'medium', 'hard')"),
) -> List[QuestionSafe]:
    params = QuestionFilterParams(subject=subject, topic=topic, difficulty=difficulty)
    return await question_service.list_safe_questions(params)


@router.get(
    "/{question_id}",
    response_model=QuestionSafe,
    summary="Get Question by ID",
    description="Retrieve a single question in student-safe format. Reference answers are strictly omitted.",
)
async def get_question(question_id: str) -> QuestionSafe:
    return await question_service.get_question_safe(question_id)


@router.post(
    "/import",
    response_model=QuestionImportResult,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_admin_api_key)],
    summary="Import Question Dataset",
    description="Restricted administrative endpoint to ingest questions from JSON or CSV file uploads.",
)
async def import_questions(
    file: UploadFile = File(..., description="JSON or CSV question dataset file")
) -> QuestionImportResult:
    content_bytes = await file.read()
    text = content_bytes.decode("utf-8")
    filename = file.filename or ""

    if filename.endswith(".csv"):
        return await question_service.import_from_csv(text)
    elif filename.endswith(".json"):
        return await question_service.import_from_json(text)
    else:
        # Auto-detect format by checking for '['
        if text.strip().startswith("["):
            return await question_service.import_from_json(text)
        elif "," in text and "\n" in text:
            return await question_service.import_from_csv(text)
        raise DatasetImportError("File format could not be determined. Please upload a .json or .csv file.")
