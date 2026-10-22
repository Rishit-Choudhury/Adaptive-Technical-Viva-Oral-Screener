import json
from conftest import make_client_with
from question_service import QuestionRepository


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["questions_loaded"]["OS"] == 9          # invalid record was skipped
    assert body["records_skipped"] == 1
    assert body["llm_available"] is False


def test_subjects(client):
    r = client.get("/subjects")
    codes = {s["code"]: s for s in r.json()}
    assert set(codes) == {"OS", "DBMS", "CN"}
    assert codes["OS"]["question_count"] == 9 and codes["CN"]["question_count"] == 0


def test_question_listing_hides_answers_and_filters(client):
    r = client.get("/subjects/OS/questions", params={"topic": "memory", "difficulty": "easy"})
    items = r.json()
    assert len(items) == 1 and items[0]["topic"] == "Memory"
    assert "model_answer" not in items[0] and "key_concepts" not in items[0]


def test_single_question_reveal(client):
    hidden = client.get("/subjects/OS/questions/1").json()
    assert "model_answer" not in hidden
    shown = client.get("/subjects/OS/questions/1", params={"reveal_answer": True}).json()
    assert shown["model_answer"] == "Model answer 1"
    assert client.get("/subjects/OS/questions/12345").status_code == 404
    assert client.get("/subjects/XYZ/questions").status_code == 400


def test_missing_question_bank_files(tmp_path, settings):
    empty_repo = QuestionRepository(tmp_path / "nope.json", [tmp_path / "also_missing.json"])
    c = make_client_with(settings, empty_repo)
    assert c.get("/health").status_code == 200            # server still runs
    assert any("not found" in w.lower() for w in c.get("/health").json()["warnings"])
    r = c.post("/session/start", json={"subject": "OS", "num_questions": 3})
    assert r.status_code == 503 and "empty" in r.json()["detail"].lower()


def test_fallback_files_used_when_main_missing(tmp_path, settings):
    f = tmp_path / "os_questions.json"
    f.write_text(json.dumps([{"id": 1, "subject": "OS", "topic": "T", "difficulty": "Easy",
                              "question": "Q?", "model_answer": "A", "key_concepts": ["x"]}]))
    repo = QuestionRepository(tmp_path / "missing.json", [f])
    assert repo.total() == 1


def test_start_session_ok(client):
    data = client.post("/session/start", json={"subject": "os", "num_questions": 5}).json()
    assert data["session_id"] and data["num_questions"] == 5
    q = data["question"]
    for field in ["id", "subject", "topic", "difficulty", "question", "model_answer", "key_concepts", "source"]:
        assert field in q                                 # frontend's clean_question needs all of these
    assert q["difficulty"] == "Medium"                    # default start level


def test_start_session_length_capped_by_bank(client):
    assert client.post("/session/start", json={"subject": "DBMS", "num_questions": 20}).json()["num_questions"] == 1


def test_start_session_errors(client):
    assert client.post("/session/start", json={"subject": "Maths", "num_questions": 3}).status_code == 400
    r = client.post("/session/start", json={"subject": "CN", "num_questions": 3})
    assert r.status_code == 404                           # valid subject, no questions
    assert client.post("/session/start", json={"subject": "OS", "num_questions": 0}).status_code == 422
    r = client.post("/session/start", content="{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422 and "Malformed JSON" in r.json()["detail"]
