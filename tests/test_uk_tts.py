"""Tests for multi-provider Ukrainian TTS fallback, voice pinning, and Hypothesis math properties."""

from __future__ import annotations

import json
import math
import struct
import tempfile
import unittest
import wave
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from hypothesis import given
from hypothesis import strategies as st

from math_books.buzzer_scene import build_buzzer_visual_spec, chain_success_probability
from math_books.cli import build_parser
from math_books.free_throws_scene import two_shot_outcomes
from math_books.tts_engine import generate_topic_tts, request_fingerprint, valid_request_fingerprints
from math_books.uk_tts_providers import (
    UkrainianFallbackTTS,
    VoiceProfile,
    build_ukrainian_providers,
    convert_to_standard_wav,
    load_voice_profiles,
)


def _write_pcm_wav(path: Path, *, sample_rate: int = 24000, channels: int = 1, duration_s: float = 0.25) -> None:
    frames = max(1, int(sample_rate * duration_s))
    samples = [int(12000 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate)) for i in range(frames)]
    if channels == 2:
        interleaved = [val for s in samples for val in (s, s)]
    else:
        interleaved = samples
    raw = struct.pack(f"<{len(interleaved)}h", *interleaved)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)


class _StubProvider:
    def __init__(self, provider_id: str, *, fail_on: set[int] | None = None, fail_all: bool = False) -> None:
        self.provider_id = provider_id
        self.kind = "stub"
        self.voice = f"voice-{provider_id}"
        self.fail_on = fail_on or set()
        self.fail_all = fail_all
        self.calls: list[str] = []

    @property
    def settings(self) -> dict[str, object]:
        return {"stub": self.provider_id}

    def synthesize_wav(self, text: str, out_wav: Path) -> None:
        call_idx = len(self.calls)
        self.calls.append(text)
        if self.fail_all or call_idx in self.fail_on:
            raise RuntimeError(f"{self.provider_id} failed on call {call_idx}")
        _write_pcm_wav(out_wav)


