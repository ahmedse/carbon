"""Store port — the engine-facing persistence seam (P2-03).

The vendored engine must not import the host's concrete ``ai.store`` module
directly.  This module declares the *shape* of the store the engine depends
on as stdlib-only ``typing.Protocol`` classes, so the host can inject its
concrete backend (``ai.store.DjangoStore``) at bootstrap time without the
engine holding a host import.

Protocols are structural: any object implementing these methods satisfies the
port, so the host store needs no inheritance from this module.
"""
from __future__ import annotations

from typing import Any, Protocol


class Session(Protocol):
    """Async session handle — mirrors the SQLAlchemy AsyncSession surface."""

    async def __aenter__(self) -> "Session":
        ...

    async def __aexit__(self, *exc_info: Any) -> None:
        ...

    def add(self, obj: Any) -> None:
        ...

    def add_all(self, objs: list[Any]) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def select(self, model: Any, *filters: Any) -> Any:
        ...

    async def get(self, model: Any, pk: Any) -> Any:
        ...

    async def delete(self, obj: Any) -> None:
        ...

    async def refresh(self, obj: Any) -> None:
        ...

    async def flush(self) -> None:
        ...

    def begin_nested(self) -> Any:
        """Return an async context manager wrapping a savepoint."""

    async def aggregate(self, model: Any, spec: dict[str, tuple[str, str]], *filters: Any) -> dict[str, Any]:
        ...

    async def close(self) -> None:
        ...

    def execute(self, statement: Any, params: Any = None, **kwargs: Any) -> Any:
        ...

    def get_bind(self, *args: Any, **kwargs: Any) -> Any:
        ...

    async def rollback(self) -> None:
        ...


class Store(Protocol):
    """Async persistence abstraction the engine delegates to."""

    def get_engine(self, name: str | None = None) -> Any:
        """Return the opaque engine handle for an instance (or shared)."""

    def get_session_factory(self, name: str | None = None) -> Any:
        """Return a session factory for an instance (or shared)."""

    def get_effective_storage_mode(self, name: str) -> str:
        """Return ``'standalone'`` or ``'shared'`` for an instance."""

    async def init_db(self, names: list[str] | None = None) -> None:
        """Initialize storage for the shared + per-instance namespaces."""

    def list_initialized_instances(self) -> list[str]:
        """Return instance names that have been initialized."""


__all__ = ["Session", "Store"]
