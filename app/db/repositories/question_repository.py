import random
from typing import Any, Dict, List, Optional
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.logging import get_logger
from app.db.mongodb import mongo_manager

logger = get_logger("app.db.repositories.question")


# In-memory store fallback when running without a live MongoDB instance
_shared_question_store: Dict[str, Dict[str, Any]] = {}


class QuestionRepository:
    """
    MongoDB repository for the 'questions' collection.
    Supports asynchronous CRUD, filtering, indexing, and offline in-memory fallback.
    """

    def __init__(self) -> None:
        self.collection_name = "questions"
        self._memory_store = _shared_question_store

    def _get_collection(self):
        if mongo_manager.is_connected and mongo_manager.db is not None:
            return mongo_manager.db[self.collection_name]
        return None

    async def create_indexes(self) -> None:
        """Create indexes on question_id, subject, topic, and difficulty."""
        col = self._get_collection()
        if col is not None:
            try:
                await col.create_index([("question_id", ASCENDING)], unique=True)
                await col.create_index([("subject", ASCENDING), ("difficulty", ASCENDING)])
                await col.create_index([("subject", ASCENDING), ("topic", ASCENDING)])
                logger.info("Question collection indexes verified.")
            except PyMongoError as exc:
                logger.warning("Could not create question indexes: %s", exc)

    async def get_by_id(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve question document by unique question_id."""
        col = self._get_collection()
        if col is not None:
            try:
                doc = await col.find_one({"question_id": question_id})
                if doc:
                    doc["_id"] = str(doc["_id"])
                    return doc
            except PyMongoError as exc:
                logger.error("Error fetching question %s from MongoDB: %s", question_id, exc)

        # Fallback to in-memory store
        return self._memory_store.get(question_id)

    async def list_questions(
        self,
        subject: Optional[str] = None,
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
        exclude_ids: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query questions matching filter criteria."""
        col = self._get_collection()
        query: Dict[str, Any] = {}
        if subject:
            query["subject"] = subject
        if topic:
            query["topic"] = topic
        if difficulty:
            query["difficulty"] = difficulty
        if exclude_ids:
            query["question_id"] = {"$nin": exclude_ids}

        if col is not None:
            try:
                cursor = col.find(query).limit(limit)
                docs = []
                async for item in cursor:
                    item["_id"] = str(item["_id"])
                    docs.append(item)
                return docs
            except PyMongoError as exc:
                logger.error("Error querying questions from MongoDB: %s", exc)

        # In-memory filter fallback
        results = []
        for q in self._memory_store.values():
            if subject and q.get("subject") != subject:
                continue
            if topic and q.get("topic") != topic:
                continue
            if difficulty and q.get("difficulty") != difficulty:
                continue
            if exclude_ids and q.get("question_id") in exclude_ids:
                continue
            results.append(q)
            if len(results) >= limit:
                break
        return results

    async def insert_question(self, question_data: Dict[str, Any]) -> str:
        """Insert a single question record."""
        q_id = question_data["question_id"]
        col = self._get_collection()
        if col is not None:
            try:
                res = await col.insert_one(question_data.copy())
                self._memory_store[q_id] = question_data.copy()
                return str(res.inserted_id)
            except DuplicateKeyError:
                raise
            except PyMongoError as exc:
                logger.error("MongoDB insert failed for %s: %s", q_id, exc)

        self._memory_store[q_id] = question_data.copy()
        return q_id

    async def insert_many(self, questions: List[Dict[str, Any]]) -> int:
        """Bulk insert questions."""
        if not questions:
            return 0

        inserted_count = 0
        col = self._get_collection()
        if col is not None:
            try:
                res = await col.insert_many(questions, ordered=False)
                inserted_count = len(res.inserted_ids)
                for q in questions:
                    self._memory_store[q["question_id"]] = q.copy()
                return inserted_count
            except PyMongoError as exc:
                logger.warning("Partial or failed bulk insert in MongoDB: %s", exc)

        # In-memory insertion
        for q in questions:
            q_id = q["question_id"]
            if q_id not in self._memory_store:
                self._memory_store[q_id] = q.copy()
                inserted_count += 1
        return inserted_count

    async def get_random_question(
        self,
        subject: str,
        difficulty: Optional[str] = None,
        exclude_ids: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Select a random eligible question matching criteria."""
        candidates = await self.list_questions(
            subject=subject,
            difficulty=difficulty,
            exclude_ids=exclude_ids,
            limit=50,
        )
        if not candidates and difficulty:
            # Fall back to any difficulty within the subject
            candidates = await self.list_questions(
                subject=subject,
                exclude_ids=exclude_ids,
                limit=50,
            )
        if candidates:
            return random.choice(candidates)
        return None

    async def count(self, subject: Optional[str] = None) -> int:
        """Count total questions."""
        col = self._get_collection()
        query = {"subject": subject} if subject else {}
        if col is not None:
            try:
                return await col.count_documents(query)
            except PyMongoError:
                pass
        if subject:
            return sum(1 for q in self._memory_store.values() if q.get("subject") == subject)
        return len(self._memory_store)
