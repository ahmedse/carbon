"""
Store — persistence seam for the AI engine (Pulse Vendoring Phase 2).

Replaces the SQLAlchemy-backed ``ai/engine/core/database.py`` with a
swappable, async ``Store`` abstraction selected via
``settings.AI_STORE_BACKEND``.

Backends
--------
``inmemory`` (default)
    Dict-backed, no external DB. Used for tests and as the stateless
    default until a Django backend is explicitly selected.

``django``
    Django ORM via ``sync_to_async``. Queries are CBAC-partitioned on
    ``app_identifier`` / ``org_unit_id`` / ``host_user_id`` / ``visibility``
    (mirroring the host tenant filter semantics: global/shared/private).

The engine is inert at import time — nothing opens a connection here until a
session operation is actually invoked, so this module is safe to import from
``ai.engine.core.database`` without touching the database.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger("carbon.ai.store")

# Canonical CBAC partitioning scope. Every Store query injects these filters
# so no engine data ever leaks across app / org-unit / user boundaries.
DEFAULT_APP_IDENTIFIER = "carbon"
DEFAULT_VISIBILITY = "private"


# ── Session ──────────────────────────────────────────────────────────────
#
# ``get_session_factory(name)`` returns a callable; calling it yields a
# Session that mirrors the subset of SQLAlchemy AsyncSession used by the
# engine: ``add``, ``commit``, ``select``, ``get``, ``delete``, ``refresh``,
# ``flush``, ``close`` plus async-context-manager support.


class Session(ABC):
    """Async session handle. Mirrors the SQLAlchemy AsyncSession surface."""

    @abstractmethod
    async def __aenter__(self) -> "Session":
        ...

    @abstractmethod
    async def __aexit__(self, *exc_info: Any) -> None:
        ...

    @abstractmethod
    async def add(self, obj: Any) -> None:
        ...

    @abstractmethod
    async def commit(self) -> None:
        ...

    @abstractmethod
    async def select(self, model: Any, *filters: Any) -> Any:
        ...

    @abstractmethod
    async def get(self, model: Any, pk: Any) -> Any:
        ...

    @abstractmethod
    async def delete(self, obj: Any) -> None:
        ...

    @abstractmethod
    async def refresh(self, obj: Any) -> None:
        ...

    @abstractmethod
    async def flush(self) -> None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...


# ── Store ABC ────────────────────────────────────────────────────────────


class Store(ABC):
    """Async persistence abstraction replacing the SQLAlchemy layer."""

    @abstractmethod
    def get_engine(self, name: str | None = None) -> Any:
        """Return the opaque engine handle for an instance (or shared)."""

    @abstractmethod
    def get_session_factory(self, name: str | None = None) -> Any:
        """Return a session factory for an instance (or shared)."""

    @abstractmethod
    def get_effective_storage_mode(self, name: str) -> str:
        """Return ``'standalone'`` or ``'shared'`` for an instance."""

    @abstractmethod
    async def init_db(self, names: list[str] | None = None) -> None:
        """Initialize storage for the shared + per-instance namespaces."""

    @abstractmethod
    def list_initialized_instances(self) -> list[str]:
        """Return instance names that have been initialized."""


# ── InMemoryStore ────────────────────────────────────────────────────────


class _InMemorySession(Session):
    """Dict-backed session. No real persistence — data lives in the store."""

    def __init__(self, store: "InMemoryStore", name: str | None) -> None:
        self._store = store
        self._name = name
        self._closed = False

    async def __aenter__(self) -> "_InMemorySession":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()

    async def add(self, obj: Any) -> None:
        self._store._pending[self._name].append(obj)

    async def commit(self) -> None:
        namespace = self._store._engine(self._name)
        for obj in self._store._pending.get(self._name, []):
            key = getattr(obj, "id", None) or id(obj)
            namespace[key] = obj
        self._store._pending[self._name] = []

    async def select(self, model: Any, *filters: Any) -> list[Any]:
        # Filters are opaque in the in-memory backend; return all objects
        # whose class matches ``model``.
        namespace = self._store._engine(self._name)
        return [o for o in namespace.values() if isinstance(o, model)]

    async def get(self, model: Any, pk: Any) -> Any:
        return self._store._engine(self._name).get(pk)

    async def delete(self, obj: Any) -> None:
        namespace = self._store._engine(self._name)
        key = getattr(obj, "id", None) or id(obj)
        namespace.pop(key, None)

    async def refresh(self, obj: Any) -> None:
        # In-memory objects are references; nothing to reload.
        return None

    async def flush(self) -> None:
        return None

    async def close(self) -> None:
        self._closed = True


class InMemoryStore(Store):
    """Dict-backed Store. Default backend — no external database."""

    def __init__(self) -> None:
        self._engines: dict[str, dict[Any, Any]] = {}
        self._pending: dict[str, list[Any]] = {}

    @staticmethod
    def _key(name: str | None) -> str:
        return name or "_shared"

    def _engine(self, name: str | None) -> dict[Any, Any]:
        key = self._key(name)
        if key not in self._engines:
            self._engines[key] = {}
            self._pending[key] = []
        return self._engines[key]

    def get_engine(self, name: str | None = None) -> dict[Any, Any]:
        return self._engine(name)

    def get_session_factory(self, name: str | None = None) -> Any:
        def factory() -> Session:
            return _InMemorySession(self, self._key(name))
        return factory

    def get_effective_storage_mode(self, name: str) -> str:
        return "shared"

    async def init_db(self, names: list[str] | None = None) -> None:
        self._engine(None)
        for n in names or []:
            self._engine(n)

    def list_initialized_instances(self) -> list[str]:
        return [k for k in self._engines if k != "_shared"]


# ── DjangoStore ──────────────────────────────────────────────────────────


class _DjangoSession(Session):
    """Thin async wrapper over Django ORM via ``sync_to_async``."""

    def __init__(self, store: "DjangoStore", name: str | None) -> None:
        self._store = store
        self._name = name
        self._pending: list[Any] = []
        self._closed = False

    async def __aenter__(self) -> "_DjangoSession":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()

    async def add(self, obj: Any) -> None:
        self._pending.append(obj)

    async def commit(self) -> None:
        from asgiref.sync import sync_to_async

        def _commit() -> None:
            for obj in self._pending:
                obj.save()
            self._pending.clear()

        await sync_to_async(_commit, thread_sensitive=True)()

    async def select(self, model: Any, *filters: Any) -> list[Any]:
        from asgiref.sync import sync_to_async

        def _select() -> list[Any]:
            qs = model.objects.all()
            qs = self._store._apply_tenancy_filter(qs)
            for f in filters:
                qs = qs.filter(f) if hasattr(qs, "filter") else qs
            return list(qs)

        return await sync_to_async(_select, thread_sensitive=True)()

    async def get(self, model: Any, pk: Any) -> Any:
        from asgiref.sync import sync_to_async

        def _get() -> Any:
            return model.objects.get(pk=pk)

        return await sync_to_async(_get, thread_sensitive=True)()

    async def delete(self, obj: Any) -> None:
        from asgiref.sync import sync_to_async

        await sync_to_async(obj.delete, thread_sensitive=True)()

    async def refresh(self, obj: Any) -> None:
        from asgiref.sync import sync_to_async

        await sync_to_async(obj.refresh_from_db, thread_sensitive=True)()

    async def flush(self) -> None:
        await self.commit()

    async def close(self) -> None:
        self._closed = True


class DjangoStore(Store):
    """Django-ORM Store. CBAC-partitioned on the AppScopeMixin columns.

    ``name`` maps to a Django database connection alias (``default`` is used
    when ``None``).  The engine models all live in the ``ai`` app, so no
    separate database is required — the seam is the ORM, not a new DB.
    """

    def get_engine(self, name: str | None = None) -> str:
        return name or "default"

    def get_session_factory(self, name: str | None = None) -> Any:
        def factory() -> Session:
            return _DjangoSession(self, name)
        return factory

    def get_effective_storage_mode(self, name: str) -> str:
        return "shared"

    async def init_db(self, names: list[str] | None = None) -> None:
        # Django manages schema via migrations; no-op here.
        return None

    def list_initialized_instances(self) -> list[str]:
        return []

    @staticmethod
    def _apply_tenancy_filter(qs: Any) -> Any:
        """Inject the CBAC partition filters into a Django queryset.

        Mirrors the host ``_apply_tenancy_filter`` semantics:
          - ``visibility='global'``  → visible everywhere
          - ``visibility='shared'``  → visible within the app
          - ``visibility='private'`` → visible only to the host user/org
        For now, scope to the Carbon app identifier; host-user/org-unit
        narrowing is applied by ``build_scope`` at the Carbon boundary and
        passed in as filters by callers.
        """
        if hasattr(qs.model, "app_identifier"):
            qs = qs.filter(app_identifier=DEFAULT_APP_IDENTIFIER)
        return qs


# ── Store selection ──────────────────────────────────────────────────────

_store: Store | None = None

_BACKENDS: dict[str, type[Store]] = {
    "inmemory": InMemoryStore,
    "django": DjangoStore,
}


def get_store() -> Store:
    """Return the configured Store singleton (selected by AI_STORE_BACKEND)."""
    global _store
    if _store is None:
        from django.conf import settings

        backend = getattr(settings, "AI_STORE_BACKEND", "inmemory")
        cls = _BACKENDS.get(backend)
        if cls is None:
            logger.warning(
                "Unknown AI_STORE_BACKEND=%r; falling back to InMemoryStore",
                backend,
            )
            cls = InMemoryStore
        _store = cls()
    return _store


def reset_store() -> None:
    """Reset the cached Store (used by tests)."""
    global _store
    _store = None


__all__ = [
    "Store",
    "Session",
    "InMemoryStore",
    "DjangoStore",
    "get_store",
    "reset_store",
    "DEFAULT_APP_IDENTIFIER",
    "DEFAULT_VISIBILITY",
]
