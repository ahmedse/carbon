"""
Persistence facade — delegates to the configured Store (Phase 2).

The SQLAlchemy-backed engine database is retired.  This module keeps the same
public function names used by the engine internals
(``get_engine``, ``get_session_factory``, ``get_effective_storage_mode``,
``get_db``, ``get_instance_db``, ``init_db``, ``list_initialized_instances``)
but now delegates to a swappable :mod:`ai.store` backend selected via
``settings.AI_STORE_BACKEND``.

The engine is inert at import time, so nothing opens a connection here until
a session operation is actually invoked.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any

from ai.store import Store, get_store

_log = logging.getLogger("pulse.database")


def _store() -> Store:
    return get_store()


def get_engine(instance_name: str | None = None):
    """Return the opaque engine handle for an instance (or shared)."""
    return _store().get_engine(instance_name)


def get_session_factory(instance_name: str | None = None):
    """Return the session factory for an instance (or shared)."""
    return _store().get_session_factory(instance_name)


def get_effective_storage_mode(instance_name: str) -> str:
    """Return ``'standalone'`` or ``'shared'`` for an instance."""
    return _store().get_effective_storage_mode(instance_name)


async def get_db() -> AsyncGenerator[Any, None]:
    """Async context manager yielding a session from the shared store.

    Retained for engine-internal FastAPI dependency compatibility.
    """
    session_factory = get_session_factory(None)
    async with session_factory() as session:
        yield session


async def get_instance_db(instance_name: str) -> AsyncGenerator[Any, None]:
    """Async context manager yielding a per-instance session."""
    session_factory = get_session_factory(instance_name)
    async with session_factory() as session:
        yield session


async def init_db(instance_names: list[str] | None = None) -> None:
    """Initialize storage for the shared + per-instance namespaces."""
    await _store().init_db(instance_names)


def list_initialized_instances() -> list[str]:
    """Return the list of instance names that have been initialized."""
    return _store().list_initialized_instances()


__all__ = [
    "get_engine",
    "get_session_factory",
    "get_effective_storage_mode",
    "get_db",
    "get_instance_db",
    "init_db",
    "list_initialized_instances",
]
