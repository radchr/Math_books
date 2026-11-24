"""Unit tests for the Buzzer-Beater sequential probability scene and model."""

from __future__ import annotations

import unittest
from fractions import Fraction
from unittest.mock import MagicMock

from manim import Mobject

from math_books.buzzer_scene import (
    CHAIN_STEP_PROBS,
    CHALLENGE_STEP_PROBS,
    DIRECT_THREE_PROB,
    BuzzerBeaterBasketball,
    build_buzzer_visual_spec,
    chain_success_probability,
)


class TestBuzzerBeater(unittest.TestCase):
    def test_direct_three_exceeds_three_step_chain(self) -> None:
        chain_prob = chain_success_probability(CHAIN_STEP_PROBS)
        self.assertEqual(chain_prob, Fraction(49, 200))
        self.assertEqual(float(chain_prob), 0.245)
        self.assertGreater(DIRECT_THREE_PROB, chain_prob)

    def test_challenge_three_steps_at_eighty_percent(self) -> None:
        challenge_prob = chain_success_probability(CHALLENGE_STEP_PROBS)
        self.assertEqual(challenge_prob, Fraction(64, 125))
        self.assertEqual(float(challenge_prob), 0.512)

    def test_visual_spec_is_derived_from_model_inputs(self) -> None:
        default_spec = build_buzzer_visual_spec()
        self.assertEqual(default_spec["direct_pct"], "30%")
        self.assertEqual(default_spec["chain_pct"], "24.5%")
        self.assertEqual(default_spec["challenge_pct"], "51.2%")
        self.assertEqual(default_spec["multiply_latex"], r"0.7 \times 0.5 \times 0.7 = 0.245 = 24.5\%")
        self.assertEqual(default_spec["challenge_latex"], r"0.8^3 = 0.512 = 51.2\%")
        self.assertGreater(float(default_spec["bar_a_height"]), float(default_spec["bar_b_height"]))

        # Changing the model inputs must dynamically update all visual numbers and bar heights.
        alt_spec = build_buzzer_visual_spec(
            direct_prob=Fraction(1, 10),
            chain_steps=(Fraction(7, 10), Fraction(1, 2), Fraction(7, 10)),
            challenge_steps=(Fraction(1, 2), Fraction(3, 5), Fraction(1, 1)),
        )
        self.assertEqual(alt_spec["direct_pct"], "10%")
        self.assertEqual(alt_spec["chain_pct"], "24.5%")
        self.assertEqual(alt_spec["verdict_text"], "10%  <  24.5%  •  Цепочка из 3 шагов выгоднее!")
        self.assertEqual(alt_spec["challenge_latex"], r"0.5 \times 0.6 \times 1 = 0.3 = 30\%")
        self.assertLess(float(alt_spec["bar_a_height"]), float(alt_spec["bar_b_height"]))

        # Equality case and uniform challenge exponent
        eq_spec = build_buzzer_visual_spec(
            direct_prob=Fraction(49, 200),
            chain_steps=(Fraction(7, 10), Fraction(1, 2), Fraction(7, 10)),
            challenge_steps=(Fraction(1, 2), Fraction(1, 2), Fraction(1, 2)),
        )
        self.assertEqual(eq_spec["verdict_text"], "24.5%  =  24.5%  •  Шансы обоих планов равны!")
        self.assertEqual(eq_spec["challenge_latex"], r"0.5^3 = 0.125 = 12.5\%")

    def test_invalid_chain_probabilities_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            chain_success_probability(())
        with self.assertRaises(ValueError):
            chain_success_probability((Fraction(7, 10), Fraction(12, 10)))
        with self.assertRaises(ValueError):
            chain_success_probability((Fraction(-1, 10),))

    def test_finish_handles_nonvector_mobjects(self) -> None:
        scene = BuzzerBeaterBasketball.__new__(BuzzerBeaterBasketball)
        scene.mobjects = [Mobject()]
        scene._pad = MagicMock()
        scene.play = MagicMock()
        scene.finish(5.0)
        scene._pad.assert_called_once_with(5.0)
        scene.play.assert_called_once()


if __name__ == "__main__":
    unittest.main()
