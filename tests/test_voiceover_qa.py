"""Audio checks must depend on actual bytes/text/policy, not a saved ok flag."""

import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from math_books import voiceover_qa


def write_audio(path, sample=b"\x01\x01"):
    with wave.open(str(path), "wb") as wav:
        wav.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        wav.writeframes(sample * 24000)


class TestVoiceoverQA(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.wav = self.root / "clip.wav"
        write_audio(self.wav)
        self.text = "Два независимых штрафных броска."

    def check(self, **kwargs):
        return voiceover_qa.verify_clip(self.wav, self.text, self.root / "qa", self.root / "models", **kwargs)

    def test_success_is_cached_without_loading_recognizer_again(self):
        seg = [{"start": 0, "end": 1, "text": self.text}]
        with patch("math_books.voiceover_qa.transcribe_audio", return_value=seg) as recognizer:
            first = self.check()
            second = self.check()
        self.assertTrue(first["ok"])
        self.assertTrue(second["cached"])
        self.assertEqual(recognizer.call_count, 1)

    def test_changed_wav_or_script_or_policy_requires_new_recognition(self):
        seg = [{"start": 0, "end": 1, "text": self.text}]
        with patch("math_books.voiceover_qa.transcribe_audio", return_value=seg) as recognizer:
            self.check()
            write_audio(self.wav, b"\x02\x02")
            self.check()
            self.text = "Три независимых штрафных броска."
            self.assertFalse(self.check()["ok"])
            with patch("math_books.voiceover_qa.QA_POLICY_VERSION", 99):
                self.check()
        self.assertEqual(recognizer.call_count, 4)

    def test_flipping_failed_report_ok_does_not_approve_bad_speech(self):
        bad_seg = [{"start": 0, "end": 1, "text": "Read the following text. " + self.text}]
        with patch("math_books.voiceover_qa.transcribe_audio", return_value=bad_seg):
            failed = self.check()
        self.assertFalse(failed["ok"])
        path = Path(failed["receipt_path"])
        payload = json.loads(path.read_text())
        payload["ok"] = True
        payload["comparison"]["ok"] = True
        path.write_text(json.dumps(payload))
        self.assertFalse(self.check()["ok"])

    def test_malformed_report_cannot_be_a_cache_hit(self):
        seg = [{"start": 0, "end": 1, "text": self.text}]
        with patch("math_books.voiceover_qa.transcribe_audio", return_value=seg) as recognizer:
            first = self.check()
            Path(first["receipt_path"]).write_text("[]")
            second = self.check()
        self.assertTrue(second["ok"])
        self.assertFalse(second["cached"])
        self.assertEqual(recognizer.call_count, 2)

    def test_backend_failure_does_not_publish_a_pass(self):
        err = voiceover_qa.RecognitionError("Recognizer unavailable")
        with patch("math_books.voiceover_qa.transcribe_audio", side_effect=err):
            with self.assertRaises(voiceover_qa.RecognitionError):
                self.check()
        self.assertEqual(list((self.root / "qa").glob("*.json")), [])

    def test_empty_recognition_is_rejected(self):
        with patch("math_books.voiceover_qa.transcribe_audio", return_value=[]):
            self.assertFalse(self.check()["ok"])

    def test_refresh_reruns_asr_instead_of_bypassing_check(self):
        with patch(
            "math_books.voiceover_qa.transcribe_audio",
            side_effect=[
                [{"start": 0, "end": 1, "text": self.text}],
                [{"start": 0, "end": 1, "text": "Неправильные слова."}],
            ],
        ):
            self.assertTrue(self.check()["ok"])
            self.assertFalse(self.check(refresh=True)["ok"])
