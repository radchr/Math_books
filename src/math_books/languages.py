"""Shared, explicit language contract for future lessons and voiceover QA."""

SUPPORTED_LANGUAGES = ("uk", "ru", "en")


def validate_language(language: str) -> str:
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language {language!r}; choose uk, ru or en")
    return language
