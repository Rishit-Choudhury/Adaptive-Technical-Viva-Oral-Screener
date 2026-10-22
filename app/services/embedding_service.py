import numpy as np
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.services.embedding")

# Lazy-loaded global sentence transformer instance
_st_model = None


class EmbeddingService:
    """
    Semantic similarity service using Sentence Transformers.
    """

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or settings.SENTENCE_TRANSFORMER_MODEL

    def _get_model(self):
        global _st_model
        if _st_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("Loading SentenceTransformer model ('%s')...", self.model_name)
                _st_model = SentenceTransformer(self.model_name)
                logger.info("SentenceTransformer model loaded.")
            except Exception as exc:
                logger.warning(
                    "SentenceTransformer could not be loaded (%s). Using fallback cosine similarity.",
                    exc,
                )
                return None
        return _st_model

    def compute_similarity(self, student_answer: str, reference_answer: str) -> float:
        """
        Calculate cosine similarity between student's answer and reference answer.
        Returns a float between 0.0 and 1.0.
        """
        if not student_answer or not student_answer.strip():
            return 0.0
        if not reference_answer or not reference_answer.strip():
            return 0.0

        model = self._get_model()
        if model is not None:
            try:
                embeddings = model.encode([student_answer, reference_answer])
                emb1 = embeddings[0]
                emb2 = embeddings[1]
                # Cosine similarity
                dot_product = float(np.dot(emb1, emb2))
                norm1 = float(np.linalg.norm(emb1))
                norm2 = float(np.linalg.norm(emb2))
                if norm1 == 0 or norm2 == 0:
                    return 0.0
                similarity = dot_product / (norm1 * norm2)
                # Clip to [0.0, 1.0]
                return round(float(max(0.0, min(1.0, similarity))), 4)
            except Exception as exc:
                logger.error("Error computing sentence embedding similarity: %s", exc)

        # Fallback keyword-overlap Jaccard/Dice similarity when model is unavailable
        words1 = set(student_answer.lower().split())
        words2 = set(reference_answer.lower().split())
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        if not union:
            return 0.0
        return round(len(intersection) / len(union), 4)


embedding_service = EmbeddingService()
