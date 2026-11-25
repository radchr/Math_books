"""Declared animation events must resolve to actual words, never guessed times."""

import copy
import unittest

from math_books.cue_timeline import event_timeline, localize_cues, resolve_cues, validate_event_log

TRANSLATIONS = {
    "uk": {"text": "Сім плюс три. Разом десять."},
    "ru": {"text": "Семь плюс три равно десяти."},
    "en": {"text": "Seven plus three equals ten."},
}
CUE: dict = {
    "id": "answer_reveal",
    "target": "formula",
    "anchor": "start",
    "occurrence": 1,
    "phrases": {"uk": "Разом", "ru": "равно", "en": "equals"},
}


class TestCueTimeline(unittest.TestCase):
    def test_cumulative_audio_clock_does_not_round_each_scene_independently(self):
        cue = {"id": "answer", "target": "formula", "phrase": "equals", "occurrence": 1, "anchor": "start"}
        scenes = [{"id": str(i), "cues": [cue]} for i in range(10)]
        manifest = [{"id": str(i), "duration": 2.01} for i in range(10)]
        snapshot = {str(i): [{"word": "equals", "start": 1, "end": 1.2}] for i in range(10)}
        events = event_timeline(scenes, manifest, snapshot, "en")
        self.assertEqual(events["9"][0]["global_frame"], round((9 * 2.41 + 1) * 30))
        self.assertEqual(events["9"][0]["sample"], events["9"][0]["global_frame"] * 800)
        records: list[dict] = [
            {
                "scene_id": key,
                "id": "answer",
                "target": "formula",
                "frame": value[0]["frame"],
                "global_frame": value[0]["global_frame"],
            }
            for key, value in events.items()
        ]
        validate_event_log(events, records)
        records[-1]["global_frame"] -= 3
        with self.assertRaises(ValueError):
            validate_event_log(events, records)

    def test_cue_never_matches_inside_a_compound_numeral(self):
        for language, narration, phrase in (
            ("en", "One hundred shots. One wins.", "one"),
            ("uk", "Двадцять один кидок. Один виграє.", "один"),
            ("ru", "Двадцать один бросок. Один выигрывает.", "один"),
        ):
            raw = narration.split()
            words = [{"word": word, "start": i * 0.2, "end": (i + 1) * 0.2} for i, word in enumerate(raw)]
            cue = {"id": "answer", "target": "formula", "phrase": phrase, "occurrence": 1, "anchor": "start"}
            result = resolve_cues({"cues": [cue]}, words, language, duration=3)
            self.assertEqual(result[0]["frame"], 18)

    def test_rendered_event_log_requires_every_target_at_its_declared_frame(self):
        timeline = {"01": [{"id": "answer", "target": "formula", "frame": 30}]}
        log = [{"scene_id": "01", "id": "answer", "target": "formula", "frame": 30}]
        validate_event_log(timeline, log)
        for invalid in ([], [log[0], log[0]], [{**log[0], "frame": 40}], [{**log[0], "target": "body"}]):
            with self.assertRaises(ValueError):
                validate_event_log(timeline, invalid)

    def test_each_language_resolves_same_event_and_quantizes_to_frame(self):
        for language, phrase in CUE["phrases"].items():
            cues = localize_cues([CUE], TRANSLATIONS, language, formula="7+3=10")
            row = {"cues": cues}
            result = resolve_cues(row, [{"word": phrase, "start": 1.234, "end": 1.6}], language, duration=3)
            self.assertEqual(result[0]["frame"], 37)
            self.assertEqual(result[0]["sample"], 37 * 800)
            self.assertEqual(result[0]["id"], "answer_reveal")

    def test_repeated_phrase_uses_explicit_occurrence_and_end_anchor(self):
        cue = {"id": "answer", "target": "formula", "phrase": "ten", "occurrence": 2, "anchor": "end"}
        words = [{"word": "10", "start": 0.2, "end": 0.4}, {"word": "ten", "start": 1, "end": 1.6}]
        result = resolve_cues({"cues": [cue]}, words, "en", duration=3)
        self.assertEqual(result[0]["frame"], 48)

    def test_missing_anchor_or_impossible_time_fails_without_fallback(self):
        cue = {"id": "answer", "target": "formula", "phrase": "equals", "occurrence": 1, "anchor": "start"}
        for words in (
            [],
            [{"word": "different", "start": 0, "end": 1}],
            [{"word": "equals", "start": float("nan"), "end": 1}],
            [{"word": "equals", "start": 5, "end": 6}],
        ):
            with self.assertRaises(ValueError):
                resolve_cues({"cues": [cue]}, words, "en", duration=3)

    def test_invalid_or_missing_multilingual_cues_rejected_before_tts(self):
        for change in ("language", "occurrence", "phrase", "target", "id"):
            cue = copy.deepcopy(CUE)
            if change == "language":
                del cue["phrases"]["uk"]
            elif change == "occurrence":
                cue["occurrence"] = True
            elif change == "phrase":
                cue["phrases"]["en"] = "not in the script"
            elif change == "target":
                cue["target"] = "unknown"
            else:
                cue["id"] = ""
            with self.assertRaises(ValueError, msg=change):
                localize_cues([cue], TRANSLATIONS, "en", formula="7+3=10")
        with self.assertRaises(ValueError):
            localize_cues([CUE, CUE], TRANSLATIONS, "uk", formula="7+3=10")
