import json
import httpx
import openai
import pytest
from dataclasses import replace

from conftest import answer, fake_openai, make_client_with, start
from errors import ApiError
from evaluation_service import BasicEvaluator, EvaluationService
from transcription_service import TranscriptionService

Q = {"id": 1, "key_concepts": ["program counter", "passive vs active"], "question": "q", "model_answer": "m"}


def test_basic_evaluator_stemming_and_partial_credit():
    out = BasicEvaluator().evaluate(Q, "A program is passive code while a process is active.")
    assert out["covered_concepts"] == ["passive vs active"]
    assert out["score"] == 50 and out["mode"] == "basic"


def test_basic_evaluator_no_concepts_gives_no_score():
    out = BasicEvaluator().evaluate({**Q, "key_concepts": []}, "anything")
    assert out["score"] is None


def _llm_service(settings, **fake_kwargs):
    s = replace(settings, evaluation_mode="llm", openai_api_key="test")
    return s, EvaluationService(s, llm_client=fake_openai(**fake_kwargs))


def test_llm_evaluator_valid_output_is_validated():
    from config import load_settings
    content = json.dumps({"score": 150, "covered_concepts": ["program counter", "made up concept"],
                          "strengths": ["good"], "suggestions": ["add more"]})
    _, svc = _llm_service(load_settings(env={}), chat_content=content)
    out = svc.evaluate(Q, "answer")
    assert out["mode"] == "llm" and out["score"] == 100           # clamped to 0-100
    assert out["covered_concepts"] == ["program counter"]          # invented concept dropped
    assert out["missing_concepts"] == ["passive vs active"]


def test_llm_failure_falls_back_with_honest_label():
    from config import load_settings
    _, svc = _llm_service(load_settings(env={}), chat_content="not json at all")
    out = svc.evaluate(Q, "program counter")
    assert out["mode"] == "basic" and "unavailable" in out["source"]


def test_llm_failure_without_fallback_is_an_error():
    from config import load_settings
    s = replace(load_settings(env={}), evaluation_mode="llm", openai_api_key="t", llm_fallback_to_basic=False)
    svc = EvaluationService(s, llm_client=fake_openai(chat_content="garbage"))
    with pytest.raises(ApiError) as e:
        svc.evaluate(Q, "x")
    assert e.value.status_code == 502


def test_llm_mode_without_key_falls_back(settings):
    svc = EvaluationService(replace(settings, evaluation_mode="llm"))   # no key, no fake client
    out = svc.evaluate(Q, "program counter")
    assert out["mode"] == "basic" and "not configured" in out["source"]


def test_end_to_end_with_llm_client_in_api(settings, repo):
    s = replace(settings, evaluation_mode="llm", openai_api_key="t")
    content = json.dumps({"score": 80, "covered_concepts": [], "strengths": [], "suggestions": []})
    c = make_client_with(s, repo, evaluator=EvaluationService(s, llm_client=fake_openai(chat_content=content)))
    st = start(c)
    body = answer(c, st["session_id"], st["question"]).json()
    assert body["score"] == 80 and body["mode"] == "llm"


# ---------------- transcription ----------------
def _upload(c, name="rec.wav", data=b"RIFFfakewavdata", ctype="audio/wav", **form):
    return c.post("/transcribe", files={"file": (name, data, ctype)}, data=form)


def _client_with_fake(settings, repo, fake, **overrides):
    s = replace(settings, openai_api_key="t", **overrides)
    return make_client_with(s, repo, transcriber=TranscriptionService(s, client=fake))


def test_transcribe_success_returns_text_only(settings, repo):
    c = _client_with_fake(settings, repo, fake_openai(transcribe_text="  a process is a running program "))
    r = _upload(c, language="en")
    assert r.status_code == 200 and r.json()["text"] == "a process is a running program"


def test_transcribe_unavailable_without_key(client):
    r = _upload(client)
    assert r.status_code == 503 and "OPENAI_API_KEY" in r.json()["detail"]
    assert client.get("/health").json()["transcription_available"] is False


def test_transcribe_validation(settings, repo):
    c = _client_with_fake(settings, repo, fake_openai(), max_audio_mb=0.001)   # ~1 KB limit
    assert _upload(c, data=b"").status_code == 400
    assert _upload(c, name="notes.txt", ctype="text/plain").status_code == 415
    assert _upload(c, name="rec.wav", ctype="image/png").status_code == 415
    assert _upload(c, data=b"x" * 5000).status_code == 413
    assert _upload(c, language="english!!").status_code == 400


def test_transcribe_service_failures(settings, repo):
    req = httpx.Request("POST", "https://example.invalid")
    timeout = _client_with_fake(settings, repo, fake_openai(transcribe_error=openai.APITimeoutError(request=req)))
    assert _upload(timeout).status_code == 504
    conn = _client_with_fake(settings, repo, fake_openai(transcribe_error=openai.APIConnectionError(request=req)))
    assert _upload(conn).status_code == 502
    silent = _client_with_fake(settings, repo, fake_openai(transcribe_text="   "))
    r = _upload(silent)
    assert r.status_code == 422 and "No speech" in r.json()["detail"]     # no fabricated transcript


def test_translate_is_separate_and_optional(settings, repo, client):
    assert client.post("/translate", json={"text": "namaste"}).status_code == 503   # no key
    c = make_client_with(replace(settings, openai_api_key="t"), repo,
                         translator_client=fake_openai(chat_content="hello"))
    body = c.post("/translate", json={"text": "namaste"}).json()
    assert body["original_text"] == "namaste" and body["translated_text"] == "hello"
