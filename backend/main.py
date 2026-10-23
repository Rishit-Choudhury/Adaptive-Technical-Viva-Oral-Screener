
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException

app = FastAPI(title="Adaptive Oral Examiner")

DATA_FILE = Path(__file__).parent / "question_bank.json"


def load_questions():
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, dict):
        data = data.get("questions", [])

    if not isinstance(data, list):
        raise ValueError("Expected a list of questions")

    return data


@app.get("/")
def home():
    return {"message": "Adaptive Oral Examiner backend is running!"}


@app.get("/questions")
def get_questions():
    try:
        questions = load_questions()
    except (OSError, ValueError, json.JSONDecodeError):
        raise HTTPException(
            status_code=500,
            detail="Could not load question_bank.json"
        )

    return [
        {
            key: q[key]
            for key in (
                "id", "subject", "topic",
                "difficulty", "question"
            )
            if key in q
        }
        for q in questions
        if isinstance(q, dict)
    ]


@app.get("/questions/{question_id}")
def get_question(question_id: int):
    try:
        questions = load_questions()
    except (OSError, ValueError, json.JSONDecodeError):
        raise HTTPException(
            status_code=500,
            detail="Could not load question_bank.json"
        )

    for q in questions:
        if isinstance(q, dict) and q.get("id") == question_id:
            return {
                key: q[key]
                for key in (
                    "id", "subject", "topic",
                    "difficulty", "question"
                )
                if key in q
            }

    raise HTTPException(status_code=404, detail="Question not found")
