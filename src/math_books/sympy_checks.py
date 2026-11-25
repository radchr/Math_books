"""Safe, bounded SymPy symbolic checkers for content_review math_checks.

Expressions are validated via a strict Python AST allowlist before parsing with
SymPy's `parse_expr` (`global_dict={}` and exact `rationalize`), preventing
arbitrary code execution while enabling exact algebra, equation solving, and
symbolic formula evaluation in editorial review dossiers.
"""

from __future__ import annotations

import ast
import re
from typing import Any

import sympy as sp
from sympy.parsing.sympy_parser import parse_expr, rationalize, standard_transformations

MAX_EXPR_LEN = 300
_SYMBOL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,15}$")

ALLOWED_CONSTANTS: dict[str, Any] = {
    "pi": sp.pi,
    "E": sp.E,
    "I": sp.I,
    "oo": sp.oo,
}

ALLOWED_FUNCTIONS: dict[str, Any] = {
    "Abs": sp.Abs,
    "abs": sp.Abs,
    "sqrt": sp.sqrt,
    "cbrt": sp.cbrt,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "cot": sp.cot,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "sinh": sp.sinh,
    "cosh": sp.cosh,
    "tanh": sp.tanh,
    "exp": sp.exp,
    "log": sp.log,
    "ln": sp.log,
    "factorial": sp.factorial,
    "binomial": sp.binomial,
    "gcd": sp.gcd,
    "lcm": sp.lcm,
    "floor": sp.floor,
    "ceiling": sp.ceiling,
    "Rational": sp.Rational,
    "Min": sp.Min,
    "Max": sp.Max,
}

ALLOWED_ASSUMPTIONS = frozenset(
    {
        "real",
        "complex",
        "positive",
        "negative",
        "nonnegative",
        "nonpositive",
        "nonzero",
        "integer",
        "even",
        "odd",
        "rational",
    }
)

DOMAINS: dict[str, Any] = {
    "reals": sp.S.Reals,
    "integers": sp.S.Integers,
    "complexes": sp.S.Complexes,
}

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)
_TRANSFORMS = (*standard_transformations, rationalize)


def _build_symbols(raw_symbols: object, context: str) -> dict[str, sp.Symbol]:
    if raw_symbols is None:
        return {}
    if not isinstance(raw_symbols, dict) or len(raw_symbols) > 16:
        raise ValueError(f"{context}: symbols must be an object with at most 16 variables")
    result: dict[str, sp.Symbol] = {}
    for name, raw_assumptions in raw_symbols.items():
        if not isinstance(name, str) or not _SYMBOL_RE.fullmatch(name):
            raise ValueError(f"{context}: invalid symbol name {name!r}")
        if name in ALLOWED_CONSTANTS or name in ALLOWED_FUNCTIONS:
            raise ValueError(f"{context}: symbol {name!r} collides with built-in constant/function")
        if not isinstance(raw_assumptions, dict):
            raise ValueError(f"{context}.symbols[{name}]: expected an object of boolean assumptions")
        assumptions: dict[str, bool] = {}
        for key, val in raw_assumptions.items():
            if key not in ALLOWED_ASSUMPTIONS or type(val) is not bool:
                raise ValueError(f"{context}.symbols[{name}]: unsupported assumption {key!r}={val!r}")
            assumptions[key] = val
        if not assumptions:
            assumptions["real"] = True
        result[name] = sp.Symbol(name, **assumptions)
    return result


