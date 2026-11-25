"""Gemini credentials must not escape through URLs or diagnostics."""

import base64
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from math_books.tts_engine import FatalTTSError, generate_topic_tts, synthesize_gemini_tts


class SecretTransportTests(unittest.TestCase):
    def test_key_is_only_in_request_header(self):
        payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": "audio/L16",
                                    "data": base64.b64encode(b"\0\0" * 24000).decode(),
                                }
                            }
                        ]
                    }
                }
            ]
        }
        response = SimpleNamespace(status_code=200, json=lambda: payload)
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("math_books.tts_engine.httpx.post", return_value=response) as post,
        ):
            synthesize_gemini_tts("hello", Path(tmp) / "clip.wav", "FAKE_API_SECRET")
        self.assertNotIn("FAKE_API_SECRET", post.call_args.args[0])
        self.assertNotIn("?", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["headers"], {"x-goog-api-key": "FAKE_API_SECRET"})

    def test_timeout_message_is_redacted_and_remains_retryable(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch(
                "math_books.tts_engine.httpx.post",
                side_effect=httpx.ReadTimeout("timeout https://example.test/?key=FAKE_API_SECRET"),
            ),
        ):
            with self.assertRaises(httpx.ReadTimeout) as caught:
                synthesize_gemini_tts("hello", Path(tmp) / "clip.wav", "FAKE_API_SECRET")
        self.assertNotIn("FAKE_API_SECRET", str(caught.exception))
        self.assertIn("timeout", str(caught.exception))

    def test_fatal_and_retryable_response_echoes_are_redacted(self):
        for status, error in ((400, FatalTTSError), (503, RuntimeError)):
            with (
                self.subTest(status=status),
                tempfile.TemporaryDirectory() as tmp,
                patch(
                    "math_books.tts_engine.httpx.post",
                    return_value=SimpleNamespace(status_code=status, text="rejected FAKE_API_SECRET"),
                ),
            ):
                with self.assertRaises(error) as caught:
                    synthesize_gemini_tts("hello", Path(tmp) / "clip.wav", "FAKE_API_SECRET")
                self.assertNotIn("FAKE_API_SECRET", str(caught.exception))

    def test_missing_audio_response_echo_is_redacted(self):
        payload = {"candidates": [{"content": {"parts": [{"text": "FAKE_API_SECRET"}]}}]}
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch(
                "math_books.tts_engine.httpx.post", return_value=SimpleNamespace(status_code=200, json=lambda: payload)
            ),
        ):
            with self.assertRaises(RuntimeError) as caught:
                synthesize_gemini_tts("hello", Path(tmp) / "clip.wav", "FAKE_API_SECRET")
        self.assertNotIn("FAKE_API_SECRET", str(caught.exception))

    def test_exhausted_batch_error_is_redacted(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict("os.environ", {"GEMINI_API_KEY": "FAKE_API_SECRET"}),
            patch("math_books.tts_engine.require_content_review"),
            patch(
                "math_books.tts_engine.synthesize_gemini_tts", side_effect=httpx.ReadTimeout("FAKE_API_SECRET")
            ) as synth,
        ):
            with self.assertRaises(httpx.ReadTimeout) as caught:
                generate_topic_tts([{"id": "a", "text": "hello"}], "demo", root=Path(tmp), delay_s=0)
        self.assertEqual(synth.call_count, 3)
        self.assertNotIn("FAKE_API_SECRET", str(caught.exception))
