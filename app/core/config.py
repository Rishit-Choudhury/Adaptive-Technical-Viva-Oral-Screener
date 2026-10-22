from functools import lru_cache
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings and environment variable definitions.
    Loaded from environment variables or .env file.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Application Information
    PROJECT_NAME: str = "Adaptive Technical Viva & Oral Screener"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # API Configuration
    API_V1_STR: str = "/api/v1"

    # CORS Origins
    CORS_ORIGINS: Union[List[str], str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(f"Invalid CORS_ORIGINS format: {v}")

    # MongoDB Configuration (PyMongo Asynchronous API)
    MONGODB_URL: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection string URI"
    )
    DATABASE_NAME: str = Field(
        default="adaptive_viva_db",
        description="Target database name"
    )
    MONGODB_MIN_POOL_SIZE: int = Field(
        default=10,
        description="Minimum connection pool size"
    )
    MONGODB_MAX_POOL_SIZE: int = Field(
        default=50,
        description="Maximum connection pool size"
    )
    MONGODB_SERVER_SELECTION_TIMEOUT_MS: int = Field(
        default=5000,
        description="Timeout in milliseconds for server selection"
    )

    # Machine Learning & AI Models
    SENTENCE_TRANSFORMER_MODEL: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence Transformers model for semantic similarity"
    )
    WHISPER_MODEL: str = Field(
        default="base",
        description="Faster-Whisper model size (tiny, base, small, medium)"
    )

    # LLM Provider Configuration
    LLM_PROVIDER: str = Field(
        default="mock",
        description="LLM provider: 'mock', 'groq', or 'openai'"
    )
    LLM_API_KEY: str = Field(
        default="",
        description="API key for the chosen LLM provider (Groq or OpenAI)"
    )
    LLM_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        description="LLM model name for conceptual analysis"
    )
    LLM_TIMEOUT_SECONDS: float = Field(
        default=15.0,
        description="Timeout for LLM API evaluation requests"
    )

    # Adaptive Viva Configuration & Thresholds
    INITIAL_DIFFICULTY: str = Field(
        default="medium",
        description="Default difficulty for the initial question ('easy', 'medium')"
    )
    LOW_SCORE_THRESHOLD: float = Field(
        default=50.0,
        description="Score threshold below which answer is considered weak (0-49)"
    )
    HIGH_SCORE_THRESHOLD: float = Field(
        default=80.0,
        description="Score threshold at or above which answer is considered excellent (80-100)"
    )
    MAX_QUESTIONS_PER_SESSION: int = Field(
        default=5,
        description="Maximum questions per viva session before automatic completion"
    )

    # Scoring Formula Weights (Must sum to 1.0)
    WEIGHT_CONCEPT_COVERAGE: float = Field(
        default=0.40,
        description="Weight for key concept coverage score"
    )
    WEIGHT_TECHNICAL_CORRECTNESS: float = Field(
        default=0.30,
        description="Weight for technical correctness score"
    )
    WEIGHT_SEMANTIC_SIMILARITY: float = Field(
        default=0.20,
        description="Weight for Sentence Transformer cosine similarity"
    )
    WEIGHT_REASONING_QUALITY: float = Field(
        default=0.10,
        description="Weight for reasoning quality score"
    )

    # Audio Constraints
    MAX_AUDIO_SIZE_MB: int = Field(
        default=20,
        description="Maximum allowed audio upload file size in Megabytes"
    )
    ALLOWED_AUDIO_EXTENSIONS: List[str] = Field(
        default=["wav", "mp3", "ogg", "m4a", "webm", "flac"],
        description="Permitted audio file extensions"
    )

    # Security & Admin Access
    ADMIN_API_KEY: str = Field(
        default="viva-admin-secret-key-2026",
        description="API Key required for restricted operations like dataset import"
    )

    # Logging
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Application logging level"
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings instance.
    """
    return Settings()


settings = get_settings()
