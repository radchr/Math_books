"""ASR evidence must stay bound to the explicit narration language."""

import json
import os
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from math_books import voiceover_qa


class TestMultilingualVoiceover(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.wav = self.root / "clip.wav"
        with wave.open(str(self.wav), "wb") as audio:
            audio.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            audio.writeframes(b"\x01\x01" * 24000)

    def test_language_model_defaults_and_environment_precedence(self):
        with patch.dict(os.environ, {}, clear=True):
            for language, model in [("uk", "small"), ("ru", "base"), ("en", "base")]:
                self.assertEqual(voiceover_qa.policy_profile(language=language)["model"], model)
            with patch.dict(os.environ, {"MATH_BOOKS_ASR_MODEL": "medium", "MATH_BOOKS_ASR_MODEL_UK": "large-v3"}):
                self.assertEqual(voiceover_qa.asr_model("uk"), "large-v3")
                self.assertEqual(voiceover_qa.asr_model("en"), "medium")

    def test_model_change_invalidates_cached_receipt(self):
        segments = [{"start": 0, "end": 1, "text": "Basketball"}]
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("math_books.voiceover_qa.transcribe_audio", return_value=segments),
        ):
            first = voiceover_qa.verify_clip(self.wav, "Basketball", self.root / "qa", self.root, language="en")
            with patch.dict(os.environ, {"MATH_BOOKS_ASR_MODEL_EN": "small"}):
                changed = voiceover_qa.verify_clip(self.wav, "Basketball", self.root / "qa", self.root, language="en")
        self.assertFalse(changed["cached"])
        self.assertNotEqual(first["receipt_path"], changed["receipt_path"])

    def test_invalid_or_english_only_models_are_rejected_before_backend(self):
        for language, model in [("en", "../other-model"), ("uk", "base.en"), ("ru", "small.en"), ("en", "unknown")]:
            with (
                self.subTest(language=language, model=model),
                patch.dict(os.environ, {"MATH_BOOKS_ASR_MODEL": model}, clear=True),
                patch("math_books.voiceover_qa.subprocess.run", side_effect=AssertionError("no backend calls")),
                self.assertRaises(ValueError),
            ):
                voiceover_qa.transcribe_audio(self.wav, self.root, language=language)

    def test_selected_model_is_loaded_for_decoding(self):
        def recognizer(cache, model_name="base"):
            return SimpleNamespace(
                transcribe=lambda samples, **kwargs: (
                    iter([SimpleNamespace(start=0, end=1, text=model_name, words=[])]),
                    None,
                )
            )

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("math_books.voiceover_qa.subprocess.run", return_value=SimpleNamespace(stdout=b"\x00" * 4)),
            patch("math_books.voiceover_qa._recognizer", side_effect=recognizer),
        ):
            self.assertEqual(voiceover_qa.transcribe_audio(self.wav, self.root, language="uk")[0]["text"], "small")
            self.assertEqual(voiceover_qa.transcribe_audio(self.wav, self.root)[0]["text"], "base")
            with patch.dict(os.environ, {"MATH_BOOKS_ASR_MODEL_RU": "medium"}):
                self.assertEqual(voiceover_qa.transcribe_audio(self.wav, self.root)[0]["text"], "medium")

    def test_receipts_do_not_reuse_evidence_across_languages(self):
        text = "Basketball"

        def recognize(path, cache, *, language="ru"):
            return [{"start": 0, "end": 1, "text": text if language == "en" else "wrong"}]

        with patch("math_books.voiceover_qa.transcribe_audio", side_effect=recognize):
            english = voiceover_qa.verify_clip(self.wav, text, self.root / "qa", self.root / "cache", language="en")
            russian = voiceover_qa.verify_clip(self.wav, text, self.root / "qa", self.root / "cache")
            cached = voiceover_qa.verify_clip(self.wav, text, self.root / "qa", self.root / "cache", language="en")
        self.assertTrue(english["ok"])
        self.assertFalse(russian["ok"])
        self.assertTrue(cached["cached"])
        self.assertEqual(english["language"], "en")
        self.assertNotEqual(english["receipt_path"], russian["receipt_path"])

    def test_whisper_decodes_with_requested_language(self):
        class Recognizer:
            def transcribe(self, samples, **options):
                return iter([SimpleNamespace(start=0, end=1, text=options["language"], words=[])]), None

        with (
            patch("math_books.voiceover_qa.subprocess.run", return_value=SimpleNamespace(stdout=b"\x00" * 4)),
            patch("math_books.voiceover_qa._recognizer", return_value=Recognizer()),
        ):
            result = voiceover_qa.transcribe_audio(self.wav, self.root, language="uk")
        self.assertEqual(result[0]["text"], "uk")

    def test_changed_receipt_language_cannot_approve_audio(self):
        segments = [{"start": 0, "end": 1, "text": "Basketball"}]
        with patch("math_books.voiceover_qa.transcribe_audio", return_value=segments):
            first = voiceover_qa.verify_clip(self.wav, "Basketball", self.root / "qa", self.root, language="en")
        path = Path(first["receipt_path"])
        receipt = json.loads(path.read_text())
        receipt["language"] = "uk"
        path.write_text(json.dumps(receipt))
        with patch("math_books.voiceover_qa.transcribe_audio", return_value=[]):
            result = voiceover_qa.verify_clip(self.wav, "Basketball", self.root / "qa", self.root, language="en")
        self.assertFalse(result["ok"])
        self.assertFalse(result["cached"])

    def test_manifest_uses_clip_language_for_comparison_and_receipt(self):
        def recognize(path, cache, *, language="ru"):
            return [{"start": 0, "end": 1, "text": "Basketball" if language == "en" else "wrong"}]

        manifest = [{"id": "opening", "wav": "clip.wav", "text": "Basketball", "language": "en"}]
        with patch("math_books.voiceover_qa.transcribe_audio", side_effect=recognize):
            result = voiceover_qa.verify_manifest(self.root / "manifest.json", manifest, self.root)
        self.assertTrue(result["ok"])
        self.assertEqual(result["clips"][0]["language"], "en")

    def test_manifest_rejects_unsupported_and_mixed_languages_before_recognition(self):
        for languages in [("fr",), ("uk", "en"), (None, "uk")]:
            with self.subTest(languages=languages):
                manifest = [
                    {
                        "id": str(index),
                        "wav": "clip.wav",
                        "text": "test",
                        **({"language": language} if language else {}),
                    }
                    for index, language in enumerate(languages)
                ]
                # No recognizer/model loading should be needed to reject invalid metadata.
                with patch("math_books.voiceover_qa.transcribe_audio", return_value=[]):
                    report = voiceover_qa.verify_manifest(self.root / "manifest.json", manifest, self.root)
                self.assertFalse(report["ok"])
                self.assertEqual(report["clips"], [])

    def test_unsupported_clip_language_is_rejected_before_audio_io(self):
        with self.assertRaisesRegex(ValueError, "Unsupported language"):
            voiceover_qa.verify_clip(Path("missing.wav"), "test", self.root, self.root, language="fr")

    def test_numeric_normalizer_change_invalidates_evidence(self):
        original = Path.read_bytes

        def changed(path):
            return b"changed numeric policy" if path.name == "multilingual_numbers.py" else original(path)

        segments = [{"start": 0, "end": 1, "text": "Basketball"}]
        with patch("math_books.voiceover_qa.transcribe_audio", return_value=segments):
            first = voiceover_qa.verify_clip(self.wav, "Basketball", self.root / "qa", self.root, language="en")
            with patch.object(Path, "read_bytes", changed):
                second = voiceover_qa.verify_clip(self.wav, "Basketball", self.root / "qa", self.root, language="en")
        self.assertFalse(second["cached"])
        self.assertNotEqual(first["receipt_path"], second["receipt_path"])

    def test_snapshot_requires_current_evidence_without_running_recognition(self):
        manifest = [{"id": "opening", "wav": "clip.wav", "text": "Basketball", "language": "en"}]
        with (
            patch("math_books.voiceover_qa.transcribe_audio", side_effect=AssertionError("must remain offline")),
            self.assertRaises(ValueError),
        ):
            voiceover_qa.timing_snapshot(self.root / "manifest.json", manifest, self.root)

    def test_snapshot_rejects_invalid_word_timing_and_stale_evidence(self):
        manifest = [{"id": "opening", "wav": "clip.wav", "text": "Basketball", "language": "en"}]
        words = [{"start": 0.1, "end": 0.7, "word": "Basketball"}]
        with patch(
            "math_books.voiceover_qa.transcribe_audio",
            return_value=[{"start": 0, "end": 1, "text": "Basketball", "words": words}],
        ):
            report = voiceover_qa.verify_manifest(self.root / "manifest.json", manifest, self.root)
        self.assertEqual(
            voiceover_qa.timing_snapshot(self.root / "manifest.json", manifest, self.root), {"opening": words}
        )
        with patch("math_books.voiceover_qa.QA_POLICY_VERSION", 99), self.assertRaises(ValueError):
            voiceover_qa.timing_snapshot(self.root / "manifest.json", manifest, self.root)
        path = Path(report["clips"][0]["receipt_path"])
        receipt = json.loads(path.read_text())
        for start, end in [(float("nan"), 0.7), (0, float("inf")), (-0.1, 0.7), (0.7, 0.1), (0.1, 1.1)]:
            with self.subTest(start=start, end=end):
                receipt["segments"][0]["words"] = [{"start": start, "end": end, "word": "Basketball"}]
                path.write_text(json.dumps(receipt))
                with self.assertRaises(ValueError):
                    voiceover_qa.timing_snapshot(self.root / "manifest.json", manifest, self.root)
        for invalid_words in [[], [{"start": 0.7, "end": 0.8, "word": "Basket"}, *words]]:
            receipt["segments"][0]["words"] = invalid_words
            path.write_text(json.dumps(receipt))
            with self.assertRaises(ValueError):
                voiceover_qa.timing_snapshot(self.root / "manifest.json", manifest, self.root)
        receipt["language"] = "uk"
        receipt["segments"][0]["words"] = words
        path.write_text(json.dumps(receipt))
        with self.assertRaises(ValueError):
            voiceover_qa.timing_snapshot(self.root / "manifest.json", manifest, self.root)


if __name__ == "__main__":
    unittest.main()
