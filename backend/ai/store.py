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


# ── SQLAlchemy statement translation (used by ``execute``) ───────────────
#
# The engine calls ``await session.execute(stmt)`` with real SQLAlchemy 2.0
# statements (``select()`` / ``update()`` / ``text()``).  The in-memory and
# Django backends translate those statements into their own query surface
# instead of letting them crash with ``AttributeError`` (the Phase 3 bug that
# silently degraded agent fan-out + skill search on every chat turn).

_ENGINE_TABLE_CACHE: dict[str, Any] | None = None


def _engine_table_map() -> dict[str, Any]:
    """Map engine ``__tablename__`` → SQLAlchemy model class (lazy, cached)."""
    global _ENGINE_TABLE_CACHE
    if _ENGINE_TABLE_CACHE is None:
        import ai.engine.core.models as _em

        _ENGINE_TABLE_CACHE = {
            _cls.__tablename__: _cls
            for _cls in vars(_em).values()
            if isinstance(_cls, type) and hasattr(_cls, "__tablename__")
        }
    return _ENGINE_TABLE_CACHE


def _stmt_model(entity: Any) -> Any:
    """Map a SQLAlchemy entity (model class or Table) → Django model class."""
    from sqlalchemy import Table

    if isinstance(entity, Table):
        engine_cls = _engine_table_map().get(entity.name)
        return resolve_model(engine_cls) if engine_cls is not None else entity
    return resolve_model(entity)


def _column_field(col: Any) -> str | None:
    """Field name of a SQLAlchemy column (``.key`` wins over ``.name``)."""
    return getattr(col, "key", None) or getattr(col, "name", None)


def _literal(value: Any) -> Any:
    """Coerce SQLAlchemy literal/expression wrappers to plain Python values."""
    from sqlalchemy.sql import elements as _el

    if value is None:
        return None
    if isinstance(value, _el.True_):
        return True
    if isinstance(value, _el.False_):
        return False
    if isinstance(value, _el.Null):
        return None
    if hasattr(value, "value") and not isinstance(value, (list, tuple, dict, set)):
        # BindParameter / _LiteralClause / _OffsetLimitParam
        return value.value
    return value


def _binary_to_q(expr: Any) -> Any:
    """Translate a SQLAlchemy ``BinaryExpression`` → Django ``Q``."""
    from django.db.models import Q

    op = getattr(expr, "operator", None)
    op_name = getattr(op, "__name__", None) or str(op)
    field = _column_field(expr.left)
    if not field:
        raise NotImplementedError(
            f"DjangoStore execute(): unsupported WHERE expression {type(expr).__name__}"
        )
    right = _literal(expr.right)
    if op_name == "eq":
        return Q(**{field: right})
    if op_name == "ne":
        return ~Q(**{field: right})
    if op_name == "is_":
        if right is None:
            return Q(**{f"{field}__isnull": True})
        return Q(**{field: bool(right)})
    if op_name == "is_not":
        if right is None:
            return ~Q(**{f"{field}__isnull": True})
        return ~Q(**{field: bool(right)})
    if op_name in ("ilike_op", "like_op"):
        term = right if isinstance(right, str) else str(right or "")
        return Q(**{f"{field}__icontains": term.replace("%", "")})
    if op_name == "in_op":
        values = right if isinstance(right, (list, tuple, set)) else [right]
        return Q(**{f"{field}__in": list(values)})
    if op_name == "not_in_op":
        return ~Q(**{f"{field}__in": list(right)})
    if op_name in ("lt", "le", "gt", "ge"):
        return Q(**{f"{field}__{op_name}": right})
    raise NotImplementedError(f"DjangoStore execute(): unsupported operator {op_name!r}")


def _criteria_to_q(criterion: Any) -> Any:
    """Recursively translate a WHERE criterion → Django ``Q`` (or None)."""
    from sqlalchemy.sql import elements as _el

    if isinstance(criterion, _el.BooleanClauseList):
        children = [_criteria_to_q(c) for c in criterion.clauses]
        children = [c for c in children if c is not None]
        if not children:
            return None
        is_or = getattr(getattr(criterion, "operator", None), "__name__", "") == "or_"
        q = children[0]
        for child in children[1:]:
            q = (q | child) if is_or else (q & child)
        return q
    if isinstance(criterion, _el.BinaryExpression):
        return _binary_to_q(criterion)
    return None


