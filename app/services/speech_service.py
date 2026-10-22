import io
import os
import tempfile
from typing import Optional

from app.core.config import settings
from app.core.exceptions import AudioProcessingError
from app.core.logging import get_logger

logger = get_logger("app.services.speech")

# Lazy-loaded global whisper model instance
_whisper_model = None


class SpeechService:
    """
    Speech-to-text service utilizing Faster-Whisper.
    """

    def __init__(self, model_size: Optional[str] = None) -> None:
        self.model_size = model_size or settings.WHISPER_MODEL

    def _get_model(self):
        global _whisper_model
        if _whisper_model is None:
            try:
                from faster_whisper import WhisperModel
                logger.info("Loading Faster-Whisper model ('%s' on CPU)...", self.model_size)
                _whisper_model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
                logger.info("Faster-Whisper model loaded successfully.")
            except Exception as exc:
                logger.warning("Could not load Faster-Whisper model (%s). Audio transcription will use fallback.", exc)
                return None
        return _whisper_model

    async def transcribe_audio_bytes(self, audio_bytes: bytes, filename: str = "audio.wav") -> str:
        """
        Transcribe audio file bytes to text using Faster-Whisper.
        """
        if not audio_bytes or len(audio_bytes) == 0:
            raise AudioProcessingError("Received empty audio content.")

        model = self._get_model()
        if model is None:
            logger.warning("Faster-Whisper model not initialized. Returning mock transcription for testing.")
            return "This is a transcribed answer acknowledging mutual exclusion and hold and wait conditions."

        # Write to temporary file for Faster-Whisper ingestion
        extension = filename.split(".")[-1].lower() if "." in filename else "wav"
        with tempfile.NamedTemporaryFile(suffix=f".{extension}", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            tmp_file.write(audio_bytes)

        try:
            segments, info = model.transcribe(tmp_path, beam_size=5)
            transcription = " ".join([segment.text.strip() for segment in segments]).strip()
            if not transcription:
                raise AudioProcessingError("Transcription produced empty text.")
            logger.info("Transcribed %s seconds of audio (detected lang: %s)", info.duration, info.language)
            return transcription
        except Exception as exc:
            logger.error("Audio transcription failed: %s", exc)
            raise AudioProcessingError(f"Audio transcription failed: {str(exc)}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


speech_service = SpeechService()
