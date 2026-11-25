"""Default vertical card visual block (title + wrapped body + optional formula)."""

from __future__ import annotations

import textwrap
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from math_books.themes import CONTENT_MAX_WIDTH, VisualTheme
from math_books.visual_blocks import VisualBlockSpec, register_visual_block


def validate_params(params: Mapping[str, Any], _translations: Mapping[str, Mapping[str, Any]], context: str) -> None:
    if params:
        raise ValueError(f"{context}: text_card accepts no visual params")


def build(theme: VisualTheme, _language: str, row: Mapping[str, Any]) -> dict[str, Any]:
    from manim import DOWN, UP, MathTex, Text

    title = Text(row["title"], font=theme.font, font_size=40, color=theme.secondary)
    if title.width > CONTENT_MAX_WIDTH:
        title.scale_to_fit_width(CONTENT_MAX_WIDTH)
    title.move_to(UP * 5.7)

    wrapped = "\n".join(
        line for paragraph in row["body"].splitlines() for line in (textwrap.wrap(paragraph, width=34) or [""])
    )
    body = Text(wrapped, font=theme.font, font_size=36, color=theme.text_primary, line_spacing=1.3)
    if body.width > 7.4:
        body.scale_to_fit_width(7.4)
    if body.height > 4.8:
        body.scale_to_fit_height(4.8)
    body.move_to(UP * 1.7)

    objects: dict[str, Any] = {"title": title, "body": body}
    if row.get("formula"):
        formula = MathTex(row["formula"], font_size=48, color=theme.text_primary)
        if formula.width > 7.4:
            formula.scale_to_fit_width(7.4)
        formula.move_to(DOWN * 2.1)
        objects["formula"] = formula
    return objects


def register() -> None:
    register_visual_block(
        VisualBlockSpec(
            name="text_card",
            pack="core",
            description="Default structured 9:16 card with title, wrapped body text, and optional MathTex formula.",
            cue_targets=frozenset({"title", "body", "formula"}),
            params_schema={},
            validate_params=validate_params,
            build=build,
            source_file=Path(__file__),
        )
    )
