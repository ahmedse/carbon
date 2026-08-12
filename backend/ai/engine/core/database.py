"""
Async database for Pulse's own data store — NOT the host database.

INSTANCE ISOLATION: Every instance gets its own SQLite database at
  instances/{name}/data/pulse.db

The shared engine (no instance name) uses the legacy data/pulse.db path
and is only used for the global instance registry table.  All instance-scoped
data (conversations, memories, knowledge graph, vectors) lives in per-instance
databases.

Usage:
    # Shared engine (global instances table only)
    engine = get_engine()          # → data/pulse.db
    session = get_db()

    # Per-instance engine
    engine = get_engine("carbon")  # → instances/carbon/data/pulse.db
    session = get_instance_db("carbon")
"""
import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ai.engine.core.config import get_settings, resolve_instance_paths

_log = logging.getLogger("pulse.database")

# Per-instance engine registry: instance_name → engine
_engines: dict[str, object] = {}
# Per-instance session factory registry
_factories: dict[str, object] = {}
# Lock: if True, all engines are already created (init_db was called)
_initialized = False


def _build_engine_url(db_path: str, *, use_postgres: bool = False) -> str:
    """Build an async engine URL for a given database path."""
    settings = get_settings()
    if use_postgres and settings.PULSE_DB_URL:
        # PostgreSQL: use the shared PG instance but with per-instance schema
        # The schema is derived from the instance name later via set_search_path
        return settings.PULSE_DB_URL
    else:
        # SQLite: per-instance file
        return f"sqlite+aiosqlite:///{db_path}"


def _create_engine(instance_name: str | None) -> tuple:
    """Create an engine + session factory for the given instance (or shared).

    Returns (engine, session_factory).
    """
    settings = get_settings()
    use_postgres = bool(settings.PULSE_DB_URL)

    if instance_name is None:
        # Shared engine: uses legacy data/pulse.db (or PULSE_DB_URL for PG)
        url = _build_engine_url(settings.PULSE_DB_PATH, use_postgres=use_postgres)
        label = "shared"
    else:
        paths = resolve_instance_paths(instance_name)
        # Ensure the directory exists
        Path(paths["data_dir"]).mkdir(parents=True, exist_ok=True)
        url = _build_engine_url(paths["db_path"], use_postgres=use_postgres)
        label = instance_name

    if use_postgres:
        _log.info("Pulse DB [%s]: postgresql (pool_size=20)", label)
        eng = create_async_engine(
            url,
            echo=False,
            pool_size=20,
            max_overflow=20,
            pool_timeout=60,
            pool_recycle=3600,
        )
    else:
        _log.info("Pulse DB [%s]: sqlite → %s", label, url)
        eng = create_async_engine(url, echo=False)

    factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    return eng, factory


def get_engine(instance_name: str | None = None):
    """Get (or create) the async engine for an instance.

    Args:
        instance_name: If None, returns the shared (legacy) engine.
                       If a string, returns the per-instance engine.

    Returns:
        AsyncEngine
    """
    key = instance_name or "_shared"
    if key not in _engines:
        eng, fac = _create_engine(instance_name)
        _engines[key] = eng
        _factories[key] = fac
    return _engines[key]


async def _ensure_pg_schema(eng) -> None:
    """Create pulse schema + vector extension on PostgreSQL. No-op on SQLite."""
    from sqlalchemy import text

    if not eng.url.drivername.startswith("postgresql"):
        return
    async with eng.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS pulse"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def get_session_factory(instance_name: str | None = None):
    """Get the session factory for an instance."""
    key = instance_name or "_shared"
    if key not in _factories:
        get_engine(instance_name)  # side-effect: populates _factories
    return _factories[key]


def get_effective_storage_mode(instance_name: str) -> str:
    """Return 'standalone' if instance has standalone=True, else 'shared'."""
    import os

    import yaml

    config_path = os.path.join("instances", instance_name, "instance.yaml")
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
        if config.get("standalone"):
            return "standalone"
    return "shared"


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a DB session from the SHARED engine.

    Use this for the global instance registry only.  For instance-scoped
    data, use get_instance_db(instance_name).
    """
    session_factory = get_session_factory(None)
    async with session_factory() as session:
        yield session


async def get_instance_db(instance_name: str) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a DB session from the PER-INSTANCE engine.

    Every instance's data is physically isolated in its own SQLite file
    (or PG schema).  Use this for conversations, memories, knowledge graph,
    and all other instance-scoped data.
    """
    session_factory = get_session_factory(instance_name)
    async with session_factory() as session:
        yield session


async def init_db(instance_names: list[str] | None = None) -> None:
    """Create all tables in the shared DB + all per-instance DBs.

    Args:
        instance_names: List of instance names to initialize. If None,
                        initializes only the shared DB (backwards compat).
    """
    global _initialized
    from ai.engine.core.models import Base
    import ai.engine.knowledge_graph.models  # noqa: F401 — registers KnowledgeNode/KnowledgeEdge with Base

    names_to_init = instance_names or []

    # 1. Shared engine (global instances table)
    try:
        await _ensure_pg_schema(get_engine(None))
    except Exception as _pg_err:
        _log.warning("_ensure_pg_schema [shared] skipped (non-fatal): %s", _pg_err)
    async with get_engine(None).begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _log.info("init_db: shared tables created")

    # 2. Per-instance engines
    for name in names_to_init:
        eng = get_engine(name)
        try:
            await _ensure_pg_schema(eng)
        except Exception as _pg_err:
            _log.warning("_ensure_pg_schema [%s] skipped (non-fatal): %s", name, _pg_err)
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _log.info("init_db: [%s] tables created", name)

    _initialized = True

    # Apply incremental schema migrations for existing installs
    await _apply_schema_migrations()


