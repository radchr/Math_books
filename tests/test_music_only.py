"""Tests for music_only mode: schema, timed cues, mandatory editorial review, music provenance, and status."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from math_books.content_review import check_content_review, dossier_digest, make_review_template
from math_books.cue_timeline import timed_event_timeline
from math_books.lessons import load_lesson, validate_lesson_data
from math_books.music_tracks import (
    generate_music_track,
    import_music_track,
    query_music_catalog,
    render_music_bed,
    resolve_music_track,
)
from math_books.topics import get_topic, project_root
from math_books.video_builder import build_video, topic_status_summary, verify_topic_video


def _music_lesson(topic: str = "echo_test") -> dict:
    return {
        "schema_version": 1,
        "topic": topic,
        "domain": "core",
        "theme": "science_lab",
        "audio_mode": "music_only",
        "music_track": "calm_science",
        "scenes": [
            {
                "id": "01_wave",
                "duration_s": 4.0,
                "formula": r"d = \frac{v \cdot t}{2}",
                "visual": {
                    "template": "image_stage",
                    "params": {"image": "assets/diagrams/echo_wave.svg", "caption_label": "cap"},
                },
                "cues": [{"id": "show_formula", "target": "formula", "at_s": 1.5}],
                "translations": {
                    "uk": {
                        "title": "Луна як рулетка",
                        "body": "Звук летить до скелі і повертається назад.",
                        "labels": {"cap": "Подвійний шлях 2d"},
                    },
                    "ru": {
                        "title": "Эхо как рулетка",
                        "body": "Звук летит к скале и возвращается назад.",
                        "labels": {"cap": "Двойной путь 2d"},
                    },
                    "en": {
                        "title": "Echo as a Tape Measure",
                        "body": "Sound travels to the cliff and bounces back.",
                        "labels": {"cap": "Round-trip path 2d"},
                    },
                },
            }
        ],
    }


class TestMusicOnlyMode(unittest.TestCase):
    def test_music_only_validation_timed_cues_and_onscreen_quote(self):
        lesson = _music_lesson()
        scenes = validate_lesson_data(lesson, "echo_test", "uk")
        self.assertEqual(scenes[0]["audio_mode"], "music_only")
        self.assertEqual(scenes[0]["music_track"], "calm_science")
        self.assertEqual(scenes[0]["duration_s"], 4.0)
        self.assertIn("Луна як рулетка", scenes[0]["text"])
        self.assertIn("Подвійний шлях 2d", scenes[0]["text"])

        timeline = timed_event_timeline(scenes)
        self.assertEqual(timeline["01_wave"][0]["frame"], 45)
        self.assertEqual(timeline["01_wave"][0]["target"], "formula")

        bad_cue = json.loads(json.dumps(lesson))
        bad_cue["scenes"][0]["cues"][0]["at_s"] = 4.5
        with self.assertRaisesRegex(ValueError, "must be inside"):
            validate_lesson_data(bad_cue, "echo_test", "uk")

    def test_music_track_registry_and_exact_duration_render(self):
        root = project_root()
        track_path, meta = resolve_music_track(root, "calm_science")
        self.assertEqual(meta["license"], "CC0-1.0")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bed.wav"
            dur = render_music_bed(track_path, out, 3.5)
            self.assertAlmostEqual(dur, 3.5, places=2)

    def test_music_only_enforces_mandatory_review_and_builds_with_provenance(self):
        src_root = project_root()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(src_root / "assets" / "music", root / "assets" / "music")
            (root / "src/math_books").mkdir(parents=True)
            for name in (
                "localized_lesson_scene.py",
                "video_ui.py",
                "lesson_math.py",
                "languages.py",
                "lessons.py",
                "cue_timeline.py",
                "music_tracks.py",
            ):
                shutil.copy2(src_root / "src/math_books" / name, root / "src/math_books" / name)
            (root / "content/lessons").mkdir(parents=True)
            lesson = _music_lesson("echo_test")
            (root / "content/lessons/echo_test.json").write_text(json.dumps(lesson), encoding="utf-8")

            # Unreviewed music_only topic MUST be blocked before build!
            with self.assertRaisesRegex(ValueError, "Content review blocked production"):
                build_video("echo_test", root=root, language="uk")

            # Complete valid editorial review matching on-screen text
            scenes = load_lesson(root, "echo_test", "uk")
            dossier = make_review_template(
                "echo_test", scenes, "src/math_books/localized_lesson_scene.py", root, language="uk"
            )
            dossier["pedagogy"].update(
                audience_age={"min": 11, "max": 14},
                learning_objective="Understand why echo distance divides round-trip travel by 2.",
                assumptions=["Speed of sound is roughly 340 m/s in air."],
                limitations=["Temperature and wind change sound speed."],
                challenge="Compute distance when echo returns in 2 seconds.",
                expected_learning="Divide v * t by 2.",
            )
            dossier["sources"] = [
                {
                    "id": "perelman",
                    "kind": "textbook",
                    "title": "Physics for Entertainment",
                    "locator": "Sound and echo chapter",
                    "url": "https://archive.org/details/physicsforentert035428mbp",
                }
            ]
            dossier["scene_reviews"][0].update(
                teaching_role="Show outgoing and returning sound wave.",
                claims=[
                    {
                        "statement": "An echo travels to the reflecting surface and back, covering 2d.",
                        "script_quote": "Звук летить до скелі і повертається назад.",
                        "kind": "model",
                        "source_ids": ["perelman"],
                        "math_check_ids": [],
                        "reasoning": "Round-trip wave propagation covers distance d twice.",
                    }
                ],
            )
            digest = dossier_digest(dossier)
            for disc in ("scientific", "pedagogical"):
                dossier["reviews"][disc].update(
                    reviewer="Test AI",
                    reviewer_type="ai",
                    reviewed_at="2026-11-25",
                    verdict="approved",
                    dossier_sha256=digest,
                )
                for crit in dossier["reviews"][disc]["criteria"].values():
                    crit.update(passed=True, rationale="Verified in unit test.")
            rev_path = root / "content_reviews/uk/echo_test.json"
            rev_path.parent.mkdir(parents=True)
            rev_path.write_text(json.dumps(dossier), encoding="utf-8")
            self.assertTrue(
                check_content_review(
                    scenes,
                    "videos/video_echo_test/uk",
                    root,
                    expected_scene_file="src/math_books/localized_lesson_scene.py",
                    language="uk",
                )["ok"]
            )

            topic = get_topic("echo_test", "uk", root)
            summary = topic_status_summary(topic, root)
            self.assertEqual(summary["review"], "approved")
            self.assertEqual(summary["audio"], "music_only")
            self.assertEqual(summary["video"], "missing")

            silent = root / topic.video_dir / "media/echo_test_silent.mp4"
            silent.parent.mkdir(parents=True)
            silent.write_bytes(b"synthetic silent video")

            def fake_render(*_args, **kwargs):
                env = kwargs["env"]
                events = json.loads(Path(env["MATH_BOOKS_EVENT_TIMELINE_PATH"]).read_text())
                records = [
                    {
                        "scene_id": sid,
                        "id": ev["id"],
                        "target": ev["target"],
                        "frame": ev["frame"],
                        "global_frame": ev["global_frame"],
                    }
                    for sid, vals in events.items()
                    for ev in vals
                ]
                Path(env["MATH_BOOKS_EVENT_LOG_PATH"]).write_text(json.dumps(records))

            def fake_mux(_s, _w, out):
                out.write_bytes(b"synthetic music_only mp4")

            with (
                patch("math_books.video_builder.subprocess.run", side_effect=fake_render),
                patch("math_books.video_builder.render_music_bed", return_value=4.3),
                patch("math_books.video_builder.mux_audio_video", side_effect=fake_mux),
                patch("math_books.video_builder.verify_video", return_value={"ok": True, "issues": []}),
            ):
                built = build_video("echo_test", root=root, language="uk")
                self.assertTrue(built["ok"])
                verified = verify_topic_video(topic, root)
                self.assertTrue(verified["ok"], verified["issues"])
                post_summary = topic_status_summary(topic, root)
                self.assertEqual(post_summary["audio"], "music_only")
                self.assertEqual(post_summary["video"], "unverified")

    def test_music_bank_procedural_generation_import_and_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry = generate_music_track(
                root,
                track_id="test_beat",
                backend="procedural",
                preset="energetic",
                bpm=120.0,
                duration_s=8.0,
                mood="energetic",
                tags=["upbeat", "test"],
            )
            self.assertEqual(entry["source"], "procedural")
            self.assertEqual(entry["license"], "CC0-1.0")
            track_path, meta = resolve_music_track(root, "test_beat")
            self.assertTrue(track_path.is_file())
            self.assertEqual(meta["mood"], "energetic")

            # Duplicate ID without overwrite is rejected
            with self.assertRaises(FileExistsError):
                generate_music_track(root, track_id="test_beat", backend="procedural", duration_s=8.0)

            # Import an external file into the same reusable bank
            imported = import_music_track(
                root,
                track_path,
                track_id="imported_track",
                title="Imported CC0 Track",
                license_str="CC0-1.0",
                author="Liborio Conti",
                mood="calm",
                tags=["ambient", "cc0"],
            )
            self.assertEqual(imported["source"], "imported")
            self.assertEqual([t["id"] for t in query_music_catalog(root, mood="calm")], ["imported_track"])
            self.assertEqual([t["id"] for t in query_music_catalog(root, tag="upbeat")], ["test_beat"])
