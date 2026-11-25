"""Sequential step-chain visual block (Step 1 -> Step 2 -> ... -> Result)."""

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
    steps = params.get("steps")
    if not isinstance(steps, list) or not 2 <= len(steps) <= 4:
        raise ValueError(f"{context}: step_chain requires 2 to 4 steps")
    for index, step in enumerate(steps):
        if not isinstance(step, Mapping):
            raise ValueError(f"{context}: step {index} must be an object")
        label_key = step.get("label")
        if not isinstance(label_key, str) or not label_key.strip():
            raise ValueError(f"{context}: step {index} requires non-empty label key")
        require_localized_label(translations, label_key, context)
        if "value" in step and (not isinstance(step["value"], str) or not step["value"].strip()):
            raise ValueError(f"{context}: step {index} value must be a non-empty string")
    result_val = params.get("result")
    if result_val is not None and (not isinstance(result_val, str) or not result_val.strip()):
        raise ValueError(f"{context}: result must be a non-empty string when provided")


def build(theme: VisualTheme, language: str, row: Mapping[str, Any]) -> dict[str, Any]:
    from manim import DOWN, LEFT, RIGHT, UP, Arrow, MathTex, RoundedRectangle, Text, VGroup

    params = row["visual"]["params"]
    steps = params["steps"]

    title = Text(row["title"], font=theme.font, font_size=38, weight="BOLD", color=theme.secondary)
    if title.width > CONTENT_MAX_WIDTH:
        title.scale_to_fit_width(CONTENT_MAX_WIDTH)
    title.move_to(UP * 6.0)

    body_text = "\n".join(textwrap.wrap(row["body"], width=36) or [row["body"]])
    body = Text(body_text, font=theme.font, font_size=26, color=theme.text_muted, line_spacing=1.2)
    if body.width > 7.4:
        body.scale_to_fit_width(7.4)
    if body.height > 1.2:
        body.scale_to_fit_height(1.2)
    body.move_to(UP * 4.7)

    objects: dict[str, Any] = {"title": title, "body": body}
    count = len(steps)
    card_h = 1.25 if count <= 3 else 1.05
    gap = 0.55 if count <= 3 else 0.4
    top_y = 3.0 if count <= 3 else 3.2

    for idx, step in enumerate(steps):
        y = top_y - idx * (card_h + gap)
        box = RoundedRectangle(
            corner_radius=0.22,
            width=7.2,
            height=card_h,
            fill_color=theme.card_bg,
            fill_opacity=0.95,
            stroke_color=theme.primary,
            stroke_width=2.5,
        ).move_to(UP * y)
        lbl = Text(localized_label(row, step["label"]), font=theme.font, font_size=26, color=theme.text_primary)
        max_lbl_w = 4.6 if step.get("value") else 6.4
        if lbl.width > max_lbl_w:
            lbl.scale_to_fit_width(max_lbl_w)
        if step.get("value"):
            lbl.move_to(box.get_left() + RIGHT * (0.45 + lbl.width / 2))
            val = Text(step["value"], font=theme.font, font_size=30, weight="BOLD", color=theme.secondary)
            if val.width > 1.8:
                val.scale_to_fit_width(1.8)
            val.move_to(box.get_right() + LEFT * (0.45 + val.width / 2))
            step_parts = [box, lbl, val]
        else:
            lbl.move_to(box.get_center())
            step_parts = [box, lbl]

        if idx < count - 1:
            arrow = Arrow(
                box.get_bottom() + DOWN * 0.04,
                box.get_bottom() + DOWN * (gap - 0.04),
                buff=0,
                color=theme.text_muted,
                stroke_width=3,
                max_tip_length_to_length_ratio=0.45,
            )
            step_parts.append(arrow)
        objects[f"step_{idx + 1}"] = VGroup(*step_parts)

    if params.get("result"):
        res_txt = Text(
            f"{ui_string('result', language)}: {params['result']}",
            font=theme.font,
            font_size=30,
            weight="BOLD",
            color=theme.text_primary,
        )
        if res_txt.width > 6.8:
            res_txt.scale_to_fit_width(6.8)
        res_box = RoundedRectangle(
            corner_radius=0.24,
            width=max(res_txt.width + 0.8, 4.8),
            height=res_txt.height + 0.45,
            fill_color=theme.card_bg,
            fill_opacity=0.98,
            stroke_color=theme.accent_positive,
            stroke_width=3.2,
        )
        res_txt.move_to(res_box.get_center())
        objects["result"] = VGroup(res_box, res_txt).move_to(DOWN * 5.0)

    if row.get("formula"):
        formula = MathTex(row["formula"], font_size=40, color=theme.text_primary)
        if formula.width > 7.4:
            formula.scale_to_fit_width(7.4)
        if formula.height > 1.4:
            formula.scale_to_fit_height(1.4)
        formula.move_to(DOWN * 3.65)
        objects["formula"] = formula
    return objects


def _available_targets(params: Mapping[str, Any], formula: str) -> frozenset[str]:
    targets = {"title", "body"}
    for idx in range(len(params.get("steps", []))):
        targets.add(f"step_{idx + 1}")
    if params.get("result"):
        targets.add("result")
    if formula:
        targets.add("formula")
    return frozenset(targets)


def register() -> None:
    register_visual_block(
        VisualBlockSpec(
            name="step_chain",
            pack="core",
            description="Vertical chain of 2-4 sequential steps with optional values and final result banner.",
            cue_targets=frozenset({"title", "body", "step_1", "step_2", "step_3", "step_4", "result", "formula"}),
            params_schema={
                "steps": "List of 2-4 objects: {label (label key), optional value string}",
                "result": "Optional final result string shown in result banner",
            },
            validate_params=validate_params,
            build=build,
            source_file=Path(__file__),
            available_targets=_available_targets,
        )
    )
