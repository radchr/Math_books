"""Regressions for failures that previously passed the pipeline's checks."""

import hashlib
import importlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
import wave
from contextlib import redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from review_fixtures import generate_reviewed_tts as generate_topic_tts
from review_fixtures import write_review_fixture

from math_books import cli, video_builder
from math_books.build_sample_md import build_markdown, crop_mineru_images, parse_page_spec
from math_books.tts_engine import audio_lock, request_fingerprint, trim_wav_edges, wav_duration
from math_books.video_builder import VIDEO_TOPICS, build_video, concat_audio_from_manifest, project_root, verify_video


def write_wav(path: Path, seconds: float = 1.0) -> float:
    with wave.open(str(path), "wb") as wav:
        wav.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        wav.writeframes(b"\0\0" * round(24000 * seconds))
    return seconds


class TestAudioCache(unittest.TestCase):
    def test_topic_lock_rejects_concurrent_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            with audio_lock(Path(tmp)):
                with self.assertRaisesRegex(RuntimeError, "busy"):
                    with audio_lock(Path(tmp)):
                        self.fail("Second operation entered locked topic")

    def test_edge_trim_preserves_internal_pause(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clip.wav"
            with wave.open(str(path), "wb") as wav:
                wav.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
                wav.writeframes(
                    b"\0\0" * 24000 + b"\xff\x7f" * 12000 + b"\0\0" * 12000 + b"\xff\x7f" * 12000 + b"\0\0" * 24000
                )
            trim_wav_edges(path)
            self.assertAlmostEqual(wav_duration(path), 1.7, places=3)

    def test_repeated_trim_edges_reuses_already_trimmed_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenes = [{"id": "01", "text": "old"}]

            def write_padded_wav(out: Path) -> float:
                with wave.open(str(out), "wb") as wav:
                    wav.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
                    wav.writeframes(b"\0\0" * 12000 + b"\xff\x7f" * 12000 + b"\0\0" * 12000)
                return 1.5

            with (
                patch.dict("os.environ", {"GEMINI_API_KEY": "test"}),
                patch(
                    "math_books.tts_engine.synthesize_gemini_tts",
                    side_effect=lambda text, out, *a, **k: write_padded_wav(out),
                ),
            ):
                first = generate_topic_tts(scenes, "video_test", root=root, delay_s=0, trim_edges=True)
                with patch("math_books.tts_engine.trim_wav_edges") as trim_mock:
                    second = generate_topic_tts(scenes, "video_test", root=root, delay_s=0, trim_edges=True)
            self.assertEqual(first, second)
            self.assertEqual(trim_mock.call_count, 0)

    def test_header_only_wav_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "broken.wav"
            write_wav(wav)
            wav.write_bytes(wav.read_bytes()[:44])
            with self.assertRaisesRegex(ValueError, "[Tt]runcated|PCM"):
                wav_duration(wav)

    def test_invalid_cache_shape_is_treated_as_a_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "video_test/audio"
            audio.mkdir(parents=True)
            (audio / "01.cache.json").write_text("[]")
            with (
                patch.dict("os.environ", {"GEMINI_API_KEY": "test"}),
                patch(
                    "math_books.tts_engine.synthesize_gemini_tts", side_effect=lambda text, out, *a, **k: write_wav(out)
                ),
            ):
                result = generate_topic_tts([{"id": "01", "text": "new"}], "video_test", root=root, delay_s=0)
            self.assertEqual(result[0]["duration"], 1)

    def test_publish_failure_preserves_previous_manifest_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with (
                patch.dict("os.environ", {"GEMINI_API_KEY": "test"}),
                patch(
                    "math_books.tts_engine.synthesize_gemini_tts",
                    side_effect=lambda text, out, *a, **k: write_wav(out, 1 if text == "old" else 2),
                ),
            ):
                first = generate_topic_tts([{"id": "01", "text": "old"}], "video_test", root=root, delay_s=0)
                audio = root / "video_test/audio"
                previous = audio / first[0]["wav"]
                content = previous.read_bytes()
                cache = audio / "01.cache.json"
                cache.unlink()
                cache.mkdir()
                with self.assertRaises(OSError):
                    generate_topic_tts([{"id": "01", "text": "new"}], "video_test", root=root, delay_s=0)
            self.assertEqual(previous.read_bytes(), content)

    def test_unchanged_cache_can_be_used_without_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenes = [{"id": "01", "text": "old"}]
            with patch.dict("os.environ", {"GEMINI_API_KEY": "test"}):
                with patch(
                    "math_books.tts_engine.synthesize_gemini_tts", side_effect=lambda text, out, *a, **k: write_wav(out)
                ):
                    first = generate_topic_tts(scenes, "video_test", root=root, delay_s=0)
            with patch("math_books.tts_engine.load_dotenv"), patch.dict("os.environ", {"GEMINI_API_KEY": ""}):
                second = generate_topic_tts(scenes, "video_test", root=root, delay_s=0)
            self.assertEqual(first, second)

    def test_script_change_regenerates_audio_and_unchanged_script_reuses_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenes = [{"id": "01", "text": "old"}]
            with patch.dict("os.environ", {"GEMINI_API_KEY": "test"}):
                with patch(
                    "math_books.tts_engine.synthesize_gemini_tts",
                    side_effect=lambda text, out, *a, **k: write_wav(out, 1 if text == "old" else 2),
                ):
                    first = generate_topic_tts(scenes, "video_test", root=root, delay_s=0)
                    second = generate_topic_tts(scenes, "video_test", root=root, delay_s=0)
                    changed = generate_topic_tts([{"id": "01", "text": "new"}], "video_test", root=root, delay_s=0)
            self.assertEqual(first, second)
            self.assertEqual(changed[0]["duration"], 2)
            self.assertFalse(Path(changed[0]["wav"]).is_absolute())

    def test_voice_change_regenerates_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            scenes = [{"id": "01", "text": "hello"}]

            def synth(text, out, *args, voice, **kwargs):
                return write_wav(out, 1 if voice == "Puck" else 2)

            with patch.dict("os.environ", {"GEMINI_API_KEY": "test"}):
                with patch("math_books.tts_engine.synthesize_gemini_tts", side_effect=synth):
                    generate_topic_tts(scenes, "video_test", root=Path(tmp), delay_s=0)
                    changed = generate_topic_tts(scenes, "video_test", root=Path(tmp), voice="Kore", delay_s=0)
            self.assertEqual(changed[0]["duration"], 2)

    def test_legacy_wav_without_provenance_is_not_relabelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "video_test/audio"
            audio.mkdir(parents=True)
            write_wav(audio / "01.wav")
            with patch.dict("os.environ", {"GEMINI_API_KEY": "test"}):
                with patch(
                    "math_books.tts_engine.synthesize_gemini_tts",
                    side_effect=lambda text, out, *a, **k: write_wav(out, 2),
                ):
                    result = generate_topic_tts([{"id": "01", "text": "new"}], "video_test", root=root, delay_s=0)
            self.assertEqual(result[0]["duration"], 2)

    def test_failed_force_generation_preserves_previous_audio_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenes = [{"id": "01", "text": "old"}]
            with patch.dict("os.environ", {"GEMINI_API_KEY": "test"}):
                with patch(
                    "math_books.tts_engine.synthesize_gemini_tts", side_effect=lambda text, out, *a, **k: write_wav(out)
                ):
                    generate_topic_tts(scenes, "video_test", root=root, delay_s=0)
                meta = json.loads((root / "video_test/audio/manifest.json").read_text())
                audio = root / "video_test/audio" / meta[0]["wav"]
                before = audio.read_bytes()
                manifest_path = root / "video_test/audio/manifest.json"
                manifest = manifest_path.read_bytes()

                def fail(text, out, *args, **kwargs):
                    out.write_bytes(b"partial")
                    raise RuntimeError("service unavailable")

                with patch("math_books.tts_engine.synthesize_gemini_tts", side_effect=fail):
                    with self.assertRaises(RuntimeError):
                        generate_topic_tts(scenes, "video_test", root=root, force=True, delay_s=0)
            self.assertEqual(audio.read_bytes(), before)
            self.assertEqual(manifest_path.read_bytes(), manifest)

    def test_relative_manifest_paths_resolve_from_manifest_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_wav(root / "01.wav")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps([{"id": "01", "wav": "01.wav", "duration": 1}]))
            duration = concat_audio_from_manifest(manifest, root / "out.wav")
            self.assertAlmostEqual(duration, 1.3)


