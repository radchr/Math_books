"""Topic production must enforce audio QA, including retries and cache hits."""

import base64
import importlib
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from review_fixtures import write_review_fixture

from math_books import cli, voiceover_qa
from math_books.tts_engine import SECONDARY_MODEL, generate_topic_tts, synthesize_gemini_tts
from math_books.video_builder import VIDEO_TOPICS, build_video, render_silent_video


def synth(text, out, *args, **kwargs):
    with wave.open(str(out), "wb") as wav:
        wav.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        wav.writeframes(b"\x01\x01" * 24000)
    return 1.0


def segments(text):
    return [{"start": 0, "end": 1, "text": text}]


class TestVoiceoverPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scenes = [{"id": "01", "text": "Два штрафных броска."}]
        write_review_fixture(self.root, self.scenes)

    def generate(self, **kwargs):
        return generate_topic_tts(self.scenes, "video_test", root=self.root, delay_s=0, **kwargs)

    def test_only_spoken_script_is_sent_to_gemini(self):
        pcm = base64.b64encode(b"\0\0" * 24000).decode()
        inline = {"inlineData": {"mimeType": "audio/L16;rate=24000", "data": pcm}}
        payload = {"candidates": [{"content": {"parts": [inline]}}]}
        response = SimpleNamespace(status_code=200, json=lambda: payload)
        with patch("math_books.tts_engine.httpx.post", return_value=response) as transport:
            synthesize_gemini_tts("Только эта реплика.", self.root / "test.wav", "test-key")
        self.assertEqual(transport.call_args.kwargs["json"]["contents"][0]["parts"], [{"text": "Только эта реплика."}])

    def test_bad_clip_is_retried_once_then_checked_again(self):
        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test"}),
            patch("math_books.tts_engine.synthesize_gemini_tts", side_effect=synth) as synthesizer,
            patch(
                "math_books.voiceover_qa.transcribe_audio",
                side_effect=[
                    segments("Read the following text. " + self.scenes[0]["text"]),
                    segments(self.scenes[0]["text"]),
                ],
            ),
        ):
            result = self.generate()
        self.assertEqual(synthesizer.call_count, 2)
        self.assertEqual(result[0]["model"], SECONDARY_MODEL)

    def test_httpx_timeout_triggers_fallback_model_and_fatal_400_does_not_retry(self):
        import httpx

        from math_books.tts_engine import FatalTTSError

        calls = []

        def timeout_then_ok(text, out, api_key, *, model, voice):
            calls.append(model)
            if len(calls) == 1:
                raise httpx.ReadTimeout("timed out")
            return synth(text, out)

        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test"}),
            patch("math_books.tts_engine.synthesize_gemini_tts", side_effect=timeout_then_ok),
            patch("math_books.voiceover_qa.transcribe_audio", return_value=segments(self.scenes[0]["text"])),
        ):
            result = self.generate()
        self.assertEqual(len(calls), 2)
        self.assertEqual(result[0]["model"], SECONDARY_MODEL)

        bad_resp = SimpleNamespace(status_code=400, text="Invalid argument")
        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test"}),
            patch("math_books.tts_engine.httpx.post", return_value=bad_resp) as post_mock,
        ):
            with self.assertRaises(FatalTTSError):
                self.generate(force=True)
        self.assertEqual(post_mock.call_count, 1)

    def test_failed_forced_generation_preserves_published_manifest(self):
        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test"}),
            patch("math_books.tts_engine.synthesize_gemini_tts", side_effect=synth),
            patch("math_books.voiceover_qa.transcribe_audio", return_value=segments(self.scenes[0]["text"])),
        ):
            self.generate()
        path = self.root / "video_test/audio/manifest.json"
        original = path.read_bytes()
        bad_segments = segments("Лишние английские слова read the text.")
        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test"}),
            patch("math_books.tts_engine.synthesize_gemini_tts", side_effect=synth) as synthesizer,
            patch("math_books.voiceover_qa.transcribe_audio", return_value=bad_segments),
        ):
            with self.assertRaisesRegex(ValueError, "[Vv]oiceover"):
                self.generate(force=True)
        self.assertEqual(synthesizer.call_count, 2)
        self.assertEqual(path.read_bytes(), original)

    def test_backend_error_does_not_trigger_paid_retry(self):
        err = voiceover_qa.RecognitionError("unavailable")
        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test"}),
            patch("math_books.tts_engine.synthesize_gemini_tts", side_effect=synth) as synthesizer,
            patch("math_books.voiceover_qa.transcribe_audio", side_effect=err),
        ):
            with self.assertRaises(voiceover_qa.RecognitionError):
                self.generate()
        self.assertEqual(synthesizer.call_count, 1)
        self.assertFalse((self.root / "video_test/audio/manifest.json").exists())

    def test_cached_audio_is_checked_without_synthesis(self):
        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test"}),
            patch("math_books.tts_engine.synthesize_gemini_tts", side_effect=synth),
            patch("math_books.voiceover_qa.transcribe_audio", return_value=segments(self.scenes[0]["text"])),
        ):
            self.generate()
        for receipt in (self.root / "video_test/audio/qa").glob("*.json"):
            receipt.unlink()
        repeated = segments("Повторяю ещё раз. " + self.scenes[0]["text"])
        with (
            patch("math_books.tts_engine.load_dotenv"),
            patch.dict("os.environ", {"GEMINI_API_KEY": ""}),
            patch("math_books.voiceover_qa.transcribe_audio", return_value=repeated),
        ):
            with self.assertRaisesRegex(ValueError, "[Vv]oiceover"):
                self.generate()

    def test_cli_has_explicit_audio_check(self):
        args = cli.build_parser().parse_args(["verify-audio", "free_throws", "--refresh"])
        self.assertTrue(args.refresh)

    def test_direct_and_skipped_renderer_both_reject_bad_speech(self):
        topic = VIDEO_TOPICS["hothand"]
        self.scenes = importlib.import_module(topic.tts_module).SCENES
        write_review_fixture(self.root, self.scenes, topic.video_dir, scene_file=topic.scene_file)
        mapping = {s["id"]: s["text"] for s in self.scenes}

        def transcribe_ok(path, _cache):
            return segments(mapping[path.stem.split("-")[0]])

        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "test"}),
            patch("math_books.tts_engine.synthesize_gemini_tts", side_effect=synth),
            patch("math_books.voiceover_qa.transcribe_audio", side_effect=transcribe_ok),
        ):
            generate_topic_tts(self.scenes, topic.video_dir, root=self.root, delay_s=0)
        for receipt in (self.root / topic.video_dir / "audio/qa").glob("*.json"):
            receipt.unlink()
        with patch("math_books.voiceover_qa.transcribe_audio", return_value=segments("Read the instructions.")):
            with self.assertRaisesRegex(ValueError, "[Vv]oiceover"):
                render_silent_video(topic, root=self.root)
            with self.assertRaisesRegex(ValueError, "[Vv]oiceover"):
                build_video(topic.key, root=self.root, skip_render=True)
