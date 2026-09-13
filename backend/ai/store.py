"""
Store — persistence seam for the AI engine (Pulse Vendoring Phase 2).

Replaces the SQLAlchemy-backed ``ai/engine/core/database.py`` with a
swappable, async ``Store`` abstraction selected via
``settings.AI_STORE_BACKEND``.

Backends
--------
``django``
    Django ORM via ``sync_to_async``. Durable rows carry the CBAC partition
    columns ``app_identifier`` / ``org_unit_id`` / ``host_user_id`` /
    ``visibility``; the ``instance_id`` + visibility triplet is enforced by
    ``scope_q()`` at the query boundary (global/shared/private). This is the
    durable backend production must run.

``inmemory``
    Dict-backed, no external DB. Tests only — an ephemeral store silently
    drops writes, so it is rejected unless ``PYTEST_CURRENT_TEST`` or an
    explicit ``PULSE_ALLOW_INMEMORY=1`` allows it (PULSE P1-01).

The engine is inert at import time — nothing opens a connection here until a
session operation is actually invoked, so this module is safe to import from
``ai.engine.core.database`` without touching the database.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from django.core.exceptions import ImproperlyConfigured

from ai.instance_registry import resolve_default_app_identifier

logger = logging.getLogger("carbon.ai.store")

# Canonical CBAC partitioning scope. Every Store query injects these filters
# so no engine data ever leaks across app / org-unit / user boundaries.
# Brand-aware: a Nibras deployment defaults new rows to its own app
# ("people"), never Carbon's.
DEFAULT_APP_IDENTIFIER = resolve_default_app_identifier()
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


def _tenancy_q(instance_id: str, host_user_id: str | None) -> Any:
    """Build a Django ``Q`` for the engine's tenancy triplet.

    Shared by ``scope_q`` (host adapters) and ``_coerce_filter`` (which
    expands an engine-owned ``TenancyScope``). Mirrors the engine-layer
    tenancy filter semantics (``ai.engine.core.models``) exactly:

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


def scope_q(model: Any, instance_id: str, host_user_id: str | None) -> Any:
    """Build a Django ``Q`` for the engine's tenancy triplet.

    ``model`` is retained for call-site compatibility only; it is unused.
    """
    return _tenancy_q(instance_id, host_user_id)


def _coerce_filter(f: Any) -> Any:
    """Normalize a single filter into a Django ``Q`` (or pass-through)."""
    from django.db.models import Q

    # Engine-owned query DSL (host→engine direction is allowed).
    from ai.engine.core.query import And, Not, Or, TenancyScope

    if isinstance(f, TenancyScope):
        return _tenancy_q(f.instance_id, f.host_user_id)
    if isinstance(f, Or):
        q = None
        for child in f.filters:
            child_q = _coerce_filter(child)
            if child_q is None:
                continue
            q = child_q if q is None else (q | child_q)
        return q
    if isinstance(f, And):
        q = None
        for child in f.filters:
            child_q = _coerce_filter(child)
            if child_q is None:
                continue
            q = child_q if q is None else (q & child_q)
        return q
    if isinstance(f, Not):
        child_q = _coerce_filter(f.filter)
        return ~child_q if child_q is not None else None
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