class TestPageMapping(unittest.TestCase):
    def test_explicit_source_page_order_is_preserved(self):
        self.assertEqual(parse_page_spec("14,13", preserve_order=True), [14, 13])

    def fixture(self, root):
        html = root / "input.html"
        html.write_text(
            '<div><div class="page-html" data-rel="14"><div class="pagebox"><p>Page fourteen</p></div></div></div>'
        )
        Image.new("RGB", (100, 100), "red").save(root / "0014.jpg")
        Image.new("RGB", (100, 100), "blue").save(root / "0013.jpg")
        data = root / "mineru.json"
        data.write_text(
            json.dumps(
                {
                    "page_numbers": [13, 14],
                    "pages": [
                        {"page_idx": 0, "blocks": []},
                        {"page_idx": 1, "blocks": [{"type": "image", "bbox": [0, 0, 0.5, 0.5]}]},
                    ],
                }
            )
        )
        return html, data

    def test_subset_keeps_source_page_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, data = self.fixture(root)
            images = crop_mineru_images(data, root, [14], root / "images")
            self.assertEqual(list(images), [14])
            with Image.open(root / "images/p0014_fig1.png") as image:
                self.assertEqual(image.size, (50, 50))

    def test_missing_html_page_fails_before_writing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            html, data = self.fixture(root)
            with self.assertRaisesRegex(ValueError, "HTML.*15"):
                build_markdown(
                    html_path=html, mineru_json_path=data, jpg_dir=root, out_dir=root / "output", page_numbers=[15]
                )
            self.assertFalse((root / "output").exists())

    def test_missing_source_scan_is_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, data = self.fixture(root)
            (root / "0014.jpg").unlink()
            with self.assertRaises(FileNotFoundError):
                crop_mineru_images(data, root, [14], root / "images")

    def test_missing_mapping_requires_explicit_source_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, data = self.fixture(root)
            payload = json.loads(data.read_text())
            del payload["page_numbers"]
            data.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "source.pages|page_numbers"):
                crop_mineru_images(data, root, [14], root / "images")

    def test_invalid_figure_bounds_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, data = self.fixture(root)
            payload = json.loads(data.read_text())
            payload["pages"][1]["blocks"][0]["bbox"] = [-0.5, 0, 1.5, 1]
            data.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "bbox"):
                crop_mineru_images(data, root, [13, 14], root / "images")


