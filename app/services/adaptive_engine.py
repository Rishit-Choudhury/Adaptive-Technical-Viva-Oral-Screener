import random
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.logging import get_logger
from app.db.repositories.question_repository import QuestionRepository
from app.schemas.evaluation import EvaluationResult
from app.schemas.question import DifficultyEnum, QuestionSafe, SubjectEnum

logger = get_logger("app.services.adaptive_engine")


class AdaptiveEngine:
    """
    Pure Python adaptive question selector.
    Selects real questions from MongoDB based on score thresholds,
    topic mastery, and missing concept matching.
    """

    def __init__(self, repo: Optional[QuestionRepository] = None) -> None:
        self.repo = repo or QuestionRepository()
        self.low_threshold = settings.LOW_SCORE_THRESHOLD
        self.high_threshold = settings.HIGH_SCORE_THRESHOLD

    def _determine_target_difficulty(self, current_difficulty: str, last_score: float) -> str:
        """
        Adjust difficulty based on previous score:
        - Score >= high_threshold (80): Increase difficulty (easy -> medium -> hard)
        - Score < low_threshold (50): Decrease difficulty (hard -> medium -> easy)
        - Moderate: Keep current difficulty
        """
        current_diff = current_difficulty.lower()
        if last_score >= self.high_threshold:
            if current_diff == "easy":
                return "medium"
            return "hard"
        elif last_score < self.low_threshold:
            if current_diff == "hard":
                return "medium"
            return "easy"
        else:
            return current_diff

    async def select_next_question(
        self,
        subject: SubjectEnum,
        last_question: Dict[str, Any],
        last_evaluation: EvaluationResult,
        previously_asked_ids: List[str],
        topic_mastery: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[QuestionSafe], str]:
        """
        Select next adaptive question based on last evaluation and missing concepts.
        Returns (QuestionSafe or None, selection_reason).
        """
        last_score = last_evaluation.scoring.final_score_100
        current_diff = last_question.get("difficulty", "medium")
        current_topic = last_question.get("topic", "")
        missing_concepts = set(last_evaluation.concept_analysis.missing_concepts)
        follow_up_focus = set(last_evaluation.concept_analysis.suggested_follow_up_focus)
        target_diff = self._determine_target_difficulty(current_diff, last_score)

        logger.info(
            "Adaptive selection: subject=%s, last_score=%.1f, target_diff=%s, missing_concepts=%s",
            subject.value,
            last_score,
            target_diff,
            missing_concepts,
        )

        # Retrieve all unasked questions for this subject
        candidates = await self.repo.list_questions(
            subject=subject.value,
            exclude_ids=previously_asked_ids,
            limit=200,
        )

        if not candidates:
            return None, "All eligible questions for this subject have been answered."

        # Rank candidates using scoring function
        ranked_candidates: List[Tuple[float, Dict[str, Any], str]] = []

        for candidate in candidates:
            cand_topic = candidate.get("topic", "")
            cand_diff = candidate.get("difficulty", "medium")
            cand_concepts = set(candidate.get("key_concepts", []))

            score = 0.0
            reasons = []

            # 1. Concept overlap with missing concepts (priority for weak/moderate answers)
            concept_overlap = cand_concepts.intersection(missing_concepts.union(follow_up_focus))
            if concept_overlap:
                overlap_score = len(concept_overlap) * 30.0
                score += overlap_score
                reasons.append(f"Targets missing concept: {', '.join(concept_overlap)}")

            # 2. Difficulty match
            if cand_diff == target_diff:
                score += 25.0
                reasons.append(f"Matches target difficulty '{target_diff}'")
            elif (target_diff == "hard" and cand_diff == "medium") or (target_diff == "easy" and cand_diff == "medium"):
                score += 10.0

            # 3. Topic strategy
            if last_score < self.low_threshold:
                # Weak answer: Prefer staying in same topic for reinforcement
                if cand_topic == current_topic:
                    score += 20.0
                    reasons.append(f"Reinforces foundational topic '{current_topic}'")
            elif last_score >= self.high_threshold:
                # Excellent answer: Assess breadth by giving points to other topics
                if cand_topic != current_topic:
                    score += 15.0
                    reasons.append(f"Explores breadth across '{cand_topic}'")
                else:
                    score += 10.0
                    reasons.append(f"Deepens mastery in '{current_topic}'")
            else:
                # Moderate answer: Either same topic or related topic
                if cand_topic == current_topic:
                    score += 15.0
                    reasons.append(f"Follows up in '{current_topic}'")

            # Add minor random noise for breaking ties
            score += random.uniform(0.1, 1.0)
            reason_str = "; ".join(reasons) or "Selected based on available subject pool"
            ranked_candidates.append((score, candidate, reason_str))

        # Sort descending by score
        ranked_candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_candidate, selection_reason = ranked_candidates[0]

        safe_question = QuestionSafe(
            question_id=best_candidate["question_id"],
            subject=best_candidate["subject"],
            topic=best_candidate["topic"],
            difficulty=best_candidate["difficulty"],
            question=best_candidate["question"],
            tags=best_candidate.get("tags", []),
        )

        return safe_question, selection_reason


adaptive_engine = AdaptiveEngine()
