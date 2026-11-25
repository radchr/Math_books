"""Data-driven comparison bar chart block using exact Fraction scaling."""

from __future__ import annotations

import textwrap
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from typing import Any

from math_books.themes import CONTENT_MAX_WIDTH, VisualTheme, ui_string, validate_color_role
from math_books.visual_blocks import (
    VisualBlockSpec,
    localized_label,
    parse_exact_fraction,
    register_visual_block,
    require_localized_label,
)


def _format_value(value: Fraction, unit: str) -> str:
    if unit == "%":
        pct = float(value * 100)
        return f"{pct:g}%"
    val = float(value)
    return f"{val:g}{unit}"


def validate_params(params: Mapping[str, Any], translations: Mapping[str, Mapping[str, Any]], context: str) -> None:
    items = params.get("items")
    if not isinstance(items, list) or not 2 <= len(items) <= 4:
        raise ValueError(f"{context}: compare_bars requires 2 to 4 items")
    ids: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ValueError(f"{context}: bar item {index} must be an object")
        ident = item.get("id")
        if not isinstance(ident, str) or not ident.strip() or ident in ids:
            raise ValueError(f"{context}: bar item requires unique non-empty id")
        ids.add(ident)
        value = parse_exact_fraction(item.get("value"), f"{context}.items[{ident}].value")
        if value < 0:
            raise ValueError(f"{context}: bar value must be non-negative")
        if "color" in item and item["color"] is not None:
            validate_color_role(item["color"], f"{context}.items[{ident}].color")
        require_localized_label(translations, ident, context)
    winner = params.get("winner")
    if winner is not None and winner not in ids:
        raise ValueError(f"{context}: winner {winner!r} must match one of the bar item ids")
    unit = params.get("unit", "%")
    if not isinstance(unit, str) or len(unit) > 12:
        raise ValueError(f"{context}: unit must be a short string")


def build(theme: VisualTheme, language: str, row: Mapping[str, Any]) -> dict[str, Any]:
    from manim import DOWN, LEFT, RIGHT, UP, Line, MathTex, Rectangle, RoundedRectangle, Text, VGroup

    params = row["visual"]["params"]
    items = params["items"]
    unit = params.get("unit", "%")
    winner_id = params.get("winner")

    title = Text(row["title"], font=theme.font, font_size=38, weight="BOLD", color=theme.secondary)
    if title.width > CONTENT_MAX_WIDTH:
        title.scale_to_fit_width(CONTENT_MAX_WIDTH)
    title.move_to(UP * 6.0)

    body_text = "\n".join(textwrap.wrap(row["body"], width=36) or [row["body"]])
    body = Text(body_text, font=theme.font, font_size=26, color=theme.text_muted, line_spacing=1.2)
    if body.width > 7.4:
        body.scale_to_fit_width(7.4)
    if body.height > 1.3:
        body.scale_to_fit_height(1.3)
    body.move_to(UP * 4.6)

    values = [parse_exact_fraction(item["value"], item["id"]) for item in items]
    max_val = max(values) if any(v > 0 for v in values) else Fraction(1)
    baseline_y = -1.6
    max_bar_h = 4.2
    count = len(items)
    total_w = 7.0
    slot_w = total_w / count
    bar_w = min(1.8, slot_w * 0.62)

    baseline = Line(LEFT * 3.6 + UP * baseline_y, RIGHT * 3.6 + UP * baseline_y, color=theme.text_muted, stroke_width=2)
    objects: dict[str, Any] = {"title": title, "body": body, "baseline": baseline}

    roles = ("primary", "secondary", "positive", "warning")
    for idx, (item, val) in enumerate(zip(items, values, strict=True)):
        x = -total_w / 2 + slot_w * (idx + 0.5)
        height = max(0.18, float(val / max_val) * max_bar_h)
        role = item.get("color", roles[idx % len(roles)])
        color = theme.color_for(role)
        bar = Rectangle(
            width=bar_w,
            height=height,
            fill_color=color,
            fill_opacity=0.92,
            stroke_color=theme.text_primary,
            stroke_width=1.5,
        )
        bar.move_to([x, baseline_y + height / 2, 0])
        val_txt = Text(_format_value(val, unit), font=theme.font, font_size=28, weight="BOLD", color=theme.text_primary)
        if val_txt.width > slot_w - 0.15:
            val_txt.scale_to_fit_width(slot_w - 0.15)
        val_txt.next_to(bar, UP, buff=0.18)

        lbl_raw = localized_label(row, item["id"])
        lbl_wrapped = "\n".join(textwrap.wrap(lbl_raw, width=14) or [lbl_raw])
        lbl_txt = Text(lbl_wrapped, font=theme.font, font_size=22, color=theme.text_muted, line_spacing=1.1)
        if lbl_txt.width > slot_w - 0.1:
            lbl_txt.scale_to_fit_width(slot_w - 0.1)
        if lbl_txt.height > 0.9:
            lbl_txt.scale_to_fit_height(0.9)
        lbl_txt.next_to(bar, DOWN, buff=0.22)
        objects[f"bar_{idx + 1}"] = VGroup(bar, val_txt, lbl_txt)

    if winner_id is not None:
        win_label = localized_label(row, winner_id)
        badge_txt = Text(
            f"{ui_string('winner', language)}: {win_label}",
            font=theme.font,
            font_size=26,
            weight="BOLD",
            color=theme.text_primary,
        )
        if badge_txt.width > 6.8:
            badge_txt.scale_to_fit_width(6.8)
        badge_box = RoundedRectangle(
            corner_radius=0.22,
            width=badge_txt.width + 0.7,
            height=badge_txt.height + 0.42,
            fill_color=theme.card_bg,
            fill_opacity=0.96,
            stroke_color=theme.accent_positive,
            stroke_width=3.0,
        )
        badge_txt.move_to(badge_box.get_center())
        winner_grp = VGroup(badge_box, badge_txt).move_to(DOWN * 5.0)
        objects["winner"] = winner_grp

    if row.get("formula"):
        formula = MathTex(row["formula"], font_size=42, color=theme.text_primary)
        if formula.width > 7.4:
            formula.scale_to_fit_width(7.4)
        if formula.height > 1.4:
            formula.scale_to_fit_height(1.4)
        formula.move_to(DOWN * 3.55)
        objects["formula"] = formula
    return objects


def _available_targets(params: Mapping[str, Any], formula: str) -> frozenset[str]:
    targets = {"title", "body", "baseline"}
    for idx in range(len(params.get("items", []))):
        targets.add(f"bar_{idx + 1}")
    if params.get("winner") is not None:
        targets.add("winner")
    if formula:
        targets.add("formula")
    return frozenset(targets)


def register() -> None:
    register_visual_block(
        VisualBlockSpec(
            name="compare_bars",
            pack="core",
            description="2-4 vertical comparison bars scaled from exact Fractions, with optional winner callout.",
            cue_targets=frozenset(
                {"title", "body", "baseline", "bar_1", "bar_2", "bar_3", "bar_4", "winner", "formula"}
            ),
            params_schema={
                "items": "List of 2-4 objects: {id, value (exact rational/decimal), optional color role}",
                "unit": "Optional display unit string (default '%')",
                "winner": "Optional item id highlighted in the winner banner",
            },
            validate_params=validate_params,
            build=build,
            source_file=Path(__file__),
            available_targets=_available_targets,
        )
    )
