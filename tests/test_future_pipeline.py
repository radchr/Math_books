"""New lessons exercise real gates; external speech/render boundaries are synthetic."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from review_fixtures import approve_fixture
from test_lessons import lesson_fixture, write_lesson
from test_uk_tts import _write_pcm_wav

from math_books.cli import build_parser, main
from math_books.content_review import check_content_review, make_review_template, review_path
from math_books.lessons import load_lesson
from math_books.tts_engine import generate_topic_tts
from math_books.video_builder import (
    build_video,
    get_topic,
    project_root,
    render_fingerprint,
    validate_topic_audio,
    verify_topic_video,
)


class TestFuturePipeline(unittest.TestCase):
    def prepare(self, root, language, *, cued=False):
        data = lesson_fixture()
        if cued:
            data["scenes"][0]["cues"] = [
                {
                    "id": "answer_reveal",
                    "target": "formula",
                    "anchor": "start",
                    "occurrence": 1,
                    "phrases": {"uk": "дорівнює", "ru": "равняется", "en": "equals"},
                }
            ]
        write_lesson(root, data)
        for name in (
            "localized_lesson_scene.py",
            "video_ui.py",
            "lesson_math.py",
            "languages.py",
            "lessons.py",
            "cue_timeline.py",
        ):
            target = root / "src/math_books" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(project_root() / "src/math_books" / name, target)
        topic = get_topic("language_demo", language, root)
        scenes = load_lesson(root, topic.key, language)
        dossier = make_review_template(topic.key, scenes, topic.scene_file, root, language=language)
        dossier["pedagogy"].update(
            learning_objective="Synthetic integration test only.",
            assumptions=["Synthetic data"],
            limitations=["Not a production review"],
            challenge="Add the numbers.",
            expected_learning="Understand addition.",
        )
        dossier["scene_reviews"][0].update(teaching_role="Synthetic test")
        dossier["scene_reviews"][0]["claims"][0].update(
            statement="Synthetic test claim.",
            kind="mathematical",
            reasoning="Test only.",
            proof="One plus one equals two by elementary arithmetic.",
        )
        approve_fixture(dossier)
        path = review_path(root, topic.key, language)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dossier))
        return topic, scenes

    def fake_synthesis(self, text, output, *args, **kwargs):
        _write_pcm_wav(output, duration_s=2.0)
        return 2.0

    def transcription(self, text):
        words = text.split()
        return [
            {
                "start": 0.0,
                "end": 1.5,
                "text": text,
                "words": [
                    {"word": word, "start": i * 1.5 / len(words), "end": (i + 1) * 1.5 / len(words)}
                    for i, word in enumerate(words)
                ],
            }
        ]

    def test_cue_log_is_required_and_tampering_blocks_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topic, scenes = self.prepare(root, "en", cued=True)
            with (
                patch.dict("os.environ", {"GEMINI_API_KEY": "synthetic-test"}),
                patch("math_books.tts_engine.synthesize_gemini_tts", side_effect=self.fake_synthesis),
                patch("math_books.voiceover_qa.transcribe_audio", return_value=self.transcription(scenes[0]["text"])),
            ):
                generate_topic_tts(scenes, topic.video_dir, root=root, language="en", delay_s=0)
            silent = root / topic.video_dir / "media/language_demo_silent.mp4"
            silent.parent.mkdir()
            silent.write_bytes(b"test silent render")

            def render(*args, **kwargs):
                env = kwargs["env"]
                events = json.loads(Path(env["MATH_BOOKS_EVENT_TIMELINE_PATH"]).read_text())
                records = [
                    {
                        "scene_id": scene,
                        "id": event["id"],
                        "target": event["target"],
                        "frame": event["frame"],
                        "global_frame": event["global_frame"],
                    }
                    for scene, values in events.items()
                    for event in values
                ]
                Path(env["MATH_BOOKS_EVENT_LOG_PATH"]).write_text(json.dumps(records))

            def mux(_silent, _wav, output):
                output.write_bytes(b"test cued final output")

            with (
                patch("math_books.video_builder.subprocess.run", side_effect=render),
                patch("math_books.video_builder.mux_audio_video", side_effect=mux),
                patch("math_books.video_builder.verify_video", return_value={"ok": True, "issues": []}),
            ):
                self.assertTrue(build_video(topic.key, root=root, language="en")["ok"])
                self.assertTrue(verify_topic_video(topic, root)["ok"])
                path = silent.with_suffix(".events.json")
                log = json.loads(path.read_text())
                log[0]["frame"] += 10
                path.write_text(json.dumps(log))
                with self.assertRaisesRegex(ValueError, "cue"):
                    build_video(topic.key, root=root, language="en", skip_render=True)
                output = root / topic.video_dir / topic.output_name
                provenance_path = output.with_suffix(".build.json")
                provenance = json.loads(provenance_path.read_text())
                provenance["events"] = log
                provenance_path.write_text(json.dumps(provenance))
                self.assertFalse(verify_topic_video(topic, root)["ok"])

    def test_three_languages_pass_real_provenance_and_qa_gates_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outputs = []
            for language in ("uk", "ru", "en"):
                topic, scenes = self.prepare(root, language)
                # Gemini here is a deterministic boundary stub; actual normalization and receipts run.
                with (
                    patch.dict("os.environ", {"GEMINI_API_KEY": "synthetic-test"}),
                    patch("math_books.tts_engine.synthesize_gemini_tts", side_effect=self.fake_synthesis),
                    patch(
                        "math_books.voiceover_qa.transcribe_audio", return_value=self.transcription(scenes[0]["text"])
                    ),
                ):
                    manifest = generate_topic_tts(
                        scenes, topic.video_dir, root=root, language=language, pin_model=True, delay_s=0
                    )
                    self.assertEqual(manifest, validate_topic_audio(topic, root))
                signature = render_fingerprint(topic, root, manifest)
                self.assertTrue(signature)
                silent = root / topic.video_dir / "media/silent.mp4"
                silent.parent.mkdir()
                silent.write_bytes(b"synthetic silent render")

                def mux(_silent, _wav, output):
                    output.write_bytes(b"synthetic final output")

                with (
                    patch("math_books.video_builder.render_silent_video", return_value=silent),
                    patch("math_books.video_builder.mux_audio_video", side_effect=mux),
                    patch("math_books.video_builder.verify_video", return_value={"ok": True, "issues": []}),
                ):
                    self.assertTrue(build_video(topic.key, root=root, language=language)["ok"])
                    self.assertTrue(verify_topic_video(topic, root)["ok"])
                outputs.append(root / topic.video_dir / topic.output_name)
                # A changed word timestamp changes render identity even with identical WAV duration.
                receipt = next((root / topic.video_dir / "audio/qa").glob("*.json"))
                evidence = json.loads(receipt.read_text())
                evidence["segments"][0]["words"][0]["start"] = 0.1
                receipt.write_text(json.dumps(evidence))
                self.assertNotEqual(signature, render_fingerprint(topic, root, manifest))
            self.assertEqual(len(set(outputs)), 3)
            self.assertTrue(all(p.is_file() for p in outputs))

    def test_review_language_and_caption_changes_block_without_approval_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topic, scenes = self.prepare(root, "uk")
            self.assertTrue(check_content_review(scenes, topic.video_dir, root, language="uk")["ok"])
            wrong = check_content_review(scenes, topic.video_dir, root, language="en")
            self.assertFalse(wrong["ok"])

    def test_direct_tts_rejects_wrong_language_output_path_before_synthesis(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topic, scenes = self.prepare(root, "ru")
            with patch("math_books.tts_engine.synthesize_gemini_tts") as synth:
                with self.assertRaisesRegex(ValueError, "path|directory"):
                    generate_topic_tts(scenes, "videos/video_language_demo/uk", root=root, language="ru")
                synth.assert_not_called()

    def test_direct_tts_requires_canonical_renderer_and_automatically_pins_future(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topic, scenes = self.prepare(root, "ru")
            path = review_path(root, topic.key, "ru")
            dossier = json.loads(path.read_text())
            (root / "other_scene.py").write_text("# wrong reviewed renderer")
            import hashlib

            dossier["scene_file"] = "other_scene.py"
            dossier["scene_sha256"] = hashlib.sha256((root / "other_scene.py").read_bytes()).hexdigest()
            approve_fixture(dossier)
            path.write_text(json.dumps(dossier))
            with self.assertRaisesRegex(ValueError, "renderer"):
                generate_topic_tts(scenes, topic.video_dir, root=root, language="ru")

    def test_cli_exposes_languages_and_refuses_old_topic_translation(self):
        for command in ("list", "review", "tts", "build", "verify-audio", "verify"):
            args = [command] + ([] if command == "list" else ["language_demo"]) + ["--lang", "uk"]
            self.assertEqual(build_parser().parse_args(args).lang, "uk")
        with self.assertRaises(SystemExit) as error:
            main(["build", "buzzer", "--lang", "en"])
        self.assertEqual(error.exception.code, 1)

    def test_build_freezes_one_timing_snapshot_for_hash_and_actual_renderer(self):
        from math_books.voiceover_qa import timing_snapshot

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topic, scenes = self.prepare(root, "en")
            with (
                patch.dict("os.environ", {"GEMINI_API_KEY": "synthetic-test"}),
                patch("math_books.tts_engine.synthesize_gemini_tts", side_effect=self.fake_synthesis),
                patch("math_books.voiceover_qa.transcribe_audio", return_value=self.transcription(scenes[0]["text"])),
            ):
                generate_topic_tts(scenes, topic.video_dir, root=root, language="en", delay_s=0)
            silent = root / topic.video_dir / "media/language_demo_silent.mp4"
            silent.parent.mkdir()
            silent.write_bytes(b"test silent render")

            def mux(_silent, _wav, output):
                output.write_bytes(b"test final output")

            with (
                patch("math_books.video_builder.timing_snapshot", wraps=timing_snapshot) as snapshot,
                patch("math_books.video_builder.subprocess.run") as renderer,
                patch("math_books.video_builder.mux_audio_video", side_effect=mux),
                patch("math_books.video_builder.verify_video", return_value={"ok": True, "issues": []}),
            ):
                self.assertTrue(build_video(topic.key, root=root, language="en")["ok"])
                self.assertEqual(snapshot.call_count, 1)
                self.assertIn("MATH_BOOKS_TIMING_SNAPSHOT_PATH", renderer.call_args.kwargs["env"])
