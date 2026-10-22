from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pymongo import ASCENDING
from pymongo.errors import PyMongoError

from app.core.logging import get_logger
from app.db.mongodb import mongo_manager

logger = get_logger("app.db.repositories.mastery")


class MasteryRepository:
    """
    MongoDB repository for the 'mastery_records' collection.
    Tracks topic-wise student performance and concept mastery.
    """

    def __init__(self) -> None:
        self.collection_name = "mastery_records"
        self._memory_store: Dict[str, Dict[str, Any]] = {}

    def _get_collection(self):
        if mongo_manager.is_connected and mongo_manager.db is not None:
            return mongo_manager.db[self.collection_name]
        return None

    def _make_key(self, session_id: str, topic: str) -> str:
        return f"{session_id}:{topic.lower()}"

    async def create_indexes(self) -> None:
        """Create compound unique index on session_id and topic."""
        col = self._get_collection()
        if col is not None:
            try:
                await col.create_index(
                    [("session_id", ASCENDING), ("topic", ASCENDING)],
                    unique=True,
                )
                logger.info("Mastery collection unique compound index verified.")
            except PyMongoError as exc:
                logger.warning("Could not create mastery indexes: %s", exc)

    async def get_topic_mastery(self, session_id: str, topic: str) -> Optional[Dict[str, Any]]:
        """Retrieve topic mastery record."""
        col = self._get_collection()
        if col is not None:
            try:
                doc = await col.find_one({"session_id": session_id, "topic": topic})
                if doc:
                    doc["_id"] = str(doc["_id"])
                    return doc
            except PyMongoError as exc:
                logger.error("Error fetching topic mastery for %s: %s", topic, exc)

        return self._memory_store.get(self._make_key(session_id, topic))

    async def list_masteries_for_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve all topic masteries recorded in a session."""
        col = self._get_collection()
        if col is not None:
            try:
                cursor = col.find({"session_id": session_id})
                docs = []
                async for item in cursor:
                    item["_id"] = str(item["_id"])
                    docs.append(item)
                return docs
            except PyMongoError as exc:
                logger.error("Error fetching session masteries for %s: %s", session_id, exc)

        prefix = f"{session_id}:"
        return [v for k, v in self._memory_store.items() if k.startswith(prefix)]

    async def upsert_topic_mastery(
        self,
        session_id: str,
        subject: str,
        topic: str,
        mastery_data: Dict[str, Any],
    ) -> bool:
        """Upsert topic mastery metrics."""
        data = mastery_data.copy()
        data["session_id"] = session_id
        data["subject"] = subject
        data["topic"] = topic
        data["updated_at"] = datetime.now(timezone.utc)

        col = self._get_collection()
        if col is not None:
            try:
                await col.update_one(
                    {"session_id": session_id, "topic": topic},
                    {"$set": data},
                    upsert=True,
                )
            except PyMongoError as exc:
                logger.error("Failed to upsert topic mastery: %s", exc)

        self._memory_store[self._make_key(session_id, topic)] = data
        return True