def _criteria_table(criterion: Any) -> str | None:
    """Engine table name referenced by a criterion (for join classification)."""
    from sqlalchemy.sql import elements as _el

    if isinstance(criterion, _el.BooleanClauseList):
        for child in criterion.clauses:
            tbl = _criteria_table(child)
            if tbl:
                return tbl
        return None
    if isinstance(criterion, _el.BinaryExpression):
        return getattr(getattr(criterion.left, "table", None), "name", None)
    return None


def _order_spec(expr: Any) -> tuple | None:
    """Normalize one ``ORDER BY`` expression → a spec tuple.

    Shapes: ``("field", name, desc, nulls_last)``,
    ``("bool", field, value)`` (boolean expression, e.g. status == X),
    ``("random",)`` (``func.random()``).
    """
    from sqlalchemy.sql import elements as _el

    if isinstance(expr, _el.BinaryExpression):
        return ("bool", _column_field(expr.left), _literal(expr.right))
    if getattr(expr, "name", None) == "random":
        return ("random",)
    if isinstance(expr, _el.UnaryExpression):
        desc, nulls_last = False, False
        node = expr
        while isinstance(node, _el.UnaryExpression):
            mod_name = getattr(getattr(node, "modifier", None), "__name__", "")
            if mod_name == "desc_op":
                desc = True
            elif mod_name == "asc_op":
                desc = False
            elif mod_name == "nulls_last_op":
                nulls_last = True
            elif mod_name == "nulls_first_op":
                nulls_last = False
            node = node.element
        field = _column_field(node)
        return ("field", field, desc, nulls_last) if field else None
    field = _column_field(expr)
    return ("field", field, False, False) if field else None


def _stmt_limit(statement: Any) -> int | None:
    clause = getattr(statement, "_limit_clause", None)
    if clause is None:
        return None
    if isinstance(clause, int):
        return clause
    value = getattr(clause, "effective_value", None)
    if value is None:
        value = getattr(clause, "value", None)
    return value


def _stmt_offset(statement: Any) -> int | None:
    clause = getattr(statement, "_offset_clause", None)
    if clause is None:
        return None
    if isinstance(clause, int):
        return clause
    value = getattr(clause, "effective_value", None)
    if value is None:
        value = getattr(clause, "value", None)
    return value


def _select_spec(statement: Any) -> dict[str, Any]:
    """Normalize a SQLAlchemy ``Select`` into a Django-translatable spec."""
    descriptions = list(statement.column_descriptions)
    if not descriptions or not descriptions[0].get("entity"):
        raise NotImplementedError(
            "DjangoStore execute(): select without ORM entities is unsupported"
        )
    entities = [d["entity"] for d in descriptions if d.get("entity")]
    from_entity = entities[0]
    from_model = resolve_model(from_entity)
    single_entity = (
        len(descriptions) == 1
        and descriptions[0]["name"] == from_entity.__name__
    )
    single_col = len(descriptions) == 1 and not single_entity

    table_map: dict[str, Any] = {
        ent.__tablename__: resolve_model(ent) for ent in entities
    }

    joins: list[dict[str, Any]] = []
    from_table = from_entity.__tablename__
    for target, onclause, _isouter, _opts in (
        getattr(statement, "_setup_joins", ()) or ()
    ):
        on_left = getattr(onclause, "left", None)
        on_right = getattr(onclause, "right", None)
        target_name = getattr(target, "name", None)
        if target_name and target_name not in table_map:
            # Join targets are not in ``column_descriptions`` when they are
            # filtered but not projected (e.g. prompt-eval's Conversation).
            table_map[target_name] = _stmt_model(target)
        on_left_table = getattr(getattr(on_left, "table", None), "name", None)
        on_right_table = getattr(getattr(on_right, "table", None), "name", None)
        # The ON-clause orientation varies (A9: join-table on the LEFT;
        # P2: from-table on the LEFT) — classify by column table.
        if on_left_table == from_table:
            from_on_field, join_on_field = _column_field(on_left), _column_field(on_right)
        else:
            from_on_field, join_on_field = _column_field(on_right), _column_field(on_left)
        joins.append(
            {
                "target_table": target_name,
                "on_left_table": on_left_table,
                "on_left_field": _column_field(on_left),
                "on_right_table": on_right_table,
                "on_right_field": _column_field(on_right),
                "from_on_field": from_on_field,
                "join_on_field": join_on_field,
            }
        )

    filters_by_table: dict[str, list[Any]] = {}
    for criterion in getattr(statement, "_where_criteria", ()) or ():
        q = _criteria_to_q(criterion)
        if q is None:
            continue
        tbl = _criteria_table(criterion) or from_entity.__tablename__
        filters_by_table.setdefault(tbl, []).append(q)

    order_by: list[tuple | None] = []
    for expr in getattr(statement, "_order_by_clauses", ()) or ():
        order_by.append(_order_spec(expr))

    return {
        "kind": "select",
        "descriptions": descriptions,
        "entities": entities,
        "from_entity": from_entity,
        "from_model": from_model,
        "from_table": from_entity.__tablename__,
        "table_map": table_map,
        "joins": joins,
        "filters_by_table": filters_by_table,
        "order_by": order_by,
        "limit": _stmt_limit(statement),
        "offset": _stmt_offset(statement),
        "single_entity": single_entity,
        "single_col": single_col,
        "cols": [d["name"] for d in descriptions],
    }


