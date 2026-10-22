import json
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.core.exceptions import LLMProviderError
from app.core.logging import get_logger
from app.schemas.evaluation import ConceptAnalysisResult
from app.utils.text_processing import compute_heuristic_concept_coverage

logger = get_logger("app.services.llm")


class LLMService:
    """
    Service for invoking LLMs to analyze student conceptual understanding.
    Supports 'mock', 'groq', and 'openai' providers with JSON validation.
    """

    def __init__(self) -> None:
        self.provider = settings.LLM_PROVIDER.lower()
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.timeout = settings.LLM_TIMEOUT_SECONDS

    def _build_prompt(
        self,
        question: str,
        reference_answer: str,
        expected_concepts: List[str],
        student_answer: str,
        subject: str,
        topic: str,
    ) -> str:
        return f"""You are a Computer Science viva oral examiner assessing student conceptual understanding in {subject} ({topic}).

Question:
"{question}"

Ground-Truth Reference Answer:
"{reference_answer}"

Expected Key Concepts:
{json.dumps(expected_concepts)}

Student's Viva Answer:
"{student_answer}"

Evaluate the student's answer objectively against the reference answer and key concepts.
Return ONLY a valid JSON object strictly matching this schema:
{{
  "technical_correctness": <float 0-100 indicating accuracy of factual statements>,
  "covered_concepts": [<list of expected key concepts clearly demonstrated in the answer>],
  "missing_concepts": [<list of expected key concepts omitted or misunderstood>],
  "incorrect_statements": [<list of false or misleading statements in the student's answer>],
  "reasoning_quality": <float 0-100 evaluating clarity, terminology, and logical coherence>,
  "feedback": "<clear, constructive 2-3 sentence explanation of strengths and gaps>",
  "suggested_follow_up_focus": [<list of 1-3 concept topics that need further probing>]
}}
Do NOT output markdown code fences (like ```json), just the raw JSON object.
"""

    async def analyze_concepts(
        self,
        question: str,
        reference_answer: str,
        expected_concepts: List[str],
        student_answer: str,
        subject: str,
        topic: str,
    ) -> ConceptAnalysisResult:
        """
        Analyze student answer against ground truth and return validated ConceptAnalysisResult.
        """
        # If student answer is empty, return empty assessment immediately
        if not student_answer or not student_answer.strip():
            return ConceptAnalysisResult(
                technical_correctness=0.0,
                covered_concepts=[],
                missing_concepts=list(expected_concepts),
                incorrect_statements=[],
                reasoning_quality=0.0,
                feedback="No answer was provided.",
                suggested_follow_up_focus=list(expected_concepts)[:2],
            )

        if self.provider == "mock" or not self.api_key:
            return self._mock_analysis(student_answer, reference_answer, expected_concepts, topic)

        if self.provider == "groq":
            return await self._call_groq(question, reference_answer, expected_concepts, student_answer, subject, topic)

        if self.provider == "openai":
            return await self._call_openai(question, reference_answer, expected_concepts, student_answer, subject, topic)

        # Fallback to mock if provider is unknown
        logger.warning("Unrecognized provider '%s', defaulting to mock analysis", self.provider)
        return self._mock_analysis(student_answer, reference_answer, expected_concepts, topic)

    def _mock_analysis(
        self,
        student_answer: str,
        reference_answer: str,
        expected_concepts: List[str],
        topic: str,
    ) -> ConceptAnalysisResult:
        """
        Deterministic mock implementation using heuristic concept analysis.
        Ensures consistent, testable evaluations without requiring third-party API keys.
        """
        covered, missing, coverage_score = compute_heuristic_concept_coverage(student_answer, expected_concepts)

        # Determine technical correctness based on coverage and length
        word_count = len(student_answer.split())
        length_factor = min(1.0, max(0.2, word_count / 25.0))
        technical_correctness = round(min(100.0, (coverage_score * 0.7) + (length_factor * 30.0)), 2)
        reasoning_quality = round(min(100.0, (coverage_score * 0.5) + (length_factor * 50.0)), 2)

        incorrect = []
        if "not" in student_answer.lower() and coverage_score < 30:
            incorrect.append("Possible negation or contradictory statement regarding core mechanism.")

        feedback = (
            f"Demonstrated good awareness of {', '.join(covered)}."
            if covered
            else "The answer lacks key technical concepts required for this topic."
        )
        if missing:
            feedback += f" Consider elaborating on {', '.join(missing[:2])}."

        return ConceptAnalysisResult(
            technical_correctness=technical_correctness,
            covered_concepts=covered,
            missing_concepts=missing,
            incorrect_statements=incorrect,
            reasoning_quality=reasoning_quality,
            feedback=feedback,
            suggested_follow_up_focus=missing[:2] if missing else [topic],
        )

    async def _call_groq(
        self,
        question: str,
        reference_answer: str,
        expected_concepts: List[str],
        student_answer: str,
        subject: str,
        topic: str,
    ) -> ConceptAnalysisResult:
        """Call Groq API using JSON mode."""
        prompt = self._build_prompt(question, reference_answer, expected_concepts, student_answer, subject, topic)
        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=self.api_key, timeout=self.timeout)
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            raw_text = response.choices[0].message.content or "{}"
            parsed = json.loads(raw_text)
            return ConceptAnalysisResult(**parsed)
        except Exception as exc:
            logger.error("Groq API call failed (%s). Falling back to heuristic analysis.", exc)
            return self._mock_analysis(student_answer, reference_answer, expected_concepts, topic)

    async def _call_openai(
        self,
        question: str,
        reference_answer: str,
        expected_concepts: List[str],
        student_answer: str,
        subject: str,
        topic: str,
    ) -> ConceptAnalysisResult:
        """Call OpenAI API with response_format json_object."""
        prompt = self._build_prompt(question, reference_answer, expected_concepts, student_answer, subject, topic)
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model if "gpt" in self.model else "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
                content = data["choices"][0]["message"]["content"]
                return ConceptAnalysisResult(**json.loads(content))
        except Exception as exc:
            logger.error("OpenAI API call failed (%s). Falling back to heuristic analysis.", exc)
            return self._mock_analysis(student_answer, reference_answer, expected_concepts, topic)


llm_service = LLMService()
