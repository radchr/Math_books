"""3b1b SampleSpace-inspired 2D probability area partition block using exact Fractions."""

from __future__ import annotations

import textwrap
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from typing import Any

from math_books.themes import CONTENT_MAX_WIDTH, VisualTheme, validate_color_role
from math_books.visual_blocks import (
    VisualBlockSpec,
    localized_label,
    parse_exact_fraction,
    register_visual_block,
    require_localized_label,
)


def _validate_prob(value: object, field: str) -> Fraction:
    frac = parse_exact_fraction(value, field)
    if not Fraction(0) < frac < Fraction(1):
        raise ValueError(f"{field}: probability must be strictly between 0 and 1")
    return frac


def validate_params(params: Mapping[str, Any], translations: Mapping[str, Mapping[str, Any]], context: str) -> None:
    _validate_prob(params.get("p_left"), f"{context}.p_left")
    for key in ("left_label", "right_label"):
        val = params.get(key)
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"{context}: {key} must be a non-empty label key")
        require_localized_label(translations, val, context)

    for side, top_key, bot_key in (
        ("left", "left_top_label", "left_bottom_label"),
        ("right", "right_top_label", "right_bottom_label"),
    ):
        p_key = f"p_{side}_top"
        if params.get(p_key) is not None:
            _validate_prob(params[p_key], f"{context}.{p_key}")
            for lbl_key in (top_key, bot_key):
                val = params.get(lbl_key)
                if not isinstance(val, str) or not val.strip():
                    raise ValueError(f"{context}: {p_key} requires non-empty {lbl_key}")
                require_localized_label(translations, val, context)

    for color_key in ("left_top_color", "left_bottom_color", "right_top_color", "right_bottom_color"):
        if params.get(color_key) is not None:
            validate_color_role(params[color_key], f"{context}.{color_key}")

    takeaway = params.get("takeaway_label")
    if takeaway is not None:
        if not isinstance(takeaway, str) or not takeaway.strip():
            raise ValueError(f"{context}: takeaway_label must be a non-empty string")
        require_localized_label(translations, takeaway, context)


def _pct_str(frac: Fraction) -> str:
    return f"{float(frac * 100):g}%"


