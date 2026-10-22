import csv
import io
import json
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.exceptions import DatasetImportError, QuestionNotFoundError
from app.core.logging import get_logger
from app.db.repositories.question_repository import QuestionRepository
from app.schemas.question import (
    DifficultyEnum,
    QuestionCreate,
    QuestionFilterParams,
    QuestionImportResult,
    QuestionSafe,
    SubjectEnum,
)
from app.utils.validators import validate_question_record

logger = get_logger("app.services.question")


class QuestionService:
    """
    Manages question retrieval, student-safe formatting, and dataset ingestion.
    """

    def __init__(self, repo: Optional[QuestionRepository] = None) -> None:
        self.repo = repo or QuestionRepository()

    def to_safe_question(self, doc: Dict[str, Any]) -> QuestionSafe:
        """
        Sanitize a question document by strictly omitting reference answers and hidden key concepts.
        """
        return QuestionSafe(
            question_id=doc["question_id"],
            subject=doc["subject"],
            topic=doc["topic"],
            difficulty=doc["difficulty"],
            question=doc["question"],
            tags=doc.get("tags", []),
        )

    async def get_question_safe(self, question_id: str) -> QuestionSafe:
        """Retrieve question by ID in student-safe format."""
        doc = await self.repo.get_by_id(question_id)
        if not doc:
            raise QuestionNotFoundError(f"Question with ID '{question_id}' not found.")
        return self.to_safe_question(doc)

    async def get_raw_question(self, question_id: str) -> Dict[str, Any]:
        """Internal retrieval of raw question including ground-truth reference answer."""
        doc = await self.repo.get_by_id(question_id)
        if not doc:
            raise QuestionNotFoundError(f"Question with ID '{question_id}' not found.")
        return doc

    async def list_safe_questions(self, params: QuestionFilterParams) -> List[QuestionSafe]:
        """List questions matching query parameters in student-safe format."""
        docs = await self.repo.list_questions(
            subject=params.subject.value if params.subject else None,
            topic=params.topic,
            difficulty=params.difficulty.value if params.difficulty else None,
        )
        return [self.to_safe_question(d) for d in docs]

    async def select_initial_question(
        self,
        subject: SubjectEnum,
        difficulty: Optional[DifficultyEnum] = None,
    ) -> QuestionSafe:
        """
        Select an eligible initial question for a viva session.
        Defaults to configured initial difficulty (typically medium or easy).
        """
        target_diff = difficulty.value if difficulty else settings.INITIAL_DIFFICULTY
        doc = await self.repo.get_random_question(
            subject=subject.value,
            difficulty=target_diff,
            exclude_ids=[],
        )
        if not doc:
            # Fall back to any question for this subject
            doc = await self.repo.get_random_question(subject=subject.value, exclude_ids=[])
        if not doc:
            raise QuestionNotFoundError(f"No questions available in dataset for subject '{subject.value}'.")
        return self.to_safe_question(doc)

    async def import_from_json(self, json_content: str) -> QuestionImportResult:
        """Import questions from raw JSON string (array of objects)."""
        try:
            records = json.loads(json_content)
            if not isinstance(records, list):
                raise DatasetImportError("JSON dataset must be a top-level list of objects.")
        except json.JSONDecodeError as exc:
            raise DatasetImportError(f"Malformed JSON dataset: {str(exc)}")

        return await self._process_and_import(records)

    async def import_from_csv(self, csv_content: str) -> QuestionImportResult:
        """Import questions from CSV text."""
        records: List[Dict[str, Any]] = []
        try:
            reader = csv.DictReader(io.StringIO(csv_content))
            for row in reader:
                # Parse list fields
                concepts_raw = row.get("key_concepts", "")
                concepts = [c.strip() for c in concepts_raw.replace(";", "|").split("|") if c.strip()]

                tags_raw = row.get("tags", "")
                tags = [t.strip() for t in tags_raw.replace(";", "|").split("|") if t.strip()]

                row["key_concepts"] = concepts
                row["tags"] = tags
                records.append(row)
        except Exception as exc:
            raise DatasetImportError(f"Failed to parse CSV dataset: {str(exc)}")

        return await self._process_and_import(records)

    async def _process_and_import(self, records: List[Dict[str, Any]]) -> QuestionImportResult:
        """Validate, normalize, and batch import questions."""
        valid_questions: List[Dict[str, Any]] = []
        invalid_records: List[str] = []
        seen_ids = set()

        for idx, rec in enumerate(records):
            is_valid, error_msg = validate_question_record(rec, idx)
            if not is_valid:
                invalid_records.append(error_msg)
                continue

            q_id = rec["question_id"].strip()
            if q_id in seen_ids:
                invalid_records.append(f"Duplicate question_id '{q_id}' within batch at index {idx}")
                continue
            seen_ids.add(q_id)

            existing = await self.repo.get_by_id(q_id)
            if existing:
                invalid_records.append(f"Question ID '{q_id}' already exists in database.")
                continue

            # Normalized record
            normalized = {
                "question_id": q_id,
                "subject": rec["subject"].upper().strip(),
                "topic": rec["topic"].strip(),
                "difficulty": rec["difficulty"].lower().strip(),
                "question": rec["question"].strip(),
                "reference_answer": rec["reference_answer"].strip(),
                "key_concepts": rec["key_concepts"],
                "tags": rec.get("tags", []),
                "is_verified_metadata": rec.get("is_verified_metadata", True),
            }
            valid_questions.append(normalized)

        imported_count = 0
        if valid_questions:
            imported_count = await self.repo.insert_many(valid_questions)

        return QuestionImportResult(
            total_processed=len(records),
            imported=imported_count,
            skipped_duplicates=len(records) - len(valid_questions),
            invalid_records=invalid_records,
        )


question_service = QuestionService()