def list_initialized_instances() -> list[str]:
    """Return the list of instance names that have engines created."""
    return [k for k in _engines if k != "_shared"]


# ── Backwards compatibility ──────────────────────────────────────────────
# `get_db()` and `get_engine()` without arguments use the shared engine,
# so all existing code continues to work unchanged.
# New instance-scoped code should use get_engine(name) / get_instance_db(name).


async def _apply_schema_migrations():
    """Run all pending migrations idempotently (safe to call on every startup)."""
    import logging
    _log = logging.getLogger("pulse.database")

    try:
        from alembic.versions.add_host_user_id import upgrade as _m_host_user_id
        await _m_host_user_id(get_engine())
    except Exception as exc:
        _log.warning(
            "Schema migration add_host_user_id failed (non-fatal on fresh DB): %s", exc
        )

    try:
        from alembic.versions.add_audit_log import upgrade as _m_audit_log
        await _m_audit_log(get_engine())
    except Exception as exc:
        _log.warning(
            "Schema migration add_audit_log failed (non-fatal on fresh DB): %s", exc
        )

    try:
        from alembic.versions.add_ops_runs import upgrade as _m_ops_runs
        await _m_ops_runs(get_engine())
    except Exception as exc:
        _log.warning(
            "Schema migration add_ops_runs failed (non-fatal on fresh DB): %s", exc
        )

    try:
        from alembic.versions.add_csv_uploads import upgrade as _m_csv_uploads
        await _m_csv_uploads(get_engine())
    except Exception as exc:
        _log.warning(
            "Schema migration add_csv_uploads failed (non-fatal on fresh DB): %s", exc
        )

    try:
        from alembic.versions.add_pr13_pr14_memory_columns import upgrade as _m_pr13_pr14
        await _m_pr13_pr14(get_engine())
    except Exception as exc:
        _log.warning(
            "Schema migration add_pr13_pr14_memory_columns failed (non-fatal on fresh DB): %s", exc
        )

    try:
        from alembic.versions.add_prompt_versions_and_evals import upgrade as _m_prompt_versions
        await _m_prompt_versions(get_engine())
    except Exception as exc:
        _log.warning(
            "Schema migration add_prompt_versions_and_evals failed (non-fatal on fresh DB): %s", exc
        )

    try:
        from alembic.versions.add_runs_and_run_steps import upgrade as _m_runs_and_run_steps
        await _m_runs_and_run_steps(get_engine())
    except Exception as exc:
        _log.warning(
            "Schema migration add_runs_and_run_steps failed (non-fatal on fresh DB): %s", exc
        )

    try:
        from alembic.versions.add_be02_3_columns import upgrade as _m_be02_3
        await _m_be02_3(get_engine())
    except Exception as exc:
        _log.warning(
            "Schema migration add_be02_3_columns failed (non-fatal on fresh DB): %s", exc
        )

    try:
        from alembic.versions.add_be02_4_columns import upgrade as _m_be02_4
        await _m_be02_4(get_engine())
    except Exception as exc:
        _log.warning(
            "Schema migration add_be02_4_columns failed (non-fatal on fresh DB): %s", exc
        )

    try:
        from alembic.versions.add_agent_registry_tables import upgrade as _m_agent_registry
        await _m_agent_registry(get_engine())
    except Exception as exc:
        _log.warning(
            "Schema migration add_agent_registry_tables failed (non-fatal on fresh DB): %s", exc
        )

    try:
        from alembic.versions.add_p34_budget_columns import upgrade as _m_p34_budget
        await _m_p34_budget(get_engine())
    except Exception as exc:
        _log.warning(
            "Schema migration add_p34_budget_columns failed (non-fatal on fresh DB): %s", exc
        )

    try:
        from alembic.versions.add_trajectory_table import upgrade as _m_trajectory
        await _m_trajectory(get_engine())
    except Exception as exc:
        _log.warning(
            "Schema migration add_trajectory_table failed (non-fatal on fresh DB): %s", exc
        )

    try:
        from alembic.versions.add_skill_admission_log import upgrade as _m_admission_log
        await _m_admission_log(get_engine())
    except Exception as exc:
        _log.warning(
            "Schema migration add_skill_admission_log failed (non-fatal on fresh DB): %s", exc
        )

    try:
        from alembic.versions.add_kg_edge_validity_columns import upgrade as _m_kg_edge_validity
        await _m_kg_edge_validity(get_engine())
    except Exception as exc:
        _log.warning(
            "Schema migration add_kg_edge_validity_columns failed (non-fatal on fresh DB): %s", exc
        )
