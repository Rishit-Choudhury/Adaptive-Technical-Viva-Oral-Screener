"""
Adaptive Viva Preparation - Streamlit frontend (single file: frontend/app.py)

WORKS NOW (local mode, no backend needed):
  - Loading questions from backend/question_bank.json
  - Subject selection, question display, answer saving, navigation
  - Model answer reveal, results dashboard built from real session data
  - Basic KEYWORD-COVERAGE check (NOT AI - clearly labelled in the UI)

NEEDS THE FASTAPI BACKEND (placeholders, not connected yet):
  - Real answer evaluation, adaptive next question, final results
  - Edit the ENDPOINTS dictionary below to match your backend/main.py

NOT IMPLEMENTED:
  - Speech-to-text. The mic only records audio; typing is the real input.

Run (Windows, inside frontend/ with venv activated):
  pip install streamlit pandas requests
  streamlit run app.py
"""

import json
import os
import random
import re
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import requests
except ImportError:  # only needed for backend mode
    requests = None

st.set_page_config(page_title="Adaptive Viva Preparation", page_icon="🎓", layout="wide")

# =====================================================================
# 1. CONFIGURATION
# =====================================================================
BASE_DIR = Path(__file__).resolve().parent
QUESTION_BANK_PATH = BASE_DIR.parent / "backend" / "question_bank.json"
FALLBACK_FILES = [  # used only if the main file is missing
    BASE_DIR / "data" / "os_questions.json",
    BASE_DIR / "data" / "dbms_questions.json",
    BASE_DIR / "data" / "cn_questions.json",
]
SUBJECTS = {
    "OS": "Operating Systems",
    "DBMS": "Database Management Systems",
    "CN": "Computer Networks",
}
REQUIRED_FIELDS = ["id", "subject", "topic", "difficulty", "question", "model_answer", "key_concepts"]

API_BASE_URL = os.getenv("VIVA_API_URL", "http://127.0.0.1:8000")
API_TIMEOUT = 10  # seconds

# PLACEHOLDERS - these paths are NOT confirmed. Change them to match backend/main.py.
ENDPOINTS = {
    "start_session": "/session/start",
    "evaluate": "/session/evaluate",
    "next_question": "/session/next",
    "end_session": "/session/end",
}

STRONG_SCORE = 70  # topic average >= this is shown as "strong"
WEAK_SCORE = 50    # topic average < this is shown as "weak"


# =====================================================================
# 2. QUESTION LOADING (no Streamlit UI code in this section)
# =====================================================================
def read_json_list(path):
    """Read a JSON file that should contain a list. Returns (list, error_message)."""
    if not path.exists():
        return [], f"File not found: {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [], f"Invalid JSON in {path.name}: {e}"
    except OSError as e:
        return [], f"Could not read {path.name}: {e}"
    if not isinstance(data, list):
        return [], f"{path.name} must contain a JSON list of questions."
    return data, None


def clean_question(raw):
    """Return a cleaned question dict, or None if it is badly formatted."""
    if not isinstance(raw, dict):
        return None
    for field in REQUIRED_FIELDS:
        if field not in raw:
            return None
    if not str(raw["question"]).strip():
        return None
    concepts = raw["key_concepts"]
    if not isinstance(concepts, list):
        concepts = []
    return {
        "id": raw["id"],
        "subject": str(raw["subject"]).strip().upper(),
        "topic": str(raw["topic"]).strip() or "General",
        "difficulty": str(raw["difficulty"]).strip().title() or "Unknown",
        "question": str(raw["question"]).strip(),
        "model_answer": str(raw["model_answer"]).strip(),
        "key_concepts": [str(c) for c in concepts],
        "source": str(raw.get("source", "")),
    }


