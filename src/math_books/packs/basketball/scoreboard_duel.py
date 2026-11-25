"""Basketball domain visual block: glowing scoreboard card with optional clock readout."""

from __future__ import annotations

import textwrap
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from math_books.themes import CONTENT_MAX_WIDTH, VisualTheme, ui_string
from math_books.visual_blocks import VisualBlockSpec, register_visual_block


def validate_params(params: Mapping[str, Any], _translations: Mapping[str, Mapping[str, Any]], context: str) -> None:
    score = params.get("score")
    if not isinstance(score, str) or not score.strip() or len(score) > 16:
        raise ValueError(f"{context}: scoreboard_duel requires short non-empty score string (e.g. '98 : 101')")
    clock = params.get("clock")
    if clock is not None and (not isinstance(clock, str) or not clock.strip() or len(clock) > 12):
        raise ValueError(f"{context}: clock must be a short non-empty string when provided")


def build(theme: VisualTheme, language: str, row: Mapping[str, Any]) -> dict[str, Any]:
    from manim import DOWN, UP, MathTex, RoundedRectangle, Text, VGroup

    params = row["visual"]["params"]
    title = Text(row["title"], font=theme.font, font_size=38, weight="BOLD", color=theme.secondary)
    if title.width > CONTENT_MAX_WIDTH:
        title.scale_to_fit_width(CONTENT_MAX_WIDTH)
    title.move_to(UP * 6.0)

    box = RoundedRectangle(
        corner_radius=0.32,
        width=6.4,
        height=3.0,
        fill_color="#09111E",
        fill_opacity=0.98,
        stroke_color=theme.primary,
        stroke_width=4.0,
    ).move_to(UP * 2.2)
    lbl = Text(
        ui_string("basketball.scoreboard", language),
        font=theme.font,
        font_size=26,
        weight="BOLD",
        color=theme.text_muted,
    ).move_to(box.get_top() + DOWN * 0.45)
    score = Text(params["score"], font=theme.font, font_size=76, weight="BOLD", color=theme.secondary)
    if score.width > 5.6:
        score.scale_to_fit_width(5.6)
    score.move_to(box.get_center() + DOWN * 0.15)
    scoreboard = VGroup(box, lbl, score)

    objects: dict[str, Any] = {"title": title, "scoreboard": scoreboard}
    if params.get("clock"):
        clock_txt = Text(
            f"{ui_string('basketball.clock', language)}: {params['clock']}",
            font=theme.font,
            font_size=32,
            weight="BOLD",
            color=theme.accent_warning,
        )
        if clock_txt.width > 5.8:
            clock_txt.scale_to_fit_width(5.8)
        clock_box = RoundedRectangle(
            corner_radius=0.2,
            width=max(clock_txt.width + 0.7, 3.6),
            height=clock_txt.height + 0.36,
            fill_color=theme.card_bg,
            fill_opacity=0.95,
            stroke_color=theme.accent_warning,
            stroke_width=2.5,
        )
        clock_txt.move_to(clock_box.get_center())
        objects["clock"] = VGroup(clock_box, clock_txt).move_to(DOWN * 0.2)

    body_text = "\n".join(textwrap.wrap(row["body"], width=34) or [row["body"]])
    body = Text(body_text, font=theme.font, font_size=30, color=theme.text_primary, line_spacing=1.25)
    if body.width > 7.4:
        body.scale_to_fit_width(7.4)
    if body.height > 2.2:
        body.scale_to_fit_height(2.2)
    body.move_to(DOWN * 2.4)
    objects["body"] = body

    if row.get("formula"):
        formula = MathTex(row["formula"], font_size=44, color=theme.text_primary)
        if formula.width > 7.4:
            formula.scale_to_fit_width(7.4)
        if formula.height > 1.5:
            formula.scale_to_fit_height(1.5)
        formula.move_to(DOWN * 4.7)
        objects["formula"] = formula
    return objects


def _available_targets(params: Mapping[str, Any], formula: str) -> frozenset[str]:
    targets = {"title", "scoreboard", "body"}
    if params.get("clock"):
        targets.add("clock")
    if formula:
        targets.add("formula")
    return frozenset(targets)


def register() -> None:
    register_visual_block(
        VisualBlockSpec(
            name="basketball.scoreboard_duel",
            pack="basketball",
            description="Arena scoreboard readout with optional countdown clock for endgame hook scenes.",
            cue_targets=frozenset({"title", "scoreboard", "clock", "body", "formula"}),
            params_schema={
                "score": "Short score string such as '98 : 101'",
                "clock": "Optional countdown clock string such as '0:10'",
            },
            validate_params=validate_params,
            build=build,
            source_file=Path(__file__),
            available_targets=_available_targets,
        )
    )
