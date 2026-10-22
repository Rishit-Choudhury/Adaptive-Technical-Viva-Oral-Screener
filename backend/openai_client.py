"""Small helpers shared by evaluation, transcription and translation.

The OpenAI package is imported lazily, so the backend still starts even if
the key is missing or the package is not installed.
"""
from errors import ApiError


def make_client(settings, timeout: float, what: str):
    """Create an OpenAI client, or raise a clear 503 if it is not configured."""
    if not settings.openai_api_key:
        raise ApiError(503, f"{what} is unavailable: OPENAI_API_KEY is not set on the backend.")
    try:
        from openai import OpenAI
    except ImportError:
        raise ApiError(503, f"{what} is unavailable: the 'openai' package is not installed.")
    # max_retries=0 so a failure is reported quickly instead of silently retrying
    return OpenAI(api_key=settings.openai_api_key, timeout=timeout, max_retries=0)


def to_api_error(exc: Exception, what: str) -> ApiError:
    """Turn an OpenAI exception into a safe ApiError (never leaks keys or raw messages)."""
    try:
        import openai
    except ImportError:
        return ApiError(503, f"{what} is unavailable: the 'openai' package is not installed.")
    if isinstance(exc, openai.APITimeoutError):      # must be checked before APIConnectionError
        return ApiError(504, f"{what} timed out. Please try again.")
    if isinstance(exc, openai.AuthenticationError):
        return ApiError(502, f"{what} failed: the backend's API key was rejected.")
    if isinstance(exc, openai.RateLimitError):
        return ApiError(503, f"{what} is rate-limited or out of quota. Try again later.")
    if isinstance(exc, openai.APIConnectionError):
        return ApiError(502, f"{what} failed: could not reach the provider.")
    if isinstance(exc, openai.APIStatusError):
        return ApiError(502, f"{what} failed (provider status {exc.status_code}).")
    return ApiError(502, f"{what} failed unexpectedly.")
