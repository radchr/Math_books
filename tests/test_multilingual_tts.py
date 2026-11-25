"""Offline language isolation and partial-cache voice identity regressions."""

import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from math_books.tts_engine import generate_topic_tts, request_fingerprint
from math_books.uk_tts_providers import UkrainianFallbackTTS, VoiceProfile


class Provider:
    kind = "stub"

    def __init__(self, name, *, fail=False, speed=1):
        self.provider_id = name
        self.voice = name
        self.fail = fail
        self.speed = speed
        self.calls = []

    @property
    def settings(self):
        return {"speed": self.speed}

    def synthesize_wav(self, text, path):
        self.calls.append(text)
        if self.fail:
            raise RuntimeError("offline")
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(b"\x01\x00" * 2400)


class MultilingualTTSTests(unittest.TestCase):
    def test_language_is_part_of_fingerprint_but_legacy_ru_is_unchanged(self):
        legacy = request_fingerprint("same", "Puck", 0)
        self.assertEqual(legacy, request_fingerprint("same", "Puck", 0, language="ru"))
        self.assertNotEqual(legacy, request_fingerprint("same", "Puck", 0, language="en"))
        self.assertNotEqual(request_fingerprint("same", "Puck", 0, language="uk"), legacy)

    def test_qa_rejection_falls_back_before_pinning(self):
        first, second = Provider("first"), Provider("second")
        service = UkrainianFallbackTTS([first, second])
        seen = []

        def validate(path):
            seen.append(path)
            if len(seen) == 1:
                raise ValueError("bad pronunciation")

        with tempfile.TemporaryDirectory() as tmp:
            identity = service.synthesize("hello", Path(tmp) / "out.wav", validate=validate)
        self.assertEqual(identity, ("second", "second"))
        self.assertIs(service.pinned_provider, second)

    def test_partial_cache_pins_voice_even_when_missing_scene_comes_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first, second = Provider("first", fail=True), Provider("second")
            profile = VoiceProfile("test", "Test", "uk", ("first", "second"))
            scenes = [{"id": "a", "text": "Привіт"}, {"id": "b", "text": "Світ"}]
            with (
                patch("math_books.tts_engine.require_content_review"),
                patch("math_books.tts_engine._check_clip_qa"),
                patch("math_books.tts_engine.build_ukrainian_providers", return_value=(profile, [first, second])),
            ):
                generate_topic_tts(scenes, "demo", provider="uk", root=root, delay_s=0)
                (root / "demo/audio/a.cache.json").unlink()
                first.fail = False
                first.calls.clear()
                second.calls.clear()
                manifest = generate_topic_tts(scenes, "demo", provider="uk", root=root, delay_s=0)
            self.assertEqual([item["model"] for item in manifest], ["second", "second"])
            self.assertEqual(first.calls, [])
            self.assertEqual(second.calls, ["Привіт"])
            self.assertTrue(all(item["language"] == "uk" for item in manifest))

    def test_profile_setting_changes_invalidate_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            provider = Provider("first")
            profile = VoiceProfile("test", "Test", "uk", ("first",))
            scenes = [{"id": "a", "text": "Привіт"}]
            with (
                patch("math_books.tts_engine.require_content_review"),
                patch("math_books.tts_engine._check_clip_qa"),
                patch("math_books.tts_engine.build_ukrainian_providers", return_value=(profile, [provider])),
            ):
                generate_topic_tts(scenes, "demo", provider="uk", root=root, delay_s=0)
                provider.speed = 2
                generate_topic_tts(scenes, "demo", provider="uk", root=root, delay_s=0)
            self.assertEqual(len(provider.calls), 2)
            manifest = json.loads((root / "demo/audio/manifest.json").read_text())
            self.assertEqual(manifest[0]["language"], "uk")

    def test_explicit_english_rejects_uk_provider_before_review(self):
        with patch("math_books.tts_engine.require_content_review") as review:
            with self.assertRaisesRegex(ValueError, "requires language"):
                generate_topic_tts([{"id": "a", "text": "Hello"}], "demo", language="en", provider="uk")
        review.assert_not_called()

    def test_piper_model_contents_are_part_of_profile_identity(self):
        from math_books.uk_tts_providers import PiperProvider, profile_fingerprint

        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / "model.onnx"
            config = Path(tmp) / "model.json"
            model.write_bytes(b"version1")
            config.write_text("{}")
            provider = PiperProvider("piper", "test", model_path=model, config_path=config)
            profile = VoiceProfile("test", "Test", "uk", ("piper",))
            first = profile_fingerprint(profile, [provider])
            model.write_bytes(b"version2")
            self.assertNotEqual(first, profile_fingerprint(profile, [provider]))

    def test_new_english_batch_pins_one_gemini_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            scenes = [{"id": str(idx), "text": "Hello"} for idx in range(4)]
            models = []

            def synthesize(text, path, api_key, *, model, voice):
                models.append(model)
                Provider("stub").synthesize_wav(text, path)

            with (
                patch("math_books.tts_engine.require_content_review"),
                patch("math_books.tts_engine.verify_clip", return_value={"ok": True}) as qa,
                patch("math_books.tts_engine.synthesize_gemini_tts", side_effect=synthesize),
                patch.dict("os.environ", {"GEMINI_API_KEY": "offline-test"}),
            ):
                generate_topic_tts(scenes, "demo", language="en", root=Path(tmp), delay_s=0)
            self.assertEqual(len(set(models)), 1)
            self.assertEqual(qa.call_args.kwargs["language"], "en")

    def test_future_russian_batch_can_pin_model_without_changing_legacy_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            scenes = [{"id": str(idx), "text": "Привет"} for idx in range(4)]
            models = []

            def synthesize(text, path, api_key, *, model, voice):
                models.append(model)
                Provider("stub").synthesize_wav(text, path)

            with (
                patch("math_books.tts_engine.require_content_review"),
                patch("math_books.tts_engine._check_clip_qa"),
                patch("math_books.tts_engine.synthesize_gemini_tts", side_effect=synthesize),
                patch.dict("os.environ", {"GEMINI_API_KEY": "offline-test"}),
            ):
                manifest = generate_topic_tts(scenes, "demo", language="ru", pin_model=True, root=Path(tmp), delay_s=0)
            self.assertEqual(len(set(models)), 1)
            self.assertTrue(all(item["pin_model"] for item in manifest))

    def test_asr_unavailable_does_not_retry_uk_providers(self):
        from math_books.voiceover_qa import RecognitionError

        first, second = Provider("first"), Provider("second")
        service = UkrainianFallbackTTS([first, second])

        def unavailable(path):
            raise RecognitionError("ASR unavailable")

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RecognitionError, "ASR unavailable"):
                service.synthesize("hello", Path(tmp) / "out.wav", validate=unavailable)
        self.assertEqual(first.calls, ["hello"])
        self.assertEqual(second.calls, [])
        self.assertIsNone(service.pinned_provider)

    def test_pinned_gemini_retries_transient_failure_on_same_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            scenes = [{"id": "a", "text": "Hello"}, {"id": "b", "text": "Again"}]
            attempts = []

            def synthesize(text, path, api_key, *, model, voice):
                attempts.append((text, model))
                if text == "Again" and len(attempts) == 2:
                    raise RuntimeError("Gemini TTS failed (429): rate limit")
                Provider("stub").synthesize_wav(text, path)

            with (
                patch("math_books.tts_engine.require_content_review"),
                patch("math_books.tts_engine._check_clip_qa"),
                patch("math_books.tts_engine.synthesize_gemini_tts", side_effect=synthesize),
                patch.dict("os.environ", {"GEMINI_API_KEY": "offline-test"}),
            ):
                manifest = generate_topic_tts(scenes, "demo", language="en", root=Path(tmp), delay_s=0)
            self.assertEqual(len(manifest), 2)
            self.assertEqual([text for text, _ in attempts], ["Hello", "Again", "Again"])
            self.assertEqual(len({model for _, model in attempts}), 1)
