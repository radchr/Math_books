"""Unit tests for Math_books digitization parser, audio assembly, registry, and CLI."""

from __future__ import annotations

import importlib
import json
import tempfile
import unittest
import wave
from pathlib import Path

from lxml import html as lxml_html

from math_books.build_sample_md import clean_text, html_page_to_md, parse_page_spec
from math_books.cli import build_parser
from math_books.video_builder import VIDEO_TOPICS, concat_audio_from_manifest, project_root


def _write_silence_wav(path: Path, duration_s: float, rate: int = 24000) -> None:
    n_frames = int(round(duration_s * rate))
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * n_frames)


class TestDigitization(unittest.TestCase):
    def test_clean_text(self) -> None:
        self.assertEqual(clean_text("  Привет,\xa0мир!\t  "), "Привет, мир!")

    def test_parse_page_spec(self) -> None:
        self.assertEqual(parse_page_spec("13-16"), [13, 14, 15, 16])
        self.assertEqual(parse_page_spec("16, 13-14, 14"), [13, 14, 16])
        with self.assertRaises(ValueError):
            parse_page_spec("16-13")
        with self.assertRaises(ValueError):
            parse_page_spec("  ")

    def test_html_page_to_md_multiple_footnotes_and_images(self) -> None:
        sample_html = """
        <div class="page-html" data-rel="14">
          <div class="pagebox">
            <div class="li1"><p>Глава I</p></div>
            <p>Первый абзац<span class="fnsymbol">*)</span> и вторая сноска<span class="fnsymbol">**)</span>.</p>
            <p>Рис. 2.</p>
            <p>Текст после рисунка.</p>
            <div class="fn">
              <p>*) Первая сноска.</p>
              <p>**) Вторая сноска.</p>
            </div>
          </div>
        </div>
        """
        el = lxml_html.fromstring(sample_html)
        md = html_page_to_md(
            el,
            14,
            [{"filename": "p0014_fig1.png", "bbox": [0, 0, 1, 1], "after_text_block_idx": 2}],
        )
        self.assertIn("## Глава I", md)
        self.assertIn("Первый абзац[^14-1] и вторая сноска[^14-2].", md)
        self.assertIn("![Рис. 2.](images/p0014_fig1.png)", md)
        self.assertIn("[^14-1]: Первая сноска.", md)
        self.assertIn("[^14-2]: Вторая сноска.", md)

    def test_html_page_to_md_converts_tables_and_rejects_unhandled_containers(self) -> None:
        table_html = """
        <div class="page-html" data-rel="15">
          <div class="pagebox">
            <p>Таблица значений:</p>
            <table>
              <tr><th>Ход</th><th>Очки</th></tr>
              <tr><td>1</td><td>17</td></tr>
            </table>
          </div>
        </div>
        """
        md = html_page_to_md(lxml_html.fromstring(table_html), 15, [])
        self.assertIn("| Ход | Очки |", md)
        self.assertIn("| 1 | 17 |", md)

        unknown_div_html = """
        <div class="page-html" data-rel="15">
          <div class="pagebox">
            <div class="unexpected"><p>Скрытое условие задачи 42.</p></div>
          </div>
        </div>
        """
        with self.assertRaisesRegex(ValueError, "Unsupported non-empty HTML element"):
            html_page_to_md(lxml_html.fromstring(unknown_div_html), 15, [])


class TestVideoBuilder(unittest.TestCase):
    def test_concat_audio_from_manifest_exact_duration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            w1 = tmp_dir / "01.wav"
            w2 = tmp_dir / "02.wav"
            _write_silence_wav(w1, 1.0)
            _write_silence_wav(w2, 1.5)
            manifest = tmp_dir / "manifest.json"
            manifest.write_text(
                json.dumps(
                    [
                        {"id": "01", "wav": str(w1), "duration": 1.0},
                        {"id": "02", "wav": str(w2), "duration": 1.5},
                    ]
                ),
                encoding="utf-8",
            )
            out_wav = tmp_dir / "full.wav"
            dur = concat_audio_from_manifest(manifest, out_wav, gap_ms=400, tail_ms=300)
            # 1.0 + 0.4 + 1.5 + 0.3 = 3.2s
            self.assertAlmostEqual(dur, 3.2, places=3)

    def test_video_topics_registry_integrity(self) -> None:
        root = project_root()
        for key, topic in VIDEO_TOPICS.items():
            self.assertEqual(key, topic.key)
            self.assertTrue((root / topic.scene_file).exists(), f"Missing scene file for {key}")
            mod = importlib.import_module(topic.tts_module)
            self.assertTrue(hasattr(mod, "SCENES"), f"Missing SCENES in {topic.tts_module}")
            self.assertEqual(len(mod.SCENES), 5)

    def test_cli_parser_subcommands(self) -> None:
        parser = build_parser()
        self.assertEqual(parser.parse_args(["list"]).command, "list")
        self.assertEqual(parser.parse_args(["tts", "moneybart", "--force"]).force, True)
        self.assertEqual(parser.parse_args(["build", "ahrens", "--skip-render"]).skip_render, True)
        self.assertEqual(parser.parse_args(["verify", "all"]).topic, "all")
        self.assertEqual(parser.parse_args(["digitize", "--pages", "13-16"]).pages, "13-16")


if __name__ == "__main__":
    unittest.main()
