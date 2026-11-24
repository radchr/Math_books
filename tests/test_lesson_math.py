"""Check the actual data used in the probability animation."""

import unittest
from fractions import Fraction

from math_books import lesson_math


class TestCoinExample(unittest.TestCase):
    def test_sequence_average_differs_from_pooled_transition_rate(self):
        rows = lesson_math.coin_followup_examples()
        self.assertEqual(len(rows), 6)
        self.assertEqual(sum((rate for _, rate in rows), Fraction()) / len(rows), Fraction(5, 12))
        hits = attempts = 0
        for sequence, rate in rows:
            following = [sequence[i + 1] for i in range(2) if sequence[i] == "О"]
            hits += following.count("О")
            attempts += len(following)
            self.assertEqual(rate, Fraction(following.count("О"), len(following)))
        self.assertEqual(Fraction(hits, attempts), Fraction(1, 2))
