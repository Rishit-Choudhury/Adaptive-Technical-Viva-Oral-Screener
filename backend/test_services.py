"""Shared test setup. No test here ever calls a real paid API."""
import json
import random
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from adaptive_service import AdaptiveService
from config import load_settings
from main import create_app
from question_service import QuestionRepository
from transcription_service import TranscriptionService

TOPICS = ["Processes", "Memory", "Scheduling"]
LEVELS = ["Easy", "Medium", "Hard"]


def make_bank():
    """OS: 3 topics x 3 difficulties = 9 questions. DBMS: 1 question. CN: none."""
    bank, n = [], 1
    for topic in TOPICS:
        for level in LEVELS:
            bank.append({"id": n, "subject": "OS", "topic": topic, "difficulty": level,
                         "question": f"Explain {topic} at {level} level ({n})?",
                         "model_answer": f"Model answer {n}",
                         "key_concepts": [f"{topic.lower()} alpha{n}", f"{topic.lower()} beta{n}"],
                         "source": "test"})
            n += 1
    bank.append({"id": 100, "subject": "DBMS", "topic": "Normalization", "difficulty": "Easy",
                 "question": "What is 1NF?", "model_answer": "Atomic values",
                 "key_concepts": ["atomic values"], "source": "test"})
    bank.append({"id": 999, "subject": "OS", "topic": "Bad", "difficulty": "Impossible",
                 "question": "invalid difficulty", "model_answer": "x", "key_concepts": []})  # must be skipped
    return bank


@pytest.fixture
def settings():
    return load_settings(env={})          # empty env: ignores any real .env / real API key


@pytest.fixture
def bank_path(tmp_path):
    p = tmp_path / "bank.json"
    p.write_text(json.dumps(make_bank()), encoding="utf-8")
    return p


@pytest.fixture
def repo(bank_path, settings):
    return QuestionRepository(bank_path, [])


@pytest.fixture
def client(settings, repo):
    adaptive = AdaptiveService(repo, settings, rng=random.Random(1))
    return TestClient(create_app(settings=settings, repo=repo, adaptive=adaptive))


def fake_openai(transcribe_text="hello world", transcribe_error=None, chat_content="{}", chat_error=None):
    """A fake OpenAI client with the two calls we use."""
    def t_create(**kwargs):
        if transcribe_error:
            raise transcribe_error
        return SimpleNamespace(text=transcribe_text)

    def c_create(**kwargs):
        if chat_error:
            raise chat_error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=chat_content))])

    return SimpleNamespace(
        audio=SimpleNamespace(transcriptions=SimpleNamespace(create=t_create)),
        chat=SimpleNamespace(completions=SimpleNamespace(create=c_create)))


def start(client, subject="OS", n=5):
    r = client.post("/session/start", json={"subject": subject, "num_questions": n})
    assert r.status_code == 200, r.text
    return r.json()


def answer(client, sid, question, good=True):
    text = ", ".join(question["key_concepts"]) if good else "I do not know"
    return client.post("/session/evaluate",
                       json={"session_id": sid, "question_id": question["id"], "answer": text})


def make_client_with(settings, repo, **kwargs):
    return TestClient(create_app(settings=settings, repo=repo, **kwargs))
