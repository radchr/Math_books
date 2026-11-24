"""Mandatory editorial review must fail closed before expensive production work."""

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from review_fixtures import approve_fixture, write_review_fixture

from math_books import cli, content_review
from math_books.tts_engine import generate_topic_tts
from math_books.video_builder import VIDEO_TOPICS, build_video, render_silent_video, verify_topic_video

SCENES = [{"id": "01", "text": "Считаем ожидаемые очки."}]
UNSET = object()


class TestContentReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path, self.dossier = write_review_fixture(self.root, SCENES)

    def check(self, dossier=UNSET, scenes=None):
        if dossier is not UNSET:
            self.path.write_text(json.dumps(dossier))
        return content_review.check_content_review(scenes or SCENES, "video_test", self.root)

    def test_complete_current_review_passes(self):
        self.assertTrue(self.check()["ok"])

    def test_missing_review_fails_with_actionable_path(self):
        self.path.unlink()
        report = self.check()
        self.assertFalse(report["ok"])
        self.assertIn("content_reviews/test.json", " ".join(report["issues"]))

    def test_script_edit_invalidates_approval(self):
        self.assertFalse(self.check(scenes=[{"id": "01", "text": "Изменённое утверждение."}])["ok"])

    def test_visual_edit_invalidates_approval(self):
        (self.root / "synthetic_scene.py").write_text("changed visual formula")
        self.assertFalse(self.check()["ok"])

    def test_supporting_math_and_ui_edits_invalidate_approval(self):
        for name in ("lesson_math.py", "video_ui.py"):
            with self.subTest(name=name):
                support = self.root / "src/math_books" / name
                support.parent.mkdir(parents=True, exist_ok=True)
                support.write_text("original helper")
                self.path, dossier = write_review_fixture(self.root, SCENES)
                self.assertTrue(self.check(dossier)["ok"])
                support.write_text("changed helper")
                self.assertFalse(self.check()["ok"])

    def test_wrong_target_age_is_not_approved_for_this_project(self):
        self.dossier["pedagogy"]["audience_age"] = 18
        approve_fixture(self.dossier)
        self.assertFalse(self.check(self.dossier)["ok"])

    def test_conflicting_duplicate_json_keys_are_rejected(self):
        raw = json.dumps(self.dossier).replace(
            '"verdict": "approved"', '"verdict": "changes_required", "verdict": "approved"', 1
        )
        self.path.write_text(raw)
        report = self.check()
        self.assertFalse(report["ok"])
        self.assertIn("duplicate", " ".join(report["issues"]).lower())

    def test_booleans_are_not_numeric_scientific_values(self):
        for field in ("schema_version", "probability", "expected"):
            dossier = copy.deepcopy(self.dossier)
            if field == "schema_version":
                dossier[field] = True
            else:
                dossier["math_checks"][0].update(probability="1", points=1, expected="1")
                dossier["math_checks"][0][field] = True
            approve_fixture(dossier)
            with self.subTest(field=field):
                self.assertFalse(self.check(dossier)["ok"])

    def test_nonfinite_numeric_inputs_return_structured_failure(self):
        self.path.write_text(json.dumps(self.dossier).replace('"0.35"', "1e999"))
        self.assertFalse(self.check()["ok"])

    def test_source_or_teaching_edit_requires_new_review(self):
        for field in ("learning_objective", "challenge", "assumptions"):
            dossier = copy.deepcopy(self.dossier)
            dossier["pedagogy"][field] = ["Changed"] if field == "assumptions" else "Changed teaching aim"
            with self.subTest(field=field):
                self.assertFalse(self.check(dossier)["ok"])

    def test_pending_or_rejected_or_missing_discipline_blocks(self):
        for verdict in ("pending", "changes_required", None):
            dossier = copy.deepcopy(self.dossier)
            if verdict is None:
                del dossier["reviews"]["pedagogical"]
            else:
                dossier["reviews"]["scientific"]["verdict"] = verdict
            with self.subTest(verdict=verdict):
                self.assertFalse(self.check(dossier)["ok"])

    def test_failed_criterion_blocks_even_with_approved_verdict(self):
        self.dossier["reviews"]["scientific"]["criteria"]["calculations_correct"]["passed"] = False
        self.assertFalse(self.check(self.dossier)["ok"])

    def test_missing_criterion_rationale_blocks(self):
        self.dossier["reviews"]["pedagogical"]["criteria"]["age_and_prerequisites"]["rationale"] = ""
        self.assertFalse(self.check(self.dossier)["ok"])

    def test_wrong_arithmetic_blocks_even_after_approval(self):
        self.dossier["math_checks"][0]["expected"] = "1.5"
        approve_fixture(self.dossier)
        report = self.check(self.dossier)
        self.assertFalse(report["ok"])
        self.assertIn("score", " ".join(report["issues"]))

    def test_coin_check_verifies_both_estimators(self):
        self.dossier["math_checks"] = [
            {"id": "coin", "kind": "fair_coin_followups", "expected_sequence_mean": "5/12", "expected_pooled": "1/2"}
        ]
        self.dossier["scene_reviews"][0]["claims"][0]["math_check_ids"] = ["coin"]
        approve_fixture(self.dossier)
        self.assertTrue(self.check(self.dossier)["ok"])
        self.dossier["math_checks"][0]["expected_pooled"] = "5/12"
        approve_fixture(self.dossier)
        self.assertFalse(self.check(self.dossier)["ok"])

    def test_independent_attempts_check_matches_complement_rule(self):
        for probability, expected in (("7/10", "91/100"), ("4/5", "24/25")):
            self.dossier["math_checks"] = [
                {
                    "id": "attempts",
                    "kind": "independent_attempts",
                    "probability": probability,
                    "attempts": 2,
                    "expected_at_least_one": expected,
                }
            ]
            self.dossier["scene_reviews"][0]["claims"][0]["math_check_ids"] = ["attempts"]
            approve_fixture(self.dossier)
            self.assertTrue(self.check(self.dossier)["ok"])
        self.dossier["math_checks"][0]["expected_at_least_one"] = "4/5"
        approve_fixture(self.dossier)
        self.assertFalse(self.check(self.dossier)["ok"])

    def test_unsupported_claim_or_unknown_reference_blocks(self):
        for kind, sources, checks in [("empirical", [], []), ("mathematical", [], ["missing"])]:
            dossier = copy.deepcopy(self.dossier)
            claim = dossier["scene_reviews"][0]["claims"][0]
            claim.update(kind=kind, source_ids=sources, math_check_ids=checks)
            approve_fixture(dossier)
            self.assertFalse(self.check(dossier)["ok"])

    def test_missing_scene_coverage_blocks(self):
        self.dossier["scene_reviews"] = []
        approve_fixture(self.dossier)
        self.assertFalse(self.check(self.dossier)["ok"])

    def test_empty_script_cannot_receive_a_passing_report(self):
        path, _ = write_review_fixture(self.root, [])
        self.assertTrue(path.exists())
        self.assertFalse(content_review.check_content_review([], "video_test", self.root)["ok"])

    def test_source_locator_edit_invalidates_review(self):
        self.dossier["sources"] = [
            {
                "id": "paper",
                "kind": "primary",
                "title": "Primary evidence",
                "url": "https://example.org/paper",
                "locator": "Table 1",
            }
        ]
        approve_fixture(self.dossier)
        self.assertTrue(self.check(self.dossier)["ok"])
        self.dossier["sources"][0]["locator"] = "Table 2"
        self.assertFalse(self.check(self.dossier)["ok"])

    def test_malformed_json_shapes_fail_without_traceback(self):
        for malformed in (
            [],
            None,
            {"reviews": []},
            {**self.dossier, "math_checks": [None]},
            {**self.dossier, "reviews": {"scientific": []}},
        ):
            with self.subTest(malformed=malformed):
                self.assertFalse(self.check(malformed)["ok"])

    def test_template_is_pending(self):
        dossier = content_review.make_review_template("test", SCENES, "synthetic_scene.py", self.root)
        self.assertFalse(self.check(dossier)["ok"])


