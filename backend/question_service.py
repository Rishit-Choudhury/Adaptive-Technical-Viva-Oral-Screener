"""Loads, validates and searches the question bank (JSON files).

Nothing here knows about FastAPI. To move to a database later, write another
class with the same methods and pass it to create_app().
"""
import json
from pathlib import Path
from typing import Optional

from errors import ApiError

SUBJECT_NAMES = {
    "OS": "Operating Systems",
    "DBMS": "Database Management Systems",
    "CN": "Computer Networks",
}
DIFFICULTY_LEVELS = ["Easy", "Medium", "Hard"]   # index = rank
REQUIRED_FIELDS = ["id", "subject", "topic", "difficulty", "question", "model_answer", "key_concepts"]


def read_json_list(path: Path):
    """Return (list, error_message)."""
    if not path.exists():
        return [], f"File not found: {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [], f"Invalid JSON in {path.name}: {e}"
    except OSError as e:
        return [], f"Could not read {path.name}: {e}"
    if not isinstance(data, list):
        return [], f"{path.name} must contain a JSON list of questions."
    return data, None


def clean_question(raw) -> Optional[dict]:
    """Return a cleaned question dict, or None if the record is invalid."""
    if not isinstance(raw, dict) or any(f not in raw for f in REQUIRED_FIELDS):
        return None
    if isinstance(raw["id"], bool) or not isinstance(raw["id"], (int, str)):
        return None
    if not str(raw["question"]).strip():
        return None
    subject = str(raw["subject"]).strip().upper()
    difficulty = str(raw["difficulty"]).strip().title()
    if subject not in SUBJECT_NAMES or difficulty not in DIFFICULTY_LEVELS:
        return None
    concepts = raw["key_concepts"] if isinstance(raw["key_concepts"], list) else []
    return {
        "id": raw["id"],
        "subject": subject,
        "topic": str(raw["topic"]).strip() or "General",
        "difficulty": difficulty,
        "question": str(raw["question"]).strip(),
        "model_answer": str(raw["model_answer"]).strip(),
        "key_concepts": [str(c).strip() for c in concepts if str(c).strip()],
        "source": str(raw.get("source", "")),
    }


class QuestionRepository:
    def __init__(self, main_path: Path, fallback_paths=None):
        self.main_path = Path(main_path)
        self.fallback_paths = [Path(p) for p in (fallback_paths or [])]
        self.warnings: list[str] = []
        self.skipped = 0
        self._by_subject: dict[str, list[dict]] = {}
        self._by_key: dict[tuple, dict] = {}
        self.load()

    # ---------- loading ----------
    def load(self):
        self.warnings, self.skipped = [], 0
        self._by_subject = {code: [] for code in SUBJECT_NAMES}
        self._by_key = {}

        raw_items, err = read_json_list(self.main_path)
        if err:
            self.warnings.append(err)
            raw_items = []
            for p in self.fallback_paths:
                data, e = read_json_list(p)
                if not e:
                    raw_items.extend(data)
        for raw in raw_items:
            q = clean_question(raw)
            key = (q["subject"], str(q["id"])) if q else None
            if q is None:
                self.skipped += 1
            elif key in self._by_key:
                self.skipped += 1
                self.warnings.append(f"Duplicate id {q['id']} in {q['subject']} skipped.")
            else:
                self._by_key[key] = q
                self._by_subject[q["subject"]].append(q)
        if self.skipped:
            self.warnings.append(f"Skipped {self.skipped} invalid or duplicate question(s).")
        if self.total() == 0:
            self.warnings.append("The question bank is empty.")

    # ---------- queries ----------
    def total(self) -> int:
        return len(self._by_key)

    def count_by_subject(self) -> dict:
        return {code: len(qs) for code, qs in self._by_subject.items()}

    @staticmethod
    def normalize_subject(subject: str) -> str:
        code = str(subject).strip().upper()
        if code not in SUBJECT_NAMES:
            raise ApiError(400, f"Invalid subject '{subject}'. Choose one of: {', '.join(SUBJECT_NAMES)}.")
        return code

    def topics(self, subject: str) -> list[str]:
        return sorted({q["topic"] for q in self._by_subject.get(subject, [])})

    def get_subject_questions(self, subject: str, topic: Optional[str] = None,
                              difficulty: Optional[str] = None) -> list[dict]:
        subject = self.normalize_subject(subject)
        if self.total() == 0:
            raise ApiError(503, "The question bank is empty or could not be loaded. Check the backend logs/README.")
        pool = list(self._by_subject[subject])
        if topic:
            pool = [q for q in pool if q["topic"].lower() == topic.strip().lower()]
        if difficulty:
            pool = [q for q in pool if q["difficulty"].lower() == difficulty.strip().lower()]
        return pool

    def get_question(self, subject: str, question_id) -> dict:
        q = self._by_key.get((self.normalize_subject(subject), str(question_id)))
        if q is None:
            raise ApiError(404, f"Question {question_id} not found in {subject}.")
        return q
