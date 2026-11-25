"""Basketball domain pack: dark arena theme, localized UI strings, and court/scoreboard blocks."""

from __future__ import annotations

from math_books.packs import DomainPack, register_pack
from math_books.themes import VisualTheme, register_theme, register_ui_strings

BASKETBALL_DARK = VisualTheme(
    name="basketball_dark",
    bg="#0D1B2A",
    card_bg="#1B263B",
    primary="#FF6B1A",
    secondary="#FFD166",
    accent_positive="#2EC4B6",
    accent_warning="#FF595E",
    text_primary="#FFFFFF",
    text_muted="#CBD5E1",
)

BASKETBALL_UI_STRINGS = {
    "basketball.scoreboard": {"uk": "ТАБЛО", "ru": "ТАБЛО", "en": "SCOREBOARD"},
    "basketball.clock": {"uk": "ЧАС", "ru": "ВРЕМЯ", "en": "CLOCK"},
}


def _register_components() -> None:
    register_theme(BASKETBALL_DARK)
    register_ui_strings(BASKETBALL_UI_STRINGS)
    from math_books.packs.basketball import half_court_diagram, scoreboard_duel

    half_court_diagram.register()
    scoreboard_duel.register()


def register_domain_pack() -> DomainPack:
    return register_pack(
        DomainPack(
            name="basketball",
            description="Basketball-themed STEM visuals (half-court diagrams, scoreboard duels, dark arena palette).",
            default_theme=BASKETBALL_DARK.name,
            register_fn=_register_components,
        )
    )