@st.cache_data
def load_question_bank():
    """Load all questions once. Returns (list_of_questions, list_of_warnings)."""
    warnings, raw_items = [], []
    data, err = read_json_list(QUESTION_BANK_PATH)
    if err is None:
        raw_items = data
    else:
        warnings.append(err + " - trying data/ folder instead.")
        for path in FALLBACK_FILES:
            data, err = read_json_list(path)
            if err:
                warnings.append(err)
            else:
                raw_items.extend(data)

    questions, bad = [], 0
    for item in raw_items:
        q = clean_question(item)
        if q is None:
            bad += 1
        else:
            questions.append(q)
    if bad:
        warnings.append(f"Skipped {bad} question(s) with missing or invalid fields.")
    return questions, warnings


def pick_questions(all_questions, subject, count, difficulty):
    """Pick random questions for a session (plain random - NOT adaptive)."""
    pool = [q for q in all_questions if q["subject"] == subject]
    if difficulty != "All":
        pool = [q for q in pool if q["difficulty"] == difficulty]
    random.shuffle(pool)
    return pool[:count]


# =====================================================================
# 3. LOCAL EVALUATION (basic keyword check - NOT AI)
# =====================================================================
def concept_is_covered(concept, answer_lower):
    """True if the concept (or most of its words) appears in the answer."""
    c = concept.lower().strip()
    if c and c in answer_lower:
        return True
    words = [w for w in re.findall(r"[a-z0-9]+", c) if len(w) > 2]
    if not words:
        return False
    hits = sum(1 for w in words if w in answer_lower)
    return hits / len(words) >= 0.6


def evaluate_locally(question, answer):
    """Compare the answer with key_concepts using simple keyword matching."""
    answer_lower = answer.lower()
    concepts = question["key_concepts"]
    covered = [c for c in concepts if concept_is_covered(c, answer_lower)]
    missing = [c for c in concepts if c not in covered]
    score = round(100 * len(covered) / len(concepts)) if concepts else None
    suggestions = []
    if missing:
        suggestions.append("Revise and mention: " + ", ".join(missing))
    suggestions.append("Compare your answer with the model answer below.")
    return {
        "score": score,
        "strengths": [f"Mentioned: {c}" for c in covered],
        "covered_concepts": covered,
        "missing_concepts": missing,
        "suggestions": suggestions,
        "adaptation_note": None,
        "source": "Local keyword check (not AI evaluation)",
    }


# =====================================================================
# 4. API LAYER (placeholders - nothing here is confirmed to exist yet)
# =====================================================================
def call_api(method, endpoint_key, payload=None):
    """Send a request to the backend. Returns (json_data, error_message)."""
    if requests is None:
        return None, "The 'requests' package is not installed (pip install requests)."
    url = API_BASE_URL.rstrip("/") + ENDPOINTS[endpoint_key]
    try:
        resp = requests.request(method, url, json=payload, timeout=API_TIMEOUT)
    except requests.exceptions.ConnectionError:
        return None, f"Cannot reach the backend at {API_BASE_URL}. Is FastAPI running?"
    except requests.exceptions.Timeout:
        return None, f"The backend did not respond within {API_TIMEOUT} seconds."
    except requests.exceptions.RequestException as e:
        return None, f"Request failed: {e}"
    if resp.status_code != 200:
        return None, f"Backend returned status {resp.status_code}: {resp.text[:200]}"
    try:
        return resp.json(), None
    except ValueError:
        return None, "Backend response was not valid JSON."


def api_start_session(subject, count):
    # ASSUMED response shape: {"session_id": ..., "question": {...question fields...}}
    return call_api("POST", "start_session", {"subject": subject, "num_questions": count})


def api_evaluate(session_id, question_id, answer):
    # ASSUMED response: score, strengths, missing_concepts, suggestions, ...
    return call_api("POST", "evaluate",
                    {"session_id": session_id, "question_id": question_id, "answer": answer})


def api_next_question(session_id):
    # ASSUMED response: {"question": {...}, "reason": "why this question"} or {"question": null}
    return call_api("POST", "next_question", {"session_id": session_id})