def _validate_ast(node: ast.AST, allowed_names: set[str], context: str) -> None:
    if isinstance(node, ast.Expression):
        _validate_ast(node.body, allowed_names, context)
        return
    if isinstance(node, ast.Constant):
        if type(node.value) not in (int, float):
            raise ValueError(f"{context}: only numeric literals are allowed")
        return
    if isinstance(node, ast.Name):
        if node.id not in allowed_names:
            raise ValueError(f"{context}: undeclared or disallowed identifier {node.id!r}")
        return
    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, _ALLOWED_UNARYOPS):
            raise ValueError(f"{context}: unsupported unary operator")
        _validate_ast(node.operand, allowed_names, context)
        return
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, _ALLOWED_BINOPS):
            raise ValueError(f"{context}: unsupported binary operator")
        _validate_ast(node.left, allowed_names, context)
        _validate_ast(node.right, allowed_names, context)
        return
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS:
            raise ValueError(f"{context}: disallowed function call")
        if node.keywords:
            raise ValueError(f"{context}: keyword arguments are not allowed in symbolic expressions")
        if not 1 <= len(node.args) <= 4:
            raise ValueError(f"{context}: function call requires 1 to 4 positional arguments")
        for arg in node.args:
            _validate_ast(arg, allowed_names, context)
        return
    raise ValueError(f"{context}: disallowed syntax {type(node).__name__} in symbolic expression")


