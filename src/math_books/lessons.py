"""Validated, declarative three-language content for new videos only."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from math_books.cue_timeline import localize_cues, localize_timed_cues
from math_books.languages import SUPPORTED_LANGUAGES, validate_language

AUDIO_MODES = ("voiceover", "music_only")
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


def validate_lesson_data(data: object, key: str, language: str = "ru", *, source_label: str = "") -> list[dict]:
    """Validate declarative 3-language lesson structure and return localized scene rows."""
    from math_books.packs import get_pack
    from math_books.themes import get_theme
    from math_books.visual_blocks import get_visual_block

    validate_language(language)
    if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("topic") != key:
        raise ValueError(f"Invalid lesson schema/topic: {source_label or key}")

    lesson_theme: str | None = None
    if "domain" in data:
        domain = data["domain"]
        if not isinstance(domain, str) or not domain.strip():
            raise ValueError("Lesson domain must be a non-empty string")
        if domain != "core":
            pack = get_pack(domain)
            lesson_theme = pack.default_theme
    if "theme" in data:
        theme_name = data["theme"]
        if not isinstance(theme_name, str) or not theme_name.strip():
            raise ValueError("Lesson theme must be a non-empty string")
        get_theme(theme_name)
        lesson_theme = theme_name

    audio_mode = data.get("audio_mode", "voiceover")
    if audio_mode not in AUDIO_MODES:
        raise ValueError(f"Unsupported audio_mode {audio_mode!r}; choose one of {', '.join(AUDIO_MODES)}")
    music_track: str | None = None
    if audio_mode == "music_only":
        track = data.get("music_track")
        if not isinstance(track, str) or not track.strip():
            raise ValueError("music_only lessons require a non-empty music_track id")
        music_track = track.strip()

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
            if not isinstance(fields, dict):
                raise ValueError(f"{ident}/{lang}: expected text, title and body")
            required_keys = {"title", "body"} if audio_mode == "music_only" else {"text", "title", "body"}
            allowed_keys = {"text", "title", "body", "labels"}
            if not required_keys <= set(fields) or not set(fields) <= allowed_keys:
                raise ValueError(f"{ident}/{lang}: expected {', '.join(sorted(required_keys))}")
            if any(not isinstance(fields[k], str) or not fields[k].strip() for k in required_keys):
                raise ValueError(f"{ident}/{lang}: translation must not be empty")
            if "text" in fields and (not isinstance(fields["text"], str) or not fields["text"].strip()):
                raise ValueError(f"{ident}/{lang}: text must be a non-empty string when provided")
            if "labels" in fields:
                labels = fields["labels"]
                if not isinstance(labels, dict) or any(
                    not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip()
                    for k, v in labels.items()
                ):
                    raise ValueError(f"{ident}/{lang}: labels must map non-empty keys to non-empty strings")
        formula = row.get("formula", "")
        if not isinstance(formula, str) or re.search(r"[^0-9A-Za-z\\{}_^=+*/().,%<>!| \-]", formula):
            raise ValueError(f"{ident}: use pure mathematical notation in formula")
        if set(re.findall(r"\\([A-Za-z]+|%)", formula)) - FORMULA_COMMANDS:
            raise ValueError(f"{ident}: unsupported LaTeX command in formula")

        allowed_targets: frozenset[str] | None = None
        visual_payload: dict | None = None
        if "visual" in row:
            visual = row["visual"]
            if not isinstance(visual, dict) or not isinstance(visual.get("template"), str):
                raise ValueError(f"{ident}: visual requires a template name")
            params = visual.get("params", {})
            if not isinstance(params, dict):
                raise ValueError(f"{ident}: visual.params must be an object")
            spec = get_visual_block(visual["template"])
            spec.validate_params(params, translations, ident)
            allowed_targets = spec.cue_targets
            visual_payload = {"template": spec.name, "params": params}

        lang_fields = dict(translations[language])
        if audio_mode == "music_only" and "text" not in lang_fields:
            parts = [lang_fields["title"], lang_fields["body"]]
            if isinstance(lang_fields.get("labels"), dict):
                parts.extend(str(v) for v in lang_fields["labels"].values())
            lang_fields["text"] = " ".join(parts)

        localized: dict = {"id": ident, **lang_fields, "formula": formula}
        if visual_payload is not None:
            localized["visual"] = visual_payload
        if lesson_theme is not None:
            localized["theme"] = lesson_theme
        if audio_mode == "music_only":
            raw_dur = row.get("duration_s")
            if raw_dur is None:
                max_words = max(
                    len(f"{translations[lang]['title']} {translations[lang]['body']}".split())
                    for lang in SUPPORTED_LANGUAGES
                )
                duration_s = round(max(3.5, max_words / 2.6 + 1.5), 2)
            else:
                if (
                    isinstance(raw_dur, bool)
                    or not isinstance(raw_dur, (int, float))
                    or not (1.5 <= float(raw_dur) <= 30.0)
                ):
                    raise ValueError(f"{ident}: duration_s must be between 1.5 and 30.0 seconds")
                duration_s = float(raw_dur)
            localized["audio_mode"] = "music_only"
            localized["music_track"] = music_track
            localized["duration_s"] = duration_s
            if "cues" in row:
                localized["cues"] = localize_timed_cues(
                    row["cues"], duration_s=duration_s, formula=formula, allowed_targets=allowed_targets
                )
        elif "cues" in row:
            localized["cues"] = localize_cues(
                row["cues"], translations, language, formula=formula, allowed_targets=allowed_targets
            )
        result.append(localized)
    return result


def load_lesson(root: Path, key: str, language: str = "ru") -> list[dict]:
    """Load narration/captions before layout; validate every supplied translation."""
    path = lesson_path(root, key)
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    return validate_lesson_data(data, key, language, source_label=str(path))


def discover_lessons(root: Path) -> list[str]:
    return sorted(path.stem for path in (root / "content" / "lessons").glob("*.json"))
