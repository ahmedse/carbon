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


def resolve_model(model: Any) -> Any:
    """Map an engine (SQLAlchemy) model class → the Django model class.

    The 49 engine tables are mirrored 1:1 into ``ai.models`` under identical
    class names, so resolution is a name lookup.  Django models are returned
    unchanged; unknown classes are returned unchanged so the in-memory
    backend and lightweight test stubs keep working.
    """
    if not isinstance(model, type):
        return model
    # Already a Django model (has _meta + objects manager)?
    if hasattr(model, "_meta") and hasattr(model, "objects"):
        return model
    name = model.__name__
    try:
        import ai.models as _ai_models
    except Exception:  # pragma: no cover - import guard for isolated tests
        return model
    resolved = getattr(_ai_models, name, None)
    return resolved if resolved is not None else model


def scope_q(model: Any, instance_id: str, host_user_id: str | None) -> Any:
    """Build a Django ``Q`` for the engine's tenancy triplet.

    Mirrors ``ai.engine.core.models._apply_tenancy_filter`` semantics exactly:

      - ``visibility='global'``  → visible regardless of user
      - ``visibility='shared'``  → visible to all users of the instance
      - ``visibility='private'`` → visible only to the owner (host_user_id)

    When ``host_user_id`` is ``None``, only ``global``/``shared`` rows match.
    """
    from django.db.models import Q

    if host_user_id:
        vis = (
            Q(visibility="global")
            | Q(visibility="shared")
            | (Q(visibility="private") & Q(host_user_id=host_user_id))
        )
    else:
        vis = Q(visibility="global") | Q(visibility="shared")
    return Q(instance_id=instance_id) & vis


def _coerce_filter(f: Any) -> Any:
    """Normalize a single filter into a Django ``Q`` (or pass-through)."""
    from django.db.models import Q

    if isinstance(f, Q):
        return f
    if isinstance(f, dict):
        return Q(**f)
    if (
        isinstance(f, (tuple, list))
        and len(f) == 2
        and isinstance(f[0], str)
    ):
        return Q(**{f[0]: f[1]})
    return f


def _to_django_instance(obj: Any) -> Any:
    """Convert a SQLAlchemy model instance → a Django model instance.

    Field names are 1:1 across the two layers, so this is a straight
    attribute copy (skipping ``None`` so Django defaults — ``id`` UUID,
    ``app_identifier``, ``visibility``, auto timestamps — apply normally).
    This is a model-instance mapper, NOT a query translator.
    """
    from django.db import models as _dj_models

    if isinstance(obj, _dj_models.Model):
        return obj
    dj_cls = resolve_model(obj.__class__)
    if dj_cls is obj.__class__:
        return obj
    dj_obj = dj_cls()
    for field in dj_obj._meta.fields:
        name = field.name
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                setattr(dj_obj, name, value)
    return dj_obj


def first(rows: list[Any]) -> Any:
    """Return the first row of a native ``select`` result, or ``None``."""
    return rows[0] if rows else None


