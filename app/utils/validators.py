from typing import Any, Dict, List, Tuple
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import AudioProcessingError, DatasetImportError
from app.schemas.question import DifficultyEnum, SubjectEnum


def validate_audio_file(file: UploadFile, content: bytes) -> None:
    """
    Validate that an uploaded audio file complies with supported extensions and size limits.
    """
    if not file.filename:
        raise AudioProcessingError("Uploaded audio file has no filename.")

    extension = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if extension not in settings.ALLOWED_AUDIO_EXTENSIONS:
        raise AudioProcessingError(
            f"Unsupported audio format '.{extension}'. Allowed: {', '.join(settings.ALLOWED_AUDIO_EXTENSIONS)}"
        )

    file_size_mb = len(content) / (1024 * 1024)
    if file_size_mb > settings.MAX_AUDIO_SIZE_MB:
        raise AudioProcessingError(
            f"Audio file size ({file_size_mb:.2f}MB) exceeds limit of {settings.MAX_AUDIO_SIZE_MB}MB."
        )

    if len(content) == 0:
        raise AudioProcessingError("Uploaded audio file is empty.")


def validate_question_record(record: Dict[str, Any], index: int) -> Tuple[bool, str]:
    """
    Validate a single question record dictionary before importing into MongoDB.
    """
    required_fields = ["question_id", "subject", "topic", "difficulty", "question", "reference_answer", "key_concepts"]
    missing = [f for f in required_fields if f not in record or not record[f]]
    if missing:
        return False, f"Record at index {index} is missing required fields: {', '.join(missing)}"

    # Subject validation
    subject = str(record["subject"]).upper().strip()
    valid_subjects = [s.value for s in SubjectEnum]
    if subject not in valid_subjects:
        return False, f"Invalid subject '{subject}' at index {index}. Must be one of {valid_subjects}"

    # Difficulty validation
    difficulty = str(record["difficulty"]).lower().strip()
    valid_difficulties = [d.value for d in DifficultyEnum]
    if difficulty not in valid_difficulties:
        return False, f"Invalid difficulty '{difficulty}' at index {index}. Must be one of {valid_difficulties}"

    # Key concepts validation
    concepts = record.get("key_concepts")
    if not isinstance(concepts, list) or len(concepts) == 0:
        return False, f"Record at index {index} has empty or non-list key_concepts."

    return True, ""
