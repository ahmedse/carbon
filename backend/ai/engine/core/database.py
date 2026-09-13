"""
Persistence facade — delegates to the host-injected Store (P2-03).

The SQLAlchemy-backed engine database is retired.  This module keeps the same
public function names used by the engine internals
(``get_engine``, ``get_session_factory``, ``get_effective_storage_mode``,
``get_db``, ``get_instance_db``, ``init_db``, ``list_initialized_instances``)
but now delegates to a swappable :class:`~ai.engine.ports.store.Store`
provided by the host at bootstrap time.

The engine is inert at import time and holds NO ``ai.store`` import: the host
must call :func:`set_store_provider` during bootstrap (``ai.apps.AIConfig.ready``).
Until then, :func:`get_store` raises a clear ``RuntimeError`` rather than
silently falling back to an ephemeral store.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Callable
from typing import Any

from ai.engine.ports.store import Store

_log = logging.getLogger("pulse.database")

# Host-injected provider returning the concrete Store backend.  The engine
# never imports ``ai.store``; the host (``ai.apps.AIConfig.ready``) wires it.
_store_provider: Callable[[], Store] | None = None


def set_store_provider(provider: Callable[[], Store]) -> None:
    """Inject the host's concrete Store provider at bootstrap time.

    Called once from ``ai.apps.AIConfig.ready`` (and from test helpers that
    construct the engine directly).
    """
    global _store_provider
    _store_provider = provider


def get_store() -> Store:
    """Return the host-injected Store, or fail-closed when not injected."""
    if _store_provider is None:
        raise RuntimeError(
            "Pulse store provider not injected; call "
            "ai.engine.core.database.set_store_provider() during bootstrap"
        )
    return _store_provider()


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
    "get_store",
    "set_store_provider",
    "get_engine",
    "get_session_factory",
    "get_effective_storage_mode",
    "get_db",
    "get_instance_db",
    "init_db",
    "list_initialized_instances",
]
