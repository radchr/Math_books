"""Legacy optional cues only consume current, byte-bound, validated ASR evidence."""

import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from math_books.video_ui import VerticalShortScene
from math_books.voiceover_qa import verify_clip


class TestTrustedWordTiming(unittest.TestCase):
    def fixture(self, root: Path, language: str, text: str, words: list[dict]):
        audio_dir = root / "audio"
        audio_dir.mkdir()
        wav = audio_dir / "clip.wav"
        with wave.open(str(wav), "wb") as out:
            out.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            out.writeframes(b"\0\0" * 24000 * 3)
        segments = [{"start": 0.0, "end": 2.0, "text": text, "words": words}]
        with patch("math_books.voiceover_qa.transcribe_audio", return_value=segments):
            report = verify_clip(wav, text, audio_dir / "qa", root / "cache", language=language)
        self.assertTrue(report["ok"])
        item = {"id": "scene", "wav": "clip.wav", "text": text, "language": language, "duration": 3.0}
        manifest = audio_dir / "manifest.json"
        manifest.write_text(json.dumps([item]))
        scene = VerticalShortScene.__new__(VerticalShortScene)
        scene._manifest_path = manifest
        scene._manifest_items = {"scene": item}
        return scene, Path(report["receipt_path"])

    def test_exact_match_does_not_accept_prefix_and_does_not_decode_audio(self):
        with tempfile.TemporaryDirectory() as temporary:
            scene, _ = self.fixture(
                Path(temporary),
                "ru",
                "Дальше. Да.",
                [{"word": " Дальше.", "start": 0.2, "end": 0.6}, {"word": " Да.", "start": 1.2, "end": 1.4}],
            )
            with patch("math_books.voiceover_qa.transcribe_audio", side_effect=AssertionError("ASR is forbidden")):
                self.assertEqual(scene.word_timestamp("scene", "да", fallback=2.0), 1.2)
                self.assertEqual(scene.word_timestamp("scene", "да", fallback=2.0, after_s=1.3), 2.0)

    def test_unicode_letters_match_and_newer_invalid_receipt_is_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            scene, receipt = self.fixture(
                Path(temporary),
                "uk",
                "Її є ґрунт.",
                [
                    {"word": "Її", "start": 0.2, "end": 0.4},
                    {"word": "є", "start": 0.5, "end": 0.6},
                    {"word": "ґрунт.", "start": 1.1, "end": 1.5},
                ],
            )
            wrong_policy = receipt.with_name(receipt.name.rsplit("-", 1)[0] + "-wrongpolicy.json")
            wrong_policy.write_text(json.dumps({"segments": [{"words": [{"word": "є", "start": 2.0}]}]}))
            self.assertEqual(scene.word_timestamp("scene", "є", fallback=2.0), 0.5)
            self.assertEqual(scene.word_timestamp("scene", "ґрунт", fallback=2.0), 1.1)

    def test_failed_tampered_receipt_or_changed_wav_never_supplies_timestamp(self):
        for tamper in ("policy", "transcript", "wav"):
            with self.subTest(tamper=tamper), tempfile.TemporaryDirectory() as temporary:
                scene, receipt = self.fixture(
                    Path(temporary),
                    "en",
                    "Answer now.",
                    [{"word": "Answer", "start": 0.5, "end": 0.9}, {"word": "now.", "start": 1.0, "end": 1.4}],
                )
                data = json.loads(receipt.read_text())
                if tamper == "policy":
                    data["policy_sha256"] = "wrong"
                elif tamper == "transcript":
                    data["transcript"] = "Different words."
                else:
                    (Path(temporary) / "audio/clip.wav").write_bytes(b"changed")
                receipt.write_text(json.dumps(data))
                self.assertEqual(scene.word_timestamp("scene", "answer", fallback=2.0), 2.0)
