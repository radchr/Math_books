"""Challenge card visual block: question -> pause badge -> cue-synced answer + model limit."""

from __future__ import annotations

import textwrap
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from math_books.themes import CONTENT_MAX_WIDTH, VisualTheme, ui_string
from math_books.visual_blocks import (
    VisualBlockSpec,
    localized_label,
    register_visual_block,
    require_localized_label,
)


def validate_params(params: Mapping[str, Any], translations: Mapping[str, Mapping[str, Any]], context: str) -> None:
    answer_key = params.get("answer_label")
    if not isinstance(answer_key, str) or not answer_key.strip():
        raise ValueError(f"{context}: challenge_card requires non-empty answer_label key")
    require_localized_label(translations, answer_key, context)
    limit_key = params.get("limit_label")
    if limit_key is not None:
        if not isinstance(limit_key, str) or not limit_key.strip():
            raise ValueError(f"{context}: limit_label must be a non-empty string when provided")
        require_localized_label(translations, limit_key, context)


def build(theme: VisualTheme, language: str, row: Mapping[str, Any]) -> dict[str, Any]:
    from manim import DOWN, UP, MathTex, RoundedRectangle, Text, VGroup

    params = row["visual"]["params"]
    badge_txt = Text(
        ui_string("challenge_badge", language), font=theme.font, font_size=30, weight="BOLD", color=theme.text_primary
    )
    badge_box = RoundedRectangle(
        corner_radius=0.22,
        width=max(badge_txt.width + 0.8, 3.8),
        height=badge_txt.height + 0.36,
        fill_color=theme.primary,
        fill_opacity=0.95,
        stroke_width=0,
    )
    badge_txt.move_to(badge_box.get_center())
    title = VGroup(badge_box, badge_txt).move_to(UP * 6.2)

    q_wrapped = "\n".join(textwrap.wrap(row["body"], width=32) or [row["body"]])
    q_txt = Text(q_wrapped, font=theme.font, font_size=32, color=theme.text_primary, line_spacing=1.25)
    if q_txt.width > 6.8:
        q_txt.scale_to_fit_width(6.8)
    if q_txt.height > 2.6:
        q_txt.scale_to_fit_height(2.6)
    q_box = RoundedRectangle(
        corner_radius=0.28,
        width=7.4,
        height=max(q_txt.height + 0.8, 2.2),
        fill_color=theme.card_bg,
        fill_opacity=0.95,
        stroke_color=theme.secondary,
        stroke_width=2.8,
    )
    q_txt.move_to(q_box.get_center())
    body = VGroup(q_box, q_txt).move_to(UP * 3.4)

    pause = Text(ui_string("pause", language), font=theme.font, font_size=28, weight="BOLD", color=theme.secondary)
    if pause.width > CONTENT_MAX_WIDTH:
        pause.scale_to_fit_width(CONTENT_MAX_WIDTH)
    pause.move_to(UP * 0.9)

    ans_text = localized_label(row, params["answer_label"])
    ans_wrapped = "\n".join(textwrap.wrap(f"{ui_string('answer', language)}: {ans_text}", width=30) or [ans_text])
    ans_txt = Text(
        ans_wrapped, font=theme.font, font_size=32, weight="BOLD", color=theme.text_primary, line_spacing=1.2
    )
    if ans_txt.width > 6.8:
        ans_txt.scale_to_fit_width(6.8)
    if ans_txt.height > 1.8:
        ans_txt.scale_to_fit_height(1.8)
    ans_box = RoundedRectangle(
        corner_radius=0.26,
        width=7.4,
        height=max(ans_txt.height + 0.65, 1.5),
        fill_color=theme.card_bg,
        fill_opacity=0.98,
        stroke_color=theme.accent_positive,
        stroke_width=3.2,
    )
    ans_txt.move_to(ans_box.get_center())
    answer = VGroup(ans_box, ans_txt).move_to(DOWN * 1.1)

    objects: dict[str, Any] = {"title": title, "body": body, "pause": pause, "answer": answer}
    if row.get("formula"):
        formula = MathTex(row["formula"], font_size=44, color=theme.text_primary)
        if formula.width > 7.4:
            formula.scale_to_fit_width(7.4)
        if formula.height > 1.5:
            formula.scale_to_fit_height(1.5)
        formula.move_to(DOWN * 3.1)
        objects["formula"] = formula
    if params.get("limit_label"):
        lim_raw = localized_label(row, params["limit_label"])
        lim_wrapped = "\n".join(
            textwrap.wrap(f"{ui_string('model_limit', language)}: {lim_raw}", width=40) or [lim_raw]
        )
        lim = Text(lim_wrapped, font=theme.font, font_size=22, color=theme.text_muted, line_spacing=1.15)
        if lim.width > 7.4:
            lim.scale_to_fit_width(7.4)
        if lim.height > 1.2:
            lim.scale_to_fit_height(1.2)
        lim.move_to(DOWN * 5.0)
        objects["limit"] = lim
    return objects


def _available_targets(params: Mapping[str, Any], formula: str) -> frozenset[str]:
    targets = {"title", "body", "pause", "answer"}
    if formula:
        targets.add("formula")
    if params.get("limit_label"):
        targets.add("limit")
    return frozenset(targets)


def register() -> None:
    register_visual_block(
        VisualBlockSpec(
            name="challenge_card",
            pack="core",
            description=(
                "End-of-lesson challenge card with pause prompt, cue-synced answer reveal, and optional model limit."
            ),
            cue_targets=frozenset({"title", "body", "pause", "answer", "formula", "limit"}),
            params_schema={
                "answer_label": "Label key in translations.<lang>.labels for the revealed answer",
                "limit_label": "Optional label key for the model limitation disclaimer",
            },
            validate_params=validate_params,
            build=build,
            source_file=Path(__file__),
            available_targets=_available_targets,
        )
    )