def _update_spec(statement: Any) -> dict[str, Any]:
    """Normalize a SQLAlchemy ``update()`` into a Django-translatable spec."""
    ed = getattr(statement, "entity_description", None) or {}
    entity = ed.get("entity")
    if entity is None:
        entity = getattr(statement, "table", None)
    model = _stmt_model(entity)

    filters: list[Any] = []
    for criterion in getattr(statement, "_where_criteria", ()) or ():
        q = _criteria_to_q(criterion)
        if q is not None:
            filters.append(q)

    values: dict[str, Any] = {}
    for key, value in (getattr(statement, "_values", None) or {}).items():
        field = key if isinstance(key, str) else _column_field(key)
        values[field] = _literal(value)

    return {"kind": "update", "model": model, "filters": filters, "values": values}


class _MultipleResultsFound(Exception):
    """Mirror of ``sqlalchemy.exc.MultipleResultsFound`` for the Result facade."""


class _ExecRow:
    """Row supporting positional unpacking + ``row["col"]`` mapping access."""

    __slots__ = ("_keys", "_values")

    def __init__(self, keys: list[str], values: list[Any]) -> None:
        self._keys = list(keys)
        self._values = list(values)

    def __iter__(self):
        return iter(self._values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._values[self._keys.index(key)]

    def __len__(self) -> int:
        return len(self._values)

    def get(self, key, default: Any = None) -> Any:
        try:
            return self[key]
        except (ValueError, IndexError):
            return default

    def _asdict(self) -> dict[str, Any]:
        return dict(zip(self._keys, self._values))

    def __repr__(self) -> str:
        return f"Row({self._asdict()!r})"


class _ExecResult:
    """SQLAlchemy ``Result``-like facade over a fetched row list."""

    def __init__(
        self,
        rows: list[Any],
        is_scalar: bool = False,
        rowcount: int | None = None,
    ) -> None:
        self._rows = list(rows)
        self._is_scalar = is_scalar
        self.rowcount = len(self._rows) if rowcount is None else rowcount

    def scalar(self) -> Any:
        return self._rows[0] if self._rows else None

    def scalar_one_or_none(self) -> Any:
        if len(self._rows) > 1:
            raise _MultipleResultsFound(
                "execute() returned more than one row for scalar_one_or_none()"
            )
        return self._rows[0] if self._rows else None

    def one_or_none(self) -> Any:
        if len(self._rows) > 1:
            raise _MultipleResultsFound(
                "execute() returned more than one row for one_or_none()"
            )
        return self._rows[0] if self._rows else None

    def first(self) -> Any:
        return self._rows[0] if self._rows else None

    def fetchone(self) -> Any:
        return self.first()

    def all(self) -> list[Any]:
        return list(self._rows)

    def scalars(self) -> "_ScalarResult":
        return _ScalarResult(self)

    def mappings(self) -> "_MappingResult":
        return _MappingResult(self)


class _ScalarResult:
    def __init__(self, result: _ExecResult) -> None:
        self._result = result

    def all(self) -> list[Any]:
        return list(self._result._rows)

    def first(self) -> Any:
        return self._result._rows[0] if self._result._rows else None

    def one_or_none(self) -> Any:
        if len(self._result._rows) > 1:
            raise _MultipleResultsFound(
                "execute() returned more than one row for scalars().one_or_none()"
            )
        return self._result._rows[0] if self._result._rows else None


class _MappingResult:
    def __init__(self, result: _ExecResult) -> None:
        self._result = result

    def all(self) -> list[Any]:
        out: list[Any] = []
        for row in self._result._rows:
            if isinstance(row, _ExecRow):
                out.append(row._asdict())
            elif isinstance(row, dict):
                out.append(row)
            elif self._result._is_scalar:
                out.append({"value": row})
            else:
                out.append(row)
        return out

    def first(self) -> Any:
        rows = self.all()
        return rows[0] if rows else None


class _DialectStub:
    def __init__(self, name: str) -> None:
        self.name = name


class _BindStub:
    """Minimal ``Engine``-like stub exposing ``.dialect.name``."""

    def __init__(self, vendor: str) -> None:
        self.dialect = _DialectStub(vendor)


def _q_check(q: Any, obj: Any) -> bool:
    """Evaluate a Django ``Q`` against a plain object (in-memory backend)."""
    from django.db.models import Q

    connector = getattr(q, "connector", "AND")
    negated = getattr(q, "negated", False)
    results: list[bool] = []
    for child in q.children:
        if isinstance(child, Q):
            results.append(_q_check(child, obj))
        else:
            field, value = child
            results.append(_field_matches(obj, field, value))
    out = all(results) if connector == "AND" else any(results)
    return not out if negated else out


def _field_matches(obj: Any, field: str, value: Any) -> bool:
    if "__" in field:
        field_name, lookup = field.rsplit("__", 1)
    else:
        field_name, lookup = field, "exact"
    actual = getattr(obj, field_name, None)
    if lookup == "exact":
        return actual == value
    if lookup in ("icontains", "contains"):
        haystack = str(actual or "")
        needle = str(value or "")
        return needle.lower() in haystack.lower() if lookup == "icontains" else needle in haystack
    if lookup == "in":
        return actual in (value or [])
    if lookup == "isnull":
        return (actual is None) == bool(value)
    if lookup == "lt":
        return actual is not None and actual < value
    if lookup == "lte":
        return actual is not None and actual <= value
    if lookup == "gt":
        return actual is not None and actual > value
    if lookup == "gte":
        return actual is not None and actual >= value
    raise NotImplementedError(f"Unsupported lookup {lookup!r} for in-memory execute()")


def _order_rows(rows: list[Any], order_specs: list[tuple | None]) -> tuple[list[Any], bool]:
    """Sort in-memory rows by order specs; returns (rows, needs_random)."""
    import random

    needs_random = any(s and s[0] == "random" for s in order_specs)
    if needs_random:
        random.shuffle(rows)
        return rows, True
    for spec in reversed([s for s in order_specs if s]):
        if spec[0] == "bool":
            field, value = spec[1], spec[2]
            rows.sort(
                key=lambda o, f=field, v=value: 1 if getattr(o, f, None) == v else 0,
                reverse=True,
            )
        elif spec[0] == "field":
            field, desc, nulls_last = spec[1], spec[2], spec[3]
            non_null = [r for r in rows if getattr(r, field, None) is not None]
            nulls = [r for r in rows if getattr(r, field, None) is None]
            non_null.sort(key=lambda o, f=field: getattr(o, f), reverse=desc)
            rows[:] = (non_null + nulls) if nulls_last else (nulls + non_null)
    return rows, False


def _project_result(rows: list[Any], spec: dict[str, Any]) -> _ExecResult:
    """Build the result facade for fetched rows per the projection shape."""
    if spec["single_entity"]:
        return _ExecResult(rows, rowcount=len(rows))
    if spec["single_col"]:
        field = spec["cols"][0]
        return _ExecResult(
            [getattr(r, field) for r in rows],
            is_scalar=True,
            rowcount=len(rows),
        )
    if len(spec["descriptions"]) == 2:
        keys = [d["name"] for d in spec["descriptions"]]
        return _ExecResult(
            [_ExecRow(keys, list(row)) for row in rows],
            rowcount=len(rows),
        )
    keys = spec["cols"]
    return _ExecResult(
        [_ExecRow(keys, [getattr(r, k) for k in keys]) for r in rows],
        rowcount=len(rows),
    )


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
        self._pending = [o for o in self._pending if o[0] is not obj]

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
            qs = self._store._apply_tenancy_filter(qs)
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
            from_qs = self._store._apply_tenancy_filter(model.objects.all())
            if from_filters:
                from_qs = from_qs.filter(*from_filters)
            from_ids = list(from_qs.values_list(join["from_on_field"], flat=True))
            join_qs = self._store._apply_tenancy_filter(join_model.objects.all())
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

        qs = self._store._apply_tenancy_filter(model.objects.all())
        if from_filters:
            qs = qs.filter(*from_filters)

        # Single-entity projection with a join (e.g. prompt-eval sampling):
        # narrow the join entity first, then filter the main query via the ON
        # column.
        if spec["joins"]:
            join = spec["joins"][0]
            join_model = spec["table_map"].get(join["target_table"])
            join_qs = self._store._apply_tenancy_filter(join_model.objects.all())
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
        qs = self._store._apply_tenancy_filter(spec["model"].objects.all())
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
