"""Viva session state + final report calculation.

IMPORTANT LIMITATION: sessions live in a Python dictionary (memory).
  - They disappear when the server restarts.
  - They are NOT shared between several server workers (run ONE uvicorn worker).
To use a database later, write a class with the same methods as
InMemorySessionStore and pass it to create_app().
"""
import threading
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from errors import ApiError
from question_service import DIFFICULTY_LEVELS


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class AnswerRecord:
    key: str            # str(question id)
    answer: str
    evaluation: dict
    attempts: int = 1


@dataclass
class Session:
    session_id: str
    subject: str
    num_questions: int
    status: str = "active"                 # "active" or "completed"
    created_at: str = field(default_factory=_now)
    ended_at: Optional[str] = None
    asked: list = field(default_factory=list)      # questions served, in order
    answers: dict = field(default_factory=dict)    # key -> AnswerRecord (latest answer)
    final_report: Optional[dict] = None

    def served_entry(self, key: str) -> Optional[dict]:
        for entry in self.asked:
            if entry["key"] == key:
                return entry
        return None

    def answered_pairs(self) -> list:
        """[(asked_entry, AnswerRecord)] in the order the questions were asked."""
        return [(e, self.answers[e["key"]]) for e in self.asked if e["key"] in self.answers]


class InMemorySessionStore:
    def __init__(self, max_sessions: int = 1000):
        self._sessions: dict = {}
        self._lock = threading.Lock()
        self.max_sessions = max_sessions

    def create(self, subject: str, num_questions: int) -> Session:
        session = Session(session_id=uuid.uuid4().hex, subject=subject, num_questions=num_questions)
        with self._lock:
            while len(self._sessions) >= self.max_sessions:     # drop the oldest session
                self._sessions.pop(next(iter(self._sessions)))
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise ApiError(404, "Session not found. It may have expired or the server was restarted - start a new session.")
        return session

    @staticmethod
    def ensure_active(session: Session):
        if session.status != "active":
            raise ApiError(409, "This session is already completed. Start a new session.")

    @staticmethod
    def serve(session: Session, question: dict, reason: Optional[str]):
        session.asked.append({
            "number": len(session.asked) + 1,
            "key": str(question["id"]),
            "question_id": question["id"],
            "topic": question["topic"],
            "difficulty": question["difficulty"],
            "question": question["question"],
            "reason": reason,
        })

    @staticmethod
    def record_answer(session: Session, key: str, answer: str, evaluation: dict) -> int:
        """Store the latest answer for a question. Returns the attempt number."""
        old = session.answers.get(key)
        attempts = old.attempts + 1 if old else 1
        session.answers[key] = AnswerRecord(key, answer, evaluation, attempts)
        return attempts

    @staticmethod
    def complete(session: Session, settings) -> dict:
        if session.status != "completed":
            session.status = "completed"
            session.ended_at = _now()
            session.final_report = build_report(session, settings)
        return session.final_report


# ======================================================================
# Report: every number below is calculated from real answers in the session
# ======================================================================
def _avg(values) -> Optional[float]:
    return round(sum(values) / len(values), 1) if values else None


def build_report(session: Session, settings) -> dict:
    pairs = session.answered_pairs()
    scored = [(e, r) for e, r in pairs if r.evaluation.get("score") is not None]
    avg = _avg([r.evaluation["score"] for _, r in scored])

    if avg is None:
        rating = None
    elif avg >= 80:
        rating = "Excellent"
    elif avg >= settings.strong_score:
        rating = "Good"
    elif avg >= settings.weak_score:
        rating = "Satisfactory"
    else:
        rating = "Needs improvement"

    # ---- topic-wise ----
    topic_attempts = Counter(e["topic"] for e, _ in pairs)
    topic_scores: dict = {}
    for e, r in scored:
        topic_scores.setdefault(e["topic"], []).append(r.evaluation["score"])
    topic_perf, strong, weak = [], [], []
    for topic in sorted(topic_attempts):
        t_avg = _avg(topic_scores.get(topic, []))
        if t_avg is None:
            status = "unscored"
        elif t_avg >= settings.strong_score:
            status = "strong"
            strong.append((t_avg, topic))
        elif t_avg < settings.weak_score:
            status = "weak"
            weak.append((t_avg, topic))
        else:
            status = "average"
        topic_perf.append({"topic": topic, "questions_attempted": topic_attempts[topic],
                           "average_score": t_avg, "status": status})
    strong_topics = [t for _, t in sorted(strong, reverse=True)]
    weak_topics = [t for _, t in sorted(weak)]

    # ---- difficulty-wise ----
    diff_attempts = Counter(e["difficulty"] for e, _ in pairs)
    diff_scores: dict = {}
    for e, r in scored:
        diff_scores.setdefault(e["difficulty"], []).append(r.evaluation["score"])
    diff_perf = [{"difficulty": d, "questions_attempted": diff_attempts[d],
                  "average_score": _avg(diff_scores.get(d, []))}
                 for d in DIFFICULTY_LEVELS if diff_attempts[d]]
    note = None
    if len(diff_perf) < 2 or len(scored) < 3:
        note = "Not enough data to compare difficulty levels yet (need answers at 2+ levels)."

    # ---- concepts ----
    covered, missed = [], Counter()
    for _, r in pairs:
        for c in r.evaluation.get("covered_concepts", []):
            if c not in covered:
                covered.append(c)
        missed.update(r.evaluation.get("missing_concepts", []))
    topics_with_gaps = []
    for e, r in pairs:
        if r.evaluation.get("missing_concepts") and e["topic"] not in topics_with_gaps:
            topics_with_gaps.append(e["topic"])
    revision = weak_topics + [t for t in topics_with_gaps if t not in weak_topics]

    return {
        "session_id": session.session_id,
        "subject": session.subject,
        "status": session.status,
        "score_scale": "0-100",
        "questions_served": len(session.asked),
        "questions_attempted": len(pairs),
        "questions_skipped": len(session.asked) - len(pairs),
        "average_score": avg,
        "overall_rating": rating,
        "topic_performance": topic_perf,
        "strong_topics": strong_topics,
        "weak_topics": weak_topics,
        "difficulty_performance": diff_perf,
        "difficulty_note": note,
        "covered_concepts": covered,
        "missing_concepts": list(missed),
        "most_missed_concepts": [{"concept": c, "times_missed": n} for c, n in missed.most_common(10)],
        "revision_topics": revision,
        "difficulty_history": [e["difficulty"] for e in session.asked],
        "questions": [{
            "number": e["number"], "question_id": e["question_id"], "topic": e["topic"],
            "difficulty": e["difficulty"], "question": e["question"],
            "attempted": e["key"] in session.answers,
            "score": session.answers[e["key"]].evaluation.get("score") if e["key"] in session.answers else None,
        } for e in session.asked],
        "evaluation_modes_used": sorted({r.evaluation.get("mode", "basic") for _, r in pairs}),
        "ended_at": session.ended_at,
    }