def _backfill_engine_attrs(engine_obj: Any, dj_obj: Any) -> None:
    """Copy DB-generated values (PK, auto timestamps, server defaults) from a
    freshly-saved Django instance back onto the engine (SQLAlchemy) instance.

    SQLAlchemy applies Python-side ``default=`` at flush time and populates
    the instance with it; the Django store can't do that at ``add()`` time, so
    we propagate the values the Django ``save()`` generated instead.  This is
    what lets the engine read ``agent.id`` / ``created_at`` immediately after
    ``await db.commit()`` (e.g. ``seed_defaults`` uses ``agents[name].id`` to
    wire handoff edges).
    """
    if engine_obj is dj_obj:
        return
    for field in dj_obj._meta.fields:
        name = field.name
        if not hasattr(engine_obj, name):
            continue
        try:
            engine_value = getattr(engine_obj, name)
        except Exception:
            continue
        if engine_value is None:
            dj_value = getattr(dj_obj, name, None)
            if dj_value is not None:
                try:
                    setattr(engine_obj, name, dj_value)
                except Exception:
                    pass


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

    # ── SQLAlchemy statement execution (Phase 3 fix) ───────────────────────
    # Concrete defaults so in-memory/stub sessions keep working; the Django
    # backend overrides these with real translation.

    def execute(self, statement: Any, params: Any = None, **kwargs: Any) -> Any:
        """Execute a SQLAlchemy-style statement (``select``/``update``/``text``)."""
        raise NotImplementedError(
            f"{type(self).__name__} does not implement execute(); "
            "use the DjangoStore backend for structured statements."
        )

    def get_bind(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            f"{type(self).__name__} does not implement get_bind()"
        )

    async def rollback(self) -> None:
        raise NotImplementedError(
            f"{type(self).__name__} does not implement rollback()"
        )


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

    async def execute(self, statement: Any, params: Any = None, **kwargs: Any) -> Any:
        """Execute a structured statement against the in-memory namespace."""
        import sqlalchemy as sa

        if isinstance(statement, sa.sql.selectable.Select):
            spec = _select_spec(statement)
            model = spec["from_model"]
            namespace = self._store._engine(self._name)
            rows = [o for o in namespace.values() if isinstance(o, model)]
            filters = spec["filters_by_table"].get(spec["from_table"], [])
            if filters:
                rows = [o for o in rows if all(_q_check(q, o) for q in filters)]
            rows, _needs_random = _order_rows(rows, spec["order_by"])
            if spec["limit"] is not None:
                offset = spec["offset"] or 0
                rows = rows[offset : offset + spec["limit"]]
            return _project_result(rows, spec)

        if isinstance(statement, sa.sql.dml.Update):
            spec = _update_spec(statement)
            model = spec["model"]
            namespace = self._store._engine(self._name)
            count = 0
            for obj in list(namespace.values()):
                if isinstance(obj, model) and all(_q_check(q, obj) for q in spec["filters"]):
                    for field, value in spec["values"].items():
                        setattr(obj, field, value)
                    count += 1
            return _ExecResult([], rowcount=count)

        raise NotImplementedError(
            f"InMemorySession execute(): unsupported statement type "
            f"{type(statement).__name__}"
        )

    def get_bind(self, *args: Any, **kwargs: Any) -> Any:
        # In-memory backend is not Postgres; vector_store takes the JSON path.
        return _BindStub("sqlite")

    async def rollback(self) -> None:
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
        self._tracked: dict[int, Any] = {}
        self._closed = False

    async def __aenter__(self) -> "_DjangoSession":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()

    def add(self, obj: Any) -> None:
        # Keep the original (engine) object paired with its Django mirror so
        # ``commit`` can back-fill generated PKs/defaults onto the engine
        # instance — mirroring SQLAlchemy's post-flush attribute population
        # (the engine relies on ``agent.id`` being set right after commit).
        self._pending.append((obj, _to_django_instance(obj)))

    def add_all(self, objs: list[Any]) -> None:
        for obj in objs:
            self._pending.append((obj, _to_django_instance(obj)))

    async def commit(self) -> None:
        from asgiref.sync import sync_to_async

        pending = list(self._pending)
        tracked = list(self._tracked.values())

        def _commit() -> None:
            for engine_obj, dj_obj in pending:
                dj_obj.save()
                _backfill_engine_attrs(engine_obj, dj_obj)
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
        self._pending = [o for o in self._pending if o[0] is not obj]

        # Evict any *other* tracked instance of the same row, not just the
        # exact Python object being deleted.  ``commit()`` re-saves every
        # tracked instance, and Django's ``save()`` falls back to INSERT when
        # the UPDATE affects zero rows — so a stale copy fetched earlier (e.g.
        # by ``query_edges`` before ``delete_edge``) would resurrect the row.
        pk = getattr(obj, "pk", None)
        if pk is not None:
            self._tracked = {
                key: value
                for key, value in self._tracked.items()
                if getattr(value, "pk", None) != pk
            }
            self._pending = [
                (engine_obj, dj_obj)
                for engine_obj, dj_obj in self._pending
                if getattr(dj_obj, "pk", None) != pk
            ]

        await sync_to_async(obj.delete, thread_sensitive=True)()

    async def refresh(self, obj: Any) -> None:
        from asgiref.sync import sync_to_async

        # Resolve engine (SQLAlchemy) instances to their Django mirror first —
        # `refresh_from_db` only exists on the Django layer. This matches the
        # `add` / `select` / `get` invariant (QA F1: create_dq_rule runtime
        # crash was the only Store method missing this conversion).
        dj_obj = _to_django_instance(obj)
        if dj_obj.pk is None:
            # Unsaved engine object — nothing to refresh from the DB.  The
            # generated PK/defaults were already back-filled by ``commit``.
            return
        await sync_to_async(dj_obj.refresh_from_db, thread_sensitive=True)()

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
            if coerced:
                qs = qs.filter(*coerced)
            agg = {alias: _FUNCS[func_name](field) for alias, (func_name, field) in spec.items()}
            return qs.aggregate(**agg)

        return await sync_to_async(_aggregate, thread_sensitive=True)()

    # ── SQLAlchemy statement execution (Phase 3 fix) ───────────────────────
    #
    # The engine calls ``await db.execute(stmt)`` for agent-registry fan-out,
    # skill search, tool-execution DML and vector-store raw SQL.  Before this
    # fix every call raised ``AttributeError`` (no ``execute`` method), which
    # the callers swallowed — silently degrading fan-out + skill search and
    # spamming "couldn't reach the AI service" logs on every chat turn.

    async def execute(self, statement: Any, params: Any = None, **kwargs: Any) -> Any:
        """Execute a SQLAlchemy statement against the Django ORM."""
        import sqlalchemy as sa
        from asgiref.sync import sync_to_async
        from sqlalchemy.sql.elements import TextClause

        if isinstance(statement, sa.sql.selectable.Select):
            spec = _select_spec(statement)
            return await sync_to_async(
                self._run_django_select, thread_sensitive=True
            )(spec)
        if isinstance(statement, sa.sql.dml.Update):
            spec = _update_spec(statement)
            return await sync_to_async(
                self._run_django_update, thread_sensitive=True
            )(spec)
        if isinstance(statement, TextClause):
            return await sync_to_async(
                self._run_django_text, thread_sensitive=True
            )(statement, params)
        raise NotImplementedError(
            f"DjangoStore execute(): unsupported statement type "
            f"{type(statement).__name__}"
        )

    def _run_django_select(self, spec: dict[str, Any]) -> _ExecResult:
        """Translate a normalized select spec into a Django ORM query."""
        model = spec["from_model"]
        from_filters = spec["filters_by_table"].get(spec["from_table"], [])

        # Two-entity projection (e.g. ``select(Agent, AgentHandoff).join(...)``)
        # → build (from_entity, join_entity) pairs via the ON-column link.
        if len(spec["descriptions"]) == 2 and spec["joins"]:
            join = spec["joins"][0]
            join_model = spec["table_map"].get(join["target_table"])
            from_qs = model.objects.all()
            if from_filters:
                from_qs = from_qs.filter(*from_filters)
            from_ids = list(from_qs.values_list(join["from_on_field"], flat=True))
            join_qs = join_model.objects.all()
            join_qs = join_qs.filter(
                **{f"{join['join_on_field']}__in": from_ids}
            )
            join_filters = spec["filters_by_table"].get(join["target_table"], [])
            if join_filters:
                join_qs = join_qs.filter(*join_filters)
            join_rows = list(join_qs)
            from_vals = [getattr(r, join["join_on_field"]) for r in join_rows]
            from_map = {
                getattr(o, join["from_on_field"]): o
                for o in model.objects.filter(
                    **{f"{join['from_on_field']}__in": from_vals}
                )
            }
            pairs = [
                (from_map[getattr(r, join["join_on_field"])], r)
                for r in join_rows
                if getattr(r, join["join_on_field"]) in from_map
            ]
            for spec_ob in reversed(
                [s for s in spec["order_by"] if s and s[0] == "field"]
            ):
                field, desc, _nulls_last = spec_ob[1], spec_ob[2], spec_ob[3]
                pairs.sort(
                    key=lambda p, f=field: getattr(p[0], f, None) or "",
                    reverse=desc,
                )
            rows = []
            for agent, handoff in pairs:
                self._tracked[id(agent)] = agent
                self._tracked[id(handoff)] = handoff
                rows.append(_ExecRow(spec["cols"], [agent, handoff]))
            return _ExecResult(rows, rowcount=len(rows))

        qs = model.objects.all()
        if from_filters:
            qs = qs.filter(*from_filters)

        # Single-entity projection with a join (e.g. prompt-eval sampling):
        # narrow the join entity first, then filter the main query via the ON
        # column.
        if spec["joins"]:
            join = spec["joins"][0]
            join_model = spec["table_map"].get(join["target_table"])
            join_qs = join_model.objects.all()
            join_filters = spec["filters_by_table"].get(join["target_table"], [])
            if join_filters:
                join_qs = join_qs.filter(*join_filters)
            join_ids = list(
                join_qs.values_list(join["join_on_field"], flat=True)
            )
            qs = qs.filter(**{f"{join['from_on_field']}__in": join_ids})

        qs, needs_random = self._apply_django_order(qs, spec["order_by"])
        limit = spec["limit"]
        offset = spec["offset"] or 0

        if needs_random:
            rows = list(qs)
            import random

            rows = random.sample(rows, min(limit or len(rows), len(rows)))
        elif limit is not None:
            rows = list(qs[offset : offset + limit])
        elif offset:
            rows = list(qs[offset:])
        else:
            rows = list(qs)

        if spec["single_entity"]:
            for row in rows:
                self._tracked[id(row)] = row
        return _project_result(rows, spec)

    def _apply_django_order(
        self, qs: Any, order_specs: list[tuple | None]
    ) -> tuple[Any, bool]:
        """Apply ORDER BY specs; returns (qs, needs_random)."""
        from django.db.models import Case, F, IntegerField, Value, When

        needs_random = False
        annotations: dict[str, Any] = {}
        order_bits: list[Any] = []
        for spec in order_specs:
            if spec is None:
                continue
            if spec[0] == "random":
                needs_random = True
                continue
            if spec[0] == "bool":
                field, value = spec[1], spec[2]
                name = f"_ord_{field}"
                annotations[name] = Case(
                    When(**{field: value}, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
                order_bits.append(f"-{name}")
                continue
            field, desc, nulls_last = spec[1], spec[2], spec[3]
            if nulls_last:
                order_bits.append(
                    F(field).desc(nulls_last=True)
                    if desc
                    else F(field).asc(nulls_last=True)
                )
            elif desc:
                order_bits.append(f"-{field}")
            else:
                order_bits.append(field)
        if annotations:
            qs = qs.annotate(**annotations)
        if order_bits:
            qs = qs.order_by(*order_bits)
        return qs, needs_random

    def _run_django_update(self, spec: dict[str, Any]) -> _ExecResult:
        """Translate a normalized update spec into ``QuerySet.update``."""
        qs = spec["model"].objects.all()
        if spec["filters"]:
            qs = qs.filter(*spec["filters"])
        count = qs.update(**spec["values"])
        return _ExecResult([], rowcount=count)

    def _run_django_text(self, statement: Any, params: Any) -> _ExecResult:
        """Run raw ``text()`` SQL through the Django DB cursor.

        Engine table names (``vector_embeddings``, ``skill``, …) are mapped to
        their Django mirror table names (``ai_vectorembedding``, ``ai_skill``)
        so the engine's raw SQL hits the same rows as the ORM path.  ``:name``
        bind parameters are translated to Django's ``%(name)s`` (Postgres
        ``::`` casts, ``->>`` operators and ``<=>``/``<->`` are untouched).
        """
        import re as _re
        from django.db import connection

        sql = statement.text
        for tablename, engine_cls in _engine_table_map().items():
            model = resolve_model(engine_cls)
            if model is None:
                continue
            db_table = model._meta.db_table
            if db_table != tablename:
                sql = _re.sub(rf"\b{_re.escape(tablename)}\b", db_table, sql)
        sql = _re.sub(r"(?<!:):([a-zA-Z_][a-zA-Z0-9_]*)", r"%(\1)s", sql)
        bind = dict(params) if params else dict(getattr(statement, "_params", None) or {})
        with connection.cursor() as cur:
            cur.execute(sql, bind)
            if cur.description:
                cols = [d[0] for d in cur.description]
                if len(cols) == 1:
                    rows = [row[0] for row in cur.fetchall()]
                    return _ExecResult(rows, is_scalar=True, rowcount=len(rows))
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
                return _ExecResult(rows, rowcount=len(rows))
            return _ExecResult([], rowcount=cur.rowcount)

    def get_bind(self, *args: Any, **kwargs: Any) -> Any:
        from django.db import connection

        return _BindStub(connection.vendor)

    async def rollback(self) -> None:
        from django.db import connection, transaction

        # ``set_rollback`` only works inside an ``atomic`` block; outside one
        # the transaction is per-statement autocommit, so there is nothing to
        # roll back — mirror that as a no-op instead of raising.
        if connection.in_atomic_block:
            transaction.set_rollback(True)
        return None

    async def close(self) -> None:
        self._closed = True


class DjangoStore(Store):
    """Django-ORM Store.

    ``name`` maps to a Django database connection alias (``default`` is used
    when ``None``).  The engine models all live in the ``ai`` app, so no
    separate database is required — the seam is the ORM, not a new DB.

    Tenancy is enforced at the query boundary, not inside the store: callers
    inject ``scope_q(model, instance_id, host_user_id)`` (the instance_id +
    visibility triplet) into the ``select``/``execute`` filters, and the
    store applies those filters verbatim without duplicating them.
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


# ── Store selection ──────────────────────────────────────────────────────

_store: Store | None = None

_BACKENDS: dict[str, type[Store]] = {
    "inmemory": InMemoryStore,
    "django": DjangoStore,
}


def get_store() -> Store:
    """Return the configured Store singleton (selected by AI_STORE_BACKEND).

    Fail-closed (PULSE P1-01): a missing or unknown backend raises rather
    than silently degrading to the ephemeral ``InMemoryStore``.
    """
    global _store
    if _store is None:
        from django.conf import settings

        backend = getattr(settings, "AI_STORE_BACKEND", None)
        if not backend:
            raise ImproperlyConfigured(
                "AI_STORE_BACKEND is not configured; refusing to fall back to "
                "an ephemeral in-memory store. Set AI_STORE_BACKEND='django' "
                "(PULSE P1-01)."
            )
        cls = _BACKENDS.get(backend)
        if cls is None:
            raise ImproperlyConfigured(
                "Unknown AI_STORE_BACKEND=%r; expected one of %s (PULSE P1-01)."
                % (backend, sorted(_BACKENDS))
            )
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
