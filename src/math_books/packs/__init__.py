"""Pluggable domain pack protocol and auto-registration."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable


@dataclasses.dataclass(frozen=True)
class DomainPack:
    """Declarative bundle of themes, visual blocks, UI strings, and review checkers."""

    name: str
    description: str
    default_theme: str
    register_fn: Callable[[], None]


_PACKS: dict[str, DomainPack] = {}
_LOADED = False


def register_pack(pack: DomainPack) -> DomainPack:
    _PACKS[pack.name] = pack
    pack.register_fn()
    return pack


def ensure_packs_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    from math_books.packs import basketball

    basketball.register_domain_pack()


def list_packs() -> dict[str, DomainPack]:
    ensure_packs_loaded()
    return dict(_PACKS)


def get_pack(name: str) -> DomainPack:
    ensure_packs_loaded()
    if name not in _PACKS:
        available = ", ".join(sorted(_PACKS))
        raise ValueError(f"Unknown domain pack {name!r}. Available: {available}")
    return _PACKS[name]
