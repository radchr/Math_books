"""Regression tests for pipeline, rendering, ASR QA, music bank, and integrity audit fixes."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from math_books import content_bank, content_review, cue_timeline, lessons, music_tracks, tts_engine, video_builder
from math_books.build_sample_md import build_markdown, crop_mineru_images
from math_books.spoken_text import compare_transcript, normalize_spoken_text
from math_books.uk_tts_providers import StyleTTS2Provider, build_ukrainian_providers, profile_fingerprint
from math_books.visual_blocks import visual_source_files


def _base_translations(extra_labels: dict[str, str] | None = None) -> dict[str, dict]:
    labels = extra_labels or {}
    return {
        "uk": {
            "text": "Двадцять чотири цілих і п'ять десятих відсотка.",
            "title": "Заголовок",
            "body": "Тіло",
            "labels": dict(labels),
        },
        "ru": {
            "text": "Двадцать четыре целых и пять десятых процента.",
            "title": "Заголовок",
            "body": "Тело",
            "labels": dict(labels),
        },
        "en": {"text": "Twenty-four point five percent.", "title": "Title", "body": "Body", "labels": dict(labels)},
    }


class AuditFixesTests(unittest.TestCase):
    def test_exact_frame_clock_has_no_rounding_drift_on_half_frame_durations(self) -> None:
        scenes = [
            {"id": "s1", "duration_s": 5.15, "cues": [{"id": "c1", "target": "body", "at_s": 1.0}]},
            {"id": "s2", "duration_s": 5.95, "cues": [{"id": "c2", "target": "body", "at_s": 2.0}]},
            {"id": "s3", "duration_s": 4.15, "cues": [{"id": "c3", "target": "body", "at_s": 0.5}]},
        ]
        timeline = cue_timeline.timed_event_timeline(scenes)
        offset = Fraction(0)
        for scene in scenes:
            dur = Fraction(str(scene["duration_s"]))
            start_frame = round(offset * 30)
            end_frame = round((offset + dur) * 30)
            ev = timeline[scene["id"]][0]
            self.assertEqual(ev["global_frame"] - start_frame, ev["frame"])
            next_offset = offset + dur + Fraction(2, 5)
            self.assertEqual(round(next_offset * 30), end_frame + 12)
            offset = next_offset

    def test_optional_cue_targets_and_color_roles_validated_at_load_time(self) -> None:
        base_lesson = {
            "schema_version": 1,
            "topic": "demo_opt",
            "audio_mode": "music_only",
            "music_track": "calm_science",
            "scenes": [
                {
                    "id": "s1",
                    "duration_s": 4.0,
                    "translations": _base_translations({"a": "A", "b": "B"}),
                    "visual": {
                        "template": "compare_bars",
                        "params": {"items": [{"id": "a", "value": "0.5"}, {"id": "b", "value": "0.3"}]},
                    },
                    "cues": [{"id": "c1", "target": "bar_3", "at_s": 1.0}],
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "Cue target"):
            lessons.validate_lesson_data(base_lesson, "demo_opt", "uk")

        base_lesson["scenes"][0]["cues"] = [{"id": "c1", "target": "winner", "at_s": 1.0}]
        with self.assertRaisesRegex(ValueError, "Cue target"):
            lessons.validate_lesson_data(base_lesson, "demo_opt", "uk")

        base_lesson["scenes"][0]["cues"] = [{"id": "c1", "target": "bar_2", "at_s": 1.0}]
        base_lesson["scenes"][0]["visual"]["params"]["items"][0]["color"] = "neon_pink"
        with self.assertRaisesRegex(ValueError, "unknown color role"):
            lessons.validate_lesson_data(base_lesson, "demo_opt", "uk")

        base_lesson["scenes"][0]["visual"]["params"]["items"][0]["color"] = "primary"
        rows = lessons.validate_lesson_data(base_lesson, "demo_opt", "uk")
        self.assertEqual(len(rows), 1)

    def test_schema_version_rejects_boolean_true(self) -> None:
        with self.assertRaises(ValueError):
            lessons.validate_lesson_data({"schema_version": True, "topic": "x", "scenes": []}, "x", "uk")
        with self.assertRaises(ValueError):
            content_bank.validate_bank_entry({"schema_version": True, "id": "x"})

    def test_visual_source_files_includes_basketball_pack_init(self) -> None:
        root = video_builder.project_root()
        names = {p.relative_to(root).as_posix() for p in visual_source_files()}
        self.assertIn("src/math_books/packs/basketball/__init__.py", names)

    def test_verify_topic_audio_handles_music_only_without_creating_audio_dir(self) -> None:
        root = video_builder.project_root()
        topic = video_builder.get_topic("perelman_echo_distance", "uk", root)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            shutil.copytree(root / "content", tmp_root / "content")
            shutil.copytree(root / "assets", tmp_root / "assets")
            shutil.copytree(root / "content_reviews", tmp_root / "content_reviews")
            shutil.copytree(root / "src", tmp_root / "src")
            # Refresh temp-only review hash for the modified localized_lesson_scene.py
            import hashlib

            dossier_path = tmp_root / "content_reviews/uk/perelman_echo_distance.json"
            dossier = json.loads(dossier_path.read_text(encoding="utf-8"))
            dossier["scene_sha256"] = hashlib.sha256((tmp_root / topic.scene_file).read_bytes()).hexdigest()
            dossier["supporting_files"] = {
                name: hashlib.sha256((tmp_root / name).read_bytes()).hexdigest()
                for name in content_review.SUPPORTING_FILES
                if (tmp_root / name).is_file()
            }
            digest = content_review.dossier_digest(dossier)
            for rev in dossier["reviews"].values():
                rev["dossier_sha256"] = digest
            dossier_path.write_text(json.dumps(dossier, ensure_ascii=False, indent=2), encoding="utf-8")

            report = video_builder.verify_topic_audio(topic, tmp_root)
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["audio_mode"], "music_only")
            self.assertFalse((tmp_root / topic.video_dir / "audio").exists())

    def test_render_fingerprint_changes_when_image_stage_asset_changes(self) -> None:
        root = video_builder.project_root()
        topic = video_builder.get_topic("perelman_echo_distance", "uk", root)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            shutil.copytree(root / "content", tmp_root / "content")
            shutil.copytree(root / "assets", tmp_root / "assets")
            shutil.copytree(root / "src", tmp_root / "src")
            scenes = video_builder.topic_scenes(topic, tmp_root)
            manifest = [{"id": s["id"], "duration": float(s["duration_s"])} for s in scenes]
            fp1 = video_builder.render_fingerprint(topic, tmp_root, manifest)
            svg = tmp_root / "assets/diagrams/echo_wave.svg"
            svg.write_text(svg.read_text(encoding="utf-8") + "\n<!-- modified -->\n", encoding="utf-8")
            fp2 = video_builder.render_fingerprint(topic, tmp_root, manifest)
            self.assertNotEqual(fp1, fp2)

    def test_gemini_and_lyria_empty_candidates_raise_runtime_error(self) -> None:
        class FakeResp:
            status_code = 200
            text = '{"candidates": []}'

            def json(self):
                return {"candidates": []}

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.wav"
            with patch("math_books.tts_engine.httpx.post", return_value=FakeResp()):
                with self.assertRaises(RuntimeError):
                    tts_engine.synthesize_gemini_tts("hello", out, "secret-key")
            with patch("math_books.music_tracks.httpx.post", return_value=FakeResp()):
                with self.assertRaises(RuntimeError):
                    music_tracks.synthesize_lyria_wav("upbeat", out, api_key="secret-key")

    def test_music_import_rejects_blank_metadata_and_does_not_corrupt_existing_wav(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            src_wav = tmp_root / "source.wav"
            music_tracks.synthesize_procedural_wav(src_wav, preset="calm", duration_s=4.0)
            with self.assertRaisesRegex(ValueError, "title"):
                music_tracks.import_music_track(
                    tmp_root, src_wav, track_id="bad_meta", title="   ", license_str="CC0-1.0", author="Me"
                )
            # Existing track registered under another filename must fail before writing dest_wav
            music_tracks.generate_music_track(
                tmp_root, track_id="track_one", backend="procedural", preset="calm", duration_s=4.0
            )
            with self.assertRaises(FileExistsError):
                music_tracks.import_music_track(
                    tmp_root,
                    src_wav,
                    track_id="track_one",
                    title="Dup",
                    license_str="CC0-1.0",
                    author="Me",
                    overwrite=False,
                )

    def test_styletts2_extract_audio_path_prefers_path_key_and_existing_file(self) -> None:
        provider = StyleTTS2Provider("styletts2", "v", space="s")
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "out.wav"
            real.write_bytes(b"RIFF")
            self.assertEqual(
                provider._extract_audio_path({"orig_name": "foo.wav", "mime_type": "audio/wav", "path": str(real)}),
                real,
            )
            self.assertEqual(provider._extract_audio_path(["Done!", str(real)]), real)

    def test_piper_profile_fingerprint_is_portable_across_project_roots(self) -> None:
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            p1, prov1 = build_ukrainian_providers(Path(t1))
            p2, prov2 = build_ukrainian_providers(Path(t2))
            self.assertEqual(profile_fingerprint(p1, prov1), profile_fingerprint(p2, prov2))

    def test_path_traversal_blocked_in_digitize_and_audio_concat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "out"
            out_dir.mkdir()
            html = root / "doc.html"
            html.write_text(
                '<div class="page-html" data-rel="1"><div class="pagebox"><p>Hello</p></div></div>',
                encoding="utf-8",
            )
            mineru = root / "mineru.json"
            mineru.write_text('{"pdf_info": [{"preproc_blocks": []}]}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "escapes"):
                build_markdown(
                    html_path=html,
                    mineru_json_path=mineru,
                    jpg_dir=root,
                    out_dir=out_dir,
                    page_numbers=[1],
                    output_filename="../escape.md",
                    source_page_numbers=[1],
                )

            audio_dir = root / "audio"
            audio_dir.mkdir()
            outside = root / "outside.wav"
            music_tracks.synthesize_procedural_wav(outside, preset="calm", duration_s=4.0)
            manifest = audio_dir / "manifest.json"
            manifest.write_text(json.dumps([{"id": "s1", "wav": "../outside.wav", "duration": 4.0}]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "escapes"):
                video_builder.concat_audio_from_manifest(manifest, root / "full.wav")

    def test_crop_mineru_rejects_bool_bbox(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new("RGB", (100, 100)).save(root / "page_0001.jpg")
            mineru = root / "mineru.json"
            mineru.write_text(
                json.dumps({"pdf_info": [{"preproc_blocks": [{"type": "image", "bbox": [False, 0.0, True, 0.5]}]}]}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                crop_mineru_images(
                    mineru_json_path=mineru,
                    jpg_dir=root,
                    page_numbers=[1],
                    images_out_dir=root / "imgs",
                )

    def test_asr_qa_zero_thousand_and_compound_hyphens_and_uk_decimals(self) -> None:
        self.assertFalse(compare_transcript("zero thousand", "1000", language="en")["ok"])
        self.assertFalse(compare_transcript("нуль тисяч", "1000", language="uk")["ok"])
        self.assertNotIn("#minus", normalize_spoken_text("three-pointer", "en"))
        self.assertNotIn("#minus", normalize_spoken_text("будь-який", "uk"))
        self.assertNotIn("минус", normalize_spoken_text("из-за", "ru"))
        self.assertTrue(
            compare_transcript("24.5%", "двадцять чотири цілих і п'ять десятих відсотка", language="uk")["ok"]
        )
        self.assertTrue(compare_transcript("51.2%", "п'ятдесят один і два десятих відсотка", language="uk")["ok"])

    def test_resolve_cues_handles_multiword_uk_decimal_and_leading_punctuation(self) -> None:
        row = {
            "id": "s1",
            "cues": [{"id": "c1", "target": "formula", "anchor": "start", "occurrence": 1, "phrase": "24.5"}],
        }
        words = [
            {"word": "—", "start": 0.1, "end": 0.2},
            {"word": "двадцять", "start": 0.5, "end": 0.7},
            {"word": "чотири", "start": 0.7, "end": 0.9},
            {"word": "цілих", "start": 0.9, "end": 1.1},
            {"word": "і", "start": 1.1, "end": 1.2},
            {"word": "п'ять", "start": 1.2, "end": 1.4},
            {"word": "десятих", "start": 1.4, "end": 1.7},
            {"word": "відсотка", "start": 1.7, "end": 2.0},
        ]
        events = cue_timeline.resolve_cues(row, words, "uk", duration=3.0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["frame"], round(0.5 * 30))

    def test_sync_bank_index_does_not_corrupt_sqlite_on_invalid_json(self) -> None:
        root = video_builder.project_root()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            shutil.copytree(root / "content", tmp_root / "content")
            shutil.copytree(root / "assets", tmp_root / "assets")
            initial = content_bank.query_bank(tmp_root)
            self.assertGreater(len(initial), 0)

            bad = tmp_root / "content/bank/broken.json"
            bad.write_text("{not json", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                content_bank.sync_bank_index(tmp_root)
            bad.unlink()

            after = content_bank.query_bank(tmp_root)
            self.assertEqual(len(after), len(initial))

    def test_check_content_review_returns_error_dict_for_invalid_ru_topic(self) -> None:
        report = content_review.check_content_review(
            [{"id": "s1", "text": "hello"}],
            "video_Bad.Topic!",
            video_builder.project_root(),
            language="ru",
        )
        self.assertFalse(report["ok"])
        self.assertTrue(report["issues"])


if __name__ == "__main__":
    unittest.main()
