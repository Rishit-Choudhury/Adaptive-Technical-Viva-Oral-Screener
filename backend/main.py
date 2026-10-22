"""FastAPI app. Routes are thin: they validate input and call the services.

Run (inside the backend folder):   uvicorn main:app --reload --port 8000
Interactive docs:                  http://127.0.0.1:8000/docs
"""
import logging
from typing import Optional, Union

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from adaptive_service import AdaptiveService
from config import load_settings
from errors import ApiError
from evaluation_service import EvaluationService
from models import (AnswerRequest, EvaluationResult, HealthResponse, NextQuestionResponse,
                    QuestionOut, QuestionPreview, SessionIdRequest, SessionReport,
                    StartSessionRequest, StartSessionResponse, SubjectInfo,
                    TranscriptionResponse, TranslateRequest, TranslateResponse)
from question_service import SUBJECT_NAMES, QuestionRepository
from session_service import InMemorySessionStore
from transcription_service import TranscriptionService
from translation_service import translate_to_english

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("viva")


def create_app(settings=None, repo=None, sessions=None, evaluator=None,
               adaptive=None, transcriber=None, translator_client=None) -> FastAPI:
    """Everything can be replaced (the tests do this with fakes)."""
    settings = settings or load_settings()
    repo = repo or QuestionRepository(settings.question_bank_path, settings.fallback_paths)
    sessions = sessions or InMemorySessionStore(settings.max_sessions)
    evaluator = evaluator or EvaluationService(settings)
    adaptive = adaptive or AdaptiveService(repo, settings)
    transcriber = transcriber or TranscriptionService(settings)

    app = FastAPI(title="Adaptive Viva Preparation API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,     # only the Streamlit origins listed in .env
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    # ---------------- error handling ----------------
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        problems = []
        for err in exc.errors():
            where = ".".join(str(p) for p in err["loc"] if p not in ("body", "query"))
            msg = str(err["msg"]).replace("Value error, ", "")
            if err.get("type") == "json_invalid":
                msg, where = "Malformed JSON in request body", ""
            problems.append(f"{where}: {msg}" if where else msg)
        return JSONResponse(status_code=422, content={"detail": "Invalid request - " + "; ".join(problems)})

    # ---------------- health & browsing ----------------
    @app.get("/health", response_model=HealthResponse)
    def health():
        return HealthResponse(
            status="ok",
            questions_loaded=repo.count_by_subject(),
            records_skipped=repo.skipped,
            warnings=repo.warnings[:10],
            evaluation_mode_configured=settings.evaluation_mode,
            llm_available=bool(settings.openai_api_key),
            transcription_available=transcriber.available,
        )

    @app.get("/subjects", response_model=list[SubjectInfo])
    def list_subjects():
        counts = repo.count_by_subject()
        return [SubjectInfo(code=c, name=n, question_count=counts.get(c, 0), topics=repo.topics(c))
                for c, n in SUBJECT_NAMES.items()]

    @app.get("/subjects/{subject}/questions", response_model=list[QuestionPreview])
    def list_questions(subject: str, topic: Optional[str] = None, difficulty: Optional[str] = None,
                       limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
        """Browse questions WITHOUT answers (answers are only revealed on request below)."""
        pool = repo.get_subject_questions(subject, topic, difficulty)
        return pool[offset: offset + limit]

    @app.get("/subjects/{subject}/questions/{question_id}",
             response_model=Union[QuestionOut, QuestionPreview])
    def get_question(subject: str, question_id: str, reveal_answer: bool = False):
        q = repo.get_question(subject, question_id)
        return q if reveal_answer else {k: v for k, v in q.items() if k not in ("model_answer", "key_concepts")}

    # ---------------- viva session ----------------
    @app.post("/session/start", response_model=StartSessionResponse)
    def start_session(req: StartSessionRequest):
        subject = repo.normalize_subject(req.subject)
        pool = repo.get_subject_questions(subject)       # 503 if the whole bank is empty
        if not pool:
            raise ApiError(404, f"No questions available for subject {subject}.")
        length = min(req.num_questions, len(pool))
        session = sessions.create(subject, length)
        question, reason = adaptive.first_question(session)
        sessions.serve(session, question, reason)
        return StartSessionResponse(session_id=session.session_id, subject=subject,
                                    num_questions=length, question=question, reason=reason)

    @app.post("/session/evaluate", response_model=EvaluationResult)
    def evaluate_answer(req: AnswerRequest):
        session = sessions.get(req.session_id)
        sessions.ensure_active(session)
        key = str(req.question_id)
        if session.served_entry(key) is None:
            raise ApiError(404, f"Question {req.question_id} was not asked in this session.")
        question = repo.get_question(session.subject, key)

        previous = session.answers.get(key)
        if previous and previous.answer == req.answer:
            # Same answer sent again: return the stored result (no new scoring, no extra API cost)
            result, attempts = previous.evaluation, previous.attempts
        else:
            result = evaluator.evaluate(question, req.answer)          # may raise 502/503/504
            attempts = sessions.record_answer(session, key, req.answer, result)  # re-submits replace the old one
        return EvaluationResult(question_id=question["id"], attempt_number=attempts, **result)

    @app.post("/session/next", response_model=NextQuestionResponse)
    def next_question(req: SessionIdRequest):
        session = sessions.get(req.session_id)
        sessions.ensure_active(session)
        question, reason = adaptive.next_question(session)
        if question is None:
            return NextQuestionResponse(question=None, reason=reason, session_complete=True)
        sessions.serve(session, question, reason)
        return NextQuestionResponse(question=question, reason=reason, session_complete=False)

    @app.post("/session/end", response_model=SessionReport)
    def end_session(req: SessionIdRequest):
        """Finalise the session and return the report. Calling it twice returns the same report."""
        session = sessions.get(req.session_id)
        return sessions.complete(session, settings)

    @app.get("/session/{session_id}/report", response_model=SessionReport)
    def get_report(session_id: str):
        session = sessions.get(session_id)
        if session.status != "completed" or session.final_report is None:
            raise ApiError(409, "Session is still active. End the session first to get the final report.")
        return session.final_report

    # ---------------- voice & translation ----------------
    @app.post("/transcribe", response_model=TranscriptionResponse)
    def transcribe(file: UploadFile = File(...), language: Optional[str] = Form(None)):
        """Audio in -> text out. Does NOT evaluate or submit anything."""
        limit = int(settings.max_audio_mb * 1024 * 1024)
        data = file.file.read(limit + 1)     # read at most limit+1 bytes, then reject if too big
        text = transcriber.transcribe(data, file.filename or "", file.content_type, language)
        return TranscriptionResponse(text=text, model=settings.openai_transcribe_model)

    @app.post("/translate", response_model=TranslateResponse)
    def translate(req: TranslateRequest):
        """OPTIONAL: Hindi/Hinglish -> English. Never called automatically."""
        out = translate_to_english(req.text, settings, translator_client)
        return TranslateResponse(original_text=req.text, translated_text=out,
                                 model=settings.openai_translate_model)

    return app


app = create_app()
