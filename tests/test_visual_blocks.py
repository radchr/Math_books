"""Tests for modular themes, domain packs, 3-language visual blocks, 9:16 bounds showcase, and check registry."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from math_books.content_review import CHECK_REGISTRY, check_content_review, make_review_template, register_math_check
from math_books.languages import SUPPORTED_LANGUAGES
from math_books.lessons import validate_lesson_data
from math_books.packs import get_pack, list_packs
from math_books.themes import get_theme, list_themes, ui_string
from math_books.video_ui import VerticalShortScene, configure_vertical_9_16
from math_books.visual_blocks import list_visual_blocks, visual_block_catalog


def _sample_rows_for_all_blocks() -> dict[str, dict]:
    return {
        "text_card": {
            "id": "s_card",
            "title": {
                "uk": "Порівняння стратегій у вирішальній атаці",
                "ru": "Сравнение стратегий в решающей атаке",
                "en": "Comparing Strategies in a Final Possession",
            },
            "body": {
                "uk": "Коли три незалежні події мають відбутися підряд, їхні ймовірності перемножуються.",
                "ru": "Когда три независимых события должны случиться подряд, их вероятности перемножаются.",
                "en": "When three independent events must all happen in sequence, their probabilities multiply.",
            },
            "formula": r"0.7 \times 0.5 \times 0.7 = 0.245",
        },
        "hook_choice": {
            "id": "s_hook",
            "visual": {
                "template": "hook_choice",
                "params": {"option_a": "opt_a", "option_b": "opt_b", "value_a": "30%", "value_b": "70% -> 50% -> 70%"},
            },
            "title": {"uk": "Який план кращий?", "ru": "Какой план лучше?", "en": "Which Plan Is Better?"},
            "body": {
                "uk": "Обери інтуїтивно до того, як побачиш точний розрахунок.",
                "ru": "Выбери интуитивно до того, как увидишь точный расчёт.",
                "en": "Make an intuitive prediction before seeing the exact calculation.",
            },
            "labels": {
                "uk": {"opt_a": "Один дальній кидок через захисника", "opt_b": "Швидкі два очки, фол і ще два"},
                "ru": {"opt_a": "Один дальний бросок через защитника", "opt_b": "Быстрые два очка, фол и ещё два"},
                "en": {"opt_a": "One contested three-point shot", "opt_b": "Quick two points, foul, and another two"},
            },
        },
        "compare_bars": {
            "id": "s_bars",
            "visual": {
                "template": "compare_bars",
                "params": {
                    "items": [
                        {"id": "plan_a", "value": "3/10", "color": "primary"},
                        {"id": "plan_b", "value": "49/200", "color": "secondary"},
                    ],
                    "unit": "%",
                    "winner": "plan_a",
                },
            },
            "title": {"uk": "Точне порівняння", "ru": "Точное сравнение", "en": "Exact Comparison"},
            "body": {
                "uk": "Висота стовпчиків пропорційна шансам.",
                "ru": "Высота столбцов пропорциональна шансам.",
                "en": "Bar heights are proportional to chances.",
            },
            "labels": {
                "uk": {"plan_a": "Дальній кидок", "plan_b": "Ланцюжок із трьох кроків"},
                "ru": {"plan_a": "Дальний бросок", "ru_extra": "ok", "plan_b": "Цепочка из трёх шагов"},
                "en": {"plan_a": "Direct Three", "plan_b": "Three-Step Chain"},
            },
            "formula": "0.30 > 0.245",
        },
        "step_chain": {
            "id": "s_chain",
            "visual": {
                "template": "step_chain",
                "params": {
                    "steps": [
                        {"label": "st1", "value": "70%"},
                        {"label": "st2", "value": "50%"},
                        {"label": "st3", "value": "70%"},
                    ],
                    "result": "24.5%",
                },
            },
            "title": {"uk": "Ланцюжок подій", "ru": "Цепочка событий", "en": "Chain of Events"},
            "body": {
                "uk": "Кожен наступний крок зменшує підсумок.",
                "ru": "Каждый следующий шаг уменьшает итог.",
                "en": "Every additional step shrinks the total.",
            },
            "labels": {
                "uk": {
                    "st1": "Швидкий прохід під кільце",
                    "st2": "Суперник схибить штрафний",
                    "st3": "Влучна відповідь на два",
                },
                "ru": {
                    "st1": "Быстрый проход под кольцо",
                    "st2": "Соперник промахнётся штрафной",
                    "st3": "Точный ответ на два",
                },
                "en": {
                    "st1": "Quick drive to the rim",
                    "st2": "Opponent misses a free throw",
                    "st3": "Game-tying two-pointer",
                },
            },
            "formula": r"0.7 \cdot 0.5 \cdot 0.7 = 0.245",
        },
        "challenge_card": {
            "id": "s_chal",
            "visual": {
                "template": "challenge_card",
                "params": {"answer_label": "ans", "limit_label": "lim"},
            },
            "title": {"uk": "Челендж", "ru": "Челлендж", "en": "Challenge"},
            "body": {
                "uk": "Якщо шанс кожного з трьох кроків 80%, чи перевищить підсумок 50%?",
                "ru": "Если шанс каждого из трёх шагов 80%, превысит ли итог 50%?",
                "en": "If each of three steps has an 80% chance, does the combined chance exceed 50%?",
            },
            "labels": {
                "uk": {"ans": "Так, 51,2%", "lim": "Це оцінка моделі, а не гарантія одного матчу."},
                "ru": {"ans": "Да, 51,2%", "lim": "Это оценка модели, а не гарантия одного матча."},
                "en": {"ans": "Yes, 51.2%", "lim": "This is a model estimate, not a single-game guarantee."},
            },
            "formula": "0.8^3 = 0.512",
        },
        "basketball.half_court_diagram": {
            "id": "s_court",
            "visual": {
                "template": "basketball.half_court_diagram",
                "params": {
                    "markers": [
                        {"id": "p1", "x": -2.0, "y": -0.6, "color": "primary"},
                        {"id": "p2", "x": 2.0, "y": -0.6, "color": "secondary"},
                        {"id": "p3", "x": 0.0, "y": 1.2, "color": "positive"},
                    ],
                    "arrows": [{"from": "p1", "to": "p2"}, {"from": "p2", "to": "p3"}],
                },
            },
            "title": {"uk": "Трикутник на майданчику", "ru": "Треугольник на площадке", "en": "Court Triangle"},
            "body": {
                "uk": "Три точки передачі розтягують захист.",
                "ru": "Три точки передачи растягивают защиту.",
                "en": "Three passing spots stretch the defense.",
            },
            "labels": {
                "uk": {"p1": "Розігруючий", "p2": "Фланг", "p3": "Центр"},
                "ru": {"p1": "Разыгрывающий", "p2": "Фланг", "p3": "Центр"},
                "en": {"p1": "Point Guard", "p2": "Wing", "p3": "Post"},
            },
        },
        "basketball.scoreboard_duel": {
            "id": "s_score",
            "visual": {
                "template": "basketball.scoreboard_duel",
                "params": {"score": "98 : 101", "clock": "0:10"},
            },
            "title": {"uk": "Останні десять секунд", "ru": "Последние десять секунд", "en": "Final Ten Seconds"},
            "body": {
                "uk": "Твоя команда поступається три очки.",
                "ru": "Твоя команда уступает три очка.",
                "en": "Your team trails by three points.",
            },
        },
    }


class TestVisualBlocksAndPacks(unittest.TestCase):
    def test_core_and_basketball_pack_are_registered(self):
        packs = list_packs()
        self.assertIn("basketball", packs)
        self.assertEqual(get_pack("basketball").default_theme, "basketball_dark")

        themes = list_themes()
        self.assertTrue({"neutral_dark", "science_lab", "basketball_dark"} <= set(themes))
        self.assertEqual(get_theme("basketball_dark").name, "basketball_dark")

        blocks = list_visual_blocks()
        expected = {
            "text_card",
            "hook_choice",
            "compare_bars",
            "step_chain",
            "challenge_card",
            "basketball.half_court_diagram",
            "basketball.scoreboard_duel",
        }
        self.assertTrue(expected <= set(blocks))
        catalog_names = {entry["name"] for entry in visual_block_catalog()}
        self.assertEqual(catalog_names, set(blocks))

        for lang in SUPPORTED_LANGUAGES:
            self.assertTrue(ui_string("pause", lang))
            self.assertTrue(ui_string("basketball.scoreboard", lang))

    def test_validate_lesson_data_rejects_missing_label_or_bad_cue_target(self):
        base = {
            "schema_version": 1,
            "topic": "demo_visual",
            "domain": "basketball",
            "scenes": [
                {
                    "id": "01_bars",
                    "visual": {
                        "template": "compare_bars",
                        "params": {
                            "items": [{"id": "a", "value": "3/10"}, {"id": "b", "value": "1/4"}],
                            "winner": "a",
                        },
                    },
                    "cues": [
                        {
                            "id": "show_winner",
                            "target": "winner",
                            "anchor": "start",
                            "occurrence": 1,
                            "phrases": {"uk": "тридцять", "ru": "тридцать", "en": "thirty"},
                        }
                    ],
                    "translations": {
                        "uk": {
                            "text": "Тридцять відсотків.",
                            "title": "Т",
                            "body": "Б",
                            "labels": {"a": "А", "b": "Б"},
                        },
                        "ru": {
                            "text": "Тридцать процентов.",
                            "title": "Т",
                            "body": "Б",
                            "labels": {"a": "А", "b": "Б"},
                        },
                        "en": {"text": "Thirty percent.", "title": "T", "body": "B", "labels": {"a": "A", "b": "B"}},
                    },
                }
            ],
        }
        rows = validate_lesson_data(base, "demo_visual", "uk")
        self.assertEqual(rows[0]["theme"], "basketball_dark")
        self.assertEqual(rows[0]["visual"]["template"], "compare_bars")
        self.assertEqual(rows[0]["cues"][0]["target"], "winner")

        missing_label = json.loads(json.dumps(base))
        del missing_label["scenes"][0]["translations"]["en"]["labels"]["b"]
        with self.assertRaisesRegex(ValueError, "missing non-empty label 'b'"):
            validate_lesson_data(missing_label, "demo_visual", "uk")

        bad_cue = json.loads(json.dumps(base))
        bad_cue["scenes"][0]["cues"][0]["target"] = "nonexistent_target"
        with self.assertRaisesRegex(ValueError, "Cue target must be unique and supported"):
            validate_lesson_data(bad_cue, "demo_visual", "uk")

    def test_three_language_9_16_showcase_fits_safe_bounds(self):
        from manim import Text, tempconfig

        configure_vertical_9_16()
        samples = _sample_rows_for_all_blocks()
        self.assertEqual(set(samples), set(list_visual_blocks()))

        def fake_mathtex(tex: str, font_size: int = 44, **kwargs):
            # Avoid requiring pdflatex in CI while preserving realistic 9:16 bounding-box geometry.
            return Text(tex, font="DejaVu Sans", font_size=max(24, font_size - 8), color=kwargs.get("color", "#FFFFFF"))

        with tempfile.TemporaryDirectory() as media_tmp, tempconfig({"media_dir": media_tmp}):
            with patch("manim.MathTex", side_effect=fake_mathtex):
                for block_name, spec in list_visual_blocks().items():
                    sample = samples[block_name]
                    theme = get_theme("basketball_dark" if spec.pack == "basketball" else "science_lab")
                    for lang in SUPPORTED_LANGUAGES:
                        with self.subTest(block=block_name, lang=lang):
                            row = {
                                "id": sample["id"],
                                "title": sample["title"][lang],
                                "body": sample["body"][lang],
                                "formula": sample.get("formula", ""),
                                **({"visual": sample["visual"]} if "visual" in sample else {}),
                                **({"labels": sample["labels"][lang]} if "labels" in sample else {}),
                            }
                            objects = spec.build(theme, lang, row)
                            self.assertTrue(set(objects) <= spec.cue_targets)
                            fake_scene = SimpleNamespace(mobjects=list(objects.values()))
                            VerticalShortScene.check_frame_bounds(fake_scene)

    def test_extensible_check_registry_and_flexible_age_for_localized_lessons(self):
        register_math_check(
            "echo_round_trip",
            lambda check: {"id": check["id"], "ok": True, "distance_m": check["speed"] * check["time"] / 2},
        )
        self.assertIn("echo_round_trip", CHECK_REGISTRY)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "content/lessons").mkdir(parents=True)
                (root / "src/math_books").mkdir(parents=True)
                scene_file = root / "src/math_books/localized_lesson_scene.py"
                scene_file.write_text("# stub\n", encoding="utf-8")
                lesson = {
                    "schema_version": 1,
                    "topic": "echo_demo",
                    "scenes": [
                        {
                            "id": "01_echo",
                            "translations": {
                                "uk": {"text": "Луна повертається за дві секунди.", "title": "Луна", "body": "340 м/с"},
                                "ru": {"text": "Эхо возвращается за две секунды.", "title": "Эхо", "body": "340 м/с"},
                                "en": {"text": "The echo returns in two seconds.", "title": "Echo", "body": "340 m/s"},
                            },
                        }
                    ],
                }
                (root / "content/lessons/echo_demo.json").write_text(json.dumps(lesson), encoding="utf-8")
                scenes = validate_lesson_data(lesson, "echo_demo", "uk")
                dossier = make_review_template(
                    "echo_demo", scenes, "src/math_books/localized_lesson_scene.py", root, language="uk"
                )
                dossier["pedagogy"].update(
                    audience_age={"min": 11, "max": 15},
                    learning_objective="Compute distance from echo round-trip time.",
                    assumptions=["Speed of sound is 340 m/s."],
                    limitations=["Temperature affects speed of sound."],
                    challenge="Find distance for 4 seconds.",
                    expected_learning="Divide round-trip distance by 2.",
                )
                dossier["sources"] = [
                    {
                        "id": "perelman",
                        "kind": "textbook",
                        "title": "Physics for Entertainment",
                        "locator": "Sound chapter",
                        "url": "https://example.org/perelman",
                    }
                ]
                dossier["math_checks"] = [{"id": "echo-2s", "kind": "echo_round_trip", "speed": 340, "time": 2}]
                dossier["scene_reviews"][0].update(
                    teaching_role="Explain echo distance.",
                    claims=[
                        {
                            "statement": "Two seconds corresponds to 340 m.",
                            "script_quote": "Луна повертається за дві секунди.",
                            "kind": "mathematical",
                            "source_ids": ["perelman"],
                            "math_check_ids": ["echo-2s"],
                            "reasoning": "d = 340 * 2 / 2 = 340 m.",
                        }
                    ],
                )
                from math_books.content_review import dossier_digest

                digest = dossier_digest(dossier)
                for disc in ("scientific", "pedagogical"):
                    dossier["reviews"][disc].update(
                        reviewer="Test AI",
                        reviewer_type="ai",
                        reviewed_at="2026-11-25",
                        verdict="approved",
                        dossier_sha256=digest,
                    )
                    for crit in dossier["reviews"][disc]["criteria"].values():
                        crit.update(passed=True, rationale="Verified in unit test.")
                review_file = root / "content_reviews/uk/echo_demo.json"
                review_file.parent.mkdir(parents=True)
                review_file.write_text(json.dumps(dossier), encoding="utf-8")
                report = check_content_review(
                    scenes,
                    "videos/video_echo_demo/uk",
                    root,
                    expected_scene_file="src/math_books/localized_lesson_scene.py",
                    language="uk",
                )
                self.assertTrue(report["ok"], report["issues"])
                self.assertEqual(report["math_checks"][0]["distance_m"], 340.0)
        finally:
            CHECK_REGISTRY.pop("echo_round_trip", None)
