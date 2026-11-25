"""Text recognition uncertainty and acoustic defects have distinct outcomes."""

import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from math_books import voiceover_qa


class TestQualityStatuses(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.wav = self.root / "clip.wav"
        with wave.open(str(self.wav), "wb") as audio:
            audio.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            audio.writeframes(b"\x01\x01" * 24000)
        self.segments = [
            {"start": 0, "end": 1, "text": "Basketball", "words": [{"start": 0.1, "end": 0.7, "word": "Basketball"}]}
        ]

    def check(self):
        return voiceover_qa.verify_clip(
            self.wav, "Basketball", self.root / "qa", self.root, language="en", quality_check=True
        )

    def test_review_required_error_is_distinct_from_recognizer_failure(self):
        self.assertTrue(issubclass(voiceover_qa.ReviewRequiredError, RuntimeError))
        self.assertFalse(issubclass(voiceover_qa.ReviewRequiredError, voiceover_qa.RecognitionError))

    def test_acoustic_status_is_separate_from_passing_text(self):
        for acoustic_status in ["pass", "fail", "needs_review"]:
            with (
                self.subTest(status=acoustic_status),
                patch("math_books.voiceover_qa.transcribe_audio", return_value=self.segments),
                patch(
                    "math_books.voiceover_qa.analyze_audio",
                    create=True,
                    return_value={"ok": acoustic_status == "pass", "status": acoustic_status, "issues": ["diagnostic"]},
                ),
            ):
                result = self.check()
                self.assertTrue(result["comparison"]["ok"])
                self.assertEqual(result["status"], acoustic_status)
                self.assertEqual(result["ok"], acoustic_status == "pass")
                self.assertTrue(result["reason"])

    def test_cached_acoustic_approval_is_recomputed(self):
        with (
            patch("math_books.voiceover_qa.transcribe_audio", return_value=self.segments),
            patch(
                "math_books.voiceover_qa.analyze_audio",
                create=True,
                return_value={"ok": True, "status": "pass", "issues": []},
            ),
        ):
            self.assertTrue(self.check()["ok"])
        with (
            patch("math_books.voiceover_qa.transcribe_audio", side_effect=AssertionError("cache expected")),
            patch(
                "math_books.voiceover_qa.analyze_audio",
                create=True,
                return_value={"ok": False, "status": "fail", "issues": ["Clipping"]},
            ),
        ):
            result = self.check()
        self.assertTrue(result["cached"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "fail")

    def test_acoustic_configuration_revision_invalidates_receipt(self):
        with (
            patch("math_books.voiceover_qa.transcribe_audio", return_value=self.segments),
            patch("math_books.voiceover_qa.analyze_audio", return_value={"ok": True, "status": "pass", "issues": []}),
        ):
            first = self.check()
            with patch("math_books.audio_quality.ACOUSTIC_POLICY_VERSION", 99):
                second = self.check()
        self.assertFalse(second["cached"])
        self.assertNotEqual(first["receipt_path"], second["receipt_path"])

    def test_text_mismatch_requests_review_instead_of_proving_bad_tts(self):
        with (
            patch("math_books.voiceover_qa.transcribe_audio", return_value=[{"start": 0, "end": 1, "text": "wrong"}]),
            patch(
                "math_books.voiceover_qa.analyze_audio",
                create=True,
                return_value={"ok": True, "status": "pass", "issues": []},
            ),
        ):
            result = self.check()
        self.assertFalse(result["comparison"]["ok"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "needs_review")

    def test_acoustic_review_reason_includes_listening_warning(self):
        with (
            patch("math_books.voiceover_qa.transcribe_audio", return_value=self.segments),
            patch(
                "math_books.voiceover_qa.analyze_audio",
                return_value={"ok": False, "status": "needs_review", "issues": [], "warnings": ["Low RMS level"]},
            ),
        ):
            result = self.check()
        self.assertIn("Low RMS level", result["reason"])

    def test_snapshot_rechecks_acoustics(self):
        with (
            patch("math_books.voiceover_qa.transcribe_audio", return_value=self.segments),
            patch(
                "math_books.voiceover_qa.analyze_audio",
                create=True,
                return_value={"ok": True, "status": "pass", "issues": []},
            ),
        ):
            self.check()
        manifest = [{"id": "opening", "wav": "clip.wav", "text": "Basketball", "language": "en", "quality_check": True}]
        with (
            patch(
                "math_books.voiceover_qa.analyze_audio",
                create=True,
                return_value={"ok": False, "status": "fail", "issues": ["Clipping"]},
            ),
            self.assertRaises(ValueError),
        ):
            voiceover_qa.timing_snapshot(self.root / "manifest.json", manifest, self.root)

    def test_manifest_enables_acoustic_gate_and_reports_defect_reason(self):
        manifest = [{"id": "opening", "wav": "clip.wav", "text": "Basketball", "language": "en", "quality_check": True}]
        with (
            patch("math_books.voiceover_qa.transcribe_audio", return_value=self.segments),
            patch(
                "math_books.voiceover_qa.analyze_audio",
                return_value={"ok": False, "status": "fail", "issues": ["Clipping"]},
            ),
        ):
            result = voiceover_qa.verify_manifest(self.root / "manifest.json", manifest, self.root)
        self.assertFalse(result["ok"])
        self.assertEqual(result["clips"][0]["status"], "fail")
        self.assertIn("Clipping", result["issues"][0])

    def test_finite_confidence_diagnostics_are_retained_without_accepting_by_confidence(self):
        word = SimpleNamespace(start=0, end=0.5, word="Basketball", probability=0.8)
        segment = SimpleNamespace(
            start=0, end=1, text="Basketball", words=[word], avg_logprob=-0.2, no_speech_prob=float("nan")
        )
        recognizer = SimpleNamespace(transcribe=lambda *args, **kwargs: (iter([segment]), None))
        with (
            patch("math_books.voiceover_qa.subprocess.run", return_value=SimpleNamespace(stdout=b"\x00" * 4)),
            patch("math_books.voiceover_qa._recognizer", return_value=recognizer),
        ):
            result = voiceover_qa.transcribe_audio(self.wav, self.root)
        self.assertEqual(result[0]["avg_logprob"], -0.2)
        self.assertEqual(result[0]["words"][0]["probability"], 0.8)
        self.assertNotIn("no_speech_prob", result[0])
