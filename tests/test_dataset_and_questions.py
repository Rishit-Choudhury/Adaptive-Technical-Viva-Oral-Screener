import json
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.question import DifficultyEnum, SubjectEnum
from app.services.question_service import QuestionService
from app.utils.validators import validate_question_record


@pytest.mark.asyncio
async def test_dataset_json_import():
    """Verify importing valid questions from JSON string."""
    service = QuestionService()
    sample_json = json.dumps([
        {
            "question_id": "TEST_OS_01",
            "subject": "OS",
            "topic": "Process Management",
            "difficulty": "easy",
            "question": "What is a process control block (PCB)?",
            "reference_answer": "A PCB is a data structure storing process state and registers.",
            "key_concepts": ["Process state", "Program counter", "CPU registers"],
            "tags": ["processes"]
        }
    ])
    result = await service.import_from_json(sample_json)
    assert result.imported == 1
    assert result.total_processed == 1
    assert len(result.invalid_records) == 0

    # Retrieve and check student-safe representation
    safe_q = await service.get_question_safe("TEST_OS_01")
    assert safe_q.question_id == "TEST_OS_01"
    assert safe_q.question == "What is a process control block (PCB)?"
    # Verify reference answer and key concepts are NOT in safe model
    assert not hasattr(safe_q, "reference_answer")
    assert not hasattr(safe_q, "key_concepts")


@pytest.mark.asyncio
async def test_dataset_csv_import():
    """Verify importing questions from CSV formatted text."""
    service = QuestionService()
    csv_data = """question_id,subject,topic,difficulty,question,reference_answer,key_concepts,tags
TEST_CN_01,CN,Transport Layer,medium,What is UDP?,UDP is a connectionless transport protocol.,Connectionless|Best effort|No handshake,udp|networking
"""
    result = await service.import_from_csv(csv_data)
    assert result.imported == 1
    assert result.total_processed == 1

    safe_q = await service.get_question_safe("TEST_CN_01")
    assert safe_q.subject == SubjectEnum.CN
    assert safe_q.difficulty == DifficultyEnum.MEDIUM


def test_question_record_validation():
    """Verify validation detects missing fields and invalid enum values."""
    # Missing reference_answer
    invalid_rec = {
        "question_id": "ERR01",
        "subject": "OS",
        "topic": "Testing",
        "difficulty": "easy",
        "question": "Incomplete record?",
        "key_concepts": ["concept"]
    }
    is_valid, msg = validate_question_record(invalid_rec, 0)
    assert not is_valid
    assert "missing required fields" in msg

    # Invalid subject
    invalid_sub = {
        "question_id": "ERR02",
        "subject": "INVALID_SUBJECT",
        "topic": "Testing",
        "difficulty": "easy",
        "question": "Test question?",
        "reference_answer": "Test answer",
        "key_concepts": ["concept"]
    }
    is_valid, msg = validate_question_record(invalid_sub, 1)
    assert not is_valid
    assert "Invalid subject" in msg


@pytest.mark.asyncio
async def test_api_questions_endpoint_student_safe():
    """Verify GET /api/v1/questions does not leak ground-truth reference answers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/questions")
        assert response.status_code == 200
        items = response.json()
        assert isinstance(items, list)
        for item in items:
            assert "reference_answer" not in item
            assert "key_concepts" not in item
            assert "question_id" in item
            assert "question" in item
