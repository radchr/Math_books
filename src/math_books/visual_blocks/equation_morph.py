"""Step-by-step equation morphing visual block powered by TransformMatchingTex and semantic colors."""

from __future__ import annotations

import itertools
import re
import textwrap
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from math_books.lessons import validate_latex_formula
from math_books.themes import CONTENT_MAX_WIDTH, VisualTheme, validate_color_role
from math_books.visual_blocks import (
    VisualBlockSpec,
    localized_label,
    register_visual_block,
    require_localized_label,
)

_STEP_NAMES = ("step_1", "step_2", "step_3", "step_4")
_MORPH_OVERLAP_PAIRS = frozenset(frozenset(pair) for pair in itertools.combinations(_STEP_NAMES, 2))


def validate_params(params: Mapping[str, Any], translations: Mapping[str, Mapping[str, Any]], context: str) -> None:
    steps = params.get("steps")
    if not isinstance(steps, list) or not 2 <= len(steps) <= 4:
        raise ValueError(f"{context}: equation_morph requires 2 to 4 equation steps")
    for idx, step in enumerate(steps):
        if not isinstance(step, Mapping):
            raise ValueError(f"{context}: step {idx} must be an object")
        tex = step.get("tex")
        if not isinstance(tex, str) or not tex.strip():
            raise ValueError(f"{context}: step {idx} requires non-empty 'tex' formula")
        validate_latex_formula(tex, f"{context}.steps[{idx}].tex")
        note_key = step.get("note_label")
        if note_key is not None:
            if not isinstance(note_key, str) or not note_key.strip():
                raise ValueError(f"{context}: step {idx} note_label must be a non-empty string")
            require_localized_label(translations, note_key, context)
    colors = params.get("formula_colors")
    if colors is not None:
        if not isinstance(colors, Mapping) or len(colors) > 12:
            raise ValueError(f"{context}: formula_colors must be an object with at most 12 entries")
        for tex_key, role in colors.items():
            if not isinstance(tex_key, str) or not tex_key.strip():
                raise ValueError(f"{context}: formula_colors keys must be non-empty TeX strings")
            validate_color_role(role, f"{context}.formula_colors[{tex_key}]")
    result_key = params.get("result_label")
    if result_key is not None:
        if not isinstance(result_key, str) or not result_key.strip():
            raise ValueError(f"{context}: result_label must be a non-empty string")
        require_localized_label(translations, result_key, context)


def _isolate_tex_tokens(tex: str, tokens: list[str]) -> str:
    """Wrap standalone matching tokens in Manim's {{...}} without touching LaTeX commands like \\cdot."""
    if not tokens:
        return tex
    ordered = sorted(tokens, key=len, reverse=True)
    # Match either a LaTeX command (skipped untouched) or a standalone target token
    tok_alt = "|".join(re.escape(t) for t in ordered)
    pattern = re.compile(rf"(\\[A-Za-z]+)|(?<![A-Za-z0-9\\])({tok_alt})(?![A-Za-z0-9])")

    def repl(match: re.Match[str]) -> str:
        if match.group(1) is not None:
            return match.group(1)
        return " {{ " + match.group(2) + " }} "

    return pattern.sub(repl, tex)


def _apply_semantic_colors(tex_mob: Any, theme: VisualTheme, color_map: Mapping[str, str]) -> None:
    from manim import MathTex

    if not isinstance(MathTex, type) or not isinstance(tex_mob, MathTex):
        return
    for substring, role in color_map.items():
        tex_mob.set_color_by_tex(substring, theme.color_for(role))


def build(theme: VisualTheme, _language: str, row: Mapping[str, Any]) -> dict[str, Any]:
    from manim import DOWN, UP, MathTex, RoundedRectangle, Text, VGroup

    params = row["visual"]["params"]
    steps = params["steps"]
    color_map = params.get("formula_colors") or row.get("formula_colors") or {}
    substrings = sorted(color_map.keys(), key=len, reverse=True)

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
    body.move_to(UP * 4.5)

    objects: dict[str, Any] = {"title": title, "body": body}

    for idx, step in enumerate(steps):
        isolated_tex = _isolate_tex_tokens(step["tex"], substrings)
        eq = MathTex(
            isolated_tex,
            font_size=56,
            color=theme.text_primary,
        )
        if color_map:
            _apply_semantic_colors(eq, theme, color_map)
        if eq.width > 7.0:
            eq.scale_to_fit_width(7.0)
        if eq.height > 2.0:
            eq.scale_to_fit_height(2.0)
        eq_box = RoundedRectangle(
            corner_radius=0.28,
            width=7.4,
            height=max(eq.height + 1.0, 2.4),
            fill_color=theme.card_bg,
            fill_opacity=0.95,
            stroke_color=theme.primary if idx < len(steps) - 1 else theme.accent_positive,
            stroke_width=3.0,
        ).move_to(UP * 1.1)
        eq.move_to(eq_box.get_center())

        parts: list[Any] = [eq_box, eq]
        if step.get("note_label"):
            note_raw = localized_label(row, step["note_label"])
            note_wrapped = "\n".join(textwrap.wrap(note_raw, width=36) or [note_raw])
            note = Text(note_wrapped, font=theme.font, font_size=26, color=theme.secondary, line_spacing=1.2)
            if note.width > 7.2:
                note.scale_to_fit_width(7.2)
            if note.height > 1.2:
                note.scale_to_fit_height(1.2)
            note.move_to(DOWN * 1.65)
            parts.append(note)

        grp = VGroup(*parts)
        objects[f"step_{idx + 1}"] = grp

    if params.get("result_label"):
        res_raw = localized_label(row, params["result_label"])
        res_wrapped = "\n".join(textwrap.wrap(res_raw, width=34) or [res_raw])
        res_txt = Text(res_wrapped, font=theme.font, font_size=28, weight="BOLD", color=theme.text_primary)
        if res_txt.width > 6.8:
            res_txt.scale_to_fit_width(6.8)
        if res_txt.height > 1.2:
            res_txt.scale_to_fit_height(1.2)
        res_box = RoundedRectangle(
            corner_radius=0.24,
            width=max(res_txt.width + 0.8, 5.0),
            height=res_txt.height + 0.5,
            fill_color=theme.card_bg,
            fill_opacity=0.98,
            stroke_color=theme.accent_positive,
            stroke_width=3.2,
        )
        res_txt.move_to(res_box.get_center())
        objects["result"] = VGroup(res_box, res_txt).move_to(DOWN * 4.5)

    return objects


def _available_targets(params: Mapping[str, Any], _formula: str) -> frozenset[str]:
    targets = {"title", "body"}
    for idx in range(len(params.get("steps", []))):
        targets.add(f"step_{idx + 1}")
    if params.get("result_label"):
        targets.add("result")
    return frozenset(targets)


def register() -> None:
    register_visual_block(
        VisualBlockSpec(
            name="equation_morph",
            pack="core",
            description=(
                "Step-by-step equation derivation with semantic variable colors and TransformMatchingTex morphs."
            ),
            cue_targets=frozenset({"title", "body", "step_1", "step_2", "step_3", "step_4", "result"}),
            params_schema={
                "steps": "List of 2-4 objects: {tex (pure LaTeX), optional note_label}",
                "formula_colors": "Optional mapping of TeX substring -> VisualTheme color role",
                "result_label": "Optional label key for the bottom takeaway badge",
            },
            validate_params=validate_params,
            build=build,
            source_file=Path(__file__),
            available_targets=_available_targets,
            allowed_overlap_pairs=_MORPH_OVERLAP_PAIRS,
        )
    )
