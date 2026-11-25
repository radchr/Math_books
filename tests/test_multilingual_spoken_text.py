"""Conservative multilingual narration comparison and exact-number regressions."""

import unittest

from math_books.spoken_text import compare_transcript, normalize_spoken_text


class TestMultilingualSpokenText(unittest.TestCase):
    def test_equivalent_numeric_forms(self):
        cases = {
            "uk": [
                ("Сімдесят відсотків", "70%"),
                ("тридцяти відсотків", "30%"),
                ("дев’ять сотих", "0.09"),
                ("одна ціла і п’ять сотих", "1.05"),
                ("п’ятдесят одна ціла і дві десятих", "51,2"),
                ("одна друга", "1/2"),
            ],
            "en": [
                ("seventy percent", "70%"),
                ("thirty percent", "30%"),
                ("zero point zero nine", "0.09"),
                ("one point zero five", "1.05"),
                ("fifty one point two", "51.2"),
                ("one half", "1/2"),
                ("three quarters", "0.75"),
                ("one hundred and five", "105"),
            ],
        }
        for language, pairs in cases.items():
            for left, right in pairs:
                with self.subTest(language=language, left=left):
                    self.assertEqual(normalize_spoken_text(left, language), normalize_spoken_text(right, language))

    def test_changed_protected_content_and_extra_takes_fail(self):
        pairs = {
            "uk": [
                ("шанс тридцять відсотків", "шанс тринадцять відсотків"),
                ("шанс сімдесят відсотків", "шанс сімнадцять відсотків"),
                ("це не гарантія", "це гарантія"),
                ("незалежні кидки", "залежні кидки"),
                ("два метри", "два секунди"),
                ("шанс ≥ 30%", "шанс ≤ 30%"),
            ],
            "en": [
                ("chance thirty percent", "chance thirteen percent"),
                ("chance seventy percent", "chance seventeen percent"),
                ("independent shots", "dependent shots"),
                ("two meters", "two seconds"),
                ("it is not guaranteed", "it is guaranteed"),
                ("chance >= 30%", "chance <= 30%"),
            ],
        }
        for language, cases in pairs.items():
            for expected, actual in cases:
                with self.subTest(language=language, expected=expected):
                    self.assertFalse(compare_transcript(expected, actual, language)["ok"])
            expected = cases[0][0]
            self.assertFalse(compare_transcript(expected, expected + " " + expected, language)["ok"])
            self.assertFalse(compare_transcript(expected, "Read the following text. " + expected, language)["ok"])

    def test_english_contractions_and_foreign_contamination(self):
        self.assertTrue(compare_transcript("It isn't a guarantee", "It is not a guarantee", "en")["ok"])
        self.assertTrue(compare_transcript("The chance is seventy percent", "The chance is 70%", "en")["ok"])
        self.assertFalse(compare_transcript("The chance is seventy percent", "The chance is 70% шанс", "en")["ok"])

    def test_apostrophes_exact_values_repeated_numbers_and_unknown_language(self):
        self.assertEqual(normalize_spoken_text("п'ять", "uk"), normalize_spoken_text("пʼять", "uk"))
        for language, repeated in [("en", "seventy seventy"), ("uk", "сімдесят сімдесят")]:
            self.assertFalse(compare_transcript("70", repeated, language)["ok"])
            self.assertFalse(compare_transcript("0.1234567890123456789", "0.1234567890123456788", language)["ok"])
            self.assertFalse(
                compare_transcript("0.2", "point twenty" if language == "en" else "кома двадцять", language)["ok"]
            )
        with self.assertRaises(ValueError):
            normalize_spoken_text("bonjour", "fr")

    def test_russian_inequality_direction_is_protected(self):
        self.assertFalse(compare_transcript("Шанс ≥ 30%", "Шанс ≤ 30%", "ru")["ok"])

    def test_additional_fractions_and_inflections(self):
        for language, left, right in [
            ("uk", "тринадцяти відсотків", "13%"),
            ("uk", "нуль цілих і дев’ять сотих", "0.09"),
            ("uk", "половина", "0.5"),
            ("en", "half", "0.5"),
            ("en", "one and a half", "1.5"),
            ("en", "two thirds", "2/3"),
        ]:
            with self.subTest(left=left):
                self.assertEqual(normalize_spoken_text(left, language), normalize_spoken_text(right, language))

    def test_operators_are_preserved_and_cannot_be_omitted(self):
        for language in ("uk", "en", "ru"):
            for expected, actual in [
                ("2 * 3 = 6", "2 / 3 = 6"),
                ("2 * 3", "2 3"),
                ("2 / 3", "2 3"),
                ("- two", "two") if language == "en" else ("- два", "два"),
            ]:
                with self.subTest(language=language, expected=expected):
                    self.assertFalse(compare_transcript(expected, actual, language)["ok"])
        for language in ("uk", "en"):
            self.assertEqual(normalize_spoken_text("2 * 3", language), normalize_spoken_text("2 × 3", language))
            self.assertEqual(normalize_spoken_text("2 / 3", language), normalize_spoken_text("2 ÷ 3", language))
            self.assertNotEqual(normalize_spoken_text("2/3", language), normalize_spoken_text("2 / 3", language))
            self.assertEqual(normalize_spoken_text("2/3", language), ["#number:2/3"])
            self.assertEqual(normalize_spoken_text("⅔", language), ["#number:2/3"])
            self.assertEqual(normalize_spoken_text("2 ∕ 3", language), normalize_spoken_text("2 ÷ 3", language))
            self.assertEqual(
                normalize_spoken_text("- two" if language == "en" else "- два", language),
                normalize_spoken_text("− two" if language == "en" else "− два", language),
            )
        self.assertEqual(normalize_spoken_text("thirty-one", "en"), normalize_spoken_text("31", "en"))
        self.assertEqual(normalize_spoken_text("two minus three", "en"), normalize_spoken_text("2 - 3", "en"))
        self.assertEqual(normalize_spoken_text("два мінус три", "uk"), normalize_spoken_text("2 - 3", "uk"))

    def test_bounded_spoken_operator_phrases_match_symbols(self):
        cases = {
            "en": [
                ("seven plus three equals ten", "7 + 3 = 10"),
                ("seven minus three equals four", "7 - 3 = 4"),
                ("seven times three equals twenty one", "7 * 3 = 21"),
                ("seven multiplied by three equals twenty one", "7 × 3 = 21"),
                ("six divided by three equals two", "6 / 3 = 2"),
            ],
            "uk": [
                ("сім плюс три дорівнює десять", "7 + 3 = 10"),
                ("сім мінус три дорівнює чотири", "7 - 3 = 4"),
                ("сім помножити на три дорівнює двадцять один", "7 * 3 = 21"),
                ("шість поділити на три дорівнює два", "6 / 3 = 2"),
            ],
        }
        for language, pairs in cases.items():
            for expected, actual in pairs:
                with self.subTest(language=language, expected=expected):
                    self.assertTrue(compare_transcript(expected, actual, language)["ok"])
                    self.assertTrue(compare_transcript(actual, expected, language)["ok"])
                    self.assertFalse(compare_transcript(expected, actual.replace("=", ""), language)["ok"])
        self.assertFalse(compare_transcript("six divided by three", "6/3", "en")["ok"])
        self.assertFalse(compare_transcript("шість поділити на три", "6/3", "uk")["ok"])
        self.assertFalse(compare_transcript("seven plus three equals ten", "7 - 3 = 10", "en")["ok"])
        self.assertFalse(compare_transcript("сім плюс три дорівнює десять", "7 - 3 = 10", "uk")["ok"])
