# Copy this file to ".env" (same folder) and edit. NEVER commit ".env" to Git.

# Needed ONLY for voice transcription, translation and LLM evaluation.
# Leave empty to run everything else (keyword evaluation, sessions, adaptive questions).
OPENAI_API_KEY=

# basic = transparent keyword check (default, free)   |   llm = OpenAI-based grading
EVALUATION_MODE=basic
# If llm mode fails, fall back to the clearly-labelled basic check (true) or return an error (false)
LLM_FALLBACK_TO_BASIC=true

# Models (check OpenAI docs for current names; "gpt-transcribe" is their newest recommendation)
OPENAI_TRANSCRIBE_MODEL=gpt-4o-mini-transcribe
OPENAI_EVAL_MODEL=gpt-4o-mini
OPENAI_TRANSLATE_MODEL=gpt-4o-mini

# Streamlit address(es) allowed by CORS, comma separated
CORS_ORIGINS=http://localhost:8501,http://127.0.0.1:8501

# Optional limits / adaptive thresholds (scores are 0-100)
MAX_AUDIO_MB=10
LLM_TIMEOUT_SECONDS=30
TRANSCRIBE_TIMEOUT_SECONDS=60
START_DIFFICULTY=Medium
LEVEL_UP_SCORE=70
LEVEL_DOWN_SCORE=40
RECENT_WINDOW=2
STRONG_SCORE=70
WEAK_SCORE=50
# QUESTION_BANK_PATH=question_bank.json