class TestProductionGate(unittest.TestCase):
    def test_verify_reports_editorial_rejection_before_media_io(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = verify_topic_video(VIDEO_TOPICS["hothand"], root)
            self.assertFalse(report["ok"])
            self.assertFalse(report["media_checked"])
            self.assertFalse(report["editorial"]["ok"])
            self.assertFalse((root / "video_hothand").exists())

    def test_registered_tts_rejects_old_caller_script_even_if_previously_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topic = VIDEO_TOPICS["hothand"]
            write_review_fixture(root, SCENES, topic.video_dir, scene_file=topic.scene_file)
            import math_books.generate_hothand_tts as current

            with patch.object(current, "SCENES", [{"id": "01", "text": "New registered narration"}]):
                with self.assertRaisesRegex(ValueError, "[Ss]cript|[Nn]arration"):
                    generate_topic_tts(SCENES, topic.video_dir, root=root)
            self.assertFalse((root / topic.video_dir / "audio").exists())

    def test_init_does_not_overwrite_an_existing_dossier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            topic = VIDEO_TOPICS["hothand"]
            import importlib

            path, _ = write_review_fixture(
                root, importlib.import_module(topic.tts_module).SCENES, topic.video_dir, scene_file=topic.scene_file
            )
            before = path.read_bytes()
            with patch("math_books.cli.project_root", return_value=root), patch("sys.stderr", io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    cli.main(["review", "hothand", "--init"])
            self.assertEqual(error.exception.code, 1)
            self.assertEqual(path.read_bytes(), before)

    def test_unapproved_force_tts_stops_before_api_or_audio_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "[Cc]ontent review"):
                generate_topic_tts(SCENES, "video_test", root=root, force=True)
            self.assertFalse((root / "video_test/audio").exists())

    def test_cached_audio_does_not_bypass_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "video_test/audio"
            audio.mkdir(parents=True)
            (audio / "01.wav").write_bytes(b"old audio")
            with self.assertRaisesRegex(ValueError, "[Cc]ontent review"):
                generate_topic_tts(SCENES, "video_test", root=root)
            self.assertEqual((audio / "01.wav").read_bytes(), b"old audio")

    def test_skip_render_still_requires_review_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "[Cc]ontent review"):
                build_video("hothand", root=Path(tmp), skip_render=True)
            self.assertFalse((Path(tmp) / "video_hothand").exists())

    def test_direct_renderer_requires_review_before_starting_manim(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "[Cc]ontent review"):
                render_silent_video(VIDEO_TOPICS["hothand"], root=Path(tmp))

    def test_cli_reports_blocked_review_as_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp, patch("math_books.cli.project_root", return_value=Path(tmp)):
            output = io.StringIO()
            with redirect_stdout(output), self.assertRaises(SystemExit) as error:
                cli.main(["review", "hothand"])
            self.assertEqual(error.exception.code, 1)
            self.assertFalse(json.loads(output.getvalue())["ok"])
