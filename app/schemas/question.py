from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class SubjectEnum(str, Enum):
    OS = "OS"
    DBMS = "DBMS"
    CN = "CN"


class DifficultyEnum(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionBase(BaseModel):
    """Base question metadata shared between models."""
    question_id: str = Field(..., description="Unique question code, e.g. 'OS001'")
    subject: SubjectEnum = Field(..., description="Subject code ('OS', 'DBMS', 'CN')")
    topic: str = Field(..., description="Topic within the subject, e.g. 'Deadlocks'")
    difficulty: DifficultyEnum = Field(..., description="Difficulty level ('easy', 'medium', 'hard')")
    question: str = Field(..., description="Viva question text")


class QuestionSafe(QuestionBase):
    """
    Student-facing question schema.
    Strictly omits reference_answer, key_concepts, and evaluation metadata.
    """
    tags: List[str] = Field(default_factory=list, description="Public topic tags")


class QuestionCreate(QuestionBase):
    """Full question schema used for dataset ingestion and administration."""
    reference_answer: str = Field(..., description="Ground-truth reference answer")
    key_concepts: List[str] = Field(..., description="Key technical concepts expected in a complete answer")
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    is_verified_metadata: bool = Field(default=True, description="Whether difficulty & concepts are verified ground truth")


class QuestionInDB(QuestionCreate):
    """Question schema stored in MongoDB."""
    id: Optional[str] = Field(default=None, alias="_id")


class QuestionFilterParams(BaseModel):
    """Query parameter filter for question retrieval."""
    subject: Optional[SubjectEnum] = None
    topic: Optional[str] = None
    difficulty: Optional[DifficultyEnum] = None


class QuestionImportResult(BaseModel):
    """Summary of a dataset import batch."""
    total_processed: int
    imported: int
    skipped_duplicates: int
    invalid_records: List[str] = Field(default_factory=list)
