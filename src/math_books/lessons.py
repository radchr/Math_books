"""Validated, declarative three-language content for new videos only."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from math_books.cue_timeline import localize_cues
from math_books.languages import SUPPORTED_LANGUAGES, validate_language

FORMULA_COMMANDS = {"frac", "times", "cdot", "sqrt", "ge", "le", "geq", "leq", "approx", "%"}


def lesson_path(root: Path, key: str) -> Path:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
        raise ValueError(f"Invalid lesson topic {key!r}")
    return root / "content" / "lessons" / f"{key}.json"


def lesson_digest(scenes: list[dict]) -> str:
    return hashlib.sha256(json.dumps(scenes, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate lesson key: {key}")
        result[key] = value
    return result


def load_lesson(root: Path, key: str, language: str = "ru") -> list[dict]:
    """Load narration/captions before layout; validate every supplied translation."""
    validate_language(language)
    path = lesson_path(root, key)
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("topic") != key:
        raise ValueError(f"Invalid lesson schema/topic: {path}")
    rows = data.get("scenes")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Lesson must contain at least one scene")
    ids = set()
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Lesson scene must be an object")
        ident = row.get("id")
        if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", ident) or ident in ids:
            raise ValueError(f"Invalid/duplicate lesson scene ID: {ident!r}")
        ids.add(ident)
        translations = row.get("translations")
        if not isinstance(translations, dict) or set(translations) != set(SUPPORTED_LANGUAGES):
            raise ValueError(f"{ident}: complete uk/ru/en translations are required")
        for lang, fields in translations.items():
            if not isinstance(fields, dict) or set(fields) != {"text", "title", "body"}:
                raise ValueError(f"{ident}/{lang}: expected text, title and body")
            if any(not isinstance(value, str) or not value.strip() for value in fields.values()):
                raise ValueError(f"{ident}/{lang}: translation must not be empty")
        formula = row.get("formula", "")
        if not isinstance(formula, str) or re.search(r"[^0-9A-Za-z\\{}_^=+*/().,%<>!| \-]", formula):
            raise ValueError(f"{ident}: use pure mathematical notation in formula")
        if set(re.findall(r"\\([A-Za-z]+|%)", formula)) - FORMULA_COMMANDS:
            raise ValueError(f"{ident}: unsupported LaTeX command in formula")
        localized = {"id": ident, **translations[language], "formula": formula}
        if "cues" in row:
            localized["cues"] = localize_cues(row["cues"], translations, language, formula=formula)
        result.append(localized)
    return result


def discover_lessons(root: Path) -> list[str]:
    return sorted(path.stem for path in (root / "content" / "lessons").glob("*.json"))