def parse_safe_expr(text: object, symbols: dict[str, sp.Symbol], context: str) -> sp.Expr:
    """Parse a declarative math expression into an exact SymPy Expr using a strict AST allowlist."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"{context}: expected a non-empty expression string")
    raw = text.strip()
    if len(raw) > MAX_EXPR_LEN:
        raise ValueError(f"{context}: expression exceeds maximum length ({MAX_EXPR_LEN})")
    try:
        tree = ast.parse(raw, mode="eval")
    except SyntaxError as error:
        raise ValueError(f"{context}: invalid expression syntax: {error.msg}") from None
    allowed_names = set(ALLOWED_CONSTANTS) | set(ALLOWED_FUNCTIONS) | set(symbols)
    _validate_ast(tree, allowed_names, context)
    local_dict: dict[str, Any] = {**ALLOWED_CONSTANTS, **ALLOWED_FUNCTIONS, **symbols}
    safe_globals: dict[str, Any] = {
        "__builtins__": {},
        "Integer": sp.Integer,
        "Float": sp.Float,
        "Rational": sp.Rational,
        "Symbol": sp.Symbol,
        "Function": sp.Function,
    }
    expr = parse_expr(raw, local_dict=local_dict, global_dict=safe_globals, transformations=_TRANSFORMS, evaluate=True)
    if not isinstance(expr, sp.Expr):
        raise ValueError(f"{context}: parsed object is not a symbolic expression")
    return expr


def _exprs_equal(lhs: sp.Expr, rhs: sp.Expr) -> bool:
    diff = sp.simplify(lhs - rhs)
    if diff == 0:
        return True
    eq = lhs.equals(rhs)
    return eq is True


def check_sympy_identity(check: dict) -> dict:
    """Verify a symbolic identity `lhs == rhs` under explicit variable assumptions."""
    ident = check["id"]
    symbols = _build_symbols(check.get("symbols"), f"{ident}")
    lhs = parse_safe_expr(check.get("lhs"), symbols, f"{ident}.lhs")
    rhs = parse_safe_expr(check.get("rhs"), symbols, f"{ident}.rhs")
    if not _exprs_equal(lhs, rhs):
        raise ValueError(f"{ident}: symbolic identity failed ({lhs} != {rhs})")
    return {"id": ident, "ok": True, "lhs": str(lhs), "rhs": str(rhs)}


def check_sympy_solve(check: dict) -> dict:
    """Verify that `solveset(Eq(lhs, rhs), variable, domain)` matches `expected_solutions`."""
    ident = check["id"]
    var_name = check.get("variable")
    if not isinstance(var_name, str) or not _SYMBOL_RE.fullmatch(var_name):
        raise ValueError(f"{ident}: variable must be a valid symbol name")
    domain_name = check.get("domain", "reals")
    if domain_name not in DOMAINS:
        raise ValueError(f"{ident}: unsupported domain {domain_name!r}; choose {', '.join(sorted(DOMAINS))}")
    raw_symbols = dict(check.get("symbols") or {})
    if var_name not in raw_symbols:
        default_assumption = {"complexes": {"complex": True}, "integers": {"integer": True}}.get(
            domain_name, {"real": True}
        )
        raw_symbols[var_name] = default_assumption
    symbols = _build_symbols(raw_symbols, f"{ident}")
    lhs = parse_safe_expr(check.get("lhs"), symbols, f"{ident}.lhs")
    rhs = parse_safe_expr(check.get("rhs"), symbols, f"{ident}.rhs")
    expected_raw = check.get("expected_solutions")
    if not isinstance(expected_raw, list) or len(expected_raw) > 20:
        raise ValueError(f"{ident}: expected_solutions must be a list of at most 20 expressions")
    expected_exprs = [
        parse_safe_expr(item, {}, f"{ident}.expected_solutions[{i}]") for i, item in enumerate(expected_raw)
    ]

    actual_set = sp.solveset(sp.Eq(lhs, rhs), symbols[var_name], domain=DOMAINS[domain_name])
    if actual_set is sp.S.EmptySet:
        actual_list: list[sp.Expr] = []
    elif isinstance(actual_set, sp.FiniteSet):
        actual_list = [arg for arg in actual_set.args if isinstance(arg, sp.Expr)]
        if len(actual_list) != len(actual_set.args):
            raise ValueError(f"{ident}: equation produced non-expression solutions ({actual_set})")
    else:
        raise ValueError(f"{ident}: equation did not resolve to a finite solution set ({actual_set})")

    if len(actual_list) != len(expected_exprs):
        raise ValueError(
            f"{ident}: solution count mismatch (actual {[str(x) for x in actual_list]}, "
            f"expected {[str(x) for x in expected_exprs]})"
        )
    unmatched = list(actual_list)
    for exp_expr in expected_exprs:
        match_idx = next((idx for idx, act in enumerate(unmatched) if _exprs_equal(act, exp_expr)), None)
        if match_idx is None:
            raise ValueError(
                f"{ident}: expected solution {exp_expr} not found in actual solutions {[str(x) for x in actual_list]}"
            )
        unmatched.pop(match_idx)
    return {
        "id": ident,
        "ok": True,
        "variable": var_name,
        "domain": domain_name,
        "solutions": [str(sp.simplify(x)) for x in expected_exprs],
    }


def check_sympy_formula_eval(check: dict) -> dict:
    """Substitute exact symbolic/numeric values into `formula` and verify `expected`."""
    ident = check["id"]
    raw_values = check.get("values")
    if not isinstance(raw_values, dict) or not raw_values or len(raw_values) > 16:
        raise ValueError(f"{ident}: values must be a non-empty object of at most 16 bindings")
    symbols = _build_symbols({k: {"real": True} for k in raw_values}, f"{ident}")
    formula = parse_safe_expr(check.get("formula"), symbols, f"{ident}.formula")
    subs: dict[sp.Basic | complex, sp.Expr | complex] = {}
    for name, raw_val in raw_values.items():
        val_str = str(raw_val) if type(raw_val) is int else raw_val
        subs[symbols[name]] = parse_safe_expr(val_str, {}, f"{ident}.values[{name}]")
    actual = sp.simplify(formula.subs(subs))
    if actual.free_symbols:
        raise ValueError(
            f"{ident}: formula has unbound symbols after substitution: {sorted(map(str, actual.free_symbols))}"
        )
    expected_raw = check.get("expected")
    expected_str = str(expected_raw) if type(expected_raw) is int else expected_raw
    expected = parse_safe_expr(expected_str, {}, f"{ident}.expected")
    if not _exprs_equal(actual, expected):
        raise ValueError(f"{ident}: formula evaluation mismatch (actual {actual}, expected {expected})")
    return {"id": ident, "ok": True, "actual": str(actual)}
