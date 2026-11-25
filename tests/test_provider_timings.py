"""Offline provider evidence, exact trim transforms, and review-required stop tests."""

import hashlib
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from math_books.tts_engine import generate_topic_tts, trim_wav_edges
from math_books.uk_tts_providers import EdgeTTSProvider, UkrainianFallbackTTS, VoiceProfile


def write_wav(path):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\0\0" * 6000 + b"\x10\x20" * 12000 + b"\0\0" * 6000)


class FakeCommunicate:
    calls = []

    def __init__(self, text, voice, **kwargs):
        self.calls.append((text, voice, kwargs))

    async def save(self, audio, metadata=None):
        Path(audio).write_bytes(b"fake-mp3")
        if metadata:
            Path(metadata).write_text(
                json.dumps({"type": "WordBoundary", "offset": 2500000, "duration": 5000000, "text": "Привіт"}) + "\n"
            )


class ProviderTimingTests(unittest.TestCase):
    def setUp(self):
        FakeCommunicate.calls = []
        self.edge = patch("edge_tts.Communicate", FakeCommunicate)
        self.convert = patch(
            "math_books.uk_tts_providers.convert_to_standard_wav", side_effect=lambda source, output: write_wav(output)
        )
        self.edge.start()
        self.convert.start()
        self.addCleanup(self.edge.stop)
        self.addCleanup(self.convert.stop)

    def test_edge_requests_word_boundaries_and_preserves_raw_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "clip.wav"
            UkrainianFallbackTTS([EdgeTTSProvider("edge", "voice")]).synthesize("Привіт", wav)
            self.assertEqual(FakeCommunicate.calls, [("Привіт", "voice", {"rate": "+0%", "boundary": "WordBoundary"})])
            evidence = json.loads(wav.with_suffix(".provider-timings.json").read_text())
            self.assertEqual(json.loads(evidence["raw_metadata"])["text"], "Привіт")
            self.assertEqual(evidence["wav_sha256"], hashlib.sha256(wav.read_bytes()).hexdigest())
            self.assertTrue(evidence["advisory"])
            self.assertIn("uncertainty", evidence)

    def test_trim_updates_exact_decoded_clock_transform(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "clip.wav"
            EdgeTTSProvider("edge", "voice").synthesize_wav("Привіт", wav)
            trim_wav_edges(wav)
            evidence = json.loads(wav.with_suffix(".provider-timings.json").read_text())
            self.assertEqual(evidence["trim_start_samples"], 3600)
            self.assertEqual(evidence["sample_rate"], 24000)
            self.assertEqual(evidence["wav_sha256"], hashlib.sha256(wav.read_bytes()).hexdigest())
            self.assertNotEqual(evidence["decoded_wav_sha256"], evidence["wav_sha256"])

    def test_future_publication_binds_evidence_and_rejects_tampering(self):
        from math_books.uk_tts_providers import validate_provider_timings

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = VoiceProfile("demo", "Demo", "uk", ("edge",))
            with (
                patch("math_books.tts_engine.require_content_review"),
                patch("math_books.tts_engine._check_clip_qa"),
                patch(
                    "math_books.tts_engine.build_ukrainian_providers",
                    return_value=(profile, [EdgeTTSProvider("edge", "voice")]),
                ),
            ):
                result = generate_topic_tts(
                    [{"id": "a", "text": "Привіт"}],
                    "demo",
                    root=root,
                    provider="uk",
                    language="uk",
                    pin_model=True,
                    trim_edges=True,
                )
            audio_dir = root / "demo/audio"
            item = result[0]
            self.assertTrue(item["quality_check"])
            self.assertTrue(item["timing_required"])
            timing = validate_provider_timings(item, audio_dir)
            assert timing is not None
            self.assertEqual(timing["trim_start_samples"], 3600)
            (audio_dir / item["provider_timings"]).write_text("{}")
            with self.assertRaises(ValueError):
                validate_provider_timings(item, audio_dir)

    def test_needs_review_stops_gemini_without_retry(self):
        from math_books.voiceover_qa import ReviewRequiredError

        with tempfile.TemporaryDirectory() as tmp:
            audio_dir = Path(tmp) / "demo/audio"
            audio_dir.mkdir(parents=True)
            manifest = audio_dir / "manifest.json"
            manifest.write_text('[{"previous": "production"}]')
            previous_manifest = manifest.read_bytes()
            report = {
                "ok": False,
                "status": "needs_review",
                "reason": "ambiguous text",
                "comparison": {"issues": ["recognizer disagreement"]},
            }
            with (
                patch("math_books.tts_engine.require_content_review"),
                patch("math_books.tts_engine.verify_clip", return_value=report) as qa,
                patch(
                    "math_books.tts_engine.synthesize_gemini_tts",
                    side_effect=lambda text, path, key, **kw: write_wav(path),
                ) as synth,
                patch.dict("os.environ", {"GEMINI_API_KEY": "offline-test"}),
            ):
                with self.assertRaises(ReviewRequiredError) as raised:
                    generate_topic_tts(
                        [{"id": "a", "text": "Hello"}], "demo", root=Path(tmp), language="en", pin_model=True, delay_s=0
                    )
            self.assertEqual(synth.call_count, 1)
            self.assertTrue(qa.call_args.kwargs["quality_check"])
            self.assertEqual(manifest.read_bytes(), previous_manifest)
            retained_wavs = list((audio_dir / "review_required").glob("*.wav"))
            retained_reports = list((audio_dir / "review_required").glob("*.json"))
            self.assertEqual(len(retained_wavs), 1)
            self.assertEqual(len(retained_reports), 1)
            self.assertIn(str(retained_wavs[0]), str(raised.exception))
            self.assertIn(str(retained_reports[0]), str(raised.exception))
            evidence = json.loads(retained_reports[0].read_text())
            self.assertEqual(evidence["source_report"], report)
            self.assertTrue(evidence["evidence_only"])
            self.assertEqual(evidence["wav_sha256"], hashlib.sha256(retained_wavs[0].read_bytes()).hexdigest())

    def test_review_required_stops_uk_before_next_provider(self):
        from math_books.voiceover_qa import ReviewRequiredError

        first = EdgeTTSProvider("first", "voice")
        second = EdgeTTSProvider("second", "other")

        def require_review(path):
            raise ReviewRequiredError("ambiguous recognizer output")

        service = UkrainianFallbackTTS([first, second])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ReviewRequiredError):
                service.synthesize("Привіт", Path(tmp) / "clip.wav", validate=require_review)
        self.assertEqual(len(FakeCommunicate.calls), 1)
        self.assertIsNone(service.pinned_provider)

    def test_future_cache_hit_rechecks_quality_then_upgrades_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenes = [{"id": "a", "text": "Hello"}]
            with (
                patch("math_books.tts_engine.require_content_review"),
                patch("math_books.tts_engine.verify_clip", return_value={"ok": True}) as qa,
                patch(
                    "math_books.tts_engine.synthesize_gemini_tts",
                    side_effect=lambda text, path, key, **kw: write_wav(path),
                ) as synth,
                patch.dict("os.environ", {"GEMINI_API_KEY": "offline-test"}),
            ):
                generate_topic_tts(scenes, "demo", root=root, language="en", pin_model=True, delay_s=0)
                cache_path = root / "demo/audio/a.cache.json"
                cache = json.loads(cache_path.read_text())
                cache.pop("quality_check")
                cache_path.write_text(json.dumps(cache))
                result = generate_topic_tts(scenes, "demo", root=root, language="en", pin_model=True, delay_s=0)
            self.assertEqual(synth.call_count, 1)
            self.assertTrue(result[0]["quality_check"])
            self.assertTrue(json.loads(cache_path.read_text())["quality_check"])
            self.assertEqual(qa.call_count, 2)
            self.assertTrue(all(call.kwargs["quality_check"] for call in qa.call_args_list))

    def test_review_evidence_reuses_identical_bytes_and_never_overwrites_collision(self):
        from math_books.tts_engine import _check_clip_qa
        from math_books.voiceover_qa import ReviewRequiredError

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio_dir = root / "audio"
            audio_dir.mkdir()
            source = root / "source.wav"
            write_wav(source)
            with patch("math_books.tts_engine.verify_clip", return_value={"ok": False, "status": "needs_review"}):
                for _ in range(2):
                    with self.assertRaises(ReviewRequiredError):
                        _check_clip_qa(source, "Hello", "a", audio_dir, root, language="en", quality_check=True)
                retained_reports = list((audio_dir / "review_required").glob("*.json"))
                self.assertEqual(len(retained_reports), 1)
                self.assertEqual(len(list((audio_dir / "review_required").glob("*.wav"))), 1)
                retained_reports[0].write_bytes(b"existing evidence must survive")
                with self.assertRaisesRegex(ReviewRequiredError, "collision"):
                    _check_clip_qa(source, "Hello", "a", audio_dir, root, language="en", quality_check=True)
                self.assertEqual(retained_reports[0].read_bytes(), b"existing evidence must survive")
