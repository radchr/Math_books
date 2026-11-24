"""Exact example data used by the educational scenes."""

from fractions import Fraction
from itertools import product


def coin_followup_examples() -> list[tuple[str, Fraction]]:
    """All length-three fair-coin sequences with at least one observable H-followup.

    An equal-weight mean of these six rates is 5/12. Pooling their eight
    eligible transitions gives 1/2. Neither changes a future fair-coin flip.
    """
    rows = []
    for flips in product("ОР", repeat=3):
        following = [flips[i + 1] for i in range(2) if flips[i] == "О"]
        if following:
            rows.append(("".join(flips), Fraction(following.count("О"), len(following))))
    return rows
