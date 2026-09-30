"""Probe registry: how a domain app answers questions a pack asks about the host.

A pack (``domain_packs/<id>/guide/guide.yaml``) names probes; the domain app
registers them. The engine never imports a domain module by name. It imports
whatever module the pack lists under ``probes:``.

Kinds and signatures (``lesson`` is the pack's lesson mapping):

    live      fn(ctx, lesson) -> dict          the live object the coach shows
    need      fn(ctx, lesson) -> dict | None   a blocker ``{code, path}`` or None
    host      fn(ctx, lesson) -> bool          a host fact a lesson also needs
    question  fn(ctx, lesson) -> dict          ``{params, correct}``; ``correct`` stays on the server

Every probe is read-only and reads only the caller's own scope.
"""
from __future__ import annotations

from typing import Callable

PLATFORM = "_platform"
KINDS = ("live", "need", "host", "question")
_PROBES: dict[tuple[str, str, str], Callable] = {}


def probe(pack_id: str, kind: str, name: str):
    if kind not in KINDS:
        raise ValueError(f"unknown probe kind: {kind}")

    def deco(fn: Callable) -> Callable:
        _PROBES[(pack_id, kind, name)] = fn
        return fn

    return deco


def find(pack_id: str, kind: str, name: str) -> Callable | None:
    return _PROBES.get((pack_id, kind, name)) or _PROBES.get((PLATFORM, kind, name))


def registered() -> dict[tuple[str, str, str], Callable]:
    return dict(_PROBES)
