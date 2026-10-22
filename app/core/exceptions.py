"""
Custom application exception classes for structured error handling.
"""
from typing import Any, Dict, Optional


class VivaException(Exception):
    """Base exception for all application-specific errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class QuestionNotFoundError(VivaException):
    """Raised when a requested question is not found in the database."""
    pass


class SessionNotFoundError(VivaException):
    """Raised when a requested session is not found in the database."""
    pass


class SessionStateError(VivaException):
    """Raised when an operation is invalid for the current session state."""
    pass


class DuplicateAnswerError(VivaException):
    """Raised when an answer is submitted for an already answered question."""
    pass


class AudioProcessingError(VivaException):
    """Raised when audio validation, processing, or transcription fails."""
    pass


class LLMProviderError(VivaException):
    """Raised when an external LLM call times out, fails, or returns invalid data."""
    pass


class DatasetImportError(VivaException):
    """Raised when dataset parsing, validation, or database ingestion fails."""
    pass


class ModelLoadError(VivaException):
    """Raised when loading an embedding or speech-to-text model fails."""
    pass
