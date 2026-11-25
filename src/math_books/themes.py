"""Shared 9:16 visual design system and pluggable named themes."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from math_books.languages import SUPPORTED_LANGUAGES, validate_language

SAFE_MAX_ABS_X = 4.35
SAFE_MIN_Y = -6.15
SAFE_MAX_Y = 7.45
CONTENT_MAX_WIDTH = 7.6
FONT_FAMILY = "DejaVu Sans"


@dataclasses.dataclass(frozen=True)
class VisualTheme:
    """Color and typography tokens for a 9:16 vertical video domain."""

    name: str
    bg: str
    card_bg: str
    primary: str
    secondary: str
    accent_positive: str
    accent_warning: str
    text_primary: str
    text_muted: str
    font: str = FONT_FAMILY

    def color_for(self, role: str) -> str:
        mapping = {
            "primary": self.primary,
            "secondary": self.secondary,
            "positive": self.accent_positive,
            "warning": self.accent_warning,
            "text": self.text_primary,
            "muted": self.text_muted,
            "card": self.card_bg,
        }
        if role in mapping:
            return mapping[role]
        raise ValueError(f"Unknown theme color role: {role!r}")


NEUTRAL_DARK = VisualTheme(
    name="neutral_dark",
    bg="#0F172A",
    card_bg="#1E293B",
    primary="#38BDF8",
    secondary="#F59E0B",
    accent_positive="#34D399",
    accent_warning="#F87171",
    text_primary="#FFFFFF",
    text_muted="#CBD5E1",
)

SCIENCE_LAB = VisualTheme(
    name="science_lab",
    bg="#0B132B",
    card_bg="#1C2541",
    primary="#5BC0BE",
    secondary="#FFD166",
    accent_positive="#06D6A0",
    accent_warning="#EF476F",
    text_primary="#FFFFFF",
    text_muted="#B8C4D4",
)

_THEMES: dict[str, VisualTheme] = {
    NEUTRAL_DARK.name: NEUTRAL_DARK,
    SCIENCE_LAB.name: SCIENCE_LAB,
}


def register_theme(theme: VisualTheme) -> VisualTheme:
    """Register or replace a named visual theme."""
    _THEMES[theme.name] = theme
    return theme


def get_theme(name: str = "neutral_dark") -> VisualTheme:
    from math_books.packs import ensure_packs_loaded

    ensure_packs_loaded()
    if name not in _THEMES:
        available = ", ".join(sorted(_THEMES))
        raise ValueError(f"Unknown visual theme {name!r}. Available: {available}")
    return _THEMES[name]


def list_themes() -> dict[str, VisualTheme]:
    from math_books.packs import ensure_packs_loaded

    ensure_packs_loaded()
    return dict(_THEMES)


@lru_cache(maxsize=1)
def _core_ui_strings() -> dict[str, dict[str, str]]:
    path = Path(__file__).with_name("ui_strings.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("ui_strings.json must be an object")
    for key, entries in raw.items():
        if not isinstance(entries, dict) or set(entries) != set(SUPPORTED_LANGUAGES):
            raise ValueError(f"UI string {key!r} requires complete uk/ru/en translations")
    return raw


_EXTRA_UI_STRINGS: dict[str, dict[str, str]] = {}


def register_ui_strings(strings: Mapping[str, Mapping[str, str]]) -> None:
    for key, entries in strings.items():
        if set(entries) != set(SUPPORTED_LANGUAGES):
            raise ValueError(f"UI string {key!r} requires complete uk/ru/en translations")
        _EXTRA_UI_STRINGS[key] = {lang: str(entries[lang]) for lang in SUPPORTED_LANGUAGES}


def ui_string(key: str, language: str) -> str:
    """Resolve a localized system UI label for uk/ru/en without hardcoded text."""
    from math_books.packs import ensure_packs_loaded

    validate_language(language)
    ensure_packs_loaded()
    if key in _EXTRA_UI_STRINGS:
        return _EXTRA_UI_STRINGS[key][language]
    core = _core_ui_strings()
    if key in core:
        return core[key][language]
    raise ValueError(f"Unknown UI string key: {key!r}")
