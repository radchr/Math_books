"""Check the exact data that drives the free-throw animation."""

import unittest
from fractions import Fraction
from types import SimpleNamespace

from manim import Mobject, Square

from math_books import free_throws_scene


class TestFreeThrows(unittest.TestCase):
    def test_scene_transition_handles_nonvector_mobjects(self):
        animations = []
        objects = [Square(), Mobject()]
        scene = SimpleNamespace(
            mobjects=objects, _pad=lambda duration: None, play=lambda animation, **kwargs: animations.append(animation)
        )
        free_throws_scene.FreeThrowsBasketball.finish(scene, 1)
        self.assertEqual(set(animations[0].mobject.submobjects), set(objects))

    def test_outcomes_are_weighted_and_sum_to_one(self):
        outcomes = free_throws_scene.two_shot_outcomes(Fraction(7, 10))
        self.assertEqual(
            outcomes,
            {"ПП": Fraction(49, 100), "ПМ": Fraction(21, 100), "МП": Fraction(21, 100), "ММ": Fraction(9, 100)},
        )
        self.assertEqual(sum(outcomes.values()), 1)
        self.assertEqual(1 - outcomes["ММ"], Fraction(91, 100))

    def test_grid_shows_nine_misses_and_ninety_one_successes(self):
        outcomes = free_throws_scene.model_grid_outcomes(7)
        self.assertEqual(len(outcomes), 100)
        self.assertEqual(outcomes.count("ММ"), 9)
        self.assertEqual(outcomes.count("ПП"), 49)
        self.assertEqual(sum(outcome != "ММ" for outcome in outcomes), 91)

    def test_challenge_and_boundary_probabilities(self):
        self.assertEqual(1 - free_throws_scene.two_shot_outcomes(Fraction(4, 5))["ММ"], Fraction(24, 25))
        self.assertEqual(free_throws_scene.two_shot_outcomes(Fraction(0))["ММ"], 1)
        self.assertEqual(free_throws_scene.two_shot_outcomes(Fraction(1))["ПП"], 1)

    def test_invalid_model_parameters_are_rejected(self):
        with self.assertRaises(ValueError):
            free_throws_scene.two_shot_outcomes(Fraction(11, 10))
        with self.assertRaises(ValueError):
            free_throws_scene.model_grid_outcomes(11)
