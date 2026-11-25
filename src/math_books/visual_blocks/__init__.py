"""Modular 9:16 visual block protocol, registry, and shared validation helpers."""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Mapping
from fractions import Fraction
from pathlib import Path
from typing import Any

from math_books.languages import SUPPORTED_LANGUAGES
from math_books.themes import VisualTheme

_RATIONAL_RE = re.compile(r"^[+-]?\d+(?:/\d+|\.\d+)?$")


def parse_exact_fraction(value: object, field: str) -> Fraction:
    """Parse an exact integer or rational/decimal string into a Fraction."""
    if type(value) is int:
        return Fraction(value)
    if isinstance(value, str) and len(value) <= 100 and _RATIONAL_RE.fullmatch(value.strip()):
        return Fraction(value.strip())
    raise ValueError(f"{field}: expected an integer or rational/decimal string")


def require_localized_label(translations: Mapping[str, Mapping[str, Any]], label_key: str, context: str) -> None:
    """Ensure every supported language provides a non-empty label for `label_key`."""
    for lang in SUPPORTED_LANGUAGES:
        labels = translations[lang].get("labels")
        if not isinstance(labels, dict):
            raise ValueError(f"{context}/{lang}: labels object is required for visual block")
        value = labels.get(label_key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{context}/{lang}: missing non-empty label {label_key!r}")


def localized_label(row: Mapping[str, Any], label_key: str) -> str:
    labels = row.get("labels")
    if not isinstance(labels, dict) or not isinstance(labels.get(label_key), str):
        raise ValueError(f"Missing localized label {label_key!r}")
    return labels[label_key]


@dataclasses.dataclass(frozen=True)
class VisualBlockSpec:
    """Declarative metadata and builder for a reusable 9:16 Manim visual block."""

    name: str
    pack: str
    description: str
    cue_targets: frozenset[str]
    params_schema: Mapping[str, str]
    validate_params: Callable[[Mapping[str, Any], Mapping[str, Mapping[str, Any]], str], None]
    build: Callable[[VisualTheme, str, Mapping[str, Any]], dict[str, Any]]
    source_file: Path


_REGISTRY: dict[str, VisualBlockSpec] = {}
_CORE_LOADED = False


def register_visual_block(spec: VisualBlockSpec) -> VisualBlockSpec:
    _REGISTRY[spec.name] = spec
    return spec


def _ensure_all_loaded() -> None:
    global _CORE_LOADED
    if not _CORE_LOADED:
        _CORE_LOADED = True
        from math_books.visual_blocks import (
            challenge_card,
            compare_bars,
            hook_choice,
            step_chain,
            text_card,
        )

        for module in (text_card, hook_choice, compare_bars, step_chain, challenge_card):
            module.register()
    from math_books.packs import ensure_packs_loaded

    ensure_packs_loaded()


def get_visual_block(name: str) -> VisualBlockSpec:
    _ensure_all_loaded()
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY))
        raise ValueError(f"Unknown visual block {name!r}. Available: {available}")
    return _REGISTRY[name]


def list_visual_blocks() -> dict[str, VisualBlockSpec]:
    _ensure_all_loaded()
    return dict(_REGISTRY)


def visual_block_catalog() -> list[dict[str, object]]:
    """Return a JSON-serializable catalog for template-aware script generation."""
    blocks = list_visual_blocks()
    return [
        {
            "name": spec.name,
            "pack": spec.pack,
            "description": spec.description,
            "cue_targets": sorted(spec.cue_targets),
            "params_schema": dict(spec.params_schema),
        }
        for _, spec in sorted(blocks.items())
    ]


def visual_source_files() -> list[Path]:
    """Return deterministic source paths for render-fingerprint provenance."""
    _ensure_all_loaded()
    paths = {
        Path(__file__).resolve(),
        Path(__file__).resolve().parents[1] / "themes.py",
        Path(__file__).resolve().parents[1] / "ui_strings.json",
        Path(__file__).resolve().parents[1] / "packs" / "__init__.py",
    }
    for spec in _REGISTRY.values():
        paths.add(spec.source_file.resolve())
    return sorted(paths)
