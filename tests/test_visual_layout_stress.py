"""Mini-ManimBench layout stress tests: bounds, overlap detection, multi-point keyframes, and draft builds."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from manim import config as manim_config

from math_books import cli, lessons, video_builder
from math_books.themes import get_theme
from math_books.video_ui import (
    DEFAULT_ALLOWED_OVERLAP_PAIRS,
    check_mobjects_frame_bounds,
    configure_vertical_9_16,
    find_mobject_overlaps,
    require_no_mobject_overlaps,
)
from math_books.visual_blocks import get_visual_block, list_visual_blocks


class VisualLayoutStressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure_vertical_9_16()
        cls._tmp_media = tempfile.TemporaryDirectory()
        cls._prev_media_dir = manim_config.media_dir
        manim_config.media_dir = cls._tmp_media.name

    @classmethod
    def tearDownClass(cls) -> None:
        manim_config.media_dir = cls._prev_media_dir
        cls._tmp_media.cleanup()

    def test_overlap_detector_catches_real_collision_and_ignores_background(self) -> None:
        from manim import Rectangle

        a = Rectangle(width=2.0, height=1.0).move_to([0, 0, 0])
        b = Rectangle(width=2.0, height=1.0).move_to([0.5, 0.2, 0])
        c = Rectangle(width=2.0, height=1.0).move_to([0, 3.0, 0])
        overlaps = find_mobject_overlaps({"a": a, "b": b, "c": c, "court": a})
        self.assertEqual(len(overlaps), 1)
        self.assertEqual(overlaps[0][:2], ("a", "b"))
        with self.assertRaisesRegex(ValueError, "Overlapping foreground mobjects"):
            require_no_mobject_overlaps({"a": a, "b": b})
        require_no_mobject_overlaps({"a": a, "c": c, "court": a})

    @classmethod
    def _tex_context(cls):
        if shutil.which("latex") is not None:
            return nullcontext()
        from manim import Text

        def fake_mathtex(tex: str, font_size: int = 44, **kwargs):
            return Text(tex, font="DejaVu Sans", font_size=max(24, font_size - 8), color=kwargs.get("color", "#FFFFFF"))

        return patch("manim.MathTex", side_effect=fake_mathtex)

    def test_all_registered_visual_blocks_pass_bounds_and_overlap_under_stress(self) -> None:
        theme = get_theme("science_lab")
        stress_cases: dict[str, dict] = {
            "text_card": {
                "title": "Дуже довгий український заголовок для перевірки меж екрана 9:16",
                "body": ("Розгорнуте пояснення фізичної моделі з кількома реченнями для перевірки переносу рядків."),
                "formula": r"\frac{a + b}{c + d} = \frac{340 \cdot 4}{2}",
                "visual": {"template": "text_card", "params": {}},
            },
            "hook_choice": {
                "title": "Що вигідніше на останніх секундах матчу?",
                "body": "Обери інтуїтивно правильний варіант перед тим, як ми порахуємо математичне очікування.",
                "formula": r"\frac{35}{100} \times 3 > \frac{50}{100} \times 2",
                "labels": {"opt_a": "Дальній триочковий кидок (35%)", "opt_b": "Надійний двоочковий прохід (50%)"},
                "visual": {
                    "template": "hook_choice",
                    "params": {"option_a": "opt_a", "option_b": "opt_b"},
                },
            },
            "compare_bars": {
                "title": "Порівняння чотирьох стратегій за очікуваними очками",
                "body": "Точне масштабування стовпчиків із підписами, формулою та банером переможця.",
                "formula": r"E = \frac{105}{100} > \frac{100}{100}",
                "labels": {
                    "b1": "Триочковий кидок",
                    "b2": "Середній кидок",
                    "b3": "Штрафні кидки",
                    "b4": "Прохід під кільце",
                },
                "visual": {
                    "template": "compare_bars",
                    "params": {
                        "items": [
                            {"id": "b1", "value": "1.05", "color": "positive"},
                            {"id": "b2", "value": "0.84", "color": "warning"},
                            {"id": "b3", "value": "0.96", "color": "secondary"},
                            {"id": "b4", "value": "1.12", "color": "primary"},
                        ],
                        "unit": " pts",
                        "winner": "b4",
                    },
                },
            },
            "step_chain": {
                "title": "Ланцюжок із чотирьох незалежних кроків",
                "body": "Перевірка чотирьох кроків разом із формулою та підсумковим банером результату.",
                "formula": r"P = \frac{7}{10} \cdot \frac{7}{10} \cdot \frac{5}{10} = \frac{49}{200}",
                "labels": {"s1": "Крок перший", "s2": "Крок другий", "s3": "Крок третій", "s4": "Крок четвертий"},
                "visual": {
                    "template": "step_chain",
                    "params": {
                        "steps": [
                            {"label": "s1", "value": "70%"},
                            {"label": "s2", "value": "70%"},
                            {"label": "s3", "value": "50%"},
                            {"label": "s4", "value": "24.5%"},
                        ],
                        "result": "24.5%",
                    },
                },
            },
            "challenge_card": {
                "title": "Фінальний челендж",
                "body": "Якщо звук луни повернувся через 6 секунд при швидкості 340 м/с, яка відстань до скелі?",
                "formula": r"d = \frac{340 \times 6}{2} = 1020",
                "labels": {
                    "ans": "1020 метрів — бо звук проходить шлях туди й назад",
                    "lim": "Модель для сухого повітря при ~15°C без сильного вітру",
                },
                "visual": {"template": "challenge_card", "params": {"answer_label": "ans", "limit_label": "lim"}},
            },
            "image_stage": {
                "title": "Акустична схема відбиття звукової хвилі",
                "body": "Звук долає відстань до перешкоди і повертається назад — подвійний шлях.",
                "formula": r"d = \frac{v \cdot t}{2}",
                "labels": {"cap": "Схема луни за Перельманом (340 м/с)"},
                "visual": {
                    "template": "image_stage",
                    "params": {"image": "assets/diagrams/echo_wave.svg", "caption_label": "cap"},
                },
            },
            "basketball.half_court_diagram": {
                "title": "Геометрія пасу та триочкового кидка",
                "body": "Позиції гравців на половині майданчика з напрямками передачі.",
                "formula": r"c = \sqrt{a^2 + b^2}",
                "labels": {"pg": "Розігруючий", "wing": "Снайпер", "rim": "Кільце"},
                "visual": {
                    "template": "basketball.half_court_diagram",
                    "params": {
                        "markers": [
                            {"id": "pg", "x": 0.0, "y": -2.0, "color": "primary"},
                            {"id": "wing", "x": 2.4, "y": 0.2, "color": "secondary"},
                            {"id": "rim", "x": 0.0, "y": 1.8, "color": "positive"},
                        ],
                        "arrows": [
                            {"from": "pg", "to": "wing", "color": "secondary"},
                            {"from": "wing", "to": "rim", "color": "positive"},
                        ],
                    },
                },
            },
            "equation_morph": {
                "title": "Покрокове виведення відстані до перешкоди",
                "body": "Колір кожної величини зберігається під час плавної підстановки чисел.",
                "labels": {
                    "n1": "Загальна формула для луни (шлях туди й назад)",
                    "n2": "Підставляємо швидкість звуку 340 м/с і час 4 с",
                    "n3": "Точний результат без наближень",
                    "res": "Відстань до скелі: 680 метрів",
                },
                "visual": {
                    "template": "equation_morph",
                    "params": {
                        "steps": [
                            {"tex": r"d = \frac{v \cdot t}{2}", "note_label": "n1"},
                            {"tex": r"d = \frac{340 \cdot 4}{2}", "note_label": "n2"},
                            {"tex": r"d = 680", "note_label": "n3"},
                        ],
                        "formula_colors": {
                            "d": "positive",
                            "v": "primary",
                            "t": "secondary",
                            "340": "primary",
                            "4": "secondary",
                            "680": "positive",
                        },
                        "result_label": "res",
                    },
                },
            },
            "basketball.scoreboard_duel": {
                "title": "Останні секунди вирішального матчу",
                "body": "Мінус три очки на табло: ризикувати дальнім кидком чи грати комбінацію?",
                "formula": r"0.30 > 0.245",
                "visual": {
                    "template": "basketball.scoreboard_duel",
                    "params": {"score": "98 : 101", "clock": "0:08"},
                },
            },
        }
        registered = set(list_visual_blocks())
        self.assertEqual(registered, set(stress_cases), "Every registered visual block must have a layout stress case")

        with self._tex_context():
            for name, row in stress_cases.items():
                with self.subTest(block=name):
                    spec = get_visual_block(name)
                    objects = spec.build(theme, "uk", row)
                    check_mobjects_frame_bounds(objects)
                    require_no_mobject_overlaps(
                        objects, allowed_pairs=DEFAULT_ALLOWED_OVERLAP_PAIRS | spec.allowed_overlap_pairs
                    )

    def test_latex_brace_balance_and_formula_colors_validation(self) -> None:
        with self.assertRaisesRegex(ValueError, "unbalanced braces"):
            lessons.validate_latex_formula(r"\frac{a+b}{c", "test")
        with self.assertRaisesRegex(ValueError, "braced numerator"):
            lessons.validate_latex_formula(r"\frac 1 2", "test")
        self.assertEqual(lessons.validate_latex_formula(r"d = \frac{v \cdot t}{2}", "test"), r"d = \frac{v \cdot t}{2}")

    def test_all_production_lessons_pass_bounds_and_overlap_checks(self) -> None:
        root = video_builder.project_root()
        with self._tex_context():
            for key in lessons.discover_lessons(root):
                rows = lessons.load_lesson(root, key, "uk")
                for row in rows:
                    template = row.get("visual", {}).get("template", "text_card")
                    spec = get_visual_block(template)
                    theme = get_theme(row.get("theme", "basketball_dark"))
                    with self.subTest(lesson=key, scene=row["id"], template=template):
                        objects = spec.build(theme, "uk", row)
                        check_mobjects_frame_bounds(objects)
                        require_no_mobject_overlaps(
                            objects, allowed_pairs=DEFAULT_ALLOWED_OVERLAP_PAIRS | spec.allowed_overlap_pairs
                        )

    def test_multi_point_keyframes_capture_start_cues_and_final(self) -> None:
        points = video_builder._scene_keyframe_offsets(
            6.0,
            [{"id": "c1", "time": 2.0}, {"id": "c2", "time": 4.5}],
            None,
        )
        labels = [label for label, _ in points]
        self.assertEqual(labels, ["start", "cue_c1", "cue_c2", "final"])
        # Very short scene deduplicates close timestamps while preserving final
        short_points = video_builder._scene_keyframe_offsets(0.4, [], None)
        self.assertEqual([label for label, _ in short_points], ["final"])

    def test_cli_build_parses_draft_flag(self) -> None:
        parser = cli.build_parser()
        args = parser.parse_args(["build", "perelman_echo_distance", "--lang", "uk", "--draft"])
        self.assertTrue(args.draft)
        with patch("math_books.cli.build_video", return_value={"ok": True, "path": str(Path("draft.mp4"))}) as mock_b:
            rc = cli.cmd_build(args)
        self.assertEqual(rc, 0)
        mock_b.assert_called_once_with("perelman_echo_distance", skip_render=False, language="uk", draft=True)


if __name__ == "__main__":
    unittest.main()
