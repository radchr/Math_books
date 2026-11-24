"""Explicit editorial fixtures for tests; never a production approval shortcut."""

import json
from pathlib import Path

from math_books import content_review


def approve_fixture(dossier):
    for discipline, criteria in content_review.REVIEW_CRITERIA.items():
        dossier["reviews"][discipline] = {
            "reviewer": "Synthetic test reviewer",
            "reviewer_type": "ai",
            "reviewed_at": "2026-11-24",
            "verdict": "approved",
            "dossier_sha256": content_review.dossier_digest(dossier),
            "criteria": {
                criterion: {"passed": True, "rationale": "Checked in synthetic test fixture."} for criterion in criteria
            },
        }
    return dossier


def write_review_fixture(root: Path, scenes, video_dir="video_test", *, scene_file="synthetic_scene.py"):
    scene = root / scene_file
    scene.parent.mkdir(parents=True, exist_ok=True)
    if not scene.exists():
        scene.write_text("# Synthetic visual scenario\n")
    topic = Path(video_dir).name.removeprefix("video_")
    dossier = content_review.make_review_template(topic, scenes, scene_file, root)
    dossier["pedagogy"] = {
        "audience_age": 12,
        "learning_objective": "Compare expected scores.",
        "prerequisites": ["Fractions and percentages"],
        "assumptions": ["Fixed independent probabilities"],
        "limitations": ["Expectation does not guarantee a result"],
        "challenge": "Compute expected points for a three-point shot.",
        "expected_learning": "Explain why 35 percent times three gives 1.05 expected points.",
    }
    dossier["math_checks"] = [
        {"id": "score", "kind": "expected_points", "probability": "0.35", "points": 3, "expected": "1.05"}
    ]
    dossier["scene_reviews"] = [
        {
            "scene_id": s["id"],
            "teaching_role": "Develop the example.",
            "claims": [
                {
                    "statement": "A three-point shot at 35 percent yields 1.05 expected points.",
                    "script_quote": s["text"],
                    "kind": "mathematical",
                    "source_ids": [],
                    "math_check_ids": ["score"],
                    "reasoning": "Expected score equals probability times points.",
                }
            ],
        }
        for s in scenes
    ]
    approve_fixture(dossier)
    path = root / "content_reviews" / f"{topic}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(dossier, ensure_ascii=False, indent=2))
    return path, dossier


def generate_reviewed_tts(scenes, video_dir_name, **kwargs):
    from unittest.mock import patch

    from math_books.tts_engine import generate_topic_tts

    write_review_fixture(kwargs["root"], scenes, video_dir_name)
    mapping = {s["id"]: s["text"] for s in scenes}

    def fake_transcribe(wav_path, _cache_dir):
        stem = wav_path.stem.split("-")[0]
        return [{"start": 0.0, "end": 1.0, "text": mapping.get(stem, scenes[0]["text"])}]

    with patch("math_books.voiceover_qa.transcribe_audio", side_effect=fake_transcribe):
        return generate_topic_tts(scenes, video_dir_name, **kwargs)