class TestVideoVerification(unittest.TestCase):
    def report(self, root, *, silence="", detector_code=0, duration="10", fps="30/1"):
        video = root / "video.mp4"
        video.touch()
        streams = {
            "streams": [
                {"codec_type": "video", "width": 1080, "height": 1920, "duration": duration, "avg_frame_rate": fps},
                {"codec_type": "audio", "duration": "10"},
            ]
        }
        with patch(
            "math_books.video_builder.subprocess.run",
            side_effect=[
                SimpleNamespace(stdout=json.dumps(streams)),
                SimpleNamespace(stderr=silence, returncode=detector_code),
            ],
        ):
            return verify_video(video)

    def test_long_silence_fails_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = self.report(Path(tmp), silence="silence_duration: 10.0")
            self.assertFalse(report["ok"])
            self.assertEqual(report["long_silences_s"], [10.0])

    def test_silence_detector_failure_fails_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(self.report(Path(tmp), detector_code=1)["ok"])

    def test_invalid_duration_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(self.report(Path(tmp), duration="N/A")["ok"])

    def test_wrong_frame_rate_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(self.report(Path(tmp), fps="15/1")["ok"])

    def test_valid_streams_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(self.report(Path(tmp))["ok"])

    def test_real_ffmpeg_silence_is_rejected_and_tone_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            for audio, expected in [
                ("anullsrc=r=24000:cl=mono", False),
                ("sine=frequency=440:sample_rate=24000", True),
            ]:
                video = Path(tmp) / f"{expected}.mp4"
                subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        "color=c=black:s=1080x1920:r=30",
                        "-f",
                        "lavfi",
                        "-i",
                        audio,
                        "-t",
                        "0.8",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "ultrafast",
                        "-c:a",
                        "aac",
                        str(video),
                    ],
                    check=True,
                )
                self.assertEqual(verify_video(video)["ok"], expected)