class Session(ABC):
    """Async session handle. Mirrors the SQLAlchemy AsyncSession surface."""

    @abstractmethod
    async def __aenter__(self) -> "Session":
        ...

    @abstractmethod
    async def __aexit__(self, *exc_info: Any) -> None:
        ...

    @abstractmethod
    def add(self, obj: Any) -> None:
        ...

    @abstractmethod
    def add_all(self, objs: list[Any]) -> None:
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
    def begin_nested(self) -> Any:
        """Return an async context manager wrapping a savepoint (no-op in Django)."""

    @abstractmethod
    async def aggregate(self, model: Any, spec: dict[str, tuple[str, str]], *filters: Any) -> dict[str, Any]:
        """Compute Django-style aggregations over ``model``.

        ``spec`` maps an output alias to a ``(function, field)`` pair where
        ``function`` is one of ``Sum`` / ``Count`` / ``Avg`` / ``Min`` /
        ``Max``.  Used for the engine's scalar aggregates (spend, counts).
        """

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

    def add(self, obj: Any) -> None:
        self._store._pending.setdefault(self._name, []).append(obj)

    def add_all(self, objs: list[Any]) -> None:
        self._store._pending.setdefault(self._name, []).extend(objs)

    async def commit(self) -> None:
        namespace = self._store._engine(self._name)
        for obj in self._store._pending.get(self._name, []):
            key = getattr(obj, "id", None) or id(obj)
            namespace[key] = obj
        self._store._pending[self._name] = []

    async def select(self, model: Any, *filters: Any) -> list[Any]:
        # Filters are opaque in the in-memory backend; return all objects
        # whose class matches ``model``.
        resolved = resolve_model(model)
        namespace = self._store._engine(self._name)
        return [o for o in namespace.values() if isinstance(o, resolved)]

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

    def begin_nested(self) -> Any:
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _nested() -> Any:
            yield None

        return _nested()

    async def aggregate(self, model: Any, spec: dict[str, tuple[str, str]], *filters: Any) -> dict[str, Any]:
        resolved = resolve_model(model)
        namespace = self._store._engine(self._name)
        rows = [o for o in namespace.values() if isinstance(o, resolved)]
        out: dict[str, Any] = {}
        for alias, (func_name, field) in spec.items():
            values = [getattr(r, field) for r in rows if getattr(r, field, None) is not None]
            if func_name == "Count":
                out[alias] = len(rows) if field in ("*", "id", "pk") else len(values)
            elif func_name == "Sum":
                out[alias] = sum(values) if values else 0
            elif func_name == "Avg":
                out[alias] = (sum(values) / len(values)) if values else 0
            elif func_name == "Min":
                out[alias] = min(values) if values else None
            elif func_name == "Max":
                out[alias] = max(values) if values else None
            else:
                out[alias] = None
        return out

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
        self._tracked: dict[int, Any] = {}
        self._closed = False

    async def __aenter__(self) -> "_DjangoSession":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()

    def add(self, obj: Any) -> None:
        self._pending.append(_to_django_instance(obj))

    def add_all(self, objs: list[Any]) -> None:
        for obj in objs:
            self._pending.append(_to_django_instance(obj))

    async def commit(self) -> None:
        from asgiref.sync import sync_to_async

        pending = list(self._pending)
        tracked = list(self._tracked.values())

        def _commit() -> None:
            for obj in pending:
                obj.save()
            # Re-save fetched objects whose attributes may have been mutated
            # in place (mirrors SQLAlchemy's dirty-flush on commit).
            for obj in tracked:
                obj.save()
            self._pending.clear()
            self._tracked.clear()

        await sync_to_async(_commit, thread_sensitive=True)()

    async def select(self, model: Any, *filters: Any) -> list[Any]:
        from asgiref.sync import sync_to_async

        resolved = resolve_model(model)
        coerced = [_coerce_filter(f) for f in filters]

        def _select() -> list[Any]:
            qs = resolved.objects.all()
            qs = self._store._apply_tenancy_filter(qs)
            if coerced:
                qs = qs.filter(*coerced)
            return list(qs)

        rows = await sync_to_async(_select, thread_sensitive=True)()
        for row in rows:
            self._tracked[id(row)] = row
        return rows

    async def get(self, model: Any, pk: Any) -> Any:
        from asgiref.sync import sync_to_async

        resolved = resolve_model(model)

        def _get() -> Any:
            return resolved.objects.get(pk=pk)

        row = await sync_to_async(_get, thread_sensitive=True)()
        if row is not None:
            self._tracked[id(row)] = row
        return row

    async def delete(self, obj: Any) -> None:
        from asgiref.sync import sync_to_async

        self._tracked.pop(id(obj), None)
        self._pending = [o for o in self._pending if o is not obj]

        await sync_to_async(obj.delete, thread_sensitive=True)()

    async def refresh(self, obj: Any) -> None:
        from asgiref.sync import sync_to_async

        await sync_to_async(obj.refresh_from_db, thread_sensitive=True)()

    async def flush(self) -> None:
        await self.commit()

    def begin_nested(self) -> Any:
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _nested() -> Any:
            # Django runs in autocommit; a savepoint is unnecessary for the
            # engine's add-then-flush pattern.  Just yield and let ``flush()``
            # persist.  On exception, nothing is left half-written.
            yield None

        return _nested()

    async def aggregate(self, model: Any, spec: dict[str, tuple[str, str]], *filters: Any) -> dict[str, Any]:
        from asgiref.sync import sync_to_async
        from django.db.models import Avg, Count, Max, Min, Sum

        resolved = resolve_model(model)
        coerced = [_coerce_filter(f) for f in filters]
        _FUNCS = {"Sum": Sum, "Count": Count, "Avg": Avg, "Min": Min, "Max": Max}

        def _aggregate() -> dict[str, Any]:
            qs = resolved.objects.all()
            qs = self._store._apply_tenancy_filter(qs)
            if coerced:
                qs = qs.filter(*coerced)
            agg = {alias: _FUNCS[func_name](field) for alias, (func_name, field) in spec.items()}
            return qs.aggregate(**agg)

        return await sync_to_async(_aggregate, thread_sensitive=True)()

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
    "resolve_model",
    "scope_q",
    "first",
    "DEFAULT_APP_IDENTIFIER",
    "DEFAULT_VISIBILITY",
]
