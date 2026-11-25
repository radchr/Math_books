"""Hook comparison visual block: Option A vs Option B cards with optional highlight."""

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
    if not isinstance(params, Mapping):
        raise ValueError(f"{context}: visual.params must be an object")
    for key in ("option_a", "option_b"):
        label_key = params.get(key)
        if not isinstance(label_key, str) or not label_key.strip():
            raise ValueError(f"{context}: hook_choice requires non-empty label key {key!r}")
        require_localized_label(translations, label_key, context)
    for key in ("value_a", "value_b"):
        if key in params and (not isinstance(params[key], str) or not params[key].strip()):
            raise ValueError(f"{context}: {key} must be a non-empty string when provided")


def _make_option_card(
    label: str, value: str | None, stroke_color: str, theme: VisualTheme, y: float, max_width: float = 7.4
):
    from manim import DOWN, UP, RoundedRectangle, Text, VGroup

    box = RoundedRectangle(
        corner_radius=0.28,
        width=max_width,
        height=2.2,
        fill_color=theme.card_bg,
        fill_opacity=0.95,
        stroke_color=stroke_color,
        stroke_width=3.0,
    ).move_to(UP * y)
    wrapped = "\n".join(textwrap.wrap(label, width=28) or [label])
    lbl = Text(wrapped, font=theme.font, font_size=30, weight="BOLD", color=theme.text_primary, line_spacing=1.15)
    if lbl.width > max_width - 0.8:
        lbl.scale_to_fit_width(max_width - 0.8)
    if lbl.height > (1.05 if value else 1.7):
        lbl.scale_to_fit_height(1.05 if value else 1.7)
    if value:
        lbl.move_to(box.get_center() + UP * 0.42)
        val = Text(value, font=theme.font, font_size=40, weight="BOLD", color=stroke_color)
        if val.width > max_width - 0.8:
            val.scale_to_fit_width(max_width - 0.8)
        val.move_to(box.get_center() + DOWN * 0.48)
        return VGroup(box, lbl, val)
    lbl.move_to(box.get_center())
    return VGroup(box, lbl)


def build(theme: VisualTheme, language: str, row: Mapping[str, Any]) -> dict[str, Any]:
    from manim import DOWN, UP, MathTex, Text

    params = row["visual"]["params"]
    title = Text(row["title"], font=theme.font, font_size=38, weight="BOLD", color=theme.secondary)
    if title.width > CONTENT_MAX_WIDTH:
        title.scale_to_fit_width(CONTENT_MAX_WIDTH)
    title.move_to(UP * 6.0)

    body_text = "\n".join(textwrap.wrap(row["body"], width=36) or [row["body"]])
    body = Text(body_text, font=theme.font, font_size=28, color=theme.text_muted, line_spacing=1.2)
    if body.width > 7.4:
        body.scale_to_fit_width(7.4)
    if body.height > 1.5:
        body.scale_to_fit_height(1.5)
    body.move_to(UP * 4.5)

    option_a = _make_option_card(
        localized_label(row, params["option_a"]),
        params.get("value_a"),
        theme.primary,
        theme,
        y=2.0,
    )
    vs = Text(ui_string("vs", language), font=theme.font, font_size=28, weight="BOLD", color=theme.secondary)
    vs.move_to(UP * 0.25)
    option_b = _make_option_card(
        localized_label(row, params["option_b"]),
        params.get("value_b"),
        theme.secondary,
        theme,
        y=-1.5,
    )

    objects: dict[str, Any] = {
        "title": title,
        "body": body,
        "option_a": option_a,
        "vs": vs,
        "option_b": option_b,
    }
    if row.get("formula"):
        formula = MathTex(row["formula"], font_size=44, color=theme.text_primary)
        if formula.width > 7.4:
            formula.scale_to_fit_width(7.4)
        formula.move_to(DOWN * 4.2)
        objects["formula"] = formula
    return objects


def register() -> None:
    register_visual_block(
        VisualBlockSpec(
            name="hook_choice",
            pack="core",
            description="Two-option hook/dilemma card (Option A vs Option B) for prediction questions.",
            cue_targets=frozenset({"title", "body", "option_a", "vs", "option_b", "formula"}),
            params_schema={
                "option_a": "Label key in translations.<lang>.labels for Option A",
                "option_b": "Label key in translations.<lang>.labels for Option B",
                "value_a": "Optional numeric/short badge string for Option A",
                "value_b": "Optional numeric/short badge string for Option B",
            },
            validate_params=validate_params,
            build=build,
            source_file=Path(__file__),
        )
    )
