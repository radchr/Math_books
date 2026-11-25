"""Fast status inspection must not verify media, write receipts or create locks."""

import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from math_books.tts_engine import audio_lock
from math_books.video_builder import VIDEO_TOPICS, topic_status_summary


class TestReadonlyStatus(unittest.TestCase):
    def setUp(self):
        self.topic = VIDEO_TOPICS["buzzer"]

    def make_present(self, root):
        folder = root / self.topic.video_dir
        audio = folder / "audio"
        audio.mkdir(parents=True)
        scenes = importlib.import_module(self.topic.tts_module).SCENES
        manifest = [
            {
                **scene,
                "wav": f"{scene['id']}.wav",
                "duration": 1,
                "model": "test",
                "voice": "test",
                "fingerprint": "unverified",
                "wav_sha256": "unverified",
            }
            for scene in scenes
        ]
        for item in manifest:
            # Deliberately invalid bytes: presence cannot certify audio/media quality.
            (audio / item["wav"]).write_bytes(b"not a WAV")
        (audio / "manifest.json").write_text(json.dumps(manifest))
        video = folder / self.topic.output_name
        video.write_bytes(b"not an MP4")
        video.with_suffix(".build.json").write_text(
            json.dumps(
                {
                    "fingerprint": "unverified",
                    "audio_sha256": ["unverified"] * len(scenes),
                    "video_sha256": "unverified",
                }
            )
        )

    def snapshot(self, root):
        return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    def test_present_media_does_not_launch_verification_or_create_any_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_present(root)
            before = self.snapshot(root)
            with (
                patch("math_books.video_builder.check_content_review", return_value={"ok": True}),
                patch("math_books.video_builder.validate_topic_audio", side_effect=AssertionError("full audio QA")),
                patch("math_books.video_builder.verify_topic_video", side_effect=AssertionError("full video QA")),
                patch("math_books.video_builder.subprocess.run", side_effect=AssertionError("external process")),
                patch.object(Path, "read_bytes", side_effect=AssertionError("media hashing")),
            ):
                summary = topic_status_summary(self.topic, root)
            self.assertEqual(summary["audio"], "unverified")
            self.assertEqual(summary["video"], "unverified")
            self.assertFalse(summary["ready"])
            self.assertEqual(self.snapshot(root), before)

    def test_missing_audio_does_not_create_directory_or_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("math_books.video_builder.check_content_review", return_value={"ok": True}):
                summary = topic_status_summary(self.topic, root)
            self.assertEqual(summary["audio"], "missing")
            self.assertEqual(summary["video"], "missing")
            self.assertEqual(list(root.rglob("*")), [])

    def test_busy_existing_pipeline_is_reported_without_reading_partial_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_present(root)
            audio = root / self.topic.video_dir / "audio"
            (audio / "manifest.json").write_text("partial JSON")
            with audio_lock(audio):
                before = self.snapshot(root)
                with patch("math_books.video_builder.check_content_review", return_value={"ok": True}):
                    summary = topic_status_summary(self.topic, root)
                self.assertEqual(summary["audio"], "busy")
                self.assertEqual(summary["video"], "busy")
                self.assertFalse(summary["ready"])
                self.assertEqual(self.snapshot(root), before)

    def test_invalid_manifest_and_build_sidecar_are_stale_without_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_present(root)
            folder = root / self.topic.video_dir
            (folder / "audio/manifest.json").write_text("{}")
            with patch("math_books.video_builder.check_content_review", return_value={"ok": True}):
                summary = topic_status_summary(self.topic, root)
            self.assertEqual(summary["audio"], "stale")
            self.assertEqual(summary["video"], "stale")
