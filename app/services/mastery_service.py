from typing import Any, Dict, List, Optional
from app.core.logging import get_logger
from app.db.repositories.mastery_repository import MasteryRepository
from app.schemas.mastery import SessionMasteryResponse, TopicMastery
from app.schemas.question import SubjectEnum

logger = get_logger("app.services.mastery")


class MasteryService:
    """
    Tracks and updates topic-wise conceptual understanding and mastery estimation.
    """

    def __init__(self, repo: Optional[MasteryRepository] = None) -> None:
        self.repo = repo or MasteryRepository()

    async def update_mastery(
        self,
        session_id: str,
        subject: str,
        topic: str,
        score_100: float,
        difficulty: str,
        covered_concepts: List[str],
        missing_concepts: List[str],
    ) -> TopicMastery:
        """
        Update rolling performance and estimated mastery after an evaluated answer.
        """
        existing = await self.repo.get_topic_mastery(session_id, topic)
        if existing:
            attempted = existing.get("questions_attempted", 0) + 1
            recent_scores = existing.get("recent_scores", []) + [score_100]
            if len(recent_scores) > 5:
                recent_scores = recent_scores[-5:]
            avg_score = round(sum(recent_scores) / len(recent_scores), 2)

            strong = list(set(existing.get("strong_concepts", []) + covered_concepts))
            weak = list(set(existing.get("weak_concepts", []) + missing_concepts))
            # If a concept was previously weak but now demonstrated, remove from weak
            weak = [c for c in weak if c not in covered_concepts]

            difficulties = list(set(existing.get("difficulties_handled", [])))
            if score_100 >= 60.0 and difficulty not in difficulties:
                difficulties.append(difficulty)
        else:
            attempted = 1
            recent_scores = [score_100]
            avg_score = score_100
            strong = list(set(covered_concepts))
            weak = list(set(missing_concepts))
            difficulties = [difficulty] if score_100 >= 60.0 else []

        # Estimated Mastery Formula:
        # Considers average score (60%), recent trajectory weight (20%), and difficulty bonus (20%)
        difficulty_multipliers = {"easy": 0.8, "medium": 1.0, "hard": 1.2}
        diff_bonus = sum(difficulty_multipliers.get(d, 1.0) for d in difficulties) / max(1, len(difficulties)) * 10.0
        recent_trend = recent_scores[-1] if recent_scores else avg_score

        estimated_mastery = (avg_score * 0.60) + (recent_trend * 0.20) + min(20.0, diff_bonus)
        estimated_mastery = round(max(0.0, min(100.0, estimated_mastery)), 2)

        record = {
            "session_id": session_id,
            "subject": subject,
            "topic": topic,
            "questions_attempted": attempted,
            "average_score": avg_score,
            "recent_scores": recent_scores,
            "estimated_mastery": estimated_mastery,
            "strong_concepts": strong,
            "weak_concepts": weak,
            "difficulties_handled": difficulties,
        }

        await self.repo.upsert_topic_mastery(session_id, subject, topic, record)
        return TopicMastery(**record)

    async def get_session_mastery(self, session_id: str, subject: SubjectEnum) -> SessionMasteryResponse:
        """Retrieve topic-wise mastery summary for a viva session."""
        docs = await self.repo.list_masteries_for_session(session_id)
        topics = [TopicMastery(**d) for d in docs]
        return SessionMasteryResponse(session_id=session_id, subject=subject, topics=topics)


mastery_service = MasteryService()
