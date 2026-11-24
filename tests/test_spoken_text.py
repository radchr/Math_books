"""Regression cases for actual prompt leakage and Russian ASR variations."""

import unittest

from math_books import spoken_text


class TestSpokenText(unittest.TestCase):
    def test_numbers_percent_and_yo_normalize(self):
        pairs = [
            ("Семьдесят процентов", "70%"),
            ("Из ста процентов вычитаем девять", "Из 100% вычитаем 9"),
            ("Девяносто один процент", "91 процентов"),
            ("Девять сотых", "0,09"),
            ("Тридцать сотых", "0.3"),
            ("Одна целая и пять сотых", "1.05"),
            ("Двадцать четыре и пять десятых", "24,5"),
            ("Пятьдесят одна целая и две десятых", "51.2"),
            ("Мяч идёт в кольцо", "Мяч идет в кольцо"),
            ("На модельной сетке", "На модельные сетки"),
            ("Сложный трёхочковый бросок", "Сложные 3 очковы бросок"),
            ("Дальний бросок на три очка", "Дальний брасок на трячка"),
            ("Вторая атака на два очка", "Второе атака на двачка"),
            ("Семьдесят сотых на пятьдесят сотых", "70-х на 50-х"),
            ("Семьдесят сотых на пятьдесят сотых", "70 сутых на 50 сутых"),
        ]
        for expected, actual in pairs:
            with self.subTest(expected=expected):
                self.assertEqual(spoken_text.normalize_spoken_text(expected), spoken_text.normalize_spoken_text(actual))

    def test_english_prompt_prefix_is_rejected(self):
        report = spoken_text.compare_transcript(
            "Представь два штрафных.", "Read the following Russian text aloud. Представь два штрафных."
        )
        self.assertFalse(report["ok"])
        self.assertTrue(report["foreign_words"])

    def test_insertions_omissions_and_repeated_takes_are_rejected(self):
        expected = "Считаем в модели. Два броска независимы. Вероятность не меняется."
        for actual in (
            expected + " " + expected,
            "Считаем в модели. Вероятность не меняется.",
            expected + " Теперь прочитаю ещё раз.",
        ):
            with self.subTest(actual=actual):
                self.assertFalse(spoken_text.compare_transcript(expected, actual)["ok"])

    def test_changed_numbers_negation_units_and_event_qualifiers_are_rejected(self):
        pairs = [
            ("Шанс семьдесят процентов.", "Шанс восемьдесят процентов."),
            ("Это не гарантия результата.", "Это гарантия результата."),
            ("Два независимых броска.", "Два зависимых броска."),
            ("Хотя бы одно попадание.", "Ровно одно попадание."),
            ("Одно очко за бросок.", "Одно очко за атаку."),
            ("Один процент.", "Один процент процент."),
            ("Ровно половину бросков.", "Ровно четверть бросков."),
            ("Шанс следующего орла.", "Шанс следующего угла."),
        ]
        for expected, actual in pairs:
            with self.subTest(expected=expected):
                self.assertFalse(spoken_text.compare_transcript(expected, actual)["ok"])

    def test_duplicated_number_is_not_merged_into_another_number(self):
        self.assertFalse(spoken_text.compare_transcript("Семьдесят процентов", "Семьдесят семьдесят процентов")["ok"])

    def test_small_noncritical_asr_substitution_is_reported(self):
        expected = "Но вероятность больше ста процентов невозможна, это видно в нашем простом примере."
        actual = "На вероятность больше 100 процентов невозможно, это видно в нашем простом примере."
        report = spoken_text.compare_transcript(expected, actual)
        self.assertTrue(report["ok"])
        self.assertEqual(report["substitutions"], 1)
        self.assertTrue(report["warnings"])

    def test_empty_or_unintelligible_transcript_is_rejected(self):
        for actual in ("", "  ...", "Неразборчивое бормотание"):
            self.assertFalse(spoken_text.compare_transcript("Два штрафных броска.", actual)["ok"])
