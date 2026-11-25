"""Shared exception identities independent of provider and QA implementations."""


class FatalTTSError(RuntimeError):
    """Non-retryable client or authentication error from a TTS provider."""


class RecognitionError(RuntimeError):
    """Recognition failed; this is not evidence of incorrect synthesized speech."""


class ReviewRequiredError(RuntimeError):
    """Evidence needs review; automatic synthesis retries cannot resolve it."""
