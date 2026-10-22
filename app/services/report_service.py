from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.db.repositories.mastery_repository import MasteryRepository
from app.schemas.question import SubjectEnum
from app.schemas.report import FinalReport, TopicPerformance

logger = get_logger("app.services.report")


class ReportService:
    """
    Computes statistical aggregation and generates final student viva examination reports.
    """

    def __init__(self, mastery_repo: Optional[MasteryRepository] = None) -> None:
        self.mastery_repo = mastery_repo or MasteryRepository()

    async def generate_report(
        self,
        session_id: str,
        subject: SubjectEnum,
        answers: List[Dict[str, Any]],
    ) -> FinalReport:
        """
        Aggregate session metrics, calculate topic distributions,
        collate strong and weak concepts, and formulate revision recommendations.
        """
        if not answers:
            return FinalReport(
                session_id=session_id,
                subject=subject,
                status="completed",
                overall_score_100=0.0,
                overall_score_10=0.0,
                questions_attempted=0,
                average_answer_score=0.0,
                topic_wise_performance=[],
                strong_concepts=[],
                weak_concepts=[],
                frequently_missed_concepts=[],
                difficulty_levels_handled=[],
                revision_recommendations=["No questions answered in this session."],
            )

        scores = [a["evaluation"]["scoring"]["final_score_100"] for a in answers]
        avg_score = round(sum(scores) / len(scores), 2)
        overall_10 = round(avg_score / 10.0, 2)

        # Topic aggregation
        topic_scores: Dict[str, List[float]] = {}
        all_covered: List[str] = []
        all_missing: List[str] = []
        difficulties: set[str] = set()

        for ans in answers:
            topic = ans.get("topic", "General")
            topic_scores.setdefault(topic, []).append(ans["evaluation"]["scoring"]["final_score_100"])
            analysis = ans["evaluation"]["concept_analysis"]
            all_covered.extend(analysis.get("covered_concepts", []))
            all_missing.extend(analysis.get("missing_concepts", []))
            if ans.get("difficulty"):
                difficulties.add(ans["difficulty"])

        topic_perf: List[TopicPerformance] = []
        for topic, t_scores in topic_scores.items():
            t_avg = round(sum(t_scores) / len(t_scores), 2)
            if t_avg >= 80:
                rating = "Proficient"
            elif t_avg >= 50:
                rating = "Developing"
            else:
                rating = "Needs Review"
            topic_perf.append(
                TopicPerformance(
                    topic=topic,
                    questions_attempted=len(t_scores),
                    average_score=t_avg,
                    mastery_percentage=t_avg,
                    mastery_rating=rating,
                )
            )

        strong_concepts = list(set(all_covered) - set(all_missing))
        weak_concepts = list(set(all_missing) - set(all_covered))

        # Frequently missed concepts (concepts appearing >= 2 times in missing list, or all if short)
        missing_counts = Counter(all_missing)
        freq_missed = [concept for concept, count in missing_counts.most_common(5)]

        # Generate revision recommendations
        recommendations: List[str] = []
        weak_topics = [tp.topic for tp in topic_perf if tp.average_score < 60]
        if weak_topics:
            recommendations.append(f"Focus revision on foundational topics: {', '.join(weak_topics)}.")
        if freq_missed:
            recommendations.append(f"Revisit key technical definitions: {', '.join(freq_missed[:4])}.")
        if avg_score >= 80:
            recommendations.append("Solid conceptual understanding. Practice deep implementation trade-offs.")
        elif avg_score >= 50:
            recommendations.append("Moderate grasp of core principles. Strengthen precision in oral answers.")
        else:
            recommendations.append("Recommend structured review of core textbook chapters and diagrams.")

        report = FinalReport(
            session_id=session_id,
            subject=subject,
            status="completed",
            overall_score_100=avg_score,
            overall_score_10=overall_10,
            questions_attempted=len(answers),
            average_answer_score=avg_score,
            topic_wise_performance=topic_perf,
            strong_concepts=strong_concepts[:10],
            weak_concepts=weak_concepts[:10],
            frequently_missed_concepts=freq_missed,
            difficulty_levels_handled=sorted(list(difficulties)),
            revision_recommendations=recommendations,
            generated_at=datetime.now(timezone.utc),
        )

        return report


report_service = ReportService()
