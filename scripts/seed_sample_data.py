"""
CLI script to seed initial sample questions and an example viva session.

Usage:
    python scripts/seed_sample_data.py
"""
import asyncio
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.mongodb import close_mongo_connection, connect_to_mongo
from app.schemas.question import SubjectEnum
from app.schemas.session import SessionCreate
from app.services.question_service import question_service
from app.services.session_service import session_service


async def seed_data():
    print("[+] Seeding sample dataset and demonstration session...")
    await connect_to_mongo()
    try:
        data_file = os.path.join("data", "question_bank.json")
        if os.path.exists(data_file):
            with open(data_file, "r", encoding="utf-8") as f:
                res = await question_service.import_from_json(f.read())
            print(f"[*] Imported {res.imported} questions from {data_file}.")

        # Seed sample viva session for Operating Systems
        print("[*] Creating demonstration viva session for OS...")
        session = await session_service.create_session(
            SessionCreate(subject=SubjectEnum.OS, max_questions=3)
        )
        print(f"[*] Created viva session: {session.session_id}")
        if session.current_question:
            print(f"[*] Initial Question ({session.current_question.question_id}): {session.current_question.question}")

        # Submit sample answer
        sample_answer = (
            "A deadlock occurs when processes hold resources and wait for each other. "
            "The Coffman conditions are mutual exclusion, hold and wait, no preemption, and circular wait."
        )
        print("\n[*] Submitting sample student answer...")
        ans_res = await session_service.submit_text_answer(session.session_id, sample_answer)
        scoring = ans_res.evaluation.scoring
        print(f"[+] Evaluation Final Score: {scoring.final_score_100}/100 ({scoring.final_score_10}/10)")
        print(f"    - Concept Coverage:      {scoring.concept_coverage}%")
        print(f"    - Technical Correctness: {scoring.technical_correctness}%")
        print(f"    - Semantic Similarity:   {scoring.semantic_similarity}%")
        print(f"    - Reasoning Quality:     {scoring.reasoning_quality}%")
        print(f"    - Feedback: {ans_res.evaluation.concept_analysis.feedback}")
        if ans_res.next_question:
            print(f"\n[+] Next Adaptive Question ({ans_res.next_question.question_id} - {ans_res.next_question.difficulty}):")
            print(f"    {ans_res.next_question.question}")
        print("\n[+] Seeding complete! Database is ready.")
    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(seed_data())
