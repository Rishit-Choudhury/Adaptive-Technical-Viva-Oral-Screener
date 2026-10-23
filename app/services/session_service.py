from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from app.core.config import settings
from app.core.exceptions import (
    DuplicateAnswerError,
    QuestionNotFoundError,
    SessionNotFoundError,
    SessionStateError,
)
from app.core.logging import get_logger
from app.db.repositories.answer_repository import AnswerRepository
from app.db.repositories.session_repository import SessionRepository
from app.schemas.answer import AnswerSubmissionResponse, AudioAnswerResponse
from app.schemas.question import DifficultyEnum, QuestionSafe, SubjectEnum
from app.schemas.report import FinalReport
from app.schemas.evaluation import EvaluationResult
from app.schemas.session import (
    AnswerRecord,
    SessionCreate,
    SessionHistoryResponse,
    SessionResponse,
    SessionStatus,
)
from app.services.adaptive_engine import adaptive_engine
from app.services.evaluation_service import evaluation_service
from app.services.mastery_service import mastery_service
from app.services.question_service import question_service
from app.services.report_service import report_service
from app.services.speech_service import speech_service

logger = get_logger("app.services.session")


class SessionService:
    """
    Coordinates end-to-end viva session lifecycle: creation, question flow,
    answer evaluation, mastery updates, adaptive transitions, and final report generation.
    """

    def __init__(
        self,
        session_repo: Optional[SessionRepository] = None,
        answer_repo: Optional[AnswerRepository] = None,
    ) -> None:
        self.session_repo = session_repo or SessionRepository()
        self.answer_repo = answer_repo or AnswerRepository()
        self.question_svc = question_service
        self.eval_svc = evaluation_service
        self.mastery_svc = mastery_service
        self.adaptive_eng = adaptive_engine
        self.report_svc = report_service
        self.speech_svc = speech_service

    async def create_session(self, payload: SessionCreate) -> SessionResponse:
        """Create a new viva session and select the initial eligible question."""
        session_id = f"viva_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        max_q = payload.max_questions or settings.MAX_QUESTIONS_PER_SESSION

        # Select starting question from dataset
        initial_q_safe = await self.question_svc.select_initial_question(
            subject=payload.subject,
            difficulty=payload.initial_difficulty,
        )

        session_doc: Dict[str, Any] = {
            "session_id": session_id,
            "subject": payload.subject.value,
            "status": SessionStatus.ACTIVE.value,
            "current_question": initial_q_safe.model_dump(),
            "previously_asked_question_ids": [initial_q_safe.question_id],
            "questions_answered_count": 0,
            "max_questions": max_q,
            "current_overall_score_100": None,
            "current_overall_score_10": None,
            "answers": [],
            "report": None,
            "created_at": now,
            "updated_at": now,
        }

        await self.session_repo.create_session(session_doc)
        logger.info("Created viva session %s for %s with first question %s", session_id, payload.subject.value, initial_q_safe.question_id)

        return SessionResponse(
            session_id=session_id,
            subject=payload.subject,
            status=SessionStatus.ACTIVE,
            current_question=initial_q_safe,
            previously_asked_question_ids=[initial_q_safe.question_id],
            questions_answered_count=0,
            max_questions=max_q,
            current_overall_score_100=None,
            current_overall_score_10=None,
            created_at=now,
            updated_at=now,
        )

    async def get_session(self, session_id: str) -> SessionResponse:
        """Retrieve current session state."""
        doc = await self.session_repo.get_session(session_id)
        if not doc:
            raise SessionNotFoundError(f"Session '{session_id}' not found.")

        current_q = QuestionSafe(**doc["current_question"]) if doc.get("current_question") else None
        return SessionResponse(
            session_id=doc["session_id"],
            subject=SubjectEnum(doc["subject"]),
            status=SessionStatus(doc["status"]),
            current_question=current_q,
            previously_asked_question_ids=doc.get("previously_asked_question_ids", []),
            questions_answered_count=doc.get("questions_answered_count", 0),
            max_questions=doc.get("max_questions", settings.MAX_QUESTIONS_PER_SESSION),
            current_overall_score_100=doc.get("current_overall_score_100"),
            current_overall_score_10=doc.get("current_overall_score_10"),
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )

    async def get_current_question(self, session_id: str) -> QuestionSafe:
        """Get the question the student is currently expected to answer."""
        session = await self.get_session(session_id)
        if session.status != SessionStatus.ACTIVE:
            raise SessionStateError(f"Session is already {session.status.value}.")
        if not session.current_question:
            raise SessionStateError("No active question in this session.")
        return session.current_question

    async def submit_text_answer(
        self,
        session_id: str,
        student_answer: str,
        question_id: Optional[str] = None,
    ) -> AnswerSubmissionResponse:
        """Submit and evaluate a written text answer."""
        return await self._process_answer_submission(
            session_id=session_id,
            student_answer=student_answer,
            transcript=None,
            target_question_id=question_id,
        )

    async def submit_audio_answer(
        self,
        session_id: str,
        audio_bytes: bytes,
        filename: str = "answer.wav",
    ) -> AudioAnswerResponse:
        """Transcribe speech-to-text with Faster-Whisper, then submit and evaluate."""
        # 1. Transcribe audio to text
        transcript = await self.speech_svc.transcribe_audio_bytes(audio_bytes, filename=filename)

        # 2. Process answer submission with transcript
        sub_res = await self._process_answer_submission(
            session_id=session_id,
            student_answer=transcript,
            transcript=transcript,
        )

        return AudioAnswerResponse(
            transcript=transcript,
            evaluation=sub_res.evaluation,
            next_question=sub_res.next_question,
            is_session_completed=sub_res.is_session_completed,
        )

    async def _process_answer_submission(
        self,
        session_id: str,
        student_answer: str,
        transcript: Optional[str] = None,
        target_question_id: Optional[str] = None,
    ) -> AnswerSubmissionResponse:
        """Core internal pipeline for evaluating and advancing answer submissions."""
        doc = await self.session_repo.get_session(session_id)
        if not doc:
            raise SessionNotFoundError(f"Session '{session_id}' not found.")

        # Explicit target question duplicate check
        if target_question_id and await self.answer_repo.has_answered_question(session_id, target_question_id):
            raise DuplicateAnswerError(f"Question '{target_question_id}' has already been answered in session '{session_id}'.")

        current_q_data = doc.get("current_question")
        if current_q_data:
            q_id = current_q_data["question_id"]
            if target_question_id and target_question_id != q_id:
                raise SessionStateError(f"Question '{target_question_id}' is not the current active question.")
            if await self.answer_repo.has_answered_question(session_id, q_id):
                raise DuplicateAnswerError(f"Question '{q_id}' has already been answered in session '{session_id}'.")
        else:
            # If current question is None and answers exist, repeated submission is a duplicate
            if await self.answer_repo.get_answers_for_session(session_id):
                raise DuplicateAnswerError(f"Question has already been answered in session '{session_id}'.")

        if doc["status"] != SessionStatus.ACTIVE.value:
            raise SessionStateError(f"Cannot submit answer: session is {doc['status']}.")

        if not current_q_data:
            raise SessionStateError("No current question assigned to this session.")

        q_id = current_q_data["question_id"]

        # Retrieve raw question with reference answer and expected key concepts
        raw_q = await self.question_svc.get_raw_question(q_id)

        # Evaluate response
        eval_result = await self.eval_svc.evaluate_answer(
            question_id=q_id,
            question=raw_q["question"],
            reference_answer=raw_q["reference_answer"],
            expected_concepts=raw_q.get("key_concepts", []),
            student_answer=student_answer,
            subject=raw_q["subject"],
            topic=raw_q["topic"],
        )

        # Update topic mastery
        await self.mastery_svc.update_mastery(
            session_id=session_id,
            subject=raw_q["subject"],
            topic=raw_q["topic"],
            score_100=eval_result.scoring.final_score_100,
            difficulty=raw_q["difficulty"],
            covered_concepts=eval_result.concept_analysis.covered_concepts,
            missing_concepts=eval_result.concept_analysis.missing_concepts,
        )

        # Persist answer to answer repository
        answer_record_doc = {
            "session_id": session_id,
            "question_id": q_id,
            "question_text": raw_q["question"],
            "topic": raw_q["topic"],
            "difficulty": raw_q["difficulty"],
            "student_answer": student_answer,
            "transcript": transcript,
            "evaluation": eval_result.model_dump(),
            "answer_index": len(doc.get("answers", [])) + 1,
            "created_at": datetime.now(timezone.utc),
        }
        await self.answer_repo.save_answer(answer_record_doc)

        # Calculate running overall score
        all_answers = doc.get("answers", []) + [answer_record_doc]
        running_scores = [a["evaluation"]["scoring"]["final_score_100"] for a in all_answers]
        overall_100 = round(sum(running_scores) / len(running_scores), 2)
        overall_10 = round(overall_100 / 10.0, 2)

        # Append answer to session document
        await self.session_repo.append_answer(
            session_id=session_id,
            answer_record=answer_record_doc,
            overall_score_100=overall_100,
            overall_score_10=overall_10,
        )

        # Check if session should complete (limit reached)
        max_q = doc.get("max_questions", settings.MAX_QUESTIONS_PER_SESSION)
        is_completed = len(all_answers) >= max_q
        next_q: Optional[QuestionSafe] = None

        if not is_completed:
            # Adaptively select next question
            prev_ids = doc.get("previously_asked_question_ids", [])
            next_q, reason = await self.adaptive_eng.select_next_question(
                subject=SubjectEnum(doc["subject"]),
                last_question=raw_q,
                last_evaluation=eval_result,
                previously_asked_ids=prev_ids,
            )
            if next_q:
                await self.session_repo.update_current_question(session_id, next_q.model_dump())
                logger.info("Adaptive engine selected next question %s for %s. Reason: %s", next_q.question_id, session_id, reason)
            else:
                # No eligible questions remain
                is_completed = True
                await self.session_repo.update_current_question(session_id, None)

        if is_completed:
            # Generate and persist final report
            report = await self.report_svc.generate_report(
                session_id=session_id,
                subject=SubjectEnum(doc["subject"]),
                answers=all_answers,
            )
            await self.session_repo.complete_session(session_id, report.model_dump())
            logger.info("Viva session %s reached completion. Final score: %.1f/100", session_id, overall_100)

        return AnswerSubmissionResponse(
            question_id=q_id,
            student_answer=student_answer,
            evaluation=eval_result,
            next_question=next_q,
            is_session_completed=is_completed,
        )

    async def advance_to_next_question(self, session_id: str) -> Optional[QuestionSafe]:
        """Explicitly trigger adaptive selection for the next question if needed."""
        doc = await self.session_repo.get_session(session_id)
        if not doc:
            raise SessionNotFoundError(f"Session '{session_id}' not found.")
        if doc["status"] != SessionStatus.ACTIVE.value:
            raise SessionStateError(f"Session is {doc['status']}.")
        if doc.get("current_question"):
            return QuestionSafe(**doc["current_question"])

        # Select next question
        answers = doc.get("answers", [])
        if not answers:
            # No answers yet, select initial question
            next_q = await self.question_svc.select_initial_question(SubjectEnum(doc["subject"]))
        else:
            last_ans = answers[-1]
            last_eval = EvaluationResult(**last_ans["evaluation"])
            last_q = await self.question_svc.get_raw_question(last_ans["question_id"])
            next_q, _ = await self.adaptive_eng.select_next_question(
                subject=SubjectEnum(doc["subject"]),
                last_question=last_q,
                last_evaluation=last_eval,
                previously_asked_ids=doc.get("previously_asked_question_ids", []),
            )

        if next_q:
            await self.session_repo.update_current_question(session_id, next_q.model_dump())
        return next_q

    async def complete_session(self, session_id: str) -> FinalReport:
        """Manually finish session and generate final report."""
        doc = await self.session_repo.get_session(session_id)
        if not doc:
            raise SessionNotFoundError(f"Session '{session_id}' not found.")

        if doc.get("report"):
            return FinalReport(**doc["report"])

        report = await self.report_svc.generate_report(
            session_id=session_id,
            subject=SubjectEnum(doc["subject"]),
            answers=doc.get("answers", []),
        )
        await self.session_repo.complete_session(session_id, report.model_dump())
        return report

    async def get_session_history(self, session_id: str) -> SessionHistoryResponse:
        """Retrieve full answer log and report for a session."""
        doc = await self.session_repo.get_session(session_id)
        if not doc:
            raise SessionNotFoundError(f"Session '{session_id}' not found.")

        answers_list: List[AnswerRecord] = []
        for a in doc.get("answers", []):
            answers_list.append(
                AnswerRecord(
                    question_id=a["question_id"],
                    question_text=a["question_text"],
                    topic=a["topic"],
                    difficulty=a["difficulty"],
                    student_answer=a["student_answer"],
                    transcript=a.get("transcript"),
                    evaluation=EvaluationResult(**a["evaluation"]),
                    answered_at=a.get("created_at", datetime.now(timezone.utc)),
                )
            )

        report = FinalReport(**doc["report"]) if doc.get("report") else None
        return SessionHistoryResponse(
            session_id=doc["session_id"],
            subject=SubjectEnum(doc["subject"]),
            status=SessionStatus(doc["status"]),
            answers=answers_list,
            report=report,
        )

    async def get_session_report(self, session_id: str) -> FinalReport:
        """Retrieve the final report for a session."""
        doc = await self.session_repo.get_session(session_id)
        if not doc:
            raise SessionNotFoundError(f"Session '{session_id}' not found.")
        if doc.get("report"):
            return FinalReport(**doc["report"])
        return await self.complete_session(session_id)


session_service = SessionService()