def build(theme: VisualTheme, _language: str, row: Mapping[str, Any]) -> dict[str, Any]:
    from manim import DOWN, UP, MathTex, Rectangle, RoundedRectangle, Text, VGroup

    params = row["visual"]["params"]
    p_left = _validate_prob(params["p_left"], "p_left")
    p_right = Fraction(1) - p_left

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
    body.move_to(UP * 4.65)

    total_w = 6.6
    total_h = 4.5
    gap = 0.08
    usable_w = total_w - gap
    left_w = usable_w * float(p_left)
    right_w = usable_w - left_w
    center_y = 0.65
    left_cx = -total_w / 2 + left_w / 2
    right_cx = total_w / 2 - right_w / 2
    top_edge_y = center_y + total_h / 2

    def make_header(label_key: str, prob: Fraction, cx: float, max_w: float, color: str) -> Any:
        txt = Text(
            f"{localized_label(row, label_key)} ({_pct_str(prob)})",
            font=theme.font,
            font_size=22,
            weight="BOLD",
            color=color,
        )
        if txt.width > max(max_w, 1.8):
            txt.scale_to_fit_width(max(max_w, 1.8))
        txt.move_to([cx, top_edge_y + 0.42, 0])
        return txt

    left_hdr = make_header(params["left_label"], p_left, left_cx, left_w, theme.primary)
    right_hdr = make_header(params["right_label"], p_right, right_cx, right_w, theme.secondary)

    objects: dict[str, Any] = {
        "title": title,
        "body": body,
        "left_header": left_hdr,
        "right_header": right_hdr,
    }

    def make_cell(
        width: float, height: float, cx: float, cy: float, color: str, label_text: str, prob: Fraction
    ) -> Any:
        rect = Rectangle(
            width=width,
            height=height,
            fill_color=color,
            fill_opacity=0.82,
            stroke_color=theme.text_primary,
            stroke_width=2.0,
        ).move_to([cx, cy, 0])
        txt = Text(
            f"{label_text}\n{_pct_str(prob)}",
            font=theme.font,
            font_size=24,
            weight="BOLD",
            color=theme.text_primary,
            line_spacing=1.15,
        )
        if txt.width > max(width - 0.25, 0.5):
            txt.scale_to_fit_width(max(width - 0.25, 0.5))
        if txt.height > max(height - 0.22, 0.4):
            txt.scale_to_fit_height(max(height - 0.22, 0.4))
        txt.move_to(rect.get_center())
        return VGroup(rect, txt)

    for side, col_w, col_cx, col_p, def_top_c, def_bot_c in (
        ("left", left_w, left_cx, p_left, "positive", "primary"),
        ("right", right_w, right_cx, p_right, "secondary", "warning"),
    ):
        p_top_raw = params.get(f"p_{side}_top")
        if p_top_raw is not None:
            p_top = _validate_prob(p_top_raw, f"p_{side}_top")
            p_bot = Fraction(1) - p_top
            usable_h = total_h - gap
            top_h = usable_h * float(p_top)
            bot_h = usable_h - top_h
            top_cy = top_edge_y - top_h / 2
            bot_cy = (center_y - total_h / 2) + bot_h / 2
            top_color = theme.color_for(params.get(f"{side}_top_color") or def_top_c)
            bot_color = theme.color_for(params.get(f"{side}_bottom_color") or def_bot_c)
            objects[f"{side}_top"] = make_cell(
                col_w,
                top_h,
                col_cx,
                top_cy,
                top_color,
                localized_label(row, params[f"{side}_top_label"]),
                col_p * p_top,
            )
            objects[f"{side}_bottom"] = make_cell(
                col_w,
                bot_h,
                col_cx,
                bot_cy,
                bot_color,
                localized_label(row, params[f"{side}_bottom_label"]),
                col_p * p_bot,
            )
        else:
            col_color = theme.color_for(params.get(f"{side}_top_color") or def_top_c)
            objects[f"{side}_region"] = make_cell(
                col_w, total_h, col_cx, center_y, col_color, localized_label(row, params[f"{side}_label"]), col_p
            )

    if row.get("formula"):
        formula = MathTex(row["formula"], font_size=42, color=theme.text_primary)
        if formula.width > 7.4:
            formula.scale_to_fit_width(7.4)
        if formula.height > 1.4:
            formula.scale_to_fit_height(1.4)
        formula.move_to(DOWN * 3.15)
        objects["formula"] = formula

    if params.get("takeaway_label"):
        tk_raw = localized_label(row, params["takeaway_label"])
        tk_wrapped = "\n".join(textwrap.wrap(tk_raw, width=34) or [tk_raw])
        tk_txt = Text(tk_wrapped, font=theme.font, font_size=26, weight="BOLD", color=theme.text_primary)
        if tk_txt.width > 6.8:
            tk_txt.scale_to_fit_width(6.8)
        if tk_txt.height > 1.1:
            tk_txt.scale_to_fit_height(1.1)
        tk_box = RoundedRectangle(
            corner_radius=0.24,
            width=max(tk_txt.width + 0.75, 4.6),
            height=tk_txt.height + 0.44,
            fill_color=theme.card_bg,
            fill_opacity=0.96,
            stroke_color=theme.accent_positive,
            stroke_width=3.0,
        )
        tk_txt.move_to(tk_box.get_center())
        objects["takeaway"] = VGroup(tk_box, tk_txt).move_to(DOWN * 4.95)

    return objects


def _available_targets(params: Mapping[str, Any], formula: str) -> frozenset[str]:
    targets = {"title", "body", "left_header", "right_header"}
    for side in ("left", "right"):
        if params.get(f"p_{side}_top") is not None:
            targets.update({f"{side}_top", f"{side}_bottom"})
        else:
            targets.add(f"{side}_region")
    if formula:
        targets.add("formula")
    if params.get("takeaway_label"):
        targets.add("takeaway")
    return frozenset(targets)


def register() -> None:
    register_visual_block(
        VisualBlockSpec(
            name="probability_area",
            pack="core",
            description="3b1b SampleSpace-style 2D probability rectangle partitioned by exact Fractions.",
            cue_targets=frozenset(
                {
                    "title",
                    "body",
                    "left_header",
                    "right_header",
                    "left_region",
                    "right_region",
                    "left_top",
                    "left_bottom",
                    "right_top",
                    "right_bottom",
                    "formula",
                    "takeaway",
                }
            ),
            params_schema={
                "p_left": "Exact Fraction/decimal in (0, 1) for left column width",
                "left_label": "Label key for left column",
                "right_label": "Label key for right column",
                "p_left_top": "Optional conditional probability in (0, 1) splitting left column vertically",
                "p_right_top": "Optional conditional probability in (0, 1) splitting right column vertically",
                "takeaway_label": "Optional label key for bottom conclusion banner",
            },
            validate_params=validate_params,
            build=build,
            source_file=Path(__file__),
            available_targets=_available_targets,
        )
    )