class UkrainianTTSProviderTests(unittest.TestCase):
    def test_load_voice_profiles_and_build_providers(self) -> None:
        config = load_voice_profiles()
        self.assertEqual(config.default_profile, "tyshyn")
        self.assertIn("styletts2_tyshyn", config.providers)

        root = Path.cwd()
        profile, providers = build_ukrainian_providers(root, profile_id="tyshyn")
        self.assertEqual(profile.profile_id, "tyshyn")
        self.assertEqual(
            [p.provider_id for p in providers],
            ["styletts2_tyshyn", "styletts2_kudryavets", "piper_oleksa", "edge_ostap"],
        )

        with self.assertRaises(ValueError):
            build_ukrainian_providers(root, profile_id="nonexistent_profile")

    def test_fallback_pins_working_provider_for_entire_batch(self) -> None:
        first = _StubProvider("styletts2_tyshyn", fail_all=True)
        second = _StubProvider("piper_oleksa")
        third = _StubProvider("edge_ostap")

        tts = UkrainianFallbackTTS([first, second, third])
        with tempfile.TemporaryDirectory() as tmpdir:
            out1 = Path(tmpdir) / "01.wav"
            out2 = Path(tmpdir) / "02.wav"
            out3 = Path(tmpdir) / "03.wav"

            pid1, voice1 = tts.synthesize("Перший рядок", out1)
            pid2, voice2 = tts.synthesize("Другий рядок", out2)
            pid3, voice3 = tts.synthesize("Третій рядок", out3)

            self.assertEqual((pid1, voice1), ("piper_oleksa", "voice-piper_oleksa"))
            self.assertEqual((pid2, voice2), ("piper_oleksa", "voice-piper_oleksa"))
            self.assertEqual((pid3, voice3), ("piper_oleksa", "voice-piper_oleksa"))
            self.assertEqual(len(first.calls), 1)
            self.assertEqual(len(second.calls), 3)
            self.assertEqual(len(third.calls), 0)
            self.assertTrue(out1.is_file() and out2.is_file() and out3.is_file())

    def test_pinned_provider_failure_does_not_mix_voices_mid_batch(self) -> None:
        first = _StubProvider("styletts2_tyshyn", fail_on={1})
        second = _StubProvider("edge_ostap")

        tts = UkrainianFallbackTTS([first, second])
        with tempfile.TemporaryDirectory() as tmpdir:
            pid1, _ = tts.synthesize("Кліп 1", Path(tmpdir) / "01.wav")
            self.assertEqual(pid1, "styletts2_tyshyn")
            with self.assertRaisesRegex(RuntimeError, "styletts2_tyshyn failed on call 1"):
                tts.synthesize("Кліп 2", Path(tmpdir) / "02.wav")
            self.assertEqual(len(second.calls), 0)

    def test_all_providers_failing_raises_clear_error(self) -> None:
        first = _StubProvider("styletts2_tyshyn", fail_all=True)
        second = _StubProvider("edge_ostap", fail_all=True)
        tts = UkrainianFallbackTTS([first, second])
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(RuntimeError, "All Ukrainian TTS providers failed"):
                tts.synthesize("Тест", Path(tmpdir) / "01.wav")

    def test_convert_to_standard_wav_normalizes_to_24k_mono_pcm16(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "stereo44k.wav"
            dst = Path(tmpdir) / "mono24k.wav"
            _write_pcm_wav(src, sample_rate=44100, channels=2, duration_s=0.3)

            convert_to_standard_wav(src, dst)
            with wave.open(str(dst), "rb") as wf:
                self.assertEqual(wf.getnchannels(), 1)
                self.assertEqual(wf.getsampwidth(), 2)
                self.assertEqual(wf.getframerate(), 24000)
                self.assertGreater(wf.getnframes(), 0)

    def test_provider_fingerprints_separate_gemini_and_uk(self) -> None:
        fp_gemini = request_fingerprint("Привіт", "Puck", 0, provider="gemini")
        fp_uk = request_fingerprint("Привіт", "uk-UA-OstapNeural", 0, provider="uk")
        self.assertNotEqual(fp_gemini, fp_uk)
        self.assertIn(fp_gemini, valid_request_fingerprints("Привіт", "Puck", 0, provider="gemini"))
        self.assertIn(fp_uk, valid_request_fingerprints("Привіт", "uk-UA-OstapNeural", 0, provider="uk"))

    def test_cli_accepts_uk_provider_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["tts", "buzzer", "--provider", "uk", "--uk-profile", "kudryavets"])
        self.assertEqual(args.command, "tts")
        self.assertEqual(args.topic, "buzzer")
        self.assertEqual(args.provider, "uk")
        self.assertEqual(args.uk_profile, "kudryavets")

    def test_generate_topic_tts_with_uk_provider_writes_provenance_manifest(self) -> None:
        scenes = [
            {"id": "01_hook", "text": "Три секунди до сирени!"},
            {"id": "02_math", "text": "Рахуємо ймовірність серії."},
        ]
        stub = _StubProvider("edge_ostap")
        profile = VoiceProfile(profile_id="tyshyn", display_name="Test", language="uk", providers=("edge_ostap",))

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            audio_dir = root / "videos" / "video_demo" / "audio"
            with (
                patch("math_books.tts_engine.require_content_review", return_value={"ok": True}),
                patch("math_books.tts_engine.build_ukrainian_providers", return_value=(profile, [stub])),
                patch("math_books.tts_engine._check_clip_qa", return_value={"ok": True}),
            ):
                manifest = generate_topic_tts(
                    scenes,
                    "videos/video_demo",
                    provider="uk",
                    uk_profile="tyshyn",
                    delay_s=0.0,
                    root=root,
                )

            self.assertEqual(len(manifest), 2)
            self.assertEqual(len(stub.calls), 2)
            for item in manifest:
                self.assertEqual(item["provider"], "uk")
                self.assertEqual(item["model"], "edge_ostap")
                self.assertEqual(item["voice"], "tyshyn")
                self.assertTrue((audio_dir / item["wav"]).is_file())
            saved = json.loads((audio_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(saved), 2)


class MathPropertyTests(unittest.TestCase):
    @given(
        st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=6,
        )
    )
    def test_chain_success_probability_bounds_and_monotonicity(self, probs: list[float]) -> None:
        result = chain_success_probability(probs)
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)
        self.assertLessEqual(result, min(probs) + 1e-12)

    @given(st.fractions(min_value=0, max_value=1, max_denominator=100))
    def test_two_shot_outcomes_sum_to_one(self, p: Fraction) -> None:
        outcomes = two_shot_outcomes(p)
        self.assertEqual(sum(outcomes.values()), Fraction(1, 1))
        for prob in outcomes.values():
            self.assertGreaterEqual(prob, Fraction(0, 1))
            self.assertLessEqual(prob, Fraction(1, 1))

    @given(
        st.fractions(min_value=Fraction(1, 20), max_value=Fraction(19, 20), max_denominator=20),
        st.fractions(min_value=Fraction(1, 20), max_value=Fraction(19, 20), max_denominator=20),
        st.fractions(min_value=Fraction(1, 20), max_value=Fraction(19, 20), max_denominator=20),
        st.fractions(min_value=Fraction(1, 20), max_value=Fraction(19, 20), max_denominator=20),
    )
    def test_buzzer_visual_spec_conclusion_matches_probabilities(
        self, direct: Fraction, step1: Fraction, step2: Fraction, step3: Fraction
    ) -> None:
        spec = build_buzzer_visual_spec(direct_prob=direct, chain_steps=(step1, step2, step3))
        chain_val = step1 * step2 * step3
        verdict = str(spec["verdict_text"])
        if direct == chain_val:
            self.assertIn("=", verdict)
        elif direct > chain_val:
            self.assertIn(">", verdict)
        else:
            self.assertIn("<", verdict)


if __name__ == "__main__":
    unittest.main()
