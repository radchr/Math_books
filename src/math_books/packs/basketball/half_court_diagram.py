"""Basketball domain visual block: parameterized half-court diagram with markers and pass/shot arrows."""

from __future__ import annotations

import textwrap
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from math_books.themes import CONTENT_MAX_WIDTH, VisualTheme
from math_books.visual_blocks import (
    VisualBlockSpec,
    localized_label,
    register_visual_block,
    require_localized_label,
)


def _validate_coord(value: object, field: str, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field}: expected numeric coordinate")
    val = float(value)
    if not lo <= val <= hi:
        raise ValueError(f"{field}: coordinate {val} out of court bounds [{lo}, {hi}]")
    return val


def validate_params(params: Mapping[str, Any], translations: Mapping[str, Mapping[str, Any]], context: str) -> None:
    markers = params.get("markers", [])
    if not isinstance(markers, list) or len(markers) > 6:
        raise ValueError(f"{context}: markers must be a list of at most 6 items")
    ids: set[str] = set()
    for index, marker in enumerate(markers):
        if not isinstance(marker, Mapping):
            raise ValueError(f"{context}: marker {index} must be an object")
        ident = marker.get("id")
        if not isinstance(ident, str) or not ident.strip() or ident in ids:
            raise ValueError(f"{context}: marker requires unique non-empty id")
        ids.add(ident)
        _validate_coord(marker.get("x"), f"{context}.markers[{ident}].x", -3.2, 3.2)
        _validate_coord(marker.get("y"), f"{context}.markers[{ident}].y", -2.6, 2.4)
        require_localized_label(translations, ident, context)

    arrows = params.get("arrows", [])
    if not isinstance(arrows, list) or len(arrows) > 6:
        raise ValueError(f"{context}: arrows must be a list of at most 6 items")
    for index, arrow in enumerate(arrows):
        if not isinstance(arrow, Mapping):
            raise ValueError(f"{context}: arrow {index} must be an object")
        src, dst = arrow.get("from"), arrow.get("to")
        if src not in ids or dst not in ids or src == dst:
            raise ValueError(f"{context}: arrow {index} must connect two distinct marker ids")


def build(theme: VisualTheme, _language: str, row: Mapping[str, Any]) -> dict[str, Any]:
    import numpy as np
    from manim import DOWN, LEFT, RIGHT, UP, Arc, Arrow, Circle, Dot, Line, MathTex, Rectangle, Text, VGroup

    params = row["visual"]["params"]
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

    center_y = 0.6
    court_box = Rectangle(
        width=7.0,
        height=5.6,
        stroke_color="#415A77",
        stroke_width=3,
        fill_color="#14243B",
        fill_opacity=0.75,
    ).move_to(UP * center_y)
    top_y = court_box.get_top()[1]
    paint = Rectangle(width=2.4, height=2.3, stroke_color="#415A77", stroke_width=2.5).move_to([0, top_y - 1.15, 0])
    three_arc = Arc(radius=2.85, start_angle=-np.pi, angle=np.pi, color="#415A77", stroke_width=2.5)
    three_arc.move_arc_center_to([0, top_y - 0.5, 0])
    backboard = Line(LEFT * 0.75, RIGHT * 0.75, color=theme.text_primary, stroke_width=5).move_to([0, top_y - 0.25, 0])
    rim = Circle(radius=0.18, color=theme.primary, stroke_width=4).move_to([0, top_y - 0.5, 0])
    court = VGroup(court_box, paint, three_arc, backboard, rim)

    marker_positions: dict[str, list[float]] = {}
    marker_mobs = []
    for marker in params.get("markers", []):
        pos = [float(marker["x"]), center_y + float(marker["y"]), 0.0]
        marker_positions[marker["id"]] = pos
        color = theme.color_for(marker.get("color", "primary"))
        dot = Dot(pos, radius=0.16, color=color)
        lbl = Text(localized_label(row, marker["id"]), font=theme.font, font_size=22, weight="BOLD", color=color)
        if lbl.width > 2.2:
            lbl.scale_to_fit_width(2.2)
        lbl.next_to(dot, DOWN, buff=0.12)
        marker_mobs.append(VGroup(dot, lbl))

    arrow_mobs = []
    for arrow_spec in params.get("arrows", []):
        color = theme.color_for(arrow_spec.get("color", "secondary"))
        arrow_mobs.append(
            Arrow(
                marker_positions[arrow_spec["from"]],
                marker_positions[arrow_spec["to"]],
                buff=0.22,
                color=color,
                stroke_width=4,
            )
        )

    objects: dict[str, Any] = {"title": title, "body": body, "court": court}
    if marker_mobs:
        objects["markers"] = VGroup(*marker_mobs)
    if arrow_mobs:
        objects["arrows"] = VGroup(*arrow_mobs)
    if row.get("formula"):
        formula = MathTex(row["formula"], font_size=42, color=theme.text_primary)
        if formula.width > 7.4:
            formula.scale_to_fit_width(7.4)
        formula.move_to(DOWN * 3.8)
        objects["formula"] = formula
    return objects


def register() -> None:
    register_visual_block(
        VisualBlockSpec(
            name="basketball.half_court_diagram",
            pack="basketball",
            description="Top-down basketball half-court with parameterized player/spot markers and pass/shot arrows.",
            cue_targets=frozenset({"title", "body", "court", "markers", "arrows", "formula"}),
            params_schema={
                "markers": (
                    "Optional list of up to 6 markers: {id (label key), x (-3.2..3.2), y (-2.6..2.4), optional color}"
                ),
                "arrows": "Optional list of up to 6 arrows: {from (marker id), to (marker id), optional color}",
            },
            validate_params=validate_params,
            build=build,
            source_file=Path(__file__),
        )
    )