class TestBuildSafety(unittest.TestCase):
    def test_legacy_audio_requires_regeneration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topic, _ = self.valid_fixture(root)
            path = root / topic.video_dir / "audio/manifest.json"
            manifest = json.loads(path.read_text())
            del manifest[0]["fingerprint"]
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "Untrusted legacy"):
                build_video(topic.key, root=root, skip_render=True)

    def test_changed_example_data_invalidates_silent_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topic, silent = self.valid_fixture(root)
            manifest = json.loads((root / topic.video_dir / "audio/manifest.json").read_text())
            silent.with_suffix(".render.json").write_text(
                json.dumps(
                    {
                        "fingerprint": video_builder.render_fingerprint(topic, root, manifest),
                        "video_sha256": hashlib.sha256(silent.read_bytes()).hexdigest(),
                    }
                )
            )
            (root / "src/math_books/lesson_math.py").write_text("changed example")
            with self.assertRaisesRegex(ValueError, "Stale|Content review"):
                build_video(topic.key, root=root, skip_render=True)

    def test_replaced_silent_mp4_invalidates_render_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topic, silent = self.valid_fixture(root)
            manifest = json.loads((root / topic.video_dir / "audio/manifest.json").read_text())
            silent.with_suffix(".render.json").write_text(
                json.dumps(
                    {
                        "fingerprint": video_builder.render_fingerprint(topic, root, manifest),
                        "video_sha256": hashlib.sha256(silent.read_bytes()).hexdigest(),
                    }
                )
            )
            silent.write_bytes(b"replaced")
            with self.assertRaisesRegex(ValueError, "Stale"):
                build_video(topic.key, root=root, skip_render=True)

    def test_verifying_old_final_after_audio_change_is_not_successful(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.valid_fixture(root)
            with patch("math_books.video_builder.verify_video", return_value={"ok": True, "issues": []}):
                report = video_builder.verify_topic_video(VIDEO_TOPICS["hothand"], root)
            self.assertFalse(report["ok"])

    def test_topic_status_summary_requires_full_media_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topic, _ = self.valid_fixture(root)
            manifest = json.loads((root / topic.video_dir / "audio/manifest.json").read_text())
            output = root / topic.video_dir / topic.output_name
            output.write_bytes(b"corrupt-mp4-bytes")
            provenance = {
                "fingerprint": video_builder.render_fingerprint(topic, root, manifest),
                "audio_sha256": [
                    hashlib.sha256((root / topic.video_dir / "audio" / s["wav"]).read_bytes()).hexdigest()
                    for s in manifest
                ],
                "video_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            }
            output.with_suffix(".build.json").write_text(json.dumps(provenance))

            with patch(
                "math_books.video_builder.verify_video",
                return_value={"ok": False, "issues": ["Long audio silence detected: [2.5]"]},
            ):
                summary = video_builder.topic_status_summary(topic, root)
            self.assertEqual(summary["video"], "stale")
            self.assertFalse(summary["ready"])

            with patch("math_books.video_builder.verify_video", return_value={"ok": True, "issues": []}):
                summary_ok = video_builder.topic_status_summary(topic, root)
            self.assertEqual(summary_ok["video"], "verified")
            self.assertTrue(summary_ok["ready"])

    def valid_fixture(self, root):
        from math_books.voiceover_qa import model_cache, verify_clip

        topic = VIDEO_TOPICS["hothand"]
        audio = root / topic.video_dir / "audio"
        audio.mkdir(parents=True)
        manifest = []
        for index, scene in enumerate(importlib.import_module(topic.tts_module).SCENES):
            wav = audio / f"{scene['id']}.wav"
            write_wav(wav)
            with patch(
                "math_books.voiceover_qa.transcribe_audio",
                return_value=[{"start": 0.0, "end": 1.0, "text": scene["text"]}],
            ):
                verify_clip(wav, scene["text"], audio / "qa", model_cache(root))
            manifest.append(
                {
                    **scene,
                    "wav": wav.name,
                    "duration": 1,
                    "voice": "Puck",
                    "model": "test",
                    "fingerprint": request_fingerprint(scene["text"], "Puck", index),
                    "wav_sha256": hashlib.sha256(wav.read_bytes()).hexdigest(),
                }
            )
        (audio / "manifest.json").write_text(json.dumps(manifest))
        (root / "src/math_books").mkdir(parents=True)
        for name in ("hothand_scene.py", "video_ui.py", "lesson_math.py"):
            shutil.copy2(project_root() / "src/math_books" / name, root / "src/math_books" / name)
        write_review_fixture(
            root, importlib.import_module(topic.tts_module).SCENES, topic.video_dir, scene_file=topic.scene_file
        )
        silent = root / topic.video_dir / "media/hothand_silent.mp4"
        silent.parent.mkdir(parents=True, exist_ok=True)
        silent.write_bytes(b"silent")
        return topic, silent

    def test_skip_render_requires_matching_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.valid_fixture(root)
            with self.assertRaisesRegex(ValueError, "[Ss]tale|untracked"):
                build_video("hothand", root=root, skip_render=True)

    def test_failed_verification_preserves_previous_final_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topic, silent = self.valid_fixture(root)
            output = root / topic.video_dir / topic.output_name
            output.write_bytes(b"previous")
            with (
                patch("math_books.video_builder.render_silent_video", return_value=silent),
                patch(
                    "math_books.video_builder.mux_audio_video", side_effect=lambda a, b, out: out.write_bytes(b"new")
                ),
                patch("math_books.video_builder.verify_video", return_value={"ok": False, "issues": ["bad audio"]}),
            ):
                report = build_video("hothand", root=root)
            self.assertFalse(report["ok"])
            self.assertEqual(output.read_bytes(), b"previous")

    def test_changed_script_is_rejected_before_render_or_mux(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topic = VIDEO_TOPICS["hothand"]
            write_review_fixture(
                root, importlib.import_module(topic.tts_module).SCENES, topic.video_dir, scene_file=topic.scene_file
            )
            audio = root / VIDEO_TOPICS["hothand"].video_dir / "audio"
            audio.mkdir(parents=True)
            write_wav(audio / "01.wav")
            (audio / "manifest.json").write_text(
                json.dumps([{"id": "01", "text": "stale", "wav": "01.wav", "duration": 1}])
            )
            with self.assertRaisesRegex(ValueError, "[Ss]tale|[Ss]cript|[Mm]anifest"):
                build_video("hothand", skip_render=True, root=root)


class TestCliFailures(unittest.TestCase):
    def test_expected_failure_has_concise_error_and_exit_code(self):
        stderr = io.StringIO()
        with patch("math_books.cli.build_video", side_effect=ValueError("stale audio")), redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as error:
                cli.main(["build", "hothand"])
        self.assertEqual(error.exception.code, 1)
        self.assertIn("stale audio", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


class TestMeasuredTiming(unittest.TestCase):
    def test_padding_uses_elapsed_time_instead_of_manual_total(self):
        from math_books.video_ui import VerticalShortScene

        waits = []
        scene = SimpleNamespace(renderer=SimpleNamespace(time=7), _segment_start=2, wait=waits.append)
        VerticalShortScene._pad(scene, 10, 999)
        self.assertEqual(waits, [5])

    def test_load_durations_prefers_manifest_env_over_stale_root_dir(self):
        from math_books.video_ui import VerticalShortScene

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stale_dir = root / "video_buzzer" / "audio"
            stale_dir.mkdir(parents=True)
            (stale_dir / "manifest.json").write_text(json.dumps([{"id": "01_hook", "duration": 3.0}]))
            verified_dir = root / "videos" / "video_buzzer" / "audio"
            verified_dir.mkdir(parents=True)
            verified_manifest = verified_dir / "manifest.json"
            verified_manifest.write_text(json.dumps([{"id": "01_hook", "duration": 10.0}]))

            scene = VerticalShortScene.__new__(VerticalShortScene)
            with patch.dict("os.environ", {"MATH_BOOKS_MANIFEST_PATH": str(verified_manifest)}):
                durations = scene._load_durations("video_buzzer")
            self.assertEqual(durations["01_hook"], 10.0)

    def test_overrun_is_rejected(self):
        from math_books.video_ui import VerticalShortScene

        scene = SimpleNamespace(renderer=SimpleNamespace(time=13), _segment_start=2)
        with self.assertRaisesRegex(ValueError, "exceed|overrun"):
            VerticalShortScene._pad(scene, 10, 0)
