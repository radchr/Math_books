"""Exact declared cue resolution on a canonical audio sample/video frame clock."""

from __future__ import annotations

import math
import re
from fractions import Fraction

from math_books.languages import SUPPORTED_LANGUAGES, validate_language
from math_books.spoken_text import normalize_spoken_text


def _contains(tokens: list[str], phrase: list[str]) -> int:
    return sum(tokens[i : i + len(phrase)] == phrase for i in range(len(tokens) - len(phrase) + 1))


def localize_cues(cues, translations: dict, language: str, *, formula: str) -> list[dict]:
    validate_language(language)
    if not isinstance(cues, list):
        raise ValueError("Scene cues must be a list")
    ids, targets = set(), set()
    result = []
    for cue in cues:
        if not isinstance(cue, dict) or set(cue) != {"id", "target", "anchor", "occurrence", "phrases"}:
            raise ValueError("Cue requires id, target, anchor, occurrence and phrases")
        ident, target = cue["id"], cue["target"]
        if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", ident) or ident in ids:
            raise ValueError("Invalid or duplicate cue ID")
        if target not in ("title", "body", "formula") or target in targets:
            raise ValueError("Cue target must be unique: title, body or formula")
        if target == "formula" and not formula:
            raise ValueError("Cannot reveal an empty formula")
        if cue["anchor"] not in ("start", "end") or type(cue["occurrence"]) is not int or cue["occurrence"] < 1:
            raise ValueError("Cue requires start/end anchor and a positive integer occurrence")
        phrases = cue["phrases"]
        if not isinstance(phrases, dict) or set(phrases) != set(SUPPORTED_LANGUAGES):
            raise ValueError("Cue phrases require uk/ru/en translations")
        for lang, phrase in phrases.items():
            if not isinstance(phrase, str) or not phrase.strip():
                raise ValueError("Cue phrase must not be empty")
            normalized = normalize_spoken_text(phrase, lang)
            script = normalize_spoken_text(translations[lang]["text"], lang)
            if not normalized or _contains(script, normalized) < cue["occurrence"]:
                raise ValueError(f"Cue {ident}: occurrence not found in {lang} narration")
        ids.add(ident)
        targets.add(target)
        result.append(
            {key: cue[key] for key in ("id", "target", "anchor", "occurrence")} | {"phrase": phrases[language]}
        )
    return result


def resolve_cues(
    row: dict,
    words: list[dict],
    language: str,
    *,
    duration: float,
    sample_rate: int = 24000,
    fps: int = 30,
    offset_s: float = 0.0,
) -> list[dict]:
    """Resolve phrase occurrences; a missing cue never silently becomes a guessed time."""
    validate_language(language)
    if (
        not math.isfinite(duration)
        or duration <= 0
        or sample_rate <= 0
        or fps <= 0
        or not math.isfinite(offset_s)
        or offset_s < 0
    ):
        raise ValueError("Invalid cue clock or duration")
    cues = row.get("cues", [])
    if not cues:
        return []
    previous = 0.0
    for word in words:
        if (
            not isinstance(word, dict)
            or not isinstance(word.get("word"), str)
            or type(word.get("start")) not in (int, float)
            or type(word.get("end")) not in (int, float)
            or not math.isfinite(word["start"])
            or not math.isfinite(word["end"])
            or word["start"] < previous
            or word["end"] < word["start"]
            or word["end"] > duration
        ):
            raise ValueError("Invalid word evidence for cue resolution")
        previous = word["start"]
    events = []
    full_tokens = normalize_spoken_text(" ".join(word["word"] for word in words), language)
    prefixes = [
        normalize_spoken_text(" ".join(word["word"] for word in words[:i]), language) for i in range(len(words) + 1)
    ]
    suffixes = [
        normalize_spoken_text(" ".join(word["word"] for word in words[i:]), language) for i in range(len(words) + 1)
    ]
    for cue in cues:
        phrase = normalize_spoken_text(cue["phrase"], language)
        matches = []
        matched_tokens = set()
        # Normalize joined spans so compound numbers work across separate ASR words.
        for first in range(len(words)):
            for last in range(first, len(words)):
                span = " ".join(word["word"] for word in words[first : last + 1])
                normalized = normalize_spoken_text(span, language)
                if normalized == phrase:
                    # A boundary may not split a compound numeral or operation.
                    # The whole narration must have the same normalized tokens.
                    token_span = (len(prefixes[first]), len(prefixes[first]) + len(phrase))
                    if (
                        prefixes[first] + phrase + suffixes[last + 1] == full_tokens
                        and token_span not in matched_tokens
                    ):
                        matches.append((first, last))
                        matched_tokens.add(token_span)
                        break
                if len(normalized) > len(phrase) + 2:
                    break
        if len(matches) < cue["occurrence"]:
            raise ValueError(f"Unresolved cue {cue['id']}: requested phrase occurrence is missing")
        first, last = matches[cue["occurrence"] - 1]
        at = words[first]["start"] if cue["anchor"] == "start" else words[last]["end"]
        global_frame = round((offset_s + at) * fps)
        frame = global_frame - round(offset_s * fps)
        # A reveal needs an actual output frame, not a transition after narration.
        if global_frame >= round((offset_s + duration) * fps):
            raise ValueError(f"Cue {cue['id']} leaves no frame inside narration")
        events.append(
            {
                **cue,
                "frame": frame,
                "sample": round(Fraction(global_frame * sample_rate, fps)),
                "global_frame": global_frame,
                "time": frame / fps,
                "sample_rate": sample_rate,
                "fps": fps,
            }
        )
    return sorted(events, key=lambda event: (event["frame"], event["id"]))


def event_timeline(scenes: list[dict], manifest: list[dict], snapshot: dict, language: str) -> dict:
    if [s["id"] for s in scenes] != [s["id"] for s in manifest]:
        raise ValueError("Cue scenes and audio manifest differ")
    result = {}
    offset = 0.0
    for scene, item in zip(scenes, manifest, strict=True):
        duration = float(item["duration"])
        result[scene["id"]] = resolve_cues(
            scene, snapshot.get(scene["id"], []), language, duration=duration, offset_s=offset
        )
        offset += duration + 0.4
    return result


def validate_event_log(timeline: dict, records: list[dict], *, tolerance_frames: int = 1) -> None:
    expected = {(scene_id, event["id"]): event for scene_id, events in timeline.items() for event in events}
    if not isinstance(records, list) or len(records) != len(expected):
        raise ValueError("Rendered cue log does not cover every declared event")
    seen = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Rendered cue record must be an object")
        key = (record.get("scene_id"), record.get("id"))
        event = expected.get(key)
        if (
            event is None
            or key in seen
            or type(record.get("frame")) is not int
            or record.get("target") != event["target"]
            or abs(record["frame"] - event["frame"]) > tolerance_frames
            or (
                "global_frame" in event
                and (
                    type(record.get("global_frame")) is not int
                    or abs(record["global_frame"] - event["global_frame"]) > tolerance_frames
                )
            )
        ):
            raise ValueError("Rendered cue differs from the frozen event timeline")
        seen.add(key)
