"""Speech-to-text. It ONLY converts audio to text - it never scores anything.

The audio is kept in memory while it is sent to OpenAI and is never written to
disk or logged. If no API key is configured the rest of the backend still works;
this feature simply answers with HTTP 503.

Supported languages: whatever the chosen OpenAI model supports (includes
English and Hindi). Hinglish (Hindi written in Latin letters) may be
transcribed inconsistently - always let the student review/edit the text.
"""
import logging
import re
from typing import Optional

from errors import ApiError
from openai_client import make_client, to_api_error

log = logging.getLogger("viva.transcription")

# formats accepted by the OpenAI transcription endpoint
ALLOWED_EXTENSIONS = {"wav", "mp3", "mp4", "mpeg", "mpga", "m4a", "ogg", "webm", "flac"}
OK_CONTENT_TYPE_PREFIXES = ("audio/", "video/webm", "video/mp4", "application/octet-stream")


class TranscriptionService:
    def __init__(self, settings, client=None):
        self.settings = settings
        self._client = client            # tests inject a fake client here

    @property
    def available(self) -> bool:
        return self._client is not None or bool(self.settings.openai_api_key)

    def transcribe(self, data: bytes, filename: str, content_type: Optional[str],
                   language: Optional[str] = None) -> str:
        # ---- validate the upload before spending any money ----
        if not data:
            raise ApiError(400, "The uploaded audio file is empty. Please record again.")
        ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise ApiError(415, f"Unsupported audio type '.{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}.")
        if content_type and not content_type.lower().startswith(OK_CONTENT_TYPE_PREFIXES):
            raise ApiError(415, f"Unsupported content type '{content_type}'. Please upload an audio file.")
        max_bytes = int(self.settings.max_audio_mb * 1024 * 1024)
        if len(data) > max_bytes:
            raise ApiError(413, f"Audio file is too large (limit {self.settings.max_audio_mb:g} MB).")
        if language and not re.fullmatch(r"[a-z]{2,3}", language.strip().lower()):
            raise ApiError(400, "language must be a short ISO code such as 'en' or 'hi'.")

        client = self._client or make_client(self.settings, self.settings.transcribe_timeout_seconds,
                                             "Transcription")
        extra = {"language": language.strip().lower()} if language else {}
        try:
            result = client.audio.transcriptions.create(
                model=self.settings.openai_transcribe_model,
                file=(filename, data, content_type or "audio/wav"),
                **extra,
            )
        except Exception as e:
            log.warning("Transcription failed: %s", type(e).__name__)   # no audio, no key in logs
            raise to_api_error(e, "Transcription")

        text = (getattr(result, "text", "") or "").strip()
        if not text:
            raise ApiError(422, "No speech was detected in the recording. Please try again or type your answer.")
        return text
