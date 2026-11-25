"""Small ASR differences must not change symbols, units or spatial conditions."""

import unittest

from math_books.spoken_text import compare_transcript


class TestScientificSubstitutions(unittest.TestCase):
    def test_short_tokens_do_not_bypass_scientific_protection(self):
        for language, text, old, new in (
            ("en", "The value of x in this simple equation can be calculated using the diagram shown here.", "x", "y"),
            (
                "en",
                "The measured delay is ten ms and the diagram shows the timing of the entire experiment.",
                "ms",
                "ns",
            ),
            ("en", "The point is on the circle and the diagram shows the geometry of this simple example.", "on", "in"),
            (
                "en",
                "The measured distance is ten micrometers and the diagram shows the scale of the entire experiment.",
                "micrometers",
                "millimeters",
            ),
            (
                "uk",
                "Виміряна затримка становить десять мс і на діаграмі показано час усього експерименту.",
                "мс",
                "нс",
            ),
            (
                "uk",
                "Точка лежить на колі і на діаграмі показано геометрію цього простого прикладу.",
                "на",
                "під",
            ),
        ):
            with self.subTest(language=language, old=old, new=new):
                self.assertFalse(
                    compare_transcript(text, text.replace(" " + old + " ", " " + new + " ", 1), language)["ok"]
                )
