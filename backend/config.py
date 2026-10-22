"""Adaptive question selection - a simple, explainable RULE-BASED strategy.
(It is NOT machine learning or reinforcement learning.)

Thresholds live in config.py / .env:
  LEVEL_UP_SCORE   (70) recent average >= this        -> one level harder
  LEVEL_DOWN_SCORE (40) recent average <  this        -> one level easier + follow-up
  RECENT_WINDOW    (2)  how many latest scored answers count as "recent"
  WEAK_SCORE       (50) a topic average below this is "weak"
  START_DIFFICULTY (Medium)

Steps for each next question
  1. Difficulty: based on the difficulty of the last scored question and the
     recent average (needs RECENT_WINDOW answers before going UP).
  2. Topic:
       - last answer scored below LEVEL_DOWN_SCORE -> follow-up in the same topic
       - else, a weak topic (most low scores first) other than the one just asked
       - else, any topic
  3. Pick an unused question at that difficulty (fallback: nearest difficulty).
     Among equals prefer questions that touch concepts the student missed,
     then topics not asked yet, then random.
  4. Never repeats a question inside a session. Skipped questions count as asked.
"""
import random
from typing import Optional

from evaluation_service import tokens
from question_service import DIFFICULTY_LEVELS


class AdaptiveService:
    def __init__(self, repo, settings, rng: Optional[random.Random] = None):
        self.repo = repo
        self.s = settings
        self.rng = rng or random.Random()

    # ---------------- public ----------------
    def first_question(self, session):
        target = DIFFICULTY_LEVELS.index(self.s.start_difficulty)
        note = f"Starting at {DIFFICULTY_LEVELS[target]} difficulty."
        q, extras = self._choose(session, target, topic=None)
        return q, " ".join([note] + extras)

    def next_question(self, session):
        """Returns (question or None, reason)."""
        if len(session.asked) >= session.num_questions:
            return None, "Session length reached."
        target, level_note = self._target_level(session)
        topic, topic_note = self._choose_topic(session)
        q, extras = self._choose(session, target, topic)
        if q is None:
            return None, "No unused questions left in this subject."
        return q, " ".join(filter(None, [level_note, topic_note] + extras))

    # ---------------- step 1: difficulty ----------------
    def _target_level(self, session):
        s = self.s
        scored = [(e, r) for e, r in session.answered_pairs() if r.evaluation.get("score") is not None]
        if not scored:
            start = DIFFICULTY_LEVELS.index(s.start_difficulty)
            return start, f"No scored answers yet, so difficulty stays at {DIFFICULTY_LEVELS[start]}."
        recent = scored[-s.recent_window:]
        avg = sum(r.evaluation["score"] for _, r in recent) / len(recent)
        base = DIFFICULTY_LEVELS.index(recent[-1][0]["difficulty"])
        top = len(DIFFICULTY_LEVELS) - 1
        if len(recent) >= s.recent_window and avg >= s.level_up_score:
            target = min(base + 1, top)
            return target, (f"Your last {len(recent)} scores averaged {avg:.0f} (>= {s.level_up_score:.0f}), "
                            f"so difficulty moves to {DIFFICULTY_LEVELS[target]}.")
        if avg < s.level_down_score:
            target = max(base - 1, 0)
            return target, (f"Your recent average was {avg:.0f} (< {s.level_down_score:.0f}), "
                            f"so difficulty moves to {DIFFICULTY_LEVELS[target]}.")
        return base, f"Your recent average was {avg:.0f}, so difficulty stays at {DIFFICULTY_LEVELS[base]}."

    # ---------------- step 2: topic ----------------
    def _choose_topic(self, session):
        last = session.asked[-1] if session.asked else None
        if last:
            rec = session.answers.get(last["key"])
            score = rec.evaluation.get("score") if rec else None
            if score is not None and score < self.s.level_down_score:
                missed = rec.evaluation.get("missing_concepts", [])
                note = f"Follow-up on {last['topic']}: you scored {score:.0f} on the last question"
                note += f" and missed: {', '.join(missed[:3])}." if missed else "."
                return last["topic"], note
        weak = self._weak_topics(session, exclude=last["topic"] if last else None)
        if weak:
            topic, t_avg = weak[0]
            return topic, f"Revisiting {topic}, a weak topic so far (average {t_avg:.0f})."
        return None, ""

    def _weak_topics(self, session, exclude):
        by_topic: dict = {}
        for e, r in session.answered_pairs():
            score = r.evaluation.get("score")
            if score is not None:
                by_topic.setdefault(e["topic"], []).append(score)
        weak = []
        for topic, scores in by_topic.items():
            t_avg = sum(scores) / len(scores)
            low_count = sum(1 for x in scores if x < self.s.weak_score)
            if t_avg < self.s.weak_score and topic != exclude:
                weak.append((topic, t_avg, low_count))
        weak.sort(key=lambda t: (-t[2], t[1]))     # repeated mistakes first, then lowest average
        return [(t, a) for t, a, _ in weak]

    # ---------------- step 3: pick a question ----------------
    def _choose(self, session, target: int, topic: Optional[str]):
        asked_keys = {e["key"] for e in session.asked}
        available = [q for q in self.repo.get_subject_questions(session.subject)
                     if str(q["id"]) not in asked_keys]
        if not available:
            return None, []
        extras = []
        pool = available
        if topic:
            topic_pool = [q for q in available if q["topic"] == topic]
            if topic_pool:
                pool = topic_pool
            else:
                extras.append(f"No unused questions left in {topic}, so another topic was used.")

        # nearest difficulty first; on a tie prefer the easier one
        order = sorted(range(len(DIFFICULTY_LEVELS)), key=lambda lvl: (abs(lvl - target), lvl))
        for lvl in order:
            candidates = [q for q in pool if q["difficulty"] == DIFFICULTY_LEVELS[lvl]]
            if candidates:
                if lvl != target:
                    extras.append(f"No unused {DIFFICULTY_LEVELS[target]} questions available, "
                                  f"so a {DIFFICULTY_LEVELS[lvl]} question was chosen.")
                question, overlap = self._pick(session, candidates)
                if overlap > 0:
                    extras.append("It also covers concepts you missed earlier.")
                return question, extras
        return None, extras  # unreachable: pool is never empty here

    def _pick(self, session, candidates):
        missed = set()
        for _, r in session.answered_pairs():
            for concept in r.evaluation.get("missing_concepts", []):
                missed |= tokens(concept)
        asked_topics = {e["topic"] for e in session.asked}

        def rank(q):
            overlap = len(missed & tokens(q["question"] + " " + " ".join(q["key_concepts"])))
            return overlap, q["topic"] not in asked_topics

        best = max(rank(q) for q in candidates)
        chosen = self.rng.choice([q for q in candidates if rank(q) == best])
        return chosen, best[0]
