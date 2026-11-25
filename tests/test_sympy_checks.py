"""Unit and security tests for declarative SymPy checkers in content_review."""

from __future__ import annotations

import unittest

from math_books.content_review import CHECK_REGISTRY, _math_check


class SymPyChecksTests(unittest.TestCase):
    def test_check_registry_exposes_sympy_checkers(self) -> None:
        self.assertIn("sympy_identity", CHECK_REGISTRY)
        self.assertIn("sympy_solve", CHECK_REGISTRY)
        self.assertIn("sympy_formula_eval", CHECK_REGISTRY)

    def test_sympy_identity_verifies_algebra_trig_and_assumptions(self) -> None:
        res = _math_check(
            {
                "id": "trig_pythagoras",
                "kind": "sympy_identity",
                "symbols": {"theta": {"real": True}},
                "lhs": "sin(theta)**2 + cos(theta)**2",
                "rhs": "1",
            }
        )
        self.assertTrue(res["ok"])

        # sqrt(x**2) == x holds for positive x, but must FAIL for general real x
        pos_res = _math_check(
            {
                "id": "sqrt_positive",
                "kind": "sympy_identity",
                "symbols": {"x": {"positive": True}},
                "lhs": "sqrt(x**2)",
                "rhs": "x",
            }
        )
        self.assertTrue(pos_res["ok"])

        with self.assertRaisesRegex(ValueError, "symbolic identity failed"):
            _math_check(
                {
                    "id": "sqrt_real_trap",
                    "kind": "sympy_identity",
                    "symbols": {"x": {"real": True}},
                    "lhs": "sqrt(x**2)",
                    "rhs": "x",
                }
            )

    def test_sympy_solve_reals_complexes_and_radicals(self) -> None:
        res = _math_check(
            {
                "id": "radical_roots",
                "kind": "sympy_solve",
                "variable": "x",
                "domain": "reals",
                "lhs": "x**2 - 2",
                "rhs": "0",
                "expected_solutions": ["-sqrt(2)", "sqrt(2)"],
            }
        )
        self.assertTrue(res["ok"])

        empty_real = _math_check(
            {
                "id": "no_real_roots",
                "kind": "sympy_solve",
                "variable": "x",
                "domain": "reals",
                "lhs": "x**2 + 1",
                "rhs": "0",
                "expected_solutions": [],
            }
        )
        self.assertTrue(empty_real["ok"])

        complex_roots = _math_check(
            {
                "id": "complex_roots",
                "kind": "sympy_solve",
                "variable": "x",
                "domain": "complexes",
                "lhs": "x**2 + 1",
                "rhs": "0",
                "expected_solutions": ["-I", "I"],
            }
        )
        self.assertTrue(complex_roots["ok"])

        with self.assertRaisesRegex(ValueError, "solution"):
            _math_check(
                {
                    "id": "wrong_root",
                    "kind": "sympy_solve",
                    "variable": "x",
                    "lhs": "x**2 - 5*x + 6",
                    "rhs": "0",
                    "expected_solutions": ["2", "4"],
                }
            )

    def test_sympy_formula_eval_exact_physics_and_decimals(self) -> None:
        echo = _math_check(
            {
                "id": "echo_distance",
                "kind": "sympy_formula_eval",
                "formula": "v * t / 2",
                "values": {"v": "340", "t": "4"},
                "expected": "680",
            }
        )
        self.assertTrue(echo["ok"])
        self.assertEqual(echo["actual"], "680")

        circle = _math_check(
            {
                "id": "circle_area",
                "kind": "sympy_formula_eval",
                "formula": "pi * r**2",
                "values": {"r": "3/2"},
                "expected": "9*pi/4",
            }
        )
        self.assertTrue(circle["ok"])

        # Exact decimal rationalization avoids IEEE 754 0.1 + 0.2 != 0.3
        exact_dec = _math_check(
            {
                "id": "exact_decimal",
                "kind": "sympy_formula_eval",
                "formula": "a + b",
                "values": {"a": "0.1", "b": "0.2"},
                "expected": "0.3",
            }
        )
        self.assertTrue(exact_dec["ok"])

        with self.assertRaisesRegex(ValueError, "formula evaluation mismatch"):
            _math_check(
                {
                    "id": "wrong_echo",
                    "kind": "sympy_formula_eval",
                    "formula": "v * t / 2",
                    "values": {"v": "340", "t": "4"},
                    "expected": "1360",
                }
            )

    def test_sympy_rejects_code_injection_and_disallowed_syntax(self) -> None:
        payloads = [
            "__import__('os').system('echo pwn')",
            "x.__class__.__mro__",
            "(lambda y: y)(1)",
            "[x for x in [1, 2]]",
            "eval('1+1')",
            "sin(x, evaluate=False)",
            "'hello'",
            "undeclared_var + 1",
            "1 + " * 100 + "1",
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    _math_check(
                        {
                            "id": "inject",
                            "kind": "sympy_identity",
                            "symbols": {"x": {"real": True}},
                            "lhs": payload,
                            "rhs": "1",
                        }
                    )


if __name__ == "__main__":
    unittest.main()