def api_end_session(session_id):
    return call_api("POST", "end_session", {"session_id": session_id})


def normalize_feedback(raw):
    """Fill missing fields so the UI never crashes on incomplete backend data."""
    raw = raw if isinstance(raw, dict) else {}
    score = raw.get("score")
    if not isinstance(score, (int, float)):
        score = None

    def as_list(value):
        return [str(v) for v in value] if isinstance(value, list) else []

    return {
        "score": score,
        "strengths": as_list(raw.get("strengths")),
        "covered_concepts": as_list(raw.get("covered_concepts")),
        "missing_concepts": as_list(raw.get("missing_concepts")),
        "suggestions": as_list(raw.get("suggestions")),
        "adaptation_note": raw.get("adaptation_note") or raw.get("reason"),
        "source": raw.get("source", "Backend evaluation"),
    }


# =====================================================================
# 5. VOICE (record only - transcription NOT implemented)
# =====================================================================
def transcribe_audio(audio_file):
    """PLACEHOLDER: connect a speech-to-text service here later. Returns None for now."""
    return None


# =====================================================================
# 6. SESSION STATE
# =====================================================================
def init_state():
    defaults = {
        "page": "home",
        "subject": None,
        "questions": [],
        "index": 0,
        "answers": {},        # {question_index: answer_text}
        "results": {},        # {question_index: {"answer":..., "feedback":...}}
        "adaptation": {},     # {question_index: reason text from backend}
        "session_count": 0,   # changes on every new session so old widgets are discarded
        "session_length": 5,
        "use_backend": False,
        "backend_session_id": None,
        "backend_final": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_session():
    """Clear all per-session data (no stale answers or feedback)."""
    st.session_state.questions = []
    st.session_state.index = 0
    st.session_state.answers = {}
    st.session_state.results = {}
    st.session_state.adaptation = {}
    st.session_state.backend_session_id = None
    st.session_state.backend_final = None
    st.session_state.session_count += 1


def go_home():
    reset_session()
    st.session_state.subject = None
    st.session_state.page = "home"


def start_session(subject, count, difficulty, all_questions):
    reset_session()
    st.session_state.subject = subject
    st.session_state.session_length = count

    if st.session_state.use_backend:
        data, err = api_start_session(subject, count)
        if err:
            st.error(err)
            return
        first = clean_question((data or {}).get("question"))
        if first is None:
            st.error("Backend did not return a valid first question.")
            return
        st.session_state.backend_session_id = data.get("session_id")
        st.session_state.questions = [first]
    else:
        chosen = pick_questions(all_questions, subject, count, difficulty)
        if not chosen:
            st.error("No questions available for this subject/difficulty.")
            return
        if len(chosen) < count:
            st.warning(f"Only {len(chosen)} question(s) available; session shortened.")
        st.session_state.questions = chosen
    st.session_state.page = "viva"
    st.rerun()


def finish_session():
    if st.session_state.use_backend and st.session_state.backend_session_id is not None:
        data, err = api_end_session(st.session_state.backend_session_id)
        if err:
            st.warning(f"Could not fetch final results from backend: {err}")
        else:
            st.session_state.backend_final = data
    st.session_state.page = "results"
    st.rerun()


# =====================================================================
# 7. PAGES
# =====================================================================
def show_sidebar():
    with st.sidebar:
        st.header("⚙️ Settings")
        st.session_state.use_backend = st.toggle(
            "Use FastAPI backend",
            value=st.session_state.use_backend,
            disabled=st.session_state.page == "viva",
            help="Off = local JSON mode. On = placeholders that need your backend endpoints.",
        )
        if st.session_state.use_backend:
            st.caption(f"API: {API_BASE_URL}")
            st.warning("Backend mode uses PLACEHOLDER endpoints. Edit ENDPOINTS in app.py first.")
        else:
            st.caption("Local mode: questions come from JSON, evaluation is a simple keyword check.")
        if st.session_state.page != "home":
            st.divider()
            if st.button("🔄 Restart session", use_container_width=True):
                subject = st.session_state.subject
                count = st.session_state.session_length
                go_home()
                st.session_state.subject = subject
                st.rerun()
            if st.button("🏠 Back to home", use_container_width=True):
                go_home()
                st.rerun()


def show_home(all_questions, warnings):
    st.title("🎓 Adaptive Viva Preparation")
    st.write(
        "Practise viva questions in **Operating Systems**, **DBMS** and **Computer Networks**. "
        "Type your answer, get feedback, and review your performance at the end."
    )
    for w in warnings:
        st.warning(w)
    if not all_questions and not st.session_state.use_backend:
        st.error("No valid questions could be loaded. Check backend/question_bank.json.")
        return

    st.subheader("1. Choose a subject")
    cols = st.columns(3)
    for col, (code, name) in zip(cols, SUBJECTS.items()):
        count = sum(1 for q in all_questions if q["subject"] == code)
        with col:
            with st.container(border=True):
                st.markdown(f"### {code}")
                st.write(name)
                st.caption(f"{count} questions in local bank")
                if st.button(f"Select {code}", key=f"pick_{code}", use_container_width=True):
                    st.session_state.subject = code

    subject = st.session_state.subject
    if subject is None:
        st.info("Select a subject to continue.")
        return

    st.success(f"Selected: {SUBJECTS[subject]}")
    st.subheader("2. Session options")
    available = [q for q in all_questions if q["subject"] == subject]
    difficulties = ["All"] + sorted({q["difficulty"] for q in available})
    c1, c2 = st.columns(2)
    with c1:
        max_q = max(1, min(20, len(available))) if not st.session_state.use_backend else 20
        count = st.slider("Number of questions", 1, max_q, min(5, max_q))
    with c2:
        difficulty = st.selectbox("Difficulty filter (local mode only)", difficulties)

    if st.button("▶️ Start viva session", type="primary"):
        start_session(subject, count, difficulty, all_questions)


def show_feedback(fb, question):
    """Display evaluation feedback (from backend or local check)."""
    st.subheader("📝 Feedback")
    st.caption(f"Source: {fb['source']}")
    if fb["score"] is None:
        st.info("Score: not provided.")
    else:
        st.metric("Score", f"{fb['score']:.0f} / 100")
        st.progress(min(max(fb["score"] / 100, 0.0), 1.0))

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**✅ Strengths**")
        if fb["strengths"]:
            for s in fb["strengths"]:
                st.write(f"- {s}")
        else:
            st.caption("None provided.")
    with c2:
        st.markdown("**⚠️ Missing concepts**")
        if fb["missing_concepts"]:
            for m in fb["missing_concepts"]:
                st.write(f"- {m}")
        else:
            st.caption("None reported.")

    st.markdown("**💡 Suggestions**")
    if fb["suggestions"]:
        for s in fb["suggestions"]:
            st.write(f"- {s}")
    else:
        st.caption("None provided.")

    st.markdown("**Key concepts for this question:** " + (", ".join(question["key_concepts"]) or "N/A"))
    with st.expander("📖 Model answer"):
        st.write(question["model_answer"])


def show_viva():
    questions = st.session_state.questions
    idx = st.session_state.index
    total = st.session_state.session_length if st.session_state.use_backend else len(questions)
    if not questions or idx >= len(questions):
        st.error("No question to display.")
        if st.button("Back to home"):
            go_home()
            st.rerun()
        return

    q = questions[idx]
    sid = st.session_state.session_count

    st.title(f"{st.session_state.subject} Viva Session")
    answered = len(st.session_state.results)
    st.progress(answered / total if total else 0, text=f"Answered {answered} of {total}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Question", f"{idx + 1} / {total}")
    c2.metric("Subject", q["subject"])
    c3.metric("Topic", q["topic"])
    c4.metric("Difficulty", q["difficulty"])

    note = st.session_state.adaptation.get(idx)
    if note:
        st.info(f"Why this question: {note}")
    elif not st.session_state.use_backend:
        st.caption("Local mode: questions are picked randomly (no adaptation).")

    st.subheader(q["question"])

    # Optional voice input (recording only)
    with st.expander("🎤 Voice answer (optional, experimental)"):
        if hasattr(st, "audio_input"):
            audio = st.audio_input("Record your answer", key=f"audio_{sid}_{idx}")
            if audio is not None:
                text = transcribe_audio(audio)
                if text:
                    st.session_state.answers[idx] = text
                else:
                    st.warning("Speech-to-text is NOT implemented yet. "
                               "The recording is not transcribed - please type your answer below.")
        else:
            st.info("Voice recording needs a newer Streamlit (pip install -U streamlit).")

    # Answer box: value comes from saved answers so nothing is lost on rerun/navigation
    answer = st.text_area(
        "Your answer",
        value=st.session_state.answers.get(idx, ""),
        key=f"answer_{sid}_{idx}",
        height=200,
        placeholder="Type your answer here...",
    )
    st.session_state.answers[idx] = answer

    with st.expander("📖 Reveal model answer (self-study)"):
        st.write(q["model_answer"])

    b1, b2, b3, b4 = st.columns(4)
    is_last = idx == total - 1 or (not st.session_state.use_backend and idx == len(questions) - 1)

    with b1:
        if st.button("⬅️ Previous", disabled=idx == 0, use_container_width=True):
            st.session_state.index -= 1
            st.rerun()
    with b2:
        if st.button("Submit Answer", type="primary", use_container_width=True):
            if not answer.strip():
                st.warning("Your answer is empty. Please type something before submitting.")
            else:
                with st.spinner("Evaluating..."):
                    if st.session_state.use_backend:
                        data, err = api_evaluate(st.session_state.backend_session_id, q["id"], answer)
                        if err:
                            st.error(err)
                            fb = None
                        else:
                            fb = normalize_feedback(data)
                    else:
                        fb = evaluate_locally(q, answer)
                if fb is not None:
                    st.session_state.results[idx] = {"answer": answer, "feedback": fb}
                    st.success("Answer submitted.")
    with b3:
        label = "Finish ✅" if is_last else "Next Question ➡️"
        if st.button(label, use_container_width=True):
            if idx not in st.session_state.results:
                st.warning("You have not submitted this answer - it will count as skipped. "
                           "Click again to continue.")
                st.session_state.skip_confirm = idx
            st.session_state.setdefault("skip_confirm", None)
            if idx in st.session_state.results or st.session_state.get("skip_confirm") == idx:
                st.session_state.skip_confirm = None
                if is_last:
                    finish_session()
                elif idx + 1 < len(questions):
                    st.session_state.index += 1
                    st.rerun()
                else:  # backend mode: ask backend for the next adaptive question
                    data, err = api_next_question(st.session_state.backend_session_id)
                    nq = clean_question((data or {}).get("question")) if not err else None
                    if err:
                        st.error(err)
                    elif nq is None:
                        st.warning("Backend has no more questions. Ending session.")
                        finish_session()
                    else:
                        st.session_state.questions.append(nq)
                        st.session_state.adaptation[idx + 1] = (data or {}).get("reason")
                        st.session_state.index += 1
                        st.rerun()
    with b4:
        if st.button("⏹️ End session", use_container_width=True):
            finish_session()

    # Show saved feedback (also when coming back with Previous)
    if idx in st.session_state.results:
        saved = st.session_state.results[idx]
        if saved["answer"] != answer:
            st.info("You edited your answer after the last evaluation. Submit again to update feedback.")
        st.divider()
        show_feedback(saved["feedback"], q)


def build_summary_rows():
    """Turn session results into rows for the dashboard (real data only)."""
    rows = []
    for idx, q in enumerate(st.session_state.questions):
        res = st.session_state.results.get(idx)
        rows.append({
            "topic": q["topic"],
            "difficulty": q["difficulty"],
            "question": q["question"],
            "attempted": res is not None,
            "score": res["feedback"]["score"] if res else None,
            "missing": res["feedback"]["missing_concepts"] if res else [],
        })
    return rows


def show_results():
    st.title("📊 Session Results")
    rows = build_summary_rows()
    if not rows:
        st.info("No session data to show.")
        if st.button("Back to home"):
            go_home()
            st.rerun()
        return

    df = pd.DataFrame(rows)
    attempted = int(df["attempted"].sum())
    scored = df.dropna(subset=["score"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Questions in session", len(df))
    c2.metric("Attempted", attempted)
    c3.metric("Skipped", len(df) - attempted)

    if scored.empty:
        st.metric("Overall score", "Not available")
        st.info("No scores were produced in this session, so charts cannot be shown.")
    else:
        overall = scored["score"].mean()
        st.metric("Overall score", f"{overall:.0f} / 100")
        st.progress(min(max(overall / 100, 0.0), 1.0))
        if not st.session_state.use_backend:
            st.caption("Scores come from a simple keyword check, not AI evaluation.")

        by_topic = scored.groupby("topic")["score"].mean().round(1)
        by_diff = scored.groupby("difficulty")["score"].mean().round(1)

        g1, g2 = st.columns(2)
        with g1:
            st.subheader("By topic")
            st.bar_chart(by_topic)
        with g2:
            st.subheader("By difficulty")
            st.bar_chart(by_diff)

        strong = [t for t, s in by_topic.items() if s >= STRONG_SCORE]
        weak = [t for t, s in by_topic.items() if s < WEAK_SCORE]
        s1, s2 = st.columns(2)
        with s1:
            st.subheader("✅ Strong topics")
            st.write(", ".join(strong) if strong else "None reached the strong threshold.")
        with s2:
            st.subheader("⚠️ Weak topics")
            st.write(", ".join(weak) if weak else "No weak topics found.")

        st.subheader("📚 Revision recommendations")
        missing_counter = Counter(c for m in df["missing"] for c in m)
        if weak:
            st.write("Revise these topics first: " + ", ".join(weak))
        if missing_counter:
            st.write("Most frequently missed concepts:")
            for concept, n in missing_counter.most_common(8):
                st.write(f"- {concept} (missed {n}x)")
        if not weak and not missing_counter:
            st.write("No specific gaps detected. Keep practising with harder questions.")

    if st.session_state.backend_final:
        with st.expander("Raw final results from backend"):
            st.json(st.session_state.backend_final)

    with st.expander("Question-by-question review"):
        for i, r in enumerate(rows, 1):
            score = "skipped" if not r["attempted"] else (
                "no score" if r["score"] is None else f"{r['score']:.0f}/100")
            st.write(f"**Q{i}** [{r['topic']} | {r['difficulty']}] {r['question']} → {score}")

    b1, b2 = st.columns(2)
    with b1:
        if st.button("🔄 Restart viva (same subject)", use_container_width=True):
            subject = st.session_state.subject
            count = st.session_state.session_length
            questions, _ = load_question_bank()
            start_session(subject, count, "All", questions)
    with b2:
        if st.button("🏠 Back to home", use_container_width=True):
            go_home()
            st.rerun()


# =====================================================================
# 8. MAIN
# =====================================================================
def main():
    init_state()
    all_questions, warnings = load_question_bank()
    show_sidebar()
    page = st.session_state.page
    if page == "home":
        show_home(all_questions, warnings)
    elif page == "viva":
        show_viva()
    else:
        show_results()


main()