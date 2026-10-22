from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pymongo import ASCENDING
from pymongo.errors import PyMongoError

from app.core.logging import get_logger
from app.db.mongodb import mongo_manager

logger = get_logger("app.db.repositories.answer")


# In-memory store fallback when running without a live MongoDB instance
_shared_answer_store: List[Dict[str, Any]] = []


class AnswerRepository:
    """
    MongoDB repository for the 'answers' collection.
    Audits every evaluated answer and prevents duplicate submissions.
    """

    def __init__(self) -> None:
        self.collection_name = "answers"
        self._memory_store = _shared_answer_store

    def _get_collection(self):
        if mongo_manager.is_connected and mongo_manager.db is not None:
            return mongo_manager.db[self.collection_name]
        return None

    async def create_indexes(self) -> None:
        """Create compound index on session_id and question_id."""
        col = self._get_collection()
        if col is not None:
            try:
                await col.create_index(
                    [("session_id", ASCENDING), ("question_id", ASCENDING)],
                    unique=True,
                )
                logger.info("Answer collection unique compound index verified.")
            except PyMongoError as exc:
                logger.warning("Could not create answer indexes: %s", exc)

    async def has_answered_question(self, session_id: str, question_id: str) -> bool:
        """Check if an answer has already been submitted for this question in this session."""
        col = self._get_collection()
        if col is not None:
            try:
                count = await col.count_documents({"session_id": session_id, "question_id": question_id})
                return count > 0
            except PyMongoError as exc:
                logger.error("Failed to check answer existence: %s", exc)

        return any(
            a.get("session_id") == session_id and a.get("question_id") == question_id
            for a in self._memory_store
        )

    async def save_answer(self, answer_data: Dict[str, Any]) -> str:
        """Save a new answer record."""
        record = answer_data.copy()
        if "created_at" not in record:
            record["created_at"] = datetime.now(timezone.utc)

        col = self._get_collection()
        if col is not None:
            try:
                res = await col.insert_one(record.copy())
                self._memory_store.append(record.copy())
                return str(res.inserted_id)
            except PyMongoError as exc:
                logger.error("Failed to save answer to MongoDB: %s", exc)

        self._memory_store.append(record.copy())
        return str(len(self._memory_store))

    async def get_answers_for_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve all answers submitted for a given session."""
        col = self._get_collection()
        if col is not None:
            try:
                cursor = col.find({"session_id": session_id}).sort("created_at", ASCENDING)
                docs = []
                async for item in cursor:
                    item["_id"] = str(item["_id"])
                    docs.append(item)
                return docs
            except PyMongoError as exc:
                logger.error("Failed to fetch answers for session %s: %s", session_id, exc)

        return [a for a in self._memory_store if a.get("session_id") == session_id]
