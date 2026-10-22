from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

from app.core.logging import get_logger
from app.db.mongodb import mongo_manager

logger = get_logger("app.db.repositories.session")


class SessionRepository:
    """
    MongoDB repository for managing viva session persistence.
    """

    def __init__(self) -> None:
        self.collection_name = "sessions"
        self._memory_store: Dict[str, Dict[str, Any]] = {}

    def _get_collection(self):
        if mongo_manager.is_connected and mongo_manager.db is not None:
            return mongo_manager.db[self.collection_name]
        return None

    async def create_indexes(self) -> None:
        """Create indexes on session_id and status."""
        col = self._get_collection()
        if col is not None:
            try:
                await col.create_index([("session_id", ASCENDING)], unique=True)
                await col.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
                logger.info("Session collection indexes verified.")
            except PyMongoError as exc:
                logger.warning("Could not create session indexes: %s", exc)

    async def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new session record."""
        session_id = session_data["session_id"]
        col = self._get_collection()
        if col is not None:
            try:
                await col.insert_one(session_data.copy())
            except PyMongoError as exc:
                logger.error("Failed to insert session %s in MongoDB: %s", session_id, exc)

        self._memory_store[session_id] = session_data.copy()
        return session_data

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session record by session_id."""
        col = self._get_collection()
        if col is not None:
            try:
                doc = await col.find_one({"session_id": session_id})
                if doc:
                    doc["_id"] = str(doc["_id"])
                    return doc
            except PyMongoError as exc:
                logger.error("Failed to fetch session %s from MongoDB: %s", session_id, exc)

        return self._memory_store.get(session_id)

    async def update_current_question(self, session_id: str, question: Optional[Dict[str, Any]]) -> bool:
        """Update the active question and previously asked question list."""
        col = self._get_collection()
        now = datetime.now(timezone.utc)
        update_fields: Dict[str, Any] = {
            "current_question": question,
            "updated_at": now,
        }
        if question and question.get("question_id"):
            push_op = {"previously_asked_question_ids": question["question_id"]}
        else:
            push_op = None

        if col is not None:
            try:
                update_query: Dict[str, Any] = {"$set": update_fields}
                if push_op:
                    update_query["$addToSet"] = push_op
                await col.update_one({"session_id": session_id}, update_query)
            except PyMongoError as exc:
                logger.error("Failed to update question in session %s: %s", session_id, exc)

        # Update in-memory
        sess = self._memory_store.get(session_id)
        if sess:
            sess["current_question"] = question
            sess["updated_at"] = now
            if question and question.get("question_id"):
                prev = sess.setdefault("previously_asked_question_ids", [])
                if question["question_id"] not in prev:
                    prev.append(question["question_id"])
            return True
        return False

    async def append_answer(
        self,
        session_id: str,
        answer_record: Dict[str, Any],
        overall_score_100: float,
        overall_score_10: float,
    ) -> bool:
        """Append an evaluated answer to the session history and update running scores."""
        col = self._get_collection()
        now = datetime.now(timezone.utc)
        if col is not None:
            try:
                await col.update_one(
                    {"session_id": session_id},
                    {
                        "$push": {"answers": answer_record},
                        "$set": {
                            "current_overall_score_100": overall_score_100,
                            "current_overall_score_10": overall_score_10,
                            "questions_answered_count": answer_record.get("answer_index", 1),
                            "updated_at": now,
                        },
                    },
                )
            except PyMongoError as exc:
                logger.error("Failed to append answer to session %s: %s", session_id, exc)

        # In-memory update
        sess = self._memory_store.get(session_id)
        if sess:
            sess.setdefault("answers", []).append(answer_record)
            sess["current_overall_score_100"] = overall_score_100
            sess["current_overall_score_10"] = overall_score_10
            sess["questions_answered_count"] = len(sess["answers"])
            sess["updated_at"] = now
            return True
        return False

    async def complete_session(self, session_id: str, final_report: Dict[str, Any]) -> bool:
        """Mark session as completed and attach final report."""
        col = self._get_collection()
        now = datetime.now(timezone.utc)
        if col is not None:
            try:
                await col.update_one(
                    {"session_id": session_id},
                    {
                        "$set": {
                            "status": "completed",
                            "current_question": None,
                            "report": final_report,
                            "updated_at": now,
                        }
                    },
                )
            except PyMongoError as exc:
                logger.error("Failed to complete session %s: %s", session_id, exc)

        sess = self._memory_store.get(session_id)
        if sess:
            sess["status"] = "completed"
            sess["current_question"] = None
            sess["report"] = final_report
            sess["updated_at"] = now
            return True
        return False
