"""Future lessons: explicit language, complete captions and isolated identities."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from math_books.lessons import lesson_digest, load_lesson


def lesson_fixture():
    return {
        "schema_version": 1,
        "topic": "language_demo",
        "scenes": [
            {
                "id": "01_example",
                "formula": "1+1=2",
                "translations": {
                    "uk": {"text": "Один плюс один дорівнює двом.", "title": "Додавання", "body": "Разом два"},
                    "ru": {"text": "Один плюс один равняется двум.", "title": "Сложение", "body": "Вместе два"},
                    "en": {"text": "One plus one equals two.", "title": "Addition", "body": "Two in total"},
                },
            }
        ],
    }


def write_lesson(root, data=None):
    path = root / "content/lessons/language_demo.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data or lesson_fixture(), ensure_ascii=False))
    return path


class TestLessons(unittest.TestCase):
    def test_future_topics_have_isolated_paths_and_legacy_is_not_translated(self):
        from math_books.video_builder import get_topic, topic_scenes

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_lesson(root)
            for lang in ("uk", "ru", "en"):
                topic = get_topic("language_demo", lang, root)
                self.assertEqual(topic.language, lang)
                self.assertEqual(topic.video_dir, f"videos/video_language_demo/{lang}")
                self.assertEqual(
                    topic_scenes(topic, root)[0]["title"], lesson_fixture()["scenes"][0]["translations"][lang]["title"]
                )
            with self.assertRaisesRegex(ValueError, "legacy|Legacy"):
                get_topic("buzzer", "uk", root)

    def test_review_is_bound_to_language_and_caption_content(self):
        from math_books.content_review import check_content_review, make_review_template

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_lesson(root)
            scene = root / "synthetic.py"
            scene.write_text("# synthetic scene")
            scenes = load_lesson(root, "language_demo", "uk")
            dossier = make_review_template("language_demo", scenes, "synthetic.py", root, language="uk")
            self.assertEqual(dossier["language"], "uk")
            self.assertEqual(dossier["localized_content_sha256"], lesson_digest(scenes))
            report = check_content_review(scenes, "videos/video_language_demo/uk", root, language="uk")
            self.assertEqual(Path(report["review_path"]), root / "content_reviews/uk/language_demo.json")
            path = Path(report["review_path"])
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(dossier))
            data = lesson_fixture()
            data["scenes"][0]["translations"]["uk"]["body"] = "Змінений підпис"
            write_lesson(root, data)
            report = check_content_review(scenes, "videos/video_language_demo/uk", root, language="uk")
            self.assertFalse(report["ok"])
            self.assertIn("content", " ".join(report["issues"]).lower())

    def test_localized_script_and_captions_have_same_scene_and_formula(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_lesson(root)
            versions = [load_lesson(root, "language_demo", lang) for lang in ("uk", "ru", "en")]
            self.assertEqual([s[0]["id"] for s in versions], ["01_example"] * 3)
            self.assertEqual([s[0]["formula"] for s in versions], ["1+1=2"] * 3)
            self.assertEqual(len({s[0]["text"] for s in versions}), 3)
            self.assertEqual(len({lesson_digest(s) for s in versions}), 3)

    def test_incomplete_language_invalid_ids_and_unsafe_math_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for mutation in ("missing", "blank", "duplicate", "formula"):
                data = copy.deepcopy(lesson_fixture())
                if mutation == "missing":
                    del data["scenes"][0]["translations"]["uk"]
                elif mutation == "blank":
                    data["scenes"][0]["translations"]["en"]["body"] = ""
                elif mutation == "duplicate":
                    data["scenes"].append(copy.deepcopy(data["scenes"][0]))
                else:
                    data["scenes"][0]["formula"] = r"\input{private}"
                write_lesson(root, data)
                with self.assertRaises(ValueError, msg=mutation):
                    load_lesson(root, "language_demo", "ru")

    def test_missing_topic_and_unknown_language_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_lesson(root)
            for key, lang in (("../escape", "uk"), ("language_demo", "de")):
                with self.assertRaises(ValueError):
                    load_lesson(root, key, lang)
