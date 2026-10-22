import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.question_service import question_service


@pytest.fixture(autouse=True)
async def seed_test_questions():
    """Ensure sample questions exist in the service for test sessions."""
    questions = [
        {
            "question_id": "OS_SESS_01",
            "subject": "OS",
            "topic": "Deadlocks",
            "difficulty": "medium",
            "question": "What is a deadlock and what are Coffman conditions?",
            "reference_answer": "A deadlock occurs when processes hold resources and wait indefinitely.",
            "key_concepts": ["Mutual exclusion", "Hold and wait", "No preemption", "Circular wait"],
        },
        {
            "question_id": "OS_SESS_02",
            "subject": "OS",
            "topic": "Memory Management",
            "difficulty": "easy",
            "question": "What is paging?",
            "reference_answer": "Paging splits logical memory into pages and physical memory into frames.",
            "key_concepts": ["Pages", "Frames", "Page table"],
        },
    ]
    await question_service.repo.insert_many(questions)


@pytest.mark.asyncio
async def test_viva_session_workflow_and_duplicate_prevention():
    """Verify end-to-end viva session workflow through REST APIs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a session
        create_res = await client.post("/api/v1/sessions", json={"subject": "OS", "max_questions": 2})
        assert create_res.status_code == 201
        session_data = create_res.json()
        session_id = session_data["session_id"]
        assert session_data["status"] == "active"
        assert session_data["current_question"] is not None
        initial_q_id = session_data["current_question"]["question_id"]

        # 2. Get current question
        cur_q_res = await client.get(f"/api/v1/sessions/{session_id}/current-question")
        assert cur_q_res.status_code == 200
        assert cur_q_res.json()["question_id"] == initial_q_id

        # 3. Submit valid text answer matching the question asked
        q_text = session_data["current_question"]["question"].lower()
        if "paging" in q_text:
            ans_text = "Paging is a memory management scheme that divides logical memory into pages and physical memory into frames using a page table."
        else:
            ans_text = "Deadlock occurs when processes hold resources and wait. Conditions include mutual exclusion, hold and wait, no preemption, and circular wait."

        ans_payload = {
            "question_id": initial_q_id,
            "student_answer": ans_text,
        }
        ans_res = await client.post(f"/api/v1/sessions/{session_id}/answers", json=ans_payload)
        assert ans_res.status_code == 200
        ans_data = ans_res.json()
        assert "evaluation" in ans_data
        assert ans_data["evaluation"]["scoring"]["final_score_100"] > 40.0

        # 4. Attempt duplicate submission on the same question -> expect HTTP 409 Conflict
        dup_res = await client.post(f"/api/v1/sessions/{session_id}/answers", json=ans_payload)
        assert dup_res.status_code == 409

        # 5. Check topic mastery endpoint
        mastery_res = await client.get(f"/api/v1/sessions/{session_id}/mastery")
        assert mastery_res.status_code == 200
        mastery_data = mastery_res.json()
        assert "topics" in mastery_data
        assert len(mastery_data["topics"]) > 0

        # 6. Check session history
        hist_res = await client.get(f"/api/v1/sessions/{session_id}/history")
        assert hist_res.status_code == 200
        hist_data = hist_res.json()
        assert len(hist_data["answers"]) == 1

        # 7. Complete session and fetch final report
        complete_res = await client.post(f"/api/v1/sessions/{session_id}/complete")
        assert complete_res.status_code == 200
        report = complete_res.json()
        assert "overall_score_100" in report
        assert "overall_score_10" in report
        assert "topic_wise_performance" in report
        assert "revision_recommendations" in report
        assert report["questions_attempted"] >= 1
