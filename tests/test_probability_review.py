"""Exact review checks for a direct attempt versus independent sequential steps."""

import unittest

from math_books.content_review import _math_check


class TestProbabilityReview(unittest.TestCase):
    def test_buzzer_probabilities_are_checked_exactly(self):
        check = {
            "id": "direct-v-chain",
            "kind": "independent_chain",
            "direct_probability": "3/10",
            "step_probabilities": ["7/10", "1/2", "7/10"],
            "expected_chain": "49/200",
            "expected_comparison": ">",
        }
        result = _math_check(check)
        self.assertEqual(result["chain_probability"], "49/200")
        self.assertEqual(result["comparison"], ">")
        for changed in (
            {"expected_chain": "1/4"},
            {"expected_comparison": "<"},
            {"step_probabilities": ["2"]},
            {"step_probabilities": []},
            {"direct_probability": True},
        ):
            with self.assertRaises(ValueError):
                _math_check({**check, **changed})

    def test_equal_and_lower_direct_probabilities(self):
        for direct, comparison in [("1/4", "="), ("1/10", "<")]:
            self.assertEqual(
                _math_check(
                    {
                        "id": "comparison",
                        "kind": "independent_chain",
                        "direct_probability": direct,
                        "step_probabilities": ["1/2", "1/2"],
                        "expected_chain": "1/4",
                        "expected_comparison": comparison,
                    }
                )["comparison"],
                comparison,
            )
