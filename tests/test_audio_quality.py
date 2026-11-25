"""Real PCM fixtures for non-mutating energy-based acoustic screening."""

import hashlib
import json
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from math_books.audio_quality import ACOUSTIC_POLICY_VERSION, analyze_audio, policy_profile


class TestAudioQuality(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "fixture.wav"
        self.rate = 24000

    def sine(self, duration=2, amplitude=12000):
        return (amplitude * np.sin(2 * np.pi * 440 * np.arange(int(duration * self.rate)) / self.rate)).astype("<i2")

    def write(self, samples, width=2):
        with wave.open(str(self.path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(width)
            output.setframerate(self.rate)
            output.writeframes(samples.tobytes())

    def test_clean_sine_passes_with_correct_metrics_without_modification(self):
        self.write(self.sine())
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        result = analyze_audio(self.path)
        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["ok"])
        self.assertEqual((result["sample_rate"], result["channels"], result["duration"]), (24000, 1, 2))
        self.assertAlmostEqual(result["peak_dbfs"], -8.73, delta=0.02)
        self.assertAlmostEqual(result["rms_dbfs"], -11.74, delta=0.02)
        self.assertEqual(result["clipped_fraction"], 0)
        self.assertAlmostEqual(result["dc_offset"], 0, delta=0.001)
        self.assertEqual(result["active_fraction"], 1)
        self.assertEqual(result["max_internal_pause_s"], 0)
        self.assertEqual(before, hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(result, analyze_audio(self.path))
        self.assertEqual(result["policy"], policy_profile())
        self.assertEqual(result["policy"]["version"], ACOUSTIC_POLICY_VERSION)
        json.dumps(result, allow_nan=False)

    def test_silence_empty_invalid_and_truncated_fail_with_json_safe_metrics(self):
        self.write(np.zeros(self.rate, dtype="<i2"))
        for payload in (self.path.read_bytes(), b"", b"not a wave"):
            self.path.write_bytes(payload)
            report = analyze_audio(self.path)
            self.assertEqual(report["status"], "fail")
            self.assertFalse(report["ok"])
            self.assertTrue(report["issues"])
            json.dumps(report, allow_nan=False)
        self.write(self.sine())
        self.path.write_bytes(self.path.read_bytes()[:-13])
        self.assertEqual(analyze_audio(self.path)["status"], "fail")
        self.write(np.array([], dtype="<i2"))
        self.assertEqual(analyze_audio(self.path)["status"], "fail")

    def test_sustained_clipping_fails_but_isolated_extreme_does_not(self):
        samples = self.sine()
        samples[: self.rate // 10] = 32767
        self.write(samples)
        report = analyze_audio(self.path)
        self.assertEqual(report["status"], "fail")
        self.assertAlmostEqual(report["clipped_fraction"], 0.05)
        samples = self.sine()
        samples[100] = -32768
        self.write(samples)
        self.assertEqual(analyze_audio(self.path)["status"], "pass")

    def test_low_level_is_review_not_silence_failure(self):
        self.write(self.sine(amplitude=30))
        result = analyze_audio(self.path)
        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["ok"])
        self.assertTrue(result["warnings"])
        self.assertEqual(result["issues"], [])

    def test_pause_metrics_distinguish_edges_internal_and_natural_gaps(self):
        silence = np.zeros(self.rate, dtype="<i2")
        self.write(np.concatenate([silence, self.sine(1), silence, silence, silence, self.sine(1), silence]))
        result = analyze_audio(self.path)
        self.assertEqual(result["status"], "needs_review")
        self.assertAlmostEqual(result["leading_silence_s"], 1)
        self.assertAlmostEqual(result["trailing_silence_s"], 1)
        self.assertAlmostEqual(result["max_internal_pause_s"], 3)
        self.assertAlmostEqual(result["active_fraction"], 2 / 7)
        self.write(np.concatenate([self.sine(1), silence[: self.rate // 4], self.sine(1)]))
        self.assertEqual(analyze_audio(self.path)["status"], "pass")

    def test_unsupported_sample_width_is_explicit_failure(self):
        self.write(np.zeros(100, dtype="u1"), width=1)
        result = analyze_audio(self.path)
        self.assertEqual(result["status"], "fail")
        self.assertIn("PCM16", " ".join(result["issues"]))

    def test_one_percent_clipping_boundary_and_stereo_energy(self):
        samples = self.sine()
        samples[: len(samples) // 100] = 32760
        self.write(samples)
        self.assertEqual(analyze_audio(self.path)["status"], "fail")
        samples[len(samples) // 100 - 1] = 0
        self.write(samples)
        self.assertEqual(analyze_audio(self.path)["status"], "pass")
        stereo = np.column_stack((self.sine(), -self.sine())).astype("<i2")
        with wave.open(str(self.path), "wb") as output:
            output.setnchannels(2)
            output.setsampwidth(2)
            output.setframerate(self.rate)
            output.writeframes(stereo.tobytes())
        result = analyze_audio(self.path)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["channels"], 2)
        self.assertEqual(result["active_fraction"], 1)

    def test_missing_file_fails_without_creating_it(self):
        self.assertEqual(analyze_audio(self.path)["status"], "fail")
        self.assertFalse(self.path.exists())
