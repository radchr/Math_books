"""Offline editorial gate: exact checks plus explicit, version-bound reviewer judgments.

This records review evidence; it does not infer scientific truth from a URL or
authenticate a reviewer's identity. Never generate an approval automatically.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Sequence
from datetime import date
from fractions import Fraction
from pathlib import Path
from urllib.parse import urlparse

from math_books.lesson_math import coin_followup_examples

REVIEW_CRITERIA = {
    "scientific": ("evidence_matches_claims", "calculations_correct", "assumptions_and_limits", "no_overclaim"),
    "pedagogical": (
        "age_and_prerequisites",
        "objective_alignment",
        "explanation_clarity",
        "challenge_checks_understanding",
    ),
}
SUPPORTING_FILES = ("src/math_books/lesson_math.py", "src/math_books/video_ui.py")


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _finite_float(value):
    number = float(value)
    _require(math.isfinite(number), "Nonfinite JSON numeric value")
    return number


def _reject_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")


def _fraction(value, name):
    _require(type(value) in (int, str), f"{name}: use an integer or a quoted rational/decimal string")
    if isinstance(value, str):
        _require(
            len(value) <= 100 and bool(re.fullmatch(r"[+-]?\d+(?:/\d+|\.\d+)?", value)),
            f"{name}: invalid rational/decimal",
        )
    return Fraction(value)


def script_digest(scenes: Sequence[dict[str, str]]) -> str:
    return _digest([{"id": s["id"], "text": s["text"]} for s in scenes])


def dossier_digest(dossier: dict) -> str:
    return _digest({key: value for key, value in dossier.items() if key != "reviews"})


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _text(value: object, name: str) -> None:
    _require(
        isinstance(value, str) and bool(value.strip()) and not re.match(r"^(TODO|TBD)\b", value.strip()),
        f"{name}: provide substantive text",
    )


def _strings(value: object, name: str, *, allow_empty: bool = False) -> None:
    _require(isinstance(value, list), f"{name}: expected a list")
    _require(allow_empty or bool(value), f"{name}: must not be empty")
    for item in value:
        _text(item, name)


def _scene_path(root: Path, relative: str) -> Path:
    _text(relative, "scene_file")
    path = (root / relative).resolve()
    _require(
        not Path(relative).is_absolute() and path.is_relative_to(root.resolve()),
        "scene_file must be inside the project",
    )
    return path


def make_review_template(topic: str, scenes: Sequence[dict[str, str]], scene_file: str, root: Path) -> dict:
    """Produce a pending dossier; an editor must supply evidence and actual judgments."""
    return {
        "schema_version": 1,
        "topic": topic,
        "script_sha256": script_digest(scenes),
        "scene_file": scene_file,
        "scene_sha256": hashlib.sha256(_scene_path(root, scene_file).read_bytes()).hexdigest(),
        "supporting_files": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in SUPPORTING_FILES
            if (root / name).is_file()
        },
        "pedagogy": {
            "audience_age": 12,
            "learning_objective": "",
            "prerequisites": [],
            "assumptions": [],
            "limitations": [],
            "challenge": "",
            "expected_learning": "",
        },
        "sources": [],
        "math_checks": [],
        "scene_reviews": [
            {
                "scene_id": s["id"],
                "teaching_role": "",
                "claims": [
                    {
                        "statement": "",
                        "script_quote": s["text"],
                        "kind": "",
                        "source_ids": [],
                        "math_check_ids": [],
                        "reasoning": "",
                    }
                ],
            }
            for s in scenes
        ],
        "unresolved_issues": [],
        "reviews": {
            discipline: {
                "reviewer": "",
                "reviewer_type": "",
                "reviewed_at": "",
                "verdict": "pending",
                "dossier_sha256": "",
                "criteria": {key: {"passed": False, "rationale": ""} for key in criteria},
            }
            for discipline, criteria in REVIEW_CRITERIA.items()
        },
    }


def _math_check(check: dict) -> dict:
    ident = check["id"]
    if check.get("kind") == "independent_attempts":
        probability = _fraction(check["probability"], f"{ident}.probability")
        attempts = check["attempts"]
        _require(
            0 <= probability <= 1 and type(attempts) is int and 1 <= attempts <= 100,
            f"{ident}: invalid probability or attempt count",
        )
        actual = 1 - (1 - probability) ** attempts
        _require(
            actual == _fraction(check["expected_at_least_one"], f"{ident}.expected_at_least_one"),
            f"{ident}: complement-rule calculation is wrong (actual {actual})",
        )
        return {"id": ident, "ok": True, "at_least_one": str(actual)}
    if check.get("kind") == "expected_points":
        probability = _fraction(check["probability"], f"{ident}.probability")
        points = check["points"]
        _require(0 <= probability <= 1 and type(points) is int and points > 0, f"{ident}: invalid probability/points")
        actual = probability * points
        _require(
            actual == _fraction(check["expected"], f"{ident}.expected"),
            f"{ident}: expected points calculation is wrong (actual {actual})",
        )
        return {"id": ident, "ok": True, "actual": str(actual)}
    if check.get("kind") == "fair_coin_followups":
        rows = coin_followup_examples()
        sequence_mean = sum((rate for _, rate in rows), Fraction()) / len(rows)
        hits = attempts = 0
        for sequence, _ in rows:
            following = [sequence[i + 1] for i in range(2) if sequence[i] == "О"]
            hits += following.count("О")
            attempts += len(following)
        pooled = Fraction(hits, attempts)
        _require(
            sequence_mean == _fraction(check["expected_sequence_mean"], f"{ident}.expected_sequence_mean")
            and pooled == _fraction(check["expected_pooled"], f"{ident}.expected_pooled"),
            f"{ident}: coin estimator calculation is wrong",
        )
        return {"id": ident, "ok": True, "sequence_mean": str(sequence_mean), "pooled": str(pooled)}
    raise ValueError(f"{ident}: unsupported math check kind; supply a supported check or a reviewed proof")


def _index(items: object, name: str, *, key: str = "id") -> dict[str, dict]:
    _require(isinstance(items, list), f"{name}: expected a list")
    indexed = {}
    for item in items:
        _require(isinstance(item, dict), f"{name}: entries must be objects")
        ident = item.get(key)
        _text(ident, f"{name}.{key}")
        _require(ident not in indexed, f"{name}: duplicate {key} {ident}")
        indexed[ident] = item
    return indexed


def _validate(dossier: dict, scenes, topic, root, expected_scene_file):
    _require(bool(scenes), "Script must contain at least one scene")
    _require(isinstance(dossier, dict), "Review dossier must be a JSON object")
    _require(
        type(dossier.get("schema_version")) is int and dossier["schema_version"] == 1,
        "Unsupported review schema_version",
    )
    _require(dossier.get("topic") == topic, "Review topic does not match requested topic")
    _require(dossier.get("script_sha256") == script_digest(scenes), "Script changed; review the current narration")
    scene_file = dossier.get("scene_file")
    if expected_scene_file is not None:
        _require(scene_file == expected_scene_file, "Reviewed scene_file does not match the topic renderer")
    _require(
        dossier.get("scene_sha256") == hashlib.sha256(_scene_path(root, scene_file).read_bytes()).hexdigest(),
        "Scene visuals changed; review the current scene",
    )
    supporting = dossier.get("supporting_files")
    _require(isinstance(supporting, dict), "supporting_files: expected a file/checksum object")
    expected = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in SUPPORTING_FILES
        if (root / name).is_file()
    }
    _require(supporting == expected, "Supporting math/UI source changed; repeat editorial review")
    pedagogy = dossier.get("pedagogy")
    _require(isinstance(pedagogy, dict), "pedagogy: expected an object")
    _require(
        type(pedagogy.get("audience_age")) is int and pedagogy["audience_age"] == 12,
        "pedagogy.audience_age: this project's target learner is 12",
    )
    for field in ("learning_objective", "challenge", "expected_learning"):
        _text(pedagogy.get(field), f"pedagogy.{field}")
    for field in ("prerequisites", "assumptions", "limitations"):
        _strings(pedagogy.get(field), f"pedagogy.{field}", allow_empty=field == "prerequisites")
    sources = _index(dossier.get("sources"), "sources")
    for source in sources.values():
        _text(source.get("title"), "source.title")
        _text(source.get("locator"), "source.locator")
        _require(source.get("kind") in ("primary", "textbook"), "source.kind: primary or textbook required")
        url = urlparse(source.get("url", ""))
        _require(url.scheme in ("https", "http") and bool(url.hostname), "source.url: valid HTTP(S) URL required")
    checks = _index(dossier.get("math_checks"), "math_checks")
    math_results = [_math_check(check) for check in checks.values()]
    scene_index = _index(list(scenes), "script")
    coverage = _index(dossier.get("scene_reviews"), "scene_reviews", key="scene_id")
    _require(set(coverage) == set(scene_index), "scene_reviews must cover every scene exactly once")
    for scene_id, entry in coverage.items():
        _text(entry.get("teaching_role"), f"{scene_id}.teaching_role")
        claims = entry.get("claims")
        _require(isinstance(claims, list) and bool(claims), f"{scene_id}: claims must not be empty")
        for claim in claims:
            _require(isinstance(claim, dict), f"{scene_id}: claim must be an object")
            for field in ("statement", "reasoning", "script_quote"):
                _text(claim.get(field), f"{scene_id}.claim.{field}")
            _require(
                claim["script_quote"] in scene_index[scene_id]["text"], f"{scene_id}: claim quote not found in script"
            )
            _require(claim.get("kind") in ("empirical", "mathematical", "model"), f"{scene_id}: invalid claim kind")
            for field, index in (("source_ids", sources), ("math_check_ids", checks)):
                _strings(claim.get(field), f"{scene_id}.{field}", allow_empty=True)
                _require(set(claim[field]) <= set(index), f"{scene_id}: unknown {field} reference")
            if claim["kind"] == "empirical":
                _require(
                    any(sources[ident]["kind"] == "primary" for ident in claim["source_ids"]),
                    f"{scene_id}: empirical claim requires a primary source",
                )
            if claim["kind"] == "mathematical" and not claim["math_check_ids"]:
                _text(claim.get("proof"), f"{scene_id}: mathematical claim requires a check or explicit proof")
    _require(dossier.get("unresolved_issues") == [], "Resolve all editorial issues before production")
    reviews = dossier.get("reviews")
    _require(isinstance(reviews, dict), "reviews: expected scientific and pedagogical review objects")
    for discipline, criteria in REVIEW_CRITERIA.items():
        review = reviews.get(discipline)
        _require(isinstance(review, dict), f"Missing {discipline} review")
        _require(review.get("verdict") == "approved", f"{discipline} review is not approved")
        _text(review.get("reviewer"), f"{discipline}.reviewer")
        _require(review.get("reviewer_type") in ("human", "ai"), f"{discipline}: declare human or ai reviewer type")
        reviewed_at = date.fromisoformat(review.get("reviewed_at", ""))
        _require(reviewed_at <= date.today(), f"{discipline}: review date is in the future")
        _require(
            review.get("dossier_sha256") == dossier_digest(dossier), f"{discipline} approval is stale; dossier changed"
        )
        results = review.get("criteria")
        _require(isinstance(results, dict), f"{discipline}.criteria: expected an object")
        for criterion in criteria:
            result = results.get(criterion)
            _require(isinstance(result, dict) and result.get("passed") is True, f"{discipline}.{criterion}: not passed")
            _text(result.get("rationale"), f"{discipline}.{criterion}.rationale")
    return math_results


def check_content_review(
    scenes: Sequence[dict[str, str]], video_dir_name: str, root: Path, *, expected_scene_file: str | None = None
) -> dict:
    topic = Path(video_dir_name).name.removeprefix("video_")
    report = {
        "topic": topic,
        "ok": False,
        "issues": [],
        "math_checks": [],
        "review_path": str(root / "content_reviews" / f"{topic}.json"),
        "scope": "Recorded editorial judgments and deterministic checks; not independent fact verification.",
    }
    try:
        _require(bool(re.fullmatch(r"[a-zA-Z0-9_-]+", topic)), "Invalid review topic name")
        path = Path(report["review_path"])
        _require(path.is_file(), f"Missing content review: {path}; run math-books review {topic} --init")
        dossier = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_keys,
            parse_float=_finite_float,
            parse_constant=_reject_constant,
        )
        if isinstance(dossier, dict):
            # Reviewers need the current digest even while a dossier is still pending.
            report["dossier_sha256"] = dossier_digest(dossier)
        report["math_checks"] = _validate(dossier, scenes, topic, root, expected_scene_file)
        report["reviewers"] = {
            key: {field: dossier["reviews"][key][field] for field in ("reviewer", "reviewer_type", "reviewed_at")}
            for key in REVIEW_CRITERIA
        }
        report["dossier_sha256"] = dossier_digest(dossier)
        report["ok"] = True
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ZeroDivisionError, OverflowError) as error:
        report["issues"].append(str(error))
    return report


def require_content_review(
    scenes: Sequence[dict[str, str]], video_dir_name: str, root: Path, *, expected_scene_file: str | None = None
) -> dict:
    report = check_content_review(scenes, video_dir_name, root, expected_scene_file=expected_scene_file)
    if not report["ok"]:
        raise ValueError("Content review blocked production: " + "; ".join(report["issues"]))
    return report
