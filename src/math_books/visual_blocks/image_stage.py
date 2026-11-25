"""Universal diagram/image stage block for physics, chemistry, biology, and general STEM lessons."""

from __future__ import annotations

import textwrap
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from math_books.themes import CONTENT_MAX_WIDTH, VisualTheme
from math_books.topics import project_root
from math_books.visual_blocks import (
    VisualBlockSpec,
    localized_label,
    register_visual_block,
    require_localized_label,
)

_ALLOWED_EXTENSIONS = {".svg", ".png", ".jpg", ".jpeg"}


def _resolve_asset(relative: str) -> Path:
    root = project_root().resolve()
    rel = Path(relative)
    if rel.is_absolute():
        raise ValueError("image_stage image path must be relative to project root")
    resolved = (root / rel).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("image_stage image path escapes project root")
    if resolved.suffix.lower() not in _ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported image_stage extension {resolved.suffix!r}")
    return resolved


def validate_params(params: Mapping[str, Any], translations: Mapping[str, Mapping[str, Any]], context: str) -> None:
    image = params.get("image")
    if not isinstance(image, str) or not image.strip():
        raise ValueError(f"{context}: image_stage requires a relative 'image' path (.svg/.png/.jpg)")
    resolved = _resolve_asset(image)
    if not resolved.is_file():
        raise ValueError(f"{context}: image_stage asset not found: {image}")
    caption_key = params.get("caption_label")
    if caption_key is not None:
        if not isinstance(caption_key, str) or not caption_key.strip():
            raise ValueError(f"{context}: caption_label must be a non-empty string when provided")
        require_localized_label(translations, caption_key, context)


def build(theme: VisualTheme, _language: str, row: Mapping[str, Any]) -> dict[str, Any]:
    from manim import DOWN, UP, ImageMobject, MathTex, RoundedRectangle, SVGMobject, Text, VGroup

    params = row["visual"]["params"]
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

    asset_path = _resolve_asset(params["image"])
    if asset_path.suffix.lower() == ".svg":
        diagram: Any = SVGMobject(str(asset_path))
    else:
        diagram = ImageMobject(str(asset_path))
    if diagram.width > 6.8:
        diagram.scale_to_fit_width(6.8)
    if diagram.height > 4.4:
        diagram.scale_to_fit_height(4.4)
    diagram.move_to(UP * 0.7)

    objects: dict[str, Any] = {"title": title, "body": body, "diagram": diagram}
    if row.get("formula"):
        formula = MathTex(row["formula"], font_size=44, color=theme.text_primary)
        if formula.width > 7.4:
            formula.scale_to_fit_width(7.4)
        formula.move_to(DOWN * 2.8)
        objects["formula"] = formula
    if params.get("caption_label"):
        cap_raw = localized_label(row, params["caption_label"])
        cap_wrapped = "\n".join(textwrap.wrap(cap_raw, width=36) or [cap_raw])
        cap_txt = Text(cap_wrapped, font=theme.font, font_size=26, color=theme.text_primary, line_spacing=1.2)
        if cap_txt.width > 6.8:
            cap_txt.scale_to_fit_width(6.8)
        if cap_txt.height > 1.1:
            cap_txt.scale_to_fit_height(1.1)
        cap_box = RoundedRectangle(
            corner_radius=0.22,
            width=max(cap_txt.width + 0.7, 4.4),
            height=cap_txt.height + 0.42,
            fill_color=theme.card_bg,
            fill_opacity=0.95,
            stroke_color=theme.primary,
            stroke_width=2.5,
        )
        cap_txt.move_to(cap_box.get_center())
        objects["caption"] = VGroup(cap_box, cap_txt).move_to(DOWN * 4.8)
    return objects


def register() -> None:
    register_visual_block(
        VisualBlockSpec(
            name="image_stage",
            pack="core",
            description=(
                "Displays a local SVG/PNG/JPG scientific diagram fitted to 9:16 with optional formula and caption."
            ),
            cue_targets=frozenset({"title", "body", "diagram", "formula", "caption"}),
            params_schema={
                "image": "Project-relative path to a local .svg, .png, or .jpg diagram asset",
                "caption_label": "Optional label key in translations.<lang>.labels for bottom caption card",
            },
            validate_params=validate_params,
            build=build,
            source_file=Path(__file__),
        )
    )
